"""Office-document + code-run payload generators for the chat composer.

This is the `image.py` analog for `message_type in {"pptx", "docx", "code"}`.
Each helper:

  - takes the user's prompt + options
  - for pptx/docx, asks the LLM for a structured JSON outline and then
    converts it into a real .pptx / .docx via python-pptx / python-docx
  - for code, asks the LLM for raw code, runs it through `code_runner`,
    and returns the captured stdout/stderr
  - returns `(payload_bytes_or_result, filename, meta)` where `meta`
    is a JSON-serializable dict the chat endpoint drops into
    `Message.meta_data`

Failures bubble up as HTTP 502 with a structured detail — the chat
endpoint's dispatcher (`backend/app/api/endpoints/chats.py`) just lets
the exception propagate so the frontend can surface it inline.

Why we don't ship Markdown instead of real files: the user explicitly
asked for downloadable .pptx / .docx. python-pptx / python-docx are the
canonical libs, total install cost is ~50 MB, and they keep us off the
Pandoc dependency chain.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException

from app.core.code_runner import CodeRunResult, run as run_code
from app.core.llm_service import LLMMessage, LLMMessageType, get_llm_service

logger = logging.getLogger("novamind.files")

# Standalone router. Most chat traffic reaches these helpers through the
# chat dispatcher (`/api/v1/chats/{id}/messages` with message_type in
# {file, code}). We expose a small parallel `/files/*` surface so the
# developer OpenAI-compat layer at `/v1/*` and any future direct-from-
# UI invocations can hit the same generators without a chat wrapper.
router = APIRouter()


# ----- Limits / defaults ----------------------------------------------------

# Hard upper bounds. A prompt that asks for "100 slides" or a 200-page
# report would OOM the worker; cap to keep requests cheap.
MAX_PPTX_SLIDES = 25
MAX_DOCX_PARAGRAPHS = 80

# Default code-exec wall-clock cap. The chat composer sets a longer
# banner timeout (~12 s) so the user sees a "still running…" message
# while we work, but the actual subprocess gets killed at 8 s to bound
# server load.
DEFAULT_CODE_TIMEOUT_S = 8.0


# ----- LLM helpers ----------------------------------------------------------

async def _llm_outline(prompt: str, *, model_name: str = "NovaMind-Chat") -> str:
    """Ask the configured LLM for raw text. Returns whatever the LLM
    emitted — callers are responsible for stripping markdown fences /
    parsing JSON.

    We force a system-style instruction at the call site instead of via
    a config-level system prompt because the project doesn't define one
    (see `app/core/llm_service.py`). The instruction lives in the user
    message because that is what every backend in the stealth-router
    fleet (Ollama chat / NovaMindLocal) supports.
    """
    try:
        llm = get_llm_service(model_name=model_name)
        # The chat surface expects `List[LLMMessage]`, NOT raw dicts.
        # Earlier we passed `{"role": ..., "content": ...}` dicts which
        # made the Ollama backend's `_to_openai_messages` crash on
        # `m.is_ai` and fall through to the canned "having trouble
        # reaching the model" reply — every slide in the deck ended up
        # padded with placeholder titles because the LLM was never
        # actually called. Wrap the prompt in a real LLMMessage so the
        # full async path runs and we get real model output.
        messages = [
            LLMMessage(
                content=prompt,
                message_type=LLMMessageType.TEXT,
                is_ai=False,
            ),
        ]
        resp = await llm.generate_response(messages=messages, temperature=0.4, max_tokens=2000)
        return (resp.content or "").strip()
    except Exception as exc:  # noqa: BLE001 — we want to swallow any LLM error
        logger.warning("LLM call for file outline failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "llm_unavailable",
                "message": "The model didn't produce a usable outline. Please try again.",
            },
        ) from exc


def _llm_outline_sync(prompt: str, *, model_name: str = "NovaMind-Chat") -> str:
    """Synchronous LLM call for places that aren't async (e.g. the
    standalone `/files/generate` endpoint when invoked from a sync
    context). Generates directly through Ollama/HTTPX — bypasses the
    semaphore-protected async service so this doesn't deadlock if the
    caller is already inside an event loop.

    Most callers should use `await _llm_outline(...)` instead. This is
    only useful for the REST fallback path.
    """
    import httpx
    from app.core.alias_config import backend_for
    from app.core.config import settings

    # `backend_for()` returns the real backend model id (e.g.
    # "llama3.2:3b") directly as a string — see `app/core/alias_config.py`.
    # We just need the resolved id; nothing else.
    backend = backend_for(model_name)
    if not backend:
        raise HTTPException(
            status_code=502,
            detail={"code": "unknown_model", "message": f"Unknown model: {model_name}"},
        )
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": backend,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "max_tokens": 2000,
                },
            )
            r.raise_for_status()
            data = r.json()
            return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as exc:
        logger.warning("sync LLM call failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"code": "llm_unavailable", "message": "LLM call failed."},
        ) from exc


def _strip_code_fence(raw: str) -> str:
    """LLMs love wrapping code in ```python ... ``` even when told not to.
    Strip the fence if present."""
    text = raw.strip()
    m = re.match(r"^```(?:python|py)?\s*\n(.*?)\n```\s*$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Also tolerate a single-line fence with no closing.
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _safe_json_loads(raw: str) -> Optional[Any]:
    """Try hard to parse the LLM's JSON. Returns the parsed value on
    success — a dict for the conventional `{...}` payload, a list for
    the bare-array payload some models emit (`[{...}, {...}]`), or
    None on failure so the caller can fall back to a degraded path
    instead of 502ing."""
    text = raw.strip()
    # Strip ```json ... ``` fences if present.
    m = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", text, re.DOTALL)
    if m:
        text = m.group(1)
    # Prefer the first balanced {...} block, then the first balanced
    # [...] block, then a full-text parse. Models love to wrap the
    # answer in preamble like "Here's the JSON:" so we can't trust a
    # naive text[start:end] window.  We also handle the bare-array
    # case (`[...]`) because small instruct models frequently skip
    # the requested wrapper and just emit the list.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ----- PPTX -----------------------------------------------------------------

# Theme → (master_index, color_hint). python-pptx ships one master per
# default theme; we layer a primary color onto title text for the
# "academic" / "pitch-deck" variants to differentiate them visually.
PPT_THEMES = {
    "modern": {"master": 0, "accent": "1F4E79"},
    "minimal": {"master": 1, "accent": "404040"},
    "academic": {"master": 2, "accent": "8B0000"},
    "pitch-deck": {"master": 0, "accent": "C00000"},
}


# Section labels used when we pad missing slides. Generic enough to fit
# any topic; the first slide is always the title page.
_PPTX_PAD_TITLES = [
    "Overview",
    "Key Points",
    "Why It Matters",
    "Next Steps",
    "Risks & Open Questions",
    "Summary",
    "Deep Dive",
    "Data & Evidence",
    "Alternatives",
    "Recommendations",
    "Appendix",
    "Q&A",
]


def _clean_slide_title(title: str) -> str:
    """Strip common LLM artifacts from slide titles:
    - leading "Slide 1:" / "Slide 1 -" prefixes
    - leading numbering "1." / "1)"
    - surrounding quotes
    - extra whitespace.
    """
    t = (title or "").strip().strip('"').strip("'").strip()
    # Strip "Slide N:" / "Slide N -" / "Slide N —" prefixes.
    import re as _re
    t = _re.sub(r"^slide\s+\d+\s*[:\-—–]\s*", "", t, flags=_re.IGNORECASE)
    # Strip leading "1." / "1)" numbering.
    t = _re.sub(r"^\d+\s*[\.\)]\s*", "", t)
    return t.strip() or "Slide"


def _pad_bullets(prompt: str, idx: int, total: int) -> list:
    """Generate fallback bullets when a slide is missing or empty.
    The first padded slide is the title page (single short bullet).
    Otherwise we derive 3-4 generic-but-relevant bullets from the prompt."""
    if idx == 0:
        return [prompt[:160].strip()]
    base = prompt[:120].rstrip(" .,;:-")
    return [
        f"Context: {base}",
        f"Key consideration for slide {idx + 1} of {total}",
        "Add supporting evidence or examples here",
        "Discuss trade-offs and follow-up questions",
    ]


def _extract_slides(parsed: Any) -> list:
    """Pull the slide list out of whatever shape the LLM happened to
    emit. Supports the conventional `{"slides": [...]}` wrapper AND a
    bare `[...]` array — the latter is what small instruct models
    actually produce when they skip the wrapper instruction. Returns a
    list of dicts; non-dict entries are dropped.
    """
    if isinstance(parsed, list):
        candidates = parsed
    elif isinstance(parsed, dict):
        candidates = parsed.get("slides") or []
    else:
        candidates = []
    return [s for s in candidates if isinstance(s, dict)]


def _fill_slides(slides: list, slide_count: int, prompt: str) -> list:
    """Pad / normalize the LLM's `slides` array to exactly `slide_count`
    entries. Each returned entry is a dict with cleaned `title`,
    non-empty `bullets`, and `notes`. We never return fewer entries than
    the user asked for — that's the contract."""
    cleaned = []
    for idx in range(slide_count):
        if idx < len(slides) and isinstance(slides[idx], dict):
            s = slides[idx]
            title = _clean_slide_title(str(s.get("title") or ""))
            bullets_raw = s.get("bullets") or []
            if not isinstance(bullets_raw, list):
                bullets_raw = [str(bullets_raw)]
            bullets = [str(b).strip() for b in bullets_raw if str(b).strip()]
            if not bullets:
                bullets = _pad_bullets(prompt, idx, slide_count)
            notes = str(s.get("notes") or "").strip()[:500]
            cleaned.append({"title": title, "bullets": bullets, "notes": notes})
        else:
            # Padded slot. Use a deterministic but topic-aware title.
            pad_title = _PPTX_PAD_TITLES[
                (idx - 1) % len(_PPTX_PAD_TITLES) if idx > 0 else 0
            ]
            if idx > 0:
                pad_title = f"{pad_title} ({idx + 1}/{slide_count})"
            cleaned.append({
                "title": pad_title,
                "bullets": _pad_bullets(prompt, idx, slide_count),
                "notes": "",
            })
    return cleaned


