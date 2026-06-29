"""
OpenAI-compatible v1 surface — `/v1/models`, `/v1/chat/completions`,
`/v1/embeddings`, `/v1/usage`, `/v1/billing`.

Authenticated via ``Authorization: Bearer nm_...`` against the existing
``api_keys`` table. Same engine (Ollama when reachable, NovaMindLocal
otherwise) as the in-app chat, so the developer surface is not a parallel
universe.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api import deps
from app.core.llm_service import LLMMessage, LLMMessageType
from app.core.ollama_service import (
    OllamaChatService,
    ollama_list_models,
    ollama_reachable,
    select_default_ollama_model,
)
from app.crud import api_key as api_key_crud
from app.crud import api_usage as api_usage_crud
from app.models import ApiKey, ApiUsage, User
from app.schemas.api_key import ModelInfo, ModelListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Auth ----------

def _bearer_or_x_api_key(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Optional[str]:
    """Accept either Authorization: Bearer nm_... or X-API-Key: nm_..."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if x_api_key:
        return x_api_key.strip()
    return None


def get_user_from_api_key(
    db: Session = Depends(deps.get_db),
    key: Optional[str] = Depends(_bearer_or_x_api_key),
    request: Request = None,
) -> tuple[User, ApiKey]:
    """Resolve a (User, ApiKey) pair from the bearer secret.

    Raises 401 for missing/unknown keys and 403 for keys that exist but
    are disabled / expired / not allowed from the caller's IP. We return
    the tuple rather than just the user so endpoints can log usage
    against the specific key.
    """
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Pass it as `Authorization: Bearer nm_...`.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    obj = api_key_crud.get_api_key_by_key(db, key)
    if not obj:
        raise HTTPException(status_code=401, detail="Invalid API key")

    client_ip = None
    if request is not None and request.client:
        client_ip = request.client.host
        # Honour X-Forwarded-For if a proxy is in front of us.
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            client_ip = fwd.split(",")[0].strip()

    if not api_key_crud.is_api_key_callable(obj, client_ip=client_ip):
        raise HTTPException(
            status_code=403,
            detail=(
                "API key is disabled, expired, or not allowed from this IP."
            ),
        )

    return obj.user, obj


# ---------- /v1/models ----------

_LOCAL_MODEL_IDS = ["NovaMind-local-v1"]


@router.get("/models", response_model=ModelListResponse)
def list_models(_: tuple = Depends(get_user_from_api_key)):
    """List models available to the caller.

    Always includes ``NovaMind-local-v1`` (the in-process rule engine,
    always available). Adds any Ollama models if Ollama is reachable.
    """
    data: List[ModelInfo] = [
        ModelInfo(id="NovaMind-local-v1", source="local"),
    ]
    if ollama_reachable():
        for m in ollama_list_models():
            data.append(ModelInfo(id=m["id"], source="ollama", created=m.get("created")))
    return ModelListResponse(data=data)


# ---------- /v1/chat/completions ----------

def _to_llm_messages(messages: List[Dict[str, Any]]) -> List[LLMMessage]:
    out: List[LLMMessage] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content") or ""
        if not content:
            continue
        out.append(
            LLMMessage(
                content=content if isinstance(content, str) else json.dumps(content),
                message_type=LLMMessageType.TEXT,
                is_ai=(role == "assistant"),
            )
        )
    return out


def _pick_service(model: Optional[str]):
    """Pick the right engine for the requested model name."""
    if not model or model == "NovaMind-local-v1":
        from app.core.local_engine import NovaMindLocal
        return NovaMindLocal()
    # Anything else: route through Ollama if reachable, else local.
    if ollama_reachable():
        return OllamaChatService(model_name=model)
    from app.core.local_engine import NovaMindLocal
    return NovaMindLocal()


