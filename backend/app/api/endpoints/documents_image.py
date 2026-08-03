"""
Image generator endpoint for NovaMind AI.

`POST /documents/image` — render a prompt as an image. Tries GPU
Stable-Diffusion-XL first (real 1024x1024 PNG, ~10s on an RTX 5060).
Falls back to the deterministic SVG poster when torch/diffusers
can't load (WDAC / Smart App Control block, missing CUDA, no
cached model). The endpoint never breaks.

Why a separate module:
* `documents.py` is already near the 500-line cap with PDF + PPTX;
  pulling image gen out keeps that file lean.
* The SDXL path needs diffusers / torch (~2 GB on disk) and pulls
  `shm.dll`, which OS-level security policies (SAC on this host)
  may block. Keeping it lazy and isolated means the SVG fallback
  keeps working even if the GPU path can't initialize.

Mounted in `app/api/v1.py` under the same `/documents` prefix as
`documents.py`, so the URL is unchanged: `POST /documents/image`.
"""
import asyncio
import hashlib
import io
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api import deps
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class ImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    title: Optional[str] = None
    style: Optional[str] = None  # e.g. "modern", "playful"


# ─────────────────────────────────────────────────────────────────────────
# SDXL pipeline — warmed in a background task at startup so the first
# user request never pays the ~10s torch + diffusers import cost.
#
# The diffusers import alone takes ~10s on a warm Python interpreter,
# which the browser sees as ERR_FAILED on the very first image request.
# Doing the load in lifespan avoids that — by the time any user hits
# /documents/image, the pipe is either loaded (GPU path) or the load
# error is recorded (SVG fallback, no retry storm).
# ─────────────────────────────────────────────────────────────────────────
_SDXL_PIPE = None
_SDXL_LOAD_ERROR: Optional[str] = None


def warm_sdxl_pipeline() -> None:
    """Load the SDXL pipeline at startup, in a worker thread.

    Safe to call multiple times — once a load succeeds or fails, the
    result is cached and subsequent calls are no-ops.
    """
    global _SDXL_PIPE, _SDXL_LOAD_ERROR
    if _SDXL_PIPE is not None or _SDXL_LOAD_ERROR is not None:
        return
    try:
        import torch
        if not torch.cuda.is_available():
            _SDXL_LOAD_ERROR = "cuda unavailable"
            logger.info("sdxl: cuda unavailable, will fall back to svg")
            return
        from diffusers import StableDiffusionXLPipeline
        model_id = "stabilityai/stable-diffusion-xl-base-1.0"
        logger.info("sdxl: loading %s on cuda", model_id)
        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
        )
        pipe = pipe.to("cuda")
        pipe.enable_attention_slicing()
        try:
            pipe.enable_xformers_memory_efficient_attention()
        except Exception:
            pass  # xformers optional on Blackwell
        _SDXL_PIPE = pipe
        logger.info("sdxl: ready")
    except Exception as e:
        _SDXL_LOAD_ERROR = f"{type(e).__name__}: {e}"
        logger.warning("sdxl: load failed (%s); will fall back to svg", e)


def _try_load_sdxl():
    """Return the warmed SDXL pipeline if available, else None.

    The pipeline is loaded at startup via ``warm_sdxl_pipeline`` so
    this is just a cache lookup in steady state. Kept as a fallback
    so a worker that never went through lifespan (e.g. tests) can
    still trigger a load.
    """
    global _SDXL_PIPE, _SDXL_LOAD_ERROR
    if _SDXL_PIPE is not None or _SDXL_LOAD_ERROR is not None:
        return _SDXL_PIPE
    warm_sdxl_pipeline()
    return _SDXL_PIPE


@router.post("/image")
async def generate_image(
    req: ImageRequest,
    current_user: User = Depends(deps.get_current_active_user),
):
    """Render a prompt as an image.

    Tries GPU SDXL first (real 1024×1024 PNG, ~10s on RTX 5060).
    Falls back to the deterministic SVG poster when diffusers/torch
    can't load (OS policy block, missing CUDA, no model cache).
    """
    pipe = _try_load_sdxl()
    if pipe is not None:
        try:
            import torch
            style_hint = f", {req.style} style" if req.style else ""
            prompt = f"{req.prompt}{style_hint}"
            generator = torch.Generator(device="cuda").manual_seed(
                int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
            )

            def _infer():
                return pipe(
                    prompt=prompt,
                    num_inference_steps=25,
                    guidance_scale=7.5,
                    height=1024,
                    width=1024,
                    generator=generator,
                )
            # Run inference in a worker thread so we don't block the event loop
            result = await asyncio.to_thread(_infer)
            image = result.images[0]
            buf = io.BytesIO()
            image.save(buf, format="PNG", optimize=True)
            return Response(
                content=buf.getvalue(),
                media_type="image/png",
                headers={
                    "Content-Disposition": 'inline; filename="novamind-image.png"',
                    "Cache-Control": "public, max-age=3600",
                    "X-Generator": "sdxl-base-1.0",
                },
            )
        except Exception as e:
            logger.warning("sdxl inference failed, falling back to svg: %s", e)

    # Fallback: deterministic SVG poster
    svg = _build_svg_poster(req.prompt, style=req.style or "")
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": 'inline; filename="novamind-image.svg"',
            "Cache-Control": "public, max-age=3600",
            "X-Generator": "svg-poster",
        },
    )


