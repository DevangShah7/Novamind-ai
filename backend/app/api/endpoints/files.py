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

async def _llm_outline(
    prompt: str, *, model_name: str = "NovaMind-Chat", max_tokens: int = 2000
) -> str:
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
        resp = await llm.generate_response(
            messages=messages, temperature=0.4, max_tokens=max_tokens
        )
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
        # Generous max_tokens so a 5-section DOCX doesn't truncate mid-JSON.
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": backend,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "max_tokens": 4000,
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

# Theme palette: accent color + matching dark + soft background + dark text.
# `bg` is the fill we paint the title-bar / accent strip with on every
# slide so the deck has a consistent brand colour even though the LLM
# hasn't supplied any. `text` is the body-text colour; we always set
# bullet text colour explicitly because python-pptx defaults to theme
# black which clashes with our cover-slide layouts.
PPT_THEMES = {
    "modern": {
        "accent": "1F4E79",   # deep blue
        "dark":   "0F2A45",   # cover background
        "bg":     "EAF2FB",   # soft title-bar / strip
        "text":   "1A1A1A",
        "title_font": "Calibri Light",
        "body_font": "Calibri",
    },
    "minimal": {
        "accent": "404040",   # graphite
        "dark":   "1A1A1A",
        "bg":     "F4F4F4",
        "text":   "222222",
        "title_font": "Helvetica",
        "body_font": "Helvetica",
    },
    "academic": {
        "accent": "8B0000",   # oxblood
        "dark":   "4A0010",
        "bg":     "FBEFEF",
        "text":   "1F1F1F",
        "title_font": "Georgia",
        "body_font": "Georgia",
    },
    "pitch-deck": {
        "accent": "C00000",   # signal red
        "dark":   "5A0000",
        "bg":     "FFF2F2",
        "text":   "141414",
        "title_font": "Calibri",
        "body_font": "Calibri",
    },
}


def _theme_palette(theme_key: str) -> Dict[str, str]:
    """Returns the palette dict for `theme_key`, falling back to
    `modern` if the requested theme isn't registered. Wrapping the
    default in a dict gives callers a safe key surface even when the
    caller passed garbage."""
    if theme_key in PPT_THEMES:
        return PPT_THEMES[theme_key]
    return PPT_THEMES["modern"]


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


# Per-slide image rendering — pull a Pollinations image for each slide
# in parallel so the deck has real visuals, not walls of text. Image
# rendering is the slow part (~3-30 s each for cold-cache, sub-second
# for warm cache) so we cap the per-call timeout at 25 s. A failure on
# any one slide is silent — the slide still renders with text only,
# and the user gets a finished deck.
_PPTX_IMAGE_TIMEOUT_S = 25.0


def _fetch_pollinations_image(
    prompt: str, *, width: int = 768, height: int = 512, seed: int = 0,
    max_retries: int = 2
) -> Optional[bytes]:
    """Fetch one image from Pollinations and return raw bytes, or None
    on any failure. Retries on 429 (rate-limit) with exponential
    backoff — Pollinations' free tier aggressively throttles serial
    requests and ~10 s of cooldown usually clears the window."""
    if not prompt or not prompt.strip():
        return None
    import httpx
    import time as _t
    from urllib.parse import quote as _quote
    url = (
        f"https://image.pollinations.ai/prompt/{_quote(prompt, safe='')}"
        f"?width={width}&height={height}&model=flux&nologo=true&enhance=false&seed={seed}"
    )
    backoff_s = 3.0
    for attempt in range(max_retries + 1):
        try:
            r = httpx.get(url, timeout=_PPTX_IMAGE_TIMEOUT_S, follow_redirects=True)
            if r.status_code == 200 and r.content and len(r.content) > 1000:
                return r.content
            if r.status_code == 429 and attempt < max_retries:
                logger.debug("Pollinations 429 for %r, backing off %.1fs", prompt[:40], backoff_s)
                _t.sleep(backoff_s)
                backoff_s *= 2
                continue
            logger.debug(
                "Pollinations fetch %r returned status=%d size=%d",
                prompt[:40], r.status_code, len(r.content or b""),
            )
            return None
        except Exception as exc:  # noqa: BLE001 — image fetch is best-effort
            logger.debug("Pollinations fetch failed for %r: %s", prompt[:40], exc)
            return None
    return None