@router.post("/chat/completions")
async def chat_completions(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """OpenAI-compatible chat completions.

    Supports both the standard (non-streaming) response and
    ``stream=true`` (SSE in the same ``data: [DONE]`` shape OpenAI uses).
    """
    user, key = auth
    model = payload.get("model")
    messages = payload.get("messages") or []
    if not messages:
        raise HTTPException(status_code=400, detail="`messages` must be a non-empty array")
    temperature = float(payload.get("temperature", 0.7))
    max_tokens = payload.get("max_tokens")
    stream = bool(payload.get("stream", False))

    llm_messages = _to_llm_messages(messages)
    service = _pick_service(model)

    t0 = time.time()
    if stream:
        async def event_source() -> AsyncGenerator[bytes, None]:
            completion_id = "chatcmpl-" + uuid.uuid4().hex
            created = int(time.time())
            emitted_any = False
            try:
                gen = service.generate_response_stream(
                    llm_messages, temperature=temperature, max_tokens=max_tokens
                )
                async for chunk in gen:
                    emitted_any = True
                    delta = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": getattr(service, "model_name", model or "unknown"),
                        "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(delta)}\n\n".encode("utf-8")
                tail = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": getattr(service, "model_name", model or "unknown"),
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(tail)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
            except Exception as e:
                logger.exception("streaming chat completion failed")
                err = {
                    "error": {"message": str(e), "type": "server_error", "code": "stream_failed"}
                }
                yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
            finally:
                # Log the request as one row, regardless of chunks emitted.
                _log_usage(
                    db=db,
                    user=user,
                    key=key,
                    endpoint="/v1/chat/completions",
                    request=request,
                    status_code=200,
                    elapsed_ms=int((time.time() - t0) * 1000),
                    tokens=None,
                    model_used=getattr(service, "model_name", model or "unknown"),
                )

        return StreamingResponse(event_source(), media_type="text/event-stream")

    # Non-streaming branch
    try:
        response = await service.generate_response(
            llm_messages, temperature=temperature, max_tokens=max_tokens
        )
    except Exception as e:
        logger.exception("chat completion failed")
        _log_usage(
            db=db,
            user=user,
            key=key,
            endpoint="/v1/chat/completions",
            request=request,
            status_code=500,
            elapsed_ms=int((time.time() - t0) * 1000),
            tokens=None,
            model_used=model or "unknown",
        )
        raise HTTPException(status_code=500, detail=f"model call failed: {e}")

    _log_usage(
        db=db,
        user=user,
        key=key,
        endpoint="/v1/chat/completions",
        request=request,
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        tokens=response.tokens_used,
        model_used=response.model_name,
    )

    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": response.model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response.content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": None,
            "completion_tokens": response.tokens_used,
            "total_tokens": response.tokens_used,
        },
        "x_novamind": {
            "engine": response.metadata.get("engine"),
            "handler": response.metadata.get("handler"),
        },
    }


# ---------- /v1/embeddings ----------