async def generate_pptx_payload(
    prompt: str,
    *,
    theme: str = "modern",
    slide_count: int = 6,
    model_name: str = "NovaMind-Chat",
) -> Tuple[bytes, str, Dict[str, Any]]:
    """Produce a real .pptx file from a prompt.

    Pipeline:
      1. Ask the LLM for JSON: {"slides": [{"title", "bullets", "notes"}, ...]}
      2. Build a python-pptx Presentation, pick a theme, fill each slide
      3. Return the binary + filename + meta dict

    Falls back to a single "title + body" slide if the LLM output is
    malformed, so a transient LLM hiccup doesn't blow up the chat.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    slide_count = max(1, min(int(slide_count or 6), MAX_PPTX_SLIDES))
    theme_key = theme if theme in PPT_THEMES else "modern"
    accent_hex = PPT_THEMES[theme_key]["accent"]

    # Step 1: get the outline. The local model (llama3.2:3b) doesn't reliably
    # emit a `{"slides": [...]}` array of the right length, so we ask for
    # numbered slides explicitly and explicitly constrain the shape. The
    # fallback in `_fill_slides` below pads the missing slots if the model
    # still returns too few.
    instruction = (
        f"You are drafting a {slide_count}-slide presentation on this topic:\n\n"
        f"TOPIC: {prompt}\n\n"
        f"Output ONLY a JSON object with exactly {slide_count} entries in a "
        '"slides" array. Each entry must have:\n'
        '  - "title": 4-8 word slide title (NOT the topic again, NOT "Slide N")\n'
        '  - "bullets": array of 3-5 short bullet points about THAT slide\n'
        '  - "notes": one short sentence for the speaker (optional, can be "")\n\n'
        f"Write exactly {slide_count} entries — one per slide. No prose, no "
        "markdown fences, no commentary. Output the JSON object only."
    )

    raw = await _llm_outline(instruction, model_name=model_name)
    parsed = _safe_json_loads(raw) or {}
    # `_safe_json_loads` returns a dict for `{...}` payloads and a list
    # for `[...]` payloads (the LLM sometimes skips the wrapper).
    # Normalize both to a list of slide dicts.
    slides = _extract_slides(parsed)

    # If we got fewer than half of what was requested, retry once with a
    # stricter prompt. The retry often pushes small models past the
    # "I'm done" stopping bias.
    if len(slides) < max(1, slide_count // 2):
        retry_instruction = (
            f"Output ONLY a JSON object with a 'slides' array of EXACTLY "
            f"{slide_count} entries. Topic: {prompt}. "
            'Each entry: {"title": str, "bullets": [str, str, str], "notes": str}. '
            f"You must include {slide_count} entries — no fewer. No prose."
        )
        try:
            retry_raw = await _llm_outline(retry_instruction, model_name=model_name)
            retry_parsed = _safe_json_loads(retry_raw) or {}
            retry_slides = _extract_slides(retry_parsed)
            if len(retry_slides) > len(slides):
                slides = retry_slides
        except HTTPException:
            # Retry failure is non-fatal; we'll fall through to padding.
            pass

    # Always pad to the requested count. Missing slides get a deterministic
    # "Section N of M" title + bullets derived from the prompt so the deck
    # is still useful instead of silently truncated.
    slides = _fill_slides(slides, slide_count, prompt)

    # Step 2: build the .pptx.
    prs = Presentation()
    title_layout = prs.slide_layouts[0]   # Title Slide
    content_layout = prs.slide_layouts[1]  # Title and Content
    section_layout = prs.slide_layouts[2]  # Section Header

    try:
        accent_rgb = RGBColor.from_string(accent_hex)
    except (ValueError, AttributeError):
        accent_rgb = RGBColor(0x1F, 0x4E, 0x79)

    for idx, slide_data in enumerate(slides[:slide_count]):
        layout = title_layout if idx == 0 else content_layout
        slide = prs.slides.add_slide(layout)
        title_text = (slide_data.get("title") or f"Slide {idx + 1}").strip()
        try:
            slide.shapes.title.text = title_text
            for r in slide.shapes.title.text_frame.paragraphs[0].runs:
                r.font.color.rgb = accent_rgb
        except (AttributeError, KeyError):
            # Layout might not have a title placeholder; fall back.
            pass

        # Body / bullets: slide 1 is title-only by layout choice, skip it.
        bullets = slide_data.get("bullets") or []
        if idx == 0:
            # Add a subtitle-style body with a short summary.
            body_ph = next(
                (ph for ph in slide.placeholders if ph.placeholder_format.idx == 1),
                None,
            )
            if body_ph is not None:
                body_ph.text = bullets[0] if bullets else prompt[:200]
            continue

        body_ph = next(
            (ph for ph in slide.placeholders if ph.placeholder_format.idx == 1),
            None,
        )
        if body_ph is None:
            # No content placeholder on this layout — append a textbox.
            from pptx.util import Inches as _In
            tx = slide.shapes.add_textbox(_In(1), _In(2), _In(8), _In(4))
            tf = tx.text_frame
            tf.word_wrap = True
            for b in bullets[:8]:
                p = tf.add_paragraph()
                p.text = str(b)
                p.level = 0
        else:
            tf = body_ph.text_frame
            tf.word_wrap = True
            tf.text = str(bullets[0]) if bullets else ""
            for b in bullets[1:8]:
                p = tf.add_paragraph()
                p.text = str(b)
                p.level = 0

        # Speaker notes — kept short so they fit the placeholder.
        notes_tf = slide.notes_slide.notes_text_frame
        notes_tf.text = (slide_data.get("notes") or "").strip()[:500]

    # Step 3: serialize to bytes.
    buf = io.BytesIO()
    prs.save(buf)
    payload = buf.getvalue()
    if not payload:
        raise HTTPException(
            status_code=502,
            detail={"code": "pptx_build_failed", "message": "Could not assemble the .pptx file."},
        )

    ts = int(time.time())
    filename = f"novamind-slides-{ts}.pptx"
    meta = {
        "kind": "pptx",
        "theme": theme_key,
        "slide_count": len(prs.slides),
        "requested_slide_count": slide_count,
        "model_used": model_name,
        "size_bytes": len(payload),
        "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "filename": filename,
        "prompt": prompt[:500],
    }
    return payload, filename, meta


# ----- DOCX -----------------------------------------------------------------

DOCX_STYLES = {"memo", "report", "letter", "outline"}


def generate_docx_payload(
    prompt: str,
    *,
    style: str = "report",
    model_name: str = "NovaMind-Chat",
) -> Tuple[bytes, str, Dict[str, Any]]:
    """Produce a real .docx file. Mirrors `generate_pptx_payload` but
    emits paragraphs instead of slides.

    For "memo" / "letter" we keep the structure rigid (header + body).
    For "report" / "outline" the LLM has more latitude.

    Sync wrapper around `await _llm_outline(...)` via asyncio.run; this
    is safe because the chat dispatcher awaits the helper before
    calling us, so the active event loop is the FastAPI one. We use the
    *sync* LLM path here (httpx.Client) instead of the async service to
    avoid nesting asyncio.run inside an already-running loop. The
    standalone `/files/generate` endpoint also uses this version."""
    from docx import Document
    from docx.shared import Pt

    style = style if style in DOCX_STYLES else "report"

    instruction = (
        f"You are drafting a {style}-style document on this topic:\n\n"
        f"TOPIC: {prompt}\n\n"
        "Output ONLY a JSON object with this exact shape, no prose:\n"
        '{"title":"...",'
        '"sections":[{"heading":"...","paragraphs":["...","..."]},...]} '
        "Include 4-5 sections and 2-3 short paragraphs per section. "
        "No markdown fences, no commentary, JSON only."
    )

    # Same async-loop avoidance as `_llm_outline_sync`: we are inside the
    # FastAPI event loop, so we use the sync httpx shim rather than
    # `asyncio.run()`.
    raw = _llm_outline_sync(instruction, model_name=model_name)
    parsed = _safe_json_loads(raw) or {}
    # `_safe_json_loads` returns a dict for the conventional
    # `{title, sections}` payload and a list for the bare-array
    # variant the small model sometimes emits.
    if isinstance(parsed, list):
        title = prompt[:80]
        sections_raw = parsed
    else:
        title = (parsed.get("title") or prompt[:80]).strip()
        sections_raw = parsed.get("sections") or []
    sections = []
    for sec in sections_raw:
        if not isinstance(sec, dict):
            continue
        heading = _clean_slide_title(str(sec.get("heading") or "Section"))
        paras_raw = sec.get("paragraphs") or []
        if not isinstance(paras_raw, list):
            paras_raw = [str(paras_raw)]
        paragraphs = [str(p).strip() for p in paras_raw if str(p).strip()]
        if not paragraphs:
            paragraphs = [f"Discuss {heading.lower()} as it relates to {prompt[:80]}."]
        sections.append({"heading": heading, "paragraphs": paragraphs})

    # Pad missing sections so the doc isn't truncated to whatever the
    # small model felt like producing.
    if len(sections) < 4:
        pad_headings = [
            "Background",
            "Key Findings",
            "Recommendations",
            "Next Steps",
        ][: 4 - len(sections)]
        for pad_heading in pad_headings:
            sections.append({
                "heading": pad_heading,
                "paragraphs": [
                    f"Add details on {pad_heading.lower()} for {prompt[:80]}.",
                    f"Cite supporting evidence and examples here.",
                ],
            })

    # Final safety net.
    if not sections:
        sections = [{"heading": "Overview", "paragraphs": [prompt[:400]]}]

    doc = Document()
    # Title.
    h = doc.add_heading(title, level=0)
    for run in h.runs:
        run.font.size = Pt(20)

    # Style-specific scaffold.
    if style == "memo":
        meta_p = doc.add_paragraph()
        meta_p.add_run("TO: ").bold = True
        meta_p.add_run("Recipient\n")
        meta_p.add_run("FROM: ").bold = True
        meta_p.add_run("NovaMind AI\n")
        meta_p.add_run("DATE: ").bold = True
        meta_p.add_run(time.strftime("%Y-%m-%d"))
    elif style == "letter":
        meta_p = doc.add_paragraph()
        meta_p.add_run(time.strftime("%Y-%m-%d") + "\n\nDear Recipient,\n").bold = False

    para_count = 1  # title
    for sec in sections[:5]:
        heading = (sec.get("heading") or "Section").strip()
        doc.add_heading(heading, level=1)
        para_count += 1
        for para_text in (sec.get("paragraphs") or [])[:4]:
            text = str(para_text).strip()
            if not text:
                continue
            doc.add_paragraph(text)
            para_count += 1
            if para_count >= MAX_DOCX_PARAGRAPHS:
                break
        if para_count >= MAX_DOCX_PARAGRAPHS:
            break

    if style == "letter":
        doc.add_paragraph("\nSincerely,\nNovaMind AI")

    buf = io.BytesIO()
    doc.save(buf)
    payload = buf.getvalue()
    if not payload:
        raise HTTPException(
            status_code=502,
            detail={"code": "docx_build_failed", "message": "Could not assemble the .docx file."},
        )

    ts = int(time.time())
    filename = f"novamind-document-{ts}.docx"
    meta = {
        "kind": "docx",
        "style": style,
        "paragraph_count": para_count,
        "model_used": model_name,
        "size_bytes": len(payload),
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "filename": filename,
        "prompt": prompt[:500],
    }
    return payload, filename, meta


# ----- Code (with sandboxed exec) ------------------------------------------

def generate_code_payload(
    prompt: str,
    *,
    language: str = "python",
    model_name: str = "NovaMind-Chat",
    timeout_s: float = DEFAULT_CODE_TIMEOUT_S,
) -> Tuple[CodeRunResult, Dict[str, Any]]:
    """Ask the LLM for code, run it through `code_runner`, return the
    raw CodeRunResult plus a small meta dict. The chat dispatcher
    embeds `result.to_meta()` into `Message.meta_data`.

    The LLM step is best-effort: if it fails (network down, model
    rate-limited), we return a `runtime_missing=True` result so the
    frontend shows "I couldn't draft the code, please try again" rather
    than a 502.
    """
    instruction = (
        f"Write only {language} source code that solves: {prompt}. "
        "Do NOT include explanations, markdown fences, or example usage. "
        "Output should be raw, runnable source code only."
    )

    meta_out: Dict[str, Any] = {
        "kind": "code",
        "language": language,
        "model_used": model_name,
        "prompt": prompt[:500],
    }

    try:
        # Same async-loop avoidance as `generate_docx_payload`: we are
        # already inside the FastAPI event loop, so we use the sync
        # httpx shim rather than `asyncio.run()`.
        raw = _llm_outline_sync(instruction, model_name=model_name)
        code = _strip_code_fence(raw)
        if not code:
            return (
                CodeRunResult(
                    language=language,
                    code="",
                    stdout="",
                    stderr="The model returned an empty response.",
                    runtime_missing=True,
                ),
                meta_out,
            )
    except HTTPException:
        # Surface as a missing-runtime result so the chat message can be
        # saved with a friendly inline error rather than a 502.
        return (
            CodeRunResult(
                language=language,
                code="",
                stdout="",
                stderr="I couldn't reach the model to draft the code. Please try again.",
                runtime_missing=True,
            ),
            meta_out,
        )

    result = run_code(language, code, timeout_s=timeout_s)
    meta_out["timed_out"] = result.timed_out
    meta_out["runtime_missing"] = result.runtime_missing
    meta_out["exit_code"] = result.exit_code
    meta_out["elapsed_ms"] = result.elapsed_ms
    return result, meta_out


# ----- Helpers used by the chat dispatcher ---------------------------------

def file_b64(payload: bytes) -> str:
    """Common base64 encoding for transport through `meta_data`."""
    return base64.b64encode(payload).decode("ascii")


# ----- REST endpoints ------------------------------------------------------
#
# Most callers hit the chat dispatcher. These endpoints exist so the
# dev OpenAI-compat layer and any frontend that wants a file without a
# chat wrapper can use the same generators.

from pydantic import BaseModel


class FileGenRequest(BaseModel):
    prompt: str
    kind: str  # "pptx" | "docx" | "code"
    theme: Optional[str] = None
    slide_count: Optional[int] = None
    style: Optional[str] = None
    language: Optional[str] = None
    model: Optional[str] = None
    timeout_s: Optional[float] = None


class FileGenResponse(BaseModel):
    kind: str
    filename: str
    mime_type: str
    file_b64: str
    size_bytes: int
    meta_data: Dict[str, Any]
    # code runs also return stdout/stderr
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    timed_out: Optional[bool] = None
    runtime_missing: Optional[bool] = None
    elapsed_ms: Optional[int] = None
    code: Optional[str] = None


@router.post("/generate", response_model=FileGenResponse)
async def generate_file(req: FileGenRequest):
    """Dispatch on `kind` and route to the matching generator."""
    kind = (req.kind or "").lower()
    if kind == "pptx":
        payload, filename, meta = await generate_pptx_payload(
            prompt=req.prompt,
            theme=req.theme or "modern",
            slide_count=req.slide_count or 6,
            model_name=req.model or "NovaMind-Chat",
        )
        return FileGenResponse(
            kind="pptx",
            filename=meta["filename"],
            mime_type=meta["mime_type"],
            file_b64=file_b64(payload),
            size_bytes=meta["size_bytes"],
            meta_data=meta,
        )
    if kind == "docx":
        payload, filename, meta = generate_docx_payload(
            prompt=req.prompt,
            style=req.style or "report",
            model_name=req.model or "NovaMind-Chat",
        )
        return FileGenResponse(
            kind="docx",
            filename=meta["filename"],
            mime_type=meta["mime_type"],
            file_b64=file_b64(payload),
            size_bytes=meta["size_bytes"],
            meta_data=meta,
        )
    if kind == "code":
        result, gen_meta = generate_code_payload(
            prompt=req.prompt,
            language=req.language or "python",
            model_name=req.model or "NovaMind-Code",
            timeout_s=req.timeout_s or 8.0,
        )
        run_meta = result.to_meta()
        return FileGenResponse(
            kind="code",
            filename="",  # code has no file artifact
            mime_type="text/plain",
            file_b64="",
            size_bytes=len(result.code.encode("utf-8")),
            meta_data={**gen_meta, **run_meta},
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            runtime_missing=result.runtime_missing,
            elapsed_ms=result.elapsed_ms,
            code=result.code,
        )
    raise HTTPException(
        status_code=400,
        detail={"code": "unknown_kind", "message": f"Unknown file kind: {req.kind!r}"},
    )