def _fetch_slide_images_parallel(slides: list, *, accent_hex: str = "1F4E79") -> list:
    """Fetch one image per slide. Tries Pollinations first; on any
    failure (rate-limit, timeout, network down) renders a local
    gradient image so the deck is never image-less.

    Pollinations' free tier is aggressively rate-limited — on this
    network we see ~1 successful call per minute from a single IP.
    Rather than block the user on retries, we degrade to a Pillow-
    rendered themed gradient seeded by the slide text. Each slide gets
    a distinct palette so the deck still looks premium, and the cover
    slide gets a real Pollinations render when the network cooperates.

    Returns a list aligned with `slides`; entries are JPEG bytes.
    """
    import time as _time

    prompts = []
    for idx, s in enumerate(slides):
        ip = (s.get("image_prompt") or "").strip()
        if not ip and isinstance(s.get("bullets"), list) and s.get("bullets"):
            base = (s.get("title") or "").strip()
            if base:
                ip = f"{base}, {s['bullets'][0]}"
            else:
                ip = f"slide {idx + 1}: {s.get('bullets', [''])[0]}"
        if not ip:
            ip = f"slide {idx + 1} of {len(slides)}"
        prompts.append(ip)

    seeds = [abs(hash(p)) % 999999 for p in prompts]
    results = [None] * len(slides)
    cover_order = [0] + [i for i in range(1, len(prompts))]
    for step, idx in enumerate(cover_order):
        prompt = prompts[idx]
        img = _fetch_pollinations_image(
            prompt, width=768, height=512, seed=seeds[idx]
        )
        if img is None:
            # Pollinations failed — render a local themed gradient so
            # the slide still has an image. Seed with the prompt so
            # each slide gets a distinct look.
            img = _local_gradient_image(
                prompt, accent_hex=accent_hex, width=768, height=512,
            )
        results[idx] = img
        if step < len(prompts) - 1:
            _time.sleep(1.0)
    return results


# Pollinations' free tier is aggressively rate-limited — when it
# fails we fall back to a locally-rendered gradient image seeded by
# the slide text so the deck still has a unique, themed visual per
# slide. Pillow ships as a python-pptx transitive dependency so this
# adds zero install cost. Cache keyed by (text, accent, dims) so
# repeat decks are instant.
_PPTX_GRADIENT_CACHE: Dict[str, bytes] = {}