@router.post("/embeddings")
def embeddings(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Trivial deterministic embedding — same input always returns the same vector.

    We're not shipping a real embedding model in this drop; this endpoint
    exists so the developer portal can exercise the contract end-to-end.
    Replace the body with a sentence-transformers / Ollama / OpenAI call
    when a real model is wired in.
    """
    user, key = auth
    t0 = time.time()
    raw = payload.get("input")
    if raw is None:
        raise HTTPException(status_code=400, detail="`input` is required")
    inputs = raw if isinstance(raw, list) else [raw]
    out = []
    for idx, text in enumerate(inputs):
        # Deterministic 16-dim vector from SHA1 — stable, tiny, never all-zero.
        import hashlib
        h = hashlib.sha1((text or "").encode("utf-8")).digest()
        vec = [(b - 128) / 128.0 for b in h[:16]]
        out.append({"object": "embedding", "index": idx, "embedding": vec})

    _log_usage(
        db=db,
        user=user,
        key=key,
        endpoint="/v1/embeddings",
        request=request,
        status_code=200,
        elapsed_ms=int((time.time() - t0) * 1000),
        tokens=sum(len((t or "").split()) for t in inputs),
        model_used="novamind-embedding-stub",
    )

    return {
        "object": "list",
        "data": out,
        "model": "novamind-embedding-stub",
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


# ---------- /v1/usage ----------

@router.get("/usage")
def v1_usage(
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
    days: int = 30,
):
    """Per-day rollup of the calling user's API usage."""
    user, _ = auth
    days = max(1, min(days, 365))
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(
            func.date(ApiUsage.created_at).label("day"),
            func.count(ApiUsage.id).label("requests"),
            func.coalesce(func.sum(ApiUsage.tokens_used), 0).label("tokens"),
            func.count(ApiUsage.status_code >= 400).label("errors"),
        )
        .filter(ApiUsage.user_id == user.id, ApiUsage.created_at >= since)
        .group_by(func.date(ApiUsage.created_at))
        .order_by(func.date(ApiUsage.created_at))
        .all()
    )

    daily = [
        {
            "date": str(r.day),
            "requests": int(r.requests),
            "tokens": int(r.tokens or 0),
            "errors": int(r.errors or 0),
        }
        for r in rows
    ]

    totals = (
        db.query(
            func.count(ApiUsage.id),
            func.coalesce(func.sum(ApiUsage.tokens_used), 0),
            func.avg(ApiUsage.response_time_ms),
        )
        .filter(ApiUsage.user_id == user.id, ApiUsage.created_at >= since)
        .one()
    )

    return {
        "object": "usage.summary",
        "window_days": days,
        "totals": {
            "requests": int(totals[0] or 0),
            "tokens": int(totals[1] or 0),
            "average_response_time_ms": round(float(totals[2] or 0), 2),
        },
        "daily": daily,
    }


# ---------- /v1/billing ----------

@router.get("/billing")
def v1_billing(
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Billing snapshot. Read-only — no charges are issued in this drop."""
    user, _ = auth
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(
            ApiUsage.model_used,
            func.count(ApiUsage.id).label("requests"),
            func.coalesce(func.sum(ApiUsage.tokens_used), 0).label("tokens"),
        )
        .filter(ApiUsage.user_id == user.id, ApiUsage.created_at >= month_start)
        .group_by(ApiUsage.model_used)
        .all()
    )

    by_model = [
        {
            "model": r.model_used or "unknown",
            "requests": int(r.requests),
            "tokens": int(r.tokens or 0),
        }
        for r in rows
    ]

    return {
        "object": "billing.summary",
        "period_start": month_start.isoformat() + "Z",
        "currency": "USD",
        "balance_usd": 0.0,            # wallet / credits — placeholder
        "month_to_date_spend_usd": 0.0,  # payment gateway not wired in this drop
        "by_model": by_model,
        "note": "Billing endpoints are read-only in this drop; payment gateway integration is a follow-up.",
    }


@router.get("/billing/invoices")
def v1_invoices(
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Invoices placeholder — empty list until the payment gateway is wired up."""
    return {"object": "list", "data": []}


# ---------- helpers ----------

def _log_usage(
    *,
    db: Session,
    user: User,
    key: ApiKey,
    endpoint: str,
    request: Request,
    status_code: int,
    elapsed_ms: int,
    tokens: Optional[int],
    model_used: Optional[str],
) -> None:
    ip = None
    if request.client:
        ip = request.client.host
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            ip = fwd.split(",")[0].strip()
    api_usage_crud.create_api_usage(
        db,
        endpoint=endpoint,
        method=request.method if request else "POST",
        status_code=status_code,
        ip_address=ip,
        user_agent=request.headers.get("user-agent") if request else None,
        response_time_ms=float(elapsed_ms),
        tokens_used=int(tokens) if tokens else None,
        model_used=model_used,
        user_id=user.id,
        api_key_id=key.id,
    )
    # Refresh the per-key monthly counter used by the portal.
    if tokens:
        key.monthly_token_count = (key.monthly_token_count or 0) + int(tokens)
    db.add(key)
    db.commit()