# ─────────────────────────────────────────────────────────────────────────
# SVG poster fallback (deterministic, prompt-driven)
# ─────────────────────────────────────────────────────────────────────────
def _derive_title(prompt: str) -> str:
    """Pull the first short, title-like phrase from the prompt."""
    first_line = (prompt.strip().splitlines() or [prompt])[0].strip()
    first_line = re.sub(r"^#+\s*", "", first_line)
    first_line = re.sub(r"[*_`]+", "", first_line)
    if len(first_line) > 80:
        first_line = first_line[:77].rsplit(" ", 1)[0] + "…"
    return first_line or "NovaMind Image"


def _build_svg_poster(prompt: str, style: str = "") -> str:
    """Generate a 1024x1024 SVG poster driven by hashing the prompt."""
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    rng_state = [seed]

    def rand() -> float:
        # LCG — not cryptographic, just for visual variety.
        rng_state[0] = (rng_state[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return rng_state[0] / 0x7FFFFFFF

    # Two hues derived from the prompt hash — same prompt → same palette.
    hue_a = seed % 360
    hue_b = (seed * 7 + 137) % 360
    c_a = _hsl_to_hex(hue_a, 70, 55)
    c_b = _hsl_to_hex(hue_b, 65, 45)
    c_accent = _hsl_to_hex((hue_a + 60) % 360, 80, 60)

    title = _derive_title(prompt)
    title_svg = (
        title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    lines = _wrap_text(title_svg, width=16)
    title_block = "\n".join(
        f'    <text x="512" y="{420 + i*68}" text-anchor="middle" '
        f'font-family="Inter, system-ui, sans-serif" font-size="58" '
        f'font-weight="700" fill="#0F172A">{ln}</text>'
        for i, ln in enumerate(lines[:3])
    )
    subtitle_svg = "Generated by NovaMind AI".replace("&", "&amp;")

    shapes = []
    for _ in range(14):
        cx = rand() * 1024
        cy = rand() * 1024
        r = 24 + rand() * 90
        opacity = 0.05 + rand() * 0.18
        if rand() < 0.5:
            shapes.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                f'fill="white" opacity="{opacity:.2f}" />'
            )
        else:
            rot = rand() * 360
            shapes.append(
                f'<rect x="{cx-r:.1f}" y="{cy-r:.1f}" width="{r*2:.1f}" '
                f'height="{r*2:.1f}" fill="white" opacity="{opacity:.2f}" '
                f'transform="rotate({rot:.1f} {cx:.1f} {cy:.1f})" />'
            )

    shapes_str = "\n    ".join(shapes)

    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" '
        f'width="1024" height="1024">\n'
        f'  <defs>\n'
        f'    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">\n'
        f'      <stop offset="0%" stop-color="{c_a}" />\n'
        f'      <stop offset="100%" stop-color="{c_b}" />\n'
        f'    </linearGradient>\n'
        f'    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">\n'
        f'      <feGaussianBlur stdDeviation="22" />\n'
        f'    </filter>\n'
        f'  </defs>\n'
        f'  <rect width="1024" height="1024" fill="url(#bg)" />\n'
        f'  {shapes_str}\n'
        f'  <circle cx="180" cy="200" r="260" fill="{c_accent}" opacity="0.35" filter="url(#soft)" />\n'
        f'  <circle cx="880" cy="860" r="240" fill="white" opacity="0.25" filter="url(#soft)" />\n'
        f'  <rect x="80" y="80" width="864" height="864" rx="36" ry="36" '
        f'fill="white" opacity="0.92" />\n'
        f'  <rect x="80" y="80" width="864" height="6" fill="{c_accent}" />\n'
        f'  <text x="120" y="180" font-family="Inter, system-ui, sans-serif" '
        f'font-size="22" font-weight="600" fill="{c_accent}" letter-spacing="2">'
        f'N O V A M I N D</text>\n'
        f'  {title_block}\n'
        f'  <line x1="380" y1="700" x2="644" y2="700" stroke="{c_accent}" '
        f'stroke-width="3" />\n'
        f'  <text x="512" y="760" text-anchor="middle" '
        f'font-family="Inter, system-ui, sans-serif" font-size="22" '
        f'font-weight="500" fill="#475569">{subtitle_svg}</text>\n'
        f'  <text x="512" y="900" text-anchor="middle" '
        f'font-family="Inter, system-ui, sans-serif" font-size="16" '
        f'fill="#94A3B8">Style: {(style or "default").title()}</text>\n'
        f'</svg>\n'
    )


def _wrap_text(text: str, width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _hsl_to_hex(h: int, s: int, l: int) -> str:
    """h, s, l are 0-360 / 0-100 / 0-100."""
    s /= 100.0
    l /= 100.0
    c = (1 - abs(2 * l - 1)) * s
    hp = h / 60.0
    x = c * (1 - abs(hp % 2 - 1))
    if 0 <= hp < 1:   r, g, b = c, x, 0
    elif hp < 2:       r, g, b = x, c, 0
    elif hp < 3:       r, g, b = 0, c, x
    elif hp < 4:       r, g, b = 0, x, c
    elif hp < 5:       r, g, b = x, 0, c
    else:              r, g, b = c, 0, x
    m = l - c / 2
    return "#{:02X}{:02X}{:02X}".format(
        int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    )