def _local_gradient_image(seed_text: str, *, accent_hex: str,
                          width: int = 768, height: int = 512) -> bytes:
    """Render a deterministic, themed gradient JPEG using Pillow."""
    cache_key = f"{seed_text}|{accent_hex}|{width}x{height}"
    if cache_key in _PPTX_GRADIENT_CACHE:
        return _PPTX_GRADIENT_CACHE[cache_key]

    accent = _hex_to_rgb(accent_hex)
    dark = _darken(accent, 0.55)
    light = _lighten(accent, 0.45)

    try:
        from PIL import Image, ImageDraw
        from io import BytesIO as _BIO
        img = Image.new("RGB", (width, height), dark)
        draw = ImageDraw.Draw(img)
        # Diagonal gradient: dark -> accent -> light.
        steps = 48
        for i in range(steps):
            t = i / (steps - 1)
            c = _lerp(dark, accent, t) if t < 0.5 else _lerp(accent, light, (t - 0.5) * 2)
            y0 = int(t * height)
            y1 = int((i + 1) / steps * height) + 1
            draw.rectangle([0, y0, width, y1], fill=c)

        # Sparse "particles" so each slide is visually distinct.
        import hashlib
        digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
        rng_offset = digest[0] | (digest[1] << 8)
        for i in range(40):
            x = ((digest[i % 32] * (i + 1)) + rng_offset) % width
            y = ((digest[(i + 7) % 32] * (i + 3)) + rng_offset) % height
            r = 2 + (digest[(i + 13) % 32] % 5)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))

        buf = _BIO()
        img.save(buf, format="JPEG", quality=85)
        data = buf.getvalue()
    except ImportError:
        # Pillow missing — fall back to a 1×1 PNG of the accent colour.
        from struct import pack
        r, g, b = accent
        sig = b"\x89PNG\r\n\x1a\n"
        def _chunk(t, d):
            return pack(">I", len(d)) + t + d + pack(">I", 0)
        ihdr = _chunk(b"IHDR", pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        raw = b"\x00" + bytes((r, g, b))
        idat = _chunk(b"IDAT", raw)
        iend = _chunk(b"IEND", b"")
        data = sig + ihdr + idat + iend

    _PPTX_GRADIENT_CACHE[cache_key] = data
    return data


def _hex_to_rgb(hex_str: str) -> tuple:
    try:
        h = hex_str.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (ValueError, IndexError):
        return (31, 78, 121)


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _darken(c: tuple, factor: float) -> tuple:
    return (int(c[0] * factor), int(c[1] * factor), int(c[2] * factor))


def _lighten(c: tuple, factor: float) -> tuple:
    return tuple(min(255, int(c[i] + (255 - c[i]) * factor)) for i in range(3))


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
      1. Ask the LLM for a structured outline. Each slide gets a
         title, 3-5 bullets, optional speaker notes, AND an
         ``image_prompt`` describing what should appear in the slide's
         hero image.
      2. Fetch one Pollinations image per slide in parallel (best-effort;
         a slide with no image still renders cleanly).
      3. Build a python-pptx Presentation with three layout types:
           - Cover slide (slide 0): full-bleed hero image with title
             overlay + accent strip.
           - Content slide (default): two-column layout — bullets on
             the left, image on the right, accent title bar on top.
           - Closing slide (last): same as content but with a
             "Thank you" / "Questions?" style footer overlay.
      4. Return the binary + filename + meta dict.

    Falls back to a single text-only slide if the LLM output is
    malformed, so a transient LLM hiccup doesn't blow up the chat.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from io import BytesIO as _BytesIO

    slide_count = max(1, min(int(slide_count or 6), MAX_PPTX_SLIDES))
    theme_key = theme if theme in PPT_THEMES else "modern"
    palette = _theme_palette(theme_key)

    def _rgb(hex_str: str) -> RGBColor:
        try:
            return RGBColor.from_string(hex_str)
        except (ValueError, AttributeError):
            return RGBColor(0, 0, 0)

    accent_rgb = _rgb(palette["accent"])
    dark_rgb = _rgb(palette["dark"])
    bg_rgb = _rgb(palette["bg"])
    text_rgb = _rgb(palette["text"])
    accent_hex = palette["accent"]
    title_font = palette["title_font"]
    body_font = palette["body_font"]

    # Step 1: ask the LLM for the outline + image prompts. The image
    # prompt is short and concrete ("a clean photograph of a quantum
    # computer chip") so Pollinations gets something it can render in
    # ~5 s. We deliberately don't ask for art direction in the JSON —
    # style is controlled by the theme, not the prompt.
    instruction = (
        f"You are drafting a {slide_count}-slide presentation on this topic:\n\n"
        f"TOPIC: {prompt}\n\n"
        f"Output ONLY a JSON object with exactly {slide_count} entries in a "
        '"slides" array. Each entry must have:\n'
        '  - "title": 4-8 word slide title (NOT the topic again, NOT "Slide N")\n'
        '  - "bullets": array of 3-5 short bullet points about THAT slide\n'
        '  - "notes": one short sentence for the speaker (optional, can be "")\n'
        '  - "image_prompt": a 6-12 word phrase describing one visual '
        'for THIS slide (e.g. "photograph of a quantum computer chip on a '
        'dark blue background", "flat illustration of entangled particles").\n\n'
        f"Write exactly {slide_count} entries — one per slide. No prose, no "
        "markdown fences, no commentary. Output the JSON object only."
    )

    raw = await _llm_outline(
        instruction, model_name=model_name,
        max_tokens=min(4000, 1200 + slide_count * 400),
    )
    parsed = _safe_json_loads(raw) or {}
    slides = _extract_slides(parsed)

    if len(slides) < max(1, slide_count // 2):
        retry_instruction = (
            f"Output ONLY a JSON object with a 'slides' array of EXACTLY "
            f"{slide_count} entries. Topic: {prompt}. "
            'Each entry: {"title": str, "bullets": [str, str, str], '
            '"notes": str, "image_prompt": str}. '
            f"You must include {slide_count} entries — no fewer. No prose."
        )
        try:
            retry_raw = await _llm_outline(
                retry_instruction, model_name=model_name,
                max_tokens=min(4000, 1200 + slide_count * 400),
            )
            retry_parsed = _safe_json_loads(retry_raw) or {}
            retry_slides = _extract_slides(retry_parsed)
            if len(retry_slides) > len(slides):
                slides = retry_slides
        except HTTPException:
            pass

    slides = _fill_slides(slides, slide_count, prompt)

    # Step 2: fetch images for every slide in parallel. Failures are
    # silent — we end up with `None` for that slide and the text-only
    # layout renders cleanly without one.
    image_bytes_list = _fetch_slide_images_parallel(slides, accent_hex=accent_hex)

    # Step 3: build the .pptx.
    prs = Presentation()
    # 16:9 widescreen — most modern displays + projectors render this
    # without black bars. The default python-pptx presentation is 4:3.
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # SLIDE WIDTH constants in EMU so we can size shapes relative to
    # the slide instead of guessing Inches values.
    SW = prs.slide_width
    SH = prs.slide_height
    MARGIN = Inches(0.55)

    def _paint_background(slide, color: RGBColor) -> None:
        """Fill the slide background with a solid colour."""
        bg_shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, SW, SH
        )
        bg_shape.fill.solid()
        bg_shape.fill.fore_color.rgb = color
        bg_shape.line.fill.background()
        # Send to back so everything else paints on top.
        spTree = bg_shape._element.getparent()
        spTree.remove(bg_shape._element)
        spTree.insert(2, bg_shape._element)

    def _add_title_bar(slide, title_text: str) -> None:
        """Accent strip + slide title across the top of the slide."""
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(0.18)
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = accent_rgb
        bar.line.fill.background()
        tx = slide.shapes.add_textbox(
            MARGIN, Inches(0.35), SW - 2 * MARGIN, Inches(1.1)
        )
        tf = tx.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title_text
        run.font.name = title_font
        run.font.size = Pt(34)
        run.font.bold = True
        run.font.color.rgb = accent_rgb

    def _add_bullets(slide, bullets: list, *, left: int, top: int,
                     width: int, height: int, font_size: int = 18) -> None:
        """Bullet list in a fixed rectangle."""
        tx = slide.shapes.add_textbox(left, top, width, height)
        tf = tx.text_frame
        tf.word_wrap = True
        for i, b in enumerate(bullets[:6]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = f"•  {str(b)}"
            run.font.name = body_font
            run.font.size = Pt(font_size)
            run.font.color.rgb = text_rgb
            p.space_after = Pt(8)
            p.line_spacing = 1.15

    def _add_image(slide, image_bytes: bytes, *,
                   left: int, top: int, width: int, height: int) -> None:
        """Place a JPEG/PNG into the slide at the given rect. python-pptx
        sniffs the bytes to pick the right image format."""
        from pptx.util import Emu as _Emu
        # `add_picture` needs a file-like, so wrap the bytes.
        bio = _BytesIO(image_bytes)
        slide.shapes.add_picture(bio, left, top, width=width, height=height)

    def _add_image_or_placeholder(slide, image_bytes: Optional[bytes], *,
                                  left: int, top: int, width: int,
                                  height: int) -> None:
        """Add the image, or — if Pollinations failed — a soft-fill
        rectangle with the slide index so the layout still has a
        visual anchor. Better than a broken-image icon in PowerPoint."""
        if image_bytes:
            _add_image(slide, image_bytes, left=left, top=top,
                       width=width, height=height)
            return
        # Placeholder rectangle — same dimensions, tinted with bg.
        ph = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, width, height
        )
        ph.fill.solid()
        ph.fill.fore_color.rgb = bg_rgb
        ph.line.color.rgb = accent_rgb
        ph.line.width = Pt(0.75)

    # --- Cover slide (idx == 0) ---------------------------------------
    cover = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    _paint_background(cover, dark_rgb)
    cover_image = image_bytes_list[0] if image_bytes_list else None
    if cover_image:
        _add_image(cover, cover_image, left=0, top=0,
                   width=SW, height=SH)
        # Dark overlay so the title text reads on top of any image.
        overlay = cover.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, Inches(2.6), SW, Inches(2.8)
        )
        overlay.fill.solid()
        overlay.fill.fore_color.rgb = dark_rgb
        overlay.fill.transparency = 0.35  # ~35% opaque dark wash
        overlay.line.fill.background()

    # Title + subtitle on the cover.
    title_box = cover.shapes.add_textbox(
        MARGIN, Inches(2.9), SW - 2 * MARGIN, Inches(2.0)
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    cover_title = (slides[0].get("title") or prompt[:120]).strip()
    run.text = cover_title
    run.font.name = title_font
    run.font.size = Pt(44)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    subtitle_text = (slides[0].get("bullets") or [prompt[:200]])[0]
    sub_box = cover.shapes.add_textbox(
        MARGIN, Inches(4.5), SW - 2 * MARGIN, Inches(1.4)
    )
    stf = sub_box.text_frame
    stf.word_wrap = True
    sp = stf.paragraphs[0]
    srun = sp.add_run()
    srun.text = str(subtitle_text)[:280]
    srun.font.name = body_font
    srun.font.size = Pt(20)
    srun.font.color.rgb = RGBColor(0xE6, 0xE6, 0xE6)

    # Accent strip at the bottom of the cover.
    strip = cover.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, SH - Inches(0.18), SW, Inches(0.18)
    )
    strip.fill.solid()
    strip.fill.fore_color.rgb = accent_rgb
    strip.line.fill.background()

    # --- Content slides (idx 1 .. slide_count-2) ----------------------
    last_content_idx = slide_count - 1
    for idx in range(1, last_content_idx):
        slide_data = slides[idx]
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
        _paint_background(slide, RGBColor(0xFF, 0xFF, 0xFF))
        _add_title_bar(slide, (slide_data.get("title") or f"Slide {idx + 1}").strip())

        bullets = slide_data.get("bullets") or _pad_bullets(prompt, idx, slide_count)
        # Left column: bullets.
        col_top = Inches(1.7)
        col_h = SH - col_top - Inches(0.4)
        _add_bullets(
            slide, bullets,
            left=MARGIN, top=col_top,
            width=Inches(6.8), height=col_h,
            font_size=18,
        )
        # Right column: image.
        img_left = Inches(7.7)
        img_top = Inches(1.7)
        img_w = SW - img_left - MARGIN
        img_h = Inches(4.6)
        _add_image_or_placeholder(
            slide, image_bytes_list[idx] if idx < len(image_bytes_list) else None,
            left=img_left, top=img_top,
            width=img_w, height=img_h,
        )
        # Speaker notes.
        notes_tf = slide.notes_slide.notes_text_frame
        notes_tf.text = (slide_data.get("notes") or "").strip()[:500]

    # --- Closing slide (last) -----------------------------------------
    if slide_count >= 2:
        slide_data = slides[last_content_idx]
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _paint_background(slide, dark_rgb)
        # Big "Thank You" or last title.
        title_box = slide.shapes.add_textbox(
            MARGIN, Inches(2.6), SW - 2 * MARGIN, Inches(1.8)
        )
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        closing_title = (slide_data.get("title") or "Thank you").strip()
        run.text = closing_title
        run.font.name = title_font
        run.font.size = Pt(48)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        # Subtitle = first bullet or prompt tail.
        subtitle_text = (slide_data.get("bullets") or [f"Questions about {prompt[:60]}?"])[0]
        sub_box = slide.shapes.add_textbox(
            MARGIN, Inches(4.6), SW - 2 * MARGIN, Inches(1.2)
        )
        stf = sub_box.text_frame
        stf.word_wrap = True
        sp = stf.paragraphs[0]
        sp.alignment = PP_ALIGN.CENTER
        srun = sp.add_run()
        srun.text = str(subtitle_text)[:240]
        srun.font.name = body_font
        srun.font.size = Pt(22)
        srun.font.color.rgb = RGBColor(0xE6, 0xE6, 0xE6)

        # Accent strip at bottom.
        strip = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, SH - Inches(0.18), SW, Inches(0.18)
        )
        strip.fill.solid()
        strip.fill.fore_color.rgb = accent_rgb
        strip.line.fill.background()

        # Closing notes
        slide.notes_slide.notes_text_frame.text = (
            (slide_data.get("notes") or "")[:500]
        )

    # If slide_count == 1 we still want a real cover; loop above skipped.
    # Already handled by the cover block above.

    # Step 4: serialize.
    buf = io.BytesIO()
    prs.save(buf)
    payload = buf.getvalue()
    if not payload:
        raise HTTPException(
            status_code=502,
            detail={"code": "pptx_build_failed",
                    "message": "Could not assemble the .pptx file."},
        )

    images_resolved = sum(1 for b in image_bytes_list if b)
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
        "images_attached": images_resolved,
        "images_requested": len(slides),
    }
    return payload, filename, meta


