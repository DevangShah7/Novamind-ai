from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from app.api import deps
from app.models.user import User
from app.core.config import settings
import json
import time
import uuid
import base64
import httpx
from urllib.parse import quote
from datetime import datetime

router = APIRouter()

# Pollinations.ai is a free, no-API-key image generation service.
# It supports FLUX and SDXL models. We proxy through the backend so
# (a) the model choice / URL format isn't leaked to the browser,
# (b) we can apply the user's style preference and width/height, and
# (c) we don't burn Pollinations' rate-limit budget on every page load
# just because the browser prefetched a route.
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

# Default model. Pollinations also supports "turbo", "sana", "klein",
# etc., but flux is the best free quality / speed tradeoff right now.
POLLINATIONS_DEFAULT_MODEL = "flux"

# How long to wait for Pollinations to render an image. FLUX is the
# slowest case — typically 5–30 s on a free GPU; SDXL/SANA is faster.
# 45 s gives a clean margin before we surface a 502 to the client.
POLLINATIONS_TIMEOUT_S = 45.0


def _pollinations_model_for_style(style: Optional[str]) -> str:
    """Map our coarse `style` knob onto a Pollinations model id.

    Pollinations doesn't expose style presets, but different models
    have different aesthetic biases. Default to flux for "realistic"
    and "artistic"; use the SDXL model when the user explicitly asks
    for cartoon/anime — those prompts do better with SDXL.
    """
    if style in ("cartoon", "anime", "illustration"):
        return "sana"  # SDXL-flavored model on Pollinations
    return POLLINATIONS_DEFAULT_MODEL


def generate_image_payload(
    prompt: str,
    style: Optional[str] = None,
    width: int = 512,
    height: int = 512,
    seed: Optional[int] = None,
) -> Tuple[str, bytes, str, Dict[str, Any]]:
    """Call Pollinations and return (image_id, raw_bytes, format, meta).

    One round trip upstream. `format` is "jpeg" or "png" derived from
    the upstream Content-Type, so the browser renders the correct MIME
    type when we build a `data:` URL on the frontend.

    Raises HTTP 502 on any upstream failure — the HTTPException is the
    public contract; callers (the standalone /image/generate endpoint
    and the chat /messages image branch) just let it propagate.
    """
    model = _pollinations_model_for_style(style)
    encoded_prompt = quote(prompt, safe="")
    # Pollinations accepts a /prompt/<text>?width=&height=&model=&seed=&nologo=true
    # query. `nologo=true` strips their watermark. `seed` makes repeat calls
    # deterministic so users can iterate.
    qs_parts = [
        f"width={width}",
        f"height={height}",
        f"model={model}",
        "nologo=true",
        "enhance=false",
    ]
    if seed is not None:
        qs_parts.append(f"seed={seed}")
    upstream_url = f"{POLLINATIONS_BASE}/{encoded_prompt}?{'&'.join(qs_parts)}"

    try:
        upstream = httpx.get(
            upstream_url, timeout=POLLINATIONS_TIMEOUT_S, follow_redirects=True
        )
        upstream.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Image generation upstream failed: {exc}",
        ) from exc

    image_bytes = upstream.content
    if not image_bytes:
        raise HTTPException(
            status_code=502,
            detail="Image generation upstream returned an empty body",
        )

    upstream_ct = upstream.headers.get("content-type", "image/jpeg")
    image_format = "jpeg" if "jpeg" in upstream_ct or "jpg" in upstream_ct else "png"

    image_id = str(uuid.uuid4())
    meta = {
        "generation_model": f"pollinations/{model}",
        "generation_time": time.time(),
        "seed": seed,
        "width": width,
        "height": height,
        "style": style,
        "bytes": len(image_bytes),
        "format": image_format,
    }
    return image_id, image_bytes, image_format, meta


class ImageGenerationRequest(BaseModel):
    prompt: str
    style: Optional[str] = None  # realistic, artistic, cartoon, etc.
    width: int = 512
    height: int = 512
    quality: str = "standard"  # standard, hd
    seed: Optional[int] = Field(default=None, description="Optional deterministic seed")

class ImageGenerationResponse(BaseModel):
    image_id: str
    prompt: str
    image_url: Optional[str] = None
    image_base64: Optional[str] = None  # For direct embedding
    image_format: str = "jpeg"  # "jpeg" or "png" — tells the browser the data: URL MIME type
    meta_data: Dict[str, Any]
    created_at: datetime

class ImageEditRequest(BaseModel):
    image_id: str
    prompt: str  # Description of edits to make
    mask_prompt: Optional[str] = None  # For inpainting

# In-memory store for generated images (in production, use database/object storage)
generated_images = {}

@router.post("/generate", response_model=ImageGenerationResponse)
def generate_image(
    image_req: ImageGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Generate an image from text prompt"""
    image_id, image_bytes, image_format, meta = generate_image_payload(
        prompt=image_req.prompt,
        style=image_req.style,
        width=image_req.width,
        height=image_req.height,
        seed=image_req.seed,
    )

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    # Track this image in the in-memory store so /image/{id} can look it up.
    # The /image/{id} GET is used by the chat composer to re-render
    # historical generations without re-fetching from Pollinations.
    image_data = {
        "id": image_id,
        "user_id": current_user.id,
        "prompt": image_req.prompt,
        "style": image_req.style,
        "width": image_req.width,
        "height": image_req.height,
        "quality": image_req.quality,
        "format": image_format,
        "bytes": len(image_bytes),
        "created_at": datetime.utcnow(),
        "meta_data": {**meta, "user_id": current_user.id},
    }
    generated_images[image_id] = image_data

    # Log generation for analytics
    background_tasks.add_task(log_image_generation, db, current_user.id, image_req.prompt)

    return ImageGenerationResponse(
        image_id=image_id,
        prompt=image_req.prompt,
        image_base64=image_b64,
        image_format=image_format,
        meta_data=image_data["meta_data"],
        created_at=image_data["created_at"],
    )

@router.post("/edit")
def edit_image(
    edit_req: ImageEditRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Edit an existing image"""
    if edit_req.image_id not in generated_images:
        raise HTTPException(status_code=404, detail="Image not found")

    image_data = generated_images[edit_req.image_id]
    if image_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # In production, this would use image editing models
    return {
        "message": "Image editing initiated",
        "image_id": edit_req.image_id,
        "edit_prompt": edit_req.prompt,
        "status": "processing"
    }

@router.get("/{image_id}")
def get_image(
    image_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get image metadata"""
    if image_id not in generated_images:
        raise HTTPException(status_code=404, detail="Image not found")

    image_data = generated_images[image_id]
    if image_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": image_data["id"],
        "prompt": image_data["prompt"],
        "style": image_data["style"],
        "width": image_data["width"],
        "height": image_data["height"],
        "created_at": image_data["created_at"],
        "meta_data": image_data["meta_data"]
    }

def log_image_generation(db: Session, user_id: int, prompt: str):
    """Log image generation for analytics"""
    print(f"Image generation logged: user={user_id}, prompt='{prompt}'")