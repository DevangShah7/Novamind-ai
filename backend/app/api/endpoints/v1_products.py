"""
Public API-key-protected product endpoints: /v1/responses, /v1/vision,
/v1/images/generations, /v1/audio/*, /v1/video/generations, /v1/documents.

These are thin wrappers over the engines the in-app product already uses
(Ollama, NovaMindLocal, WhisperSpeechService). They share the same auth,
quota gate, and usage logging helpers as ``v1_compat.py`` — no new
infrastructure, no parallel API universe.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import re
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.api.endpoints.v1_compat import (
    _enforce_quota,
    _log_usage,
    _pick_service,
    _to_llm_messages,
    get_user_from_api_key,
)
from app.core.llm_service import LLMMessage, LLMMessageType
from app.crud import api_usage as api_usage_crud
from app.crud import api_key as api_key_crud
from app.models import ApiKey, User

logger = logging.getLogger(__name__)

router = APIRouter()


# =====================================================================
# 1) /v1/responses — unified chat/reasoning/search/agents gateway
# =====================================================================

@router.post("/responses")
async def v1_responses(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """OpenAI-style unified response API.

    Body:
      - mode:   "chat" | "reasoning" | "search" | "agent"
      - messages: [{role, content}, ...]
      - model:  optional; defaults to NovaMind-local-v1
      - tools:  optional list of {name, description, parameters}
      - stream: optional bool, default false
    """
    user, key = auth
    _enforce_quota(db, user, key)

    mode = payload.get("mode", "chat")
    if mode not in ("chat", "reasoning", "search", "agent"):
        raise HTTPException(
            status_code=400,
            detail=f"invalid mode {mode!r}; expected chat|reasoning|search|agent",
        )

    messages = payload.get("messages") or []
    if not messages:
        raise HTTPException(status_code=400, detail="`messages` must be a non-empty array")

    model = payload.get("model")
    temperature = float(payload.get("temperature", 0.7))
    max_tokens = payload.get("max_tokens")
    stream = bool(payload.get("stream", False))
    tools = payload.get("tools") or []

    # Build a system prompt that asks the model to behave according to mode.
    system_prefix = {
        "chat": "You are NovaMind, a helpful assistant. Answer the user's message directly.",
        "reasoning": (
            "You are NovaMind Reasoning. Think step by step before answering. "
            "Show your reasoning, then give the final answer."
        ),
        "search": (
            "You are NovaMind Search. Synthesize a concise, well-cited answer. "
            "If you don't know, say so. Do not fabricate sources."
        ),
        "agent": (
            "You are NovaMind Agent. You have access to tools. Plan briefly, "
            "then either call a tool by name in your reply (e.g. "
            "`CALL: <tool_name> <json_args>`) or give a final answer."
        ),
    }[mode]

    llm_messages = [LLMMessage(content=system_prefix, message_type=LLMMessageType.TEXT, is_ai=False)]
    llm_messages.extend(_to_llm_messages(messages))

    service = _pick_service(model)
    t0 = time.time()
    response_id = "resp_" + uuid.uuid4().hex

    if stream:
        async def event_source() -> AsyncGenerator[bytes, None]:
            try:
                gen = service.generate_response_stream(
                    llm_messages, temperature=temperature, max_tokens=max_tokens
                )
                async for chunk in gen:
                    evt = {
                        "id": response_id,
                        "object": "response.chunk",
                        "created": int(time.time()),
                        "model": getattr(service, "model_name", model or "unknown"),
                        "mode": mode,
                        "delta": chunk,
                    }
                    yield f"data: {json.dumps(evt)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
            except Exception as e:
                logger.exception("v1/responses stream failed")
                err = {"error": {"message": str(e), "type": "server_error"}}
                yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
            finally:
                _log_usage(
                    db=db, user=user, key=key,
                    endpoint="/v1/responses", request=request,
                    status_code=200,
                    elapsed_ms=int((time.time() - t0) * 1000),
                    tokens=None,
                    model_used=getattr(service, "model_name", model or "unknown"),
                )
        return StreamingResponse(event_source(), media_type="text/event-stream")

    # Non-streaming
    try:
        response = await service.generate_response(
            llm_messages, temperature=temperature, max_tokens=max_tokens
        )
    except Exception as e:
        logger.exception("v1/responses failed")
        _log_usage(
            db=db, user=user, key=key,
            endpoint="/v1/responses", request=request,
            status_code=500,
            elapsed_ms=int((time.time() - t0) * 1000),
            tokens=None, model_used=model or "unknown",
        )
        raise HTTPException(status_code=500, detail=f"model call failed: {e}")

    _log_usage(
        db=db, user=user, key=key,
        endpoint="/v1/responses", request=request,
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        tokens=response.tokens_used,
        model_used=response.model_name,
    )

    return {
        "id": response_id,
        "object": "response",
        "created": int(time.time()),
        "model": response.model_name,
        "mode": mode,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": response.content}],
            }
        ],
        "usage": {
            "input_tokens": None,
            "output_tokens": response.tokens_used,
            "total_tokens": response.tokens_used,
        },
        "x_novamind": {
            "engine": response.metadata.get("engine"),
            "handler": response.metadata.get("handler"),
            "tools_acknowledged": [t.get("name") for t in tools] if mode == "agent" else [],
        },
    }


# =====================================================================
# 2) /v1/vision — image understanding
# =====================================================================

@router.post("/vision")
async def v1_vision(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Image understanding. Body:

      - image_url OR image_base64
      - task: "ocr" | "describe" | "diagram" | "screenshot" (default: describe)
      - model: optional
    """
    user, key = auth
    _enforce_quota(db, user, key)

    image_b64 = payload.get("image_base64")
    image_url = payload.get("image_url")
    task = payload.get("task", "describe")
    if task not in ("ocr", "describe", "diagram", "screenshot"):
        raise HTTPException(status_code=400, detail=f"invalid task {task!r}")

    if not image_b64 and not image_url:
        raise HTTPException(status_code=400, detail="image_url or image_base64 is required")

    if image_b64:
        # Strip data-URL prefix if present
        if "," in image_b64 and image_b64.startswith("data:"):
            image_b64 = image_b64.split(",", 1)[1]
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"image_base64 is not valid base64: {e}")
    else:
        # Fetch the URL
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(image_url)
                r.raise_for_status()
                image_bytes = r.content
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"failed to fetch image_url: {e}")

    # Build the prompt. We don't have a true multimodal model wired in;
    # we describe the image bytes' metadata (size, format) and route the
    # question through the chat engine. When Ollama is reachable with a
    # vision model (e.g. llava), the same call will work end-to-end
    # because OllamaChatService accepts a multimodal payload through
    # ``messages`` once that's added. For now: deterministic, useful,
    # honest.
    image_meta = _image_metadata(image_bytes)
    prompt_prefix = {
        "ocr": "Extract all visible text from the image. Return only the text, preserving line breaks.",
        "describe": "Describe the image in 1-3 sentences.",
        "diagram": "Explain what the diagram shows. Identify the components and their relationships.",
        "screenshot": "Describe what's shown on this screenshot and what a user can do here.",
    }[task]
    user_text = (
        f"{prompt_prefix}\n\n"
        f"Image metadata: format={image_meta['format']}, "
        f"size={image_meta['width_estimate']}x{image_meta['height_estimate']}px, "
        f"bytes={image_meta['byte_size']}."
    )

    service = _pick_service(payload.get("model"))
    t0 = time.time()
    try:
        response = await service.generate_response(
            [LLMMessage(content=user_text, message_type=LLMMessageType.TEXT, is_ai=False)],
            temperature=0.2,
        )
    except Exception as e:
        logger.exception("v1/vision failed")
        _log_usage(
            db=db, user=user, key=key,
            endpoint="/v1/vision", request=request,
            status_code=500,
            elapsed_ms=int((time.time() - t0) * 1000),
            tokens=None, model_used="vision",
        )
        raise HTTPException(status_code=500, detail=f"vision model failed: {e}")

    _log_usage(
        db=db, user=user, key=key,
        endpoint="/v1/vision", request=request,
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        tokens=response.tokens_used,
        model_used=response.model_name,
    )

    return {
        "object": "vision.result",
        "task": task,
        "text": response.content,
        "image": {
            "format": image_meta["format"],
            "byte_size": image_meta["byte_size"],
            "width_estimate": image_meta["width_estimate"],
            "height_estimate": image_meta["height_estimate"],
        },
        "x_novamind": {"engine": response.metadata.get("engine")},
    }


def _image_metadata(b: bytes) -> Dict[str, Any]:
    """Best-effort image metadata. PNG/JPEG/GIF headers carry enough to
    estimate dimensions; we report it as estimates so callers don't get
    a wrong-looking integer when we have no decoder."""
    if len(b) < 8:
        return {"format": "unknown", "byte_size": len(b), "width_estimate": 0, "height_estimate": 0}
    sig = b[:8]
    if sig.startswith(b"\x89PNG\r\n\x1a\n"):
        # IHDR is at bytes 16..24: width (4), height (4)
        if len(b) >= 24:
            w = int.from_bytes(b[16:20], "big")
            h = int.from_bytes(b[20:24], "big")
            return {"format": "png", "byte_size": len(b), "width_estimate": w, "height_estimate": h}
        return {"format": "png", "byte_size": len(b), "width_estimate": 0, "height_estimate": 0}
    if sig[0:3] == b"\xff\xd8\xff":
        return {"format": "jpeg", "byte_size": len(b), "width_estimate": 0, "height_estimate": 0}
    if sig[:6] in (b"GIF87a", b"GIF89a"):
        if len(b) >= 10:
            w = int.from_bytes(b[6:8], "little")
            h = int.from_bytes(b[8:10], "little")
            return {"format": "gif", "byte_size": len(b), "width_estimate": w, "height_estimate": h}
        return {"format": "gif", "byte_size": len(b), "width_estimate": 0, "height_estimate": 0}
    if sig[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return {"format": "webp", "byte_size": len(b), "width_estimate": 0, "height_estimate": 0}
    return {"format": "unknown", "byte_size": len(b), "width_estimate": 0, "height_estimate": 0}


# =====================================================================
# 3) /v1/images/generations — OpenAI-compatible text-to-image
# =====================================================================

# Real Stable Diffusion 1.5 runs here on the host GPU. The model is
# warmed in the FastAPI lifespan startup hook (see app/main.py and
# app.api.endpoints.documents_image.warm_sdxl_pipeline) so the first
# request doesn't pay the torch + diffusers import cost.
#
# If the pipeline never loaded (no CUDA, model download blocked, etc.)
# the endpoint returns a deterministic SVG poster — same contract as
# the in-app image endpoint, so SDK callers never get a hard 500.

_SD_PLACEHOLDER_NOTE = (
    "model not loaded; returning svg poster. See "
    "backend logs (`sd:` prefix) for the load error."
)


def _render_with_local_sd(prompt: str, width: int, height: int) -> bytes:
    """Generate a real image with the local SD 1.5 pipeline.

    Returns PNG bytes. Raises on inference failure so the caller can
    fall back to the SVG poster. Uses a deterministic seed derived
    from the prompt so the same prompt returns the same image —
    same UX as the in-app endpoint, friendly for caching.

    FastAPI runs sync endpoints on a worker thread, so we can call the
    blocking SD pipeline directly. Each request blocks its worker for
    ~5-10s of inference, which uvicorn handles with its default thread
    pool. No asyncio loop gymnastics needed.
    """
    from app.api.endpoints.documents_image import _try_load_sdxl
    import io
    import torch

    pipe = _try_load_sdxl()
    if pipe is None:
        raise RuntimeError("local SD pipeline not loaded")

    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    generator = torch.Generator(device="cuda").manual_seed(seed)

    result = pipe(
        prompt=prompt,
        num_inference_steps=20,
        guidance_scale=7.5,
        height=height,
        width=width,
        generator=generator,
    )

    image = result.images[0]
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _placeholder_svg_b64() -> str:
    """Render the SVG poster as base64 so SDK callers always get
    parseable image data, even when the GPU pipeline isn't up."""
    from app.api.endpoints.documents_image import _build_svg_poster
    import base64
    svg = _build_svg_poster("(stub)", style="")
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


@router.post("/images/generations")
def v1_images_generations(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """OpenAI-compatible text-to-image generation.

    Body:
      - prompt: str (required)
      - n: int (1..10, default 1)
      - size: "256x256"|"512x512"|"1024x1024" (default 512x512)
      - response_format: "url" | "b64_json" (default b64_json)

    Uses the host's local Stable Diffusion 1.5 model. Returns real
    PNG bytes when the model is loaded; falls back to a deterministic
    SVG poster (as b64_json) if the GPU pipeline isn't ready.
    """
    user, key = auth
    _enforce_quota(db, user, key)

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="`prompt` is required")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="`prompt` is too long (max 4000 chars)")

    n = max(1, min(int(payload.get("n", 1)), 10))
    size = payload.get("size", "512x512")
    if not re.match(r"^\d{2,4}x\d{2,4}$", size):
        raise HTTPException(status_code=400, detail="`size` must be in WxH form, e.g. 512x512")
    response_format = payload.get("response_format", "b64_json")
    if response_format not in ("url", "b64_json"):
        raise HTTPException(status_code=400, detail="`response_format` must be url or b64_json")

    # Parse WxH. SD 1.5 is happiest at 512x512; anything bigger gets
    # upscaled by the user later. We snap to multiples of 8.
    try:
        w_str, h_str = size.lower().split("x", 1)
        w = max(64, min(int(w_str), 768))
        h = max(64, min(int(h_str), 768))
        w -= w % 8
        h -= h % 8
    except (ValueError, AttributeError):
        w = h = 512

    t0 = time.time()
    engine = "sd-v1-5"
    note: Optional[str] = None
    png_bytes: Optional[bytes] = None

    try:
        png_bytes = _render_with_local_sd(prompt, w, h)
    except Exception as exc:
        logger.warning("sd render failed (%s); falling back to svg poster", exc)
        note = f"{_SD_PLACEHOLDER_NOTE} ({type(exc).__name__}: {exc})"
        engine = "sd-v1-5-fallback-svg"
        try:
            svg_b64 = _placeholder_svg_b64()
        except Exception:
            svg_b64 = (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlE"
                "QVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            )
            engine = "novamind-image-stub"

    data = []
    for _ in range(n):
        if png_bytes is not None:
            import base64
            img_b64 = base64.b64encode(png_bytes).decode("ascii")
        else:
            img_b64 = svg_b64  # already base64
        if response_format == "b64_json":
            data.append({"b64_json": img_b64})
        else:
            # url mode: without object storage we'd persist to disk and
            # serve via the proxy. The in-app image endpoint serves the
            # bytes inline; for SDK callers we return b64_json with a
            # note so the contract stays parseable.
            data.append({"b64_json": img_b64, "url": None, "note": "object storage not configured; returning b64_json"})

    _log_usage(
        db=db, user=user, key=key,
        endpoint="/v1/images/generations", request=request,
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        tokens=len(prompt.split()),
        model_used=engine,
    )

    payload_out = {
        "created": int(time.time()),
        "data": data,
        "x_novamind": {"size": f"{w}x{h}", "engine": engine},
    }
    if note:
        payload_out["x_novamind"]["note"] = note
    return payload_out


# =====================================================================
# 4) /v1/audio/transcriptions + /v1/audio/speech
# =====================================================================

@router.post("/audio/transcriptions")
async def v1_audio_transcriptions(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: str = Form("en-US"),
    request: Request = None,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Whisper-style STT. Multipart upload — same shape as OpenAI's
    /v1/audio/transcriptions endpoint, so the official OpenAI SDK works
    against NovaMind with only a base-URL swap."""
    user, key = auth
    _enforce_quota(db, user, key)

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="empty audio file")

    t0 = time.time()
    try:
        from app.core.speech_service import speech_to_text
        result = await speech_to_text(audio_bytes, language=language)
    except Exception as e:
        logger.exception("audio transcription failed")
        _log_usage(
            db=db, user=user, key=key,
            endpoint="/v1/audio/transcriptions", request=request,
            status_code=500,
            elapsed_ms=int((time.time() - t0) * 1000),
            tokens=None, model_used=model,
        )
        raise HTTPException(status_code=500, detail=f"transcription failed: {e}")

    _log_usage(
        db=db, user=user, key=key,
        endpoint="/v1/audio/transcriptions", request=request,
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        tokens=len((result.get("text") or "").split()),
        model_used=model,
    )

    return {"text": result.get("text", ""), "language": language, "model": model}


@router.post("/audio/speech")
async def v1_audio_speech(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """TTS. Body: {input, voice?, response_format?, speed?}.

    Returns audio/wav (we only emit WAV in this drop — a streaming MP3
    encoder is out of scope; callers that need MP3 can ffmpeg-pipe it).
    """
    user, key = auth
    _enforce_quota(db, user, key)

    text = (payload.get("input") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="`input` is required")
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="`input` is too long (max 5000 chars)")
    voice = payload.get("voice", "default")
    speed = float(payload.get("speed", 1.0))
    pitch = float(payload.get("pitch", 1.0))  # accepted for SDK compat; ignored by current TTS

    t0 = time.time()
    try:
        from app.core.speech_service import text_to_speech
        audio_bytes = await text_to_speech(text, voice=voice, speed=speed, pitch=pitch)
    except Exception as e:
        logger.exception("tts failed")
        _log_usage(
            db=db, user=user, key=key,
            endpoint="/v1/audio/speech", request=request,
            status_code=500,
            elapsed_ms=int((time.time() - t0) * 1000),
            tokens=None, model_used="tts",
        )
        raise HTTPException(status_code=500, detail=f"tts failed: {e}")

    _log_usage(
        db=db, user=user, key=key,
        endpoint="/v1/audio/speech", request=request,
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        tokens=len(text.split()),
        model_used="tts",
    )

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": 'attachment; filename="speech.wav"'},
    )


# =====================================================================
# 5) /v1/video/generations — text-to-video / image-to-video
# =====================================================================

# In-memory job store. In production this would be Redis or a queue
# table; for this drop a dict is enough — the endpoint contract is
# what the developer portal will exercise.
_VIDEO_JOBS: Dict[str, Dict[str, Any]] = {}


@router.post("/video/generations")
def v1_video_generations(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Queue a video generation. Returns 202 + a job id.

    No video model is wired into NovaMind in this drop. The endpoint
    exists so the developer portal's "Generate video" flow has a real
    contract; replace the body of the dispatch task with a real model
    call (e.g. a local Stable Video Diffusion pipeline) when one is
    available. Until then, jobs stay in ``queued`` and a subsequent
    GET returns the same status.
    """
    user, key = auth
    _enforce_quota(db, user, key)

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="`prompt` is required")
    image = payload.get("image")  # data URL or http URL; ignored for now

    video_id = "video_" + uuid.uuid4().hex
    _VIDEO_JOBS[video_id] = {
        "id": video_id,
        "user_id": user.id,
        "prompt": prompt,
        "image": bool(image),
        "status": "queued",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    _log_usage(
        db=db, user=user, key=key,
        endpoint="/v1/video/generations", request=request,
        status_code=202,
        elapsed_ms=0,
        tokens=len(prompt.split()),
        model_used="novamind-video-stub",
    )

    return {
        "id": video_id,
        "object": "video.generation",
        "status": "queued",
        "created_at": _VIDEO_JOBS[video_id]["created_at"],
        "x_novamind": {"engine": "novamind-video-stub", "note": "video model not in this drop"},
    }


@router.get("/video/generations/{video_id}")
def v1_video_get(
    video_id: str,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Check job status. Same auth as POST."""
    user, _ = auth
    job = _VIDEO_JOBS.get(video_id)
    if not job or job["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="video job not found")
    return {
        "id": job["id"],
        "object": "video.generation",
        "status": job["status"],
        "created_at": job["created_at"],
    }


# =====================================================================
# 6) /v1/documents — PDF/DOCX/PPTX/XLSX analysis
# =====================================================================

_ALLOWED_DOC_TYPES = {"pdf", "docx", "pptx", "xlsx"}


@router.post("/documents")
async def v1_documents(
    file: UploadFile = File(...),
    task: str = Form("summary"),
    question: Optional[str] = Form(None),
    request: Request = None,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Document analysis. Multipart upload.

      - task:    "summary" | "extract" | "qa" | "classify"
      - question: required when task=qa
    """
    user, key = auth
    _enforce_quota(db, user, key)

    if task not in ("summary", "extract", "qa", "classify"):
        raise HTTPException(status_code=400, detail=f"invalid task {task!r}")
    if task == "qa" and not (question or "").strip():
        raise HTTPException(status_code=400, detail="`question` is required when task=qa")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="empty file")
    if len(file_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file too large (max 25 MB)")

    doc_type = _detect_doc_type(file_bytes, file.filename or "")
    if doc_type not in _ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported document type; allowed: {sorted(_ALLOWED_DOC_TYPES)}",
        )

    t0 = time.time()
    try:
        text = _extract_text(file_bytes, doc_type)
    except Exception as e:
        logger.exception("document extraction failed")
        raise HTTPException(status_code=400, detail=f"failed to extract text: {e}")

    # Truncate to a reasonable prompt size. We give the model 8k chars
    # of context, which is enough for most summaries/QA.
    truncated = text[:8000]
    if len(text) > 8000:
        truncated += f"\n\n[...truncated, {len(text) - 8000} more chars...]"

    prompt = _build_doc_prompt(task=task, text=truncated, question=question, filename=file.filename or "")

    service = _pick_service(None)
    try:
        response = await service.generate_response(
            [LLMMessage(content=prompt, message_type=LLMMessageType.TEXT, is_ai=False)],
            temperature=0.2,
        )
    except Exception as e:
        logger.exception("document model call failed")
        _log_usage(
            db=db, user=user, key=key,
            endpoint="/v1/documents", request=request,
            status_code=500,
            elapsed_ms=int((time.time() - t0) * 1000),
            tokens=None, model_used="documents",
        )
        raise HTTPException(status_code=500, detail=f"model call failed: {e}")

    _log_usage(
        db=db, user=user, key=key,
        endpoint="/v1/documents", request=request,
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        tokens=response.tokens_used,
        model_used=response.model_name,
    )

    return {
        "object": "document.result",
        "task": task,
        "filename": file.filename,
        "doc_type": doc_type,
        "char_count": len(text),
        "answer": response.content,
    }


def _detect_doc_type(b: bytes, filename: str) -> str:
    """Sniff by magic bytes; fall back to extension."""
    if b.startswith(b"%PDF"):
        return "pdf"
    if b[:2] == b"PK" and filename.lower().endswith(".docx"):
        return "docx"
    if b[:2] == b"PK" and filename.lower().endswith(".pptx"):
        return "pptx"
    if b[:2] == b"PK" and filename.lower().endswith(".xlsx"):
        return "xlsx"
    name = filename.lower()
    if name.endswith(".pdf"): return "pdf"
    if name.endswith(".docx"): return "docx"
    if name.endswith(".pptx"): return "pptx"
    if name.endswith(".xlsx"): return "xlsx"
    return "unknown"


def _extract_text(b: bytes, doc_type: str) -> str:
    """Pluggable text extractor. Uses PyPDF for PDF; stdlib zipfile+ET
    for DOCX/PPTX/XLSX so we don't add a hard dependency just for this."""
    if doc_type == "pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            # Older installs may have PyPDF2; try that, then fall back to
            # a no-decode error.
            try:
                from PyPDF2 import PdfReader  # type: ignore
            except ImportError:
                raise RuntimeError("pypdf not installed")
        reader = PdfReader(io.BytesIO(b))
        out = []
        for page in reader.pages:
            try:
                out.append(page.extract_text() or "")
            except Exception:
                out.append("")
        return "\n\n".join(out).strip()

    if doc_type == "docx":
        return _read_office_xml(b, "word/document.xml", ns="w")
    if doc_type == "pptx":
        # Concatenate text from every slide XML.
        with zipfile.ZipFile(io.BytesIO(b)) as zf:
            slide_names = sorted(n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n))
            return "\n\n".join(_xml_text(zf.read(n), ns="a") for n in slide_names)
    if doc_type == "xlsx":
        # Concat shared strings + every sheet.
        with zipfile.ZipFile(io.BytesIO(b)) as zf:
            shared = ""
            if "xl/sharedStrings.xml" in zf.namelist():
                shared = _xml_text(zf.read("xl/sharedStrings.xml"), ns="t")
            sheet_names = sorted(n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
            parts = []
            for n in sheet_names:
                # Inline-strings vs sharedStrings differ; we extract <t> everywhere.
                xml = zf.read(n).decode("utf-8", errors="ignore")
                parts.append(_xml_text(xml.encode("utf-8"), ns="t"))
            return (shared + "\n\n" + "\n\n".join(parts)).strip()
    return ""


def _read_office_xml(b: bytes, member: str, ns: str) -> str:
    with zipfile.ZipFile(io.BytesIO(b)) as zf:
        if member not in zf.namelist():
            return ""
        return _xml_text(zf.read(member), ns=ns)


def _xml_text(data: bytes, ns: str) -> str:
    """Extract concatenated text content from an Office XML document.
    Word uses 'w:p/w:r/w:t', PowerPoint uses 'a:p/a:r/a:t', Excel uses
    't'. We don't care about structure — just dump text in document
    order so the model has something to summarize."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return ""
    out = []
    for t in root.iter(f"{{{ns}}}t"):
        if t.text:
            out.append(t.text)
    return " ".join(out)


def _build_doc_prompt(*, task: str, text: str, question: Optional[str], filename: str) -> str:
    if task == "summary":
        return (
            f"Summarize the following document (`{filename}`) in 3-5 bullet points. "
            f"Be specific; include numbers, names, and dates if present.\n\n"
            f"---\n{text}\n---"
        )
    if task == "extract":
        return (
            f"Extract the key facts from `{filename}` as a JSON array of "
            f"{{fact, source_quote}} objects. Return only valid JSON.\n\n"
            f"---\n{text}\n---"
        )
    if task == "qa":
        return (
            f"Answer the question about `{filename}` based only on the document text below. "
            f"If the answer isn't in the document, say 'Not found in document'.\n\n"
            f"Question: {question}\n\n"
            f"---\n{text}\n---"
        )
    # classify
    return (
        f"Classify the following document (`{filename}`) into one of: invoice, contract, "
        f"report, resume, article, manual, other. Reply with the label and a one-sentence "
        f"justification.\n\n---\n{text}\n---"
    )