# ----- DOCX -----------------------------------------------------------------

DOCX_STYLES = {"memo", "report", "letter", "outline"}


def generate_docx_payload(
    prompt: str,
    *,
    style: str = "report",
    theme: str = "modern",
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
    from docx.shared import Pt, RGBColor as DocxRGB, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    style = style if style in DOCX_STYLES else "report"
    palette = _theme_palette(theme)
    body_font = palette["body_font"]
    title_font = palette["title_font"]

    def _docx_rgb(hex_str: str) -> DocxRGB:
        try:
            return DocxRGB.from_string(hex_str)
        except (ValueError, AttributeError):
            return DocxRGB(0, 0, 0)

    accent_rgb = _docx_rgb(palette["accent"])
    text_rgb = _docx_rgb(palette["text"])
    dark_rgb = _docx_rgb(palette["dark"])

    instruction = (
        f"You are drafting a {style}-style document on this topic:\n\n"
        f"TOPIC: {prompt}\n\n"
        "Output ONLY a JSON object with this exact shape, no prose:\n"
        '{"title":"...",'
        '"sections":[{"heading":"...","paragraphs":["...","..."]},...]} '
        "Include 4-5 sections and 2-3 short paragraphs per section. "
        "Each paragraph should be 2-4 sentences with concrete details, "
        "not just one-liners. "
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
    # Page margins — narrower than default so the body has more line length.
    for section in doc.sections:
        section.top_margin = Cm(2.2)
        section.bottom_margin = Cm(2.2)
        section.left_margin = Cm(2.4)
        section.right_margin = Cm(2.4)

    # Style the built-in Normal style so every paragraph inherits the
    # theme fonts/colours/spacing. python-docx's default is Calibri 11
    # black on white — fine for letters, bland for a branded report.
    normal = doc.styles["Normal"]
    normal.font.name = body_font
    normal.font.size = Pt(11)
    normal.font.color.rgb = text_rgb
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    # Title — large accent-coloured heading with a thin accent rule
    # beneath. The bottom-border trick scales with page width and
    # avoids a separate empty paragraph just for the rule.
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    title_run = title_p.add_run(title)
    title_run.font.name = title_font
    title_run.font.size = Pt(28)
    title_run.font.bold = True
    title_run.font.color.rgb = accent_rgb
    title_p.paragraph_format.space_after = Pt(4)
    pPr = title_p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), palette["accent"])
    pBdr.append(bottom)
    pPr.append(pBdr)
    para_count = 1

    # Style-specific scaffold.
    if style == "memo":
        meta_p = doc.add_paragraph()
        meta_run = meta_p.add_run("MEMO")
        meta_run.bold = True
        meta_run.font.name = title_font
        meta_run.font.size = Pt(13)
        meta_run.font.color.rgb = dark_rgb
        meta_p.paragraph_format.space_after = Pt(2)

        meta_p = doc.add_paragraph()
        for label, value in [
            ("TO", "Recipient"),
            ("FROM", "NovaMind AI"),
            ("DATE", time.strftime("%Y-%m-%d")),
        ]:
            r = meta_p.add_run(f"{label}: ")
            r.bold = True
            r.font.name = body_font
            r.font.size = Pt(11)
            r2 = meta_p.add_run(f"{value}\n")
            r2.font.name = body_font
            r2.font.size = Pt(11)
        para_count += 2
    elif style == "letter":
        date_p = doc.add_paragraph()
        date_p.add_run(time.strftime("%Y-%m-%d")).font.size = Pt(11)
        doc.add_paragraph()
        greeting = doc.add_paragraph()
        greeting.add_run("Dear Recipient,").font.size = Pt(11)
        para_count += 3

    for sec in sections[:6]:
        heading = (sec.get("heading") or "Section").strip()
        h_p = doc.add_paragraph()
        h_run = h_p.add_run(heading)
        h_run.font.name = title_font
        h_run.font.size = Pt(16)
        h_run.font.bold = True
        h_run.font.color.rgb = accent_rgb
        h_p.paragraph_format.space_before = Pt(10)
        h_p.paragraph_format.space_after = Pt(4)
        para_count += 1
        for para_text in (sec.get("paragraphs") or [])[:4]:
            text = str(para_text).strip()
            if not text:
                continue
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            run = p.add_run(text)
            run.font.name = body_font
            run.font.size = Pt(11)
            run.font.color.rgb = text_rgb
            para_count += 1
            if para_count >= MAX_DOCX_PARAGRAPHS:
                break
        if para_count >= MAX_DOCX_PARAGRAPHS:
            break

    if style == "letter":
        doc.add_paragraph()
        closing = doc.add_paragraph()
        closing.add_run("Sincerely,\n").font.size = Pt(11)
        closing.add_run("NovaMind AI").font.size = Pt(11)
        para_count += 2

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
            theme=req.theme or "modern",
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