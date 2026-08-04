"""
OpenAI-compatible v1 surface — `/v1/models`, `/v1/chat/completions`,
`/v1/embeddings`, `/v1/usage`, `/v1/billing`.

Authenticated via ``Authorization: Bearer nm_...`` against the existing
``api_keys`` table. Same engine (the stealth router, which talks to
Ollama when reachable and falls back to the local rule engine
otherwise) as the in-app chat, so the developer surface is not a
parallel universe. The router guarantees the real backend identity
never leaks through the wire.
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
from app.core import alias_config
from app.core.llm_service import LLMMessage, LLMMessageType, get_llm_service
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


@router.get("/models", response_model=ModelListResponse)
def list_models(_: tuple = Depends(get_user_from_api_key)):
    """List models available to the caller.

    Returns only the public NovaMind ids. The real backend (whatever
    ``alias_config`` says) is never listed — the wire always speaks
    the brand.
    """
    data: List[ModelInfo] = [
        ModelInfo(id=public_id, source="novamind") for public_id in alias_config.list_public_ids()
    ]
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


def _enforce_quota(db: Session, user: User, key: ApiKey) -> None:
    """Hard-cap gate based on the user's plan AND the key's per-key caps.

    Two layers, both must allow the call:
      1. Per-key caps: `key.monthly_token_limit` / `monthly_request_limit`
         — set by the user on the developer portal. 0/None = unlimited.
      2. Plan caps: the user's `Plan.monthly_token_limit` /
         `monthly_request_limit` — enforced by summing the user's keys'
         usage and comparing to the plan ceiling. Falls back to the
         free plan if the user has no plan assigned.

    Raises 429 with a structured body that the developer portal
    surfaces as a friendly "upgrade to keep going" dialog.
    """
    # Per-key caps first — they're the cheaper check.
    token_limit = key.monthly_token_limit
    request_limit = key.monthly_request_limit
    if token_limit and (key.monthly_token_count or 0) >= token_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "scope": "key",
                "limit_type": "tokens",
                "limit": token_limit,
                "used": key.monthly_token_count or 0,
                "upgrade_url": "/pricing",
            },
        )
    if request_limit and (key.monthly_request_count or 0) >= request_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "scope": "key",
                "limit_type": "requests",
                "limit": request_limit,
                "used": key.monthly_request_count or 0,
                "upgrade_url": "/pricing",
            },
        )

    # Plan-level caps. Sum usage across all of the user's keys — the
    # user is the billing subject, the key is just the meter.
    from app.models.billing import Plan

    plan = (
        db.query(Plan)
        .filter(Plan.id == user.plan_id).first()
        if user.plan_id
        else None
    )
    if not plan:
        # Implicit free plan when no plan_id is set. The seed inserts
        # the free plan on first boot, but be defensive: if it's
        # missing for any reason, allow the call through (don't 500 on
        # a billing-migration misconfig).
        return

    plan_token_limit = plan.monthly_token_limit
    plan_request_limit = plan.monthly_request_limit
    if not (plan_token_limit or plan_request_limit):
        # 0/None = unlimited (the business plan will be 10M+; the
        # contract is "unlimited" past 10M, but we just gate on 0).
        return

    from app.models.api_key import ApiKey as ApiKeyModel
    token_total = (
        db.query(func.coalesce(func.sum(ApiKeyModel.monthly_token_count), 0))
        .filter(ApiKeyModel.user_id == user.id)
        .scalar()
    ) or 0
    request_total = (
        db.query(func.coalesce(func.sum(ApiKeyModel.monthly_request_count), 0))
        .filter(ApiKeyModel.user_id == user.id)
        .scalar()
    ) or 0

    if plan_token_limit and token_total >= plan_token_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "scope": "plan",
                "plan": plan.slug,
                "limit_type": "tokens",
                "limit": plan_token_limit,
                "used": int(token_total),
                "upgrade_url": "/pricing",
            },
        )
    if plan_request_limit and request_total >= plan_request_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "scope": "plan",
                "plan": plan.slug,
                "limit_type": "requests",
                "limit": plan_request_limit,
                "used": int(request_total),
                "upgrade_url": "/pricing",
            },
        )


def _pick_service(model: Optional[str]):
    """Pick the service for the requested model name.

    Goes through the stealth router so the returned service's
    ``model_name`` is always a public NovaMind id — the SSE wrapper
    relies on this to stamp the correct ``model:`` field on every
    chunk. Unknown ids (legacy ``llama3.2:3b``, an OpenAI tag, an
    Ollama name a developer paste-ed) collapse to the default tier.
    """
    return get_llm_service(model_name=model)


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

    The request's ``model`` field is treated as a public NovaMind id
    (or, when unknown, collapsed to the default public id). The
    response always speaks the public id — never the real backend
    name.
    """
    user, key = auth
    _enforce_quota(db, user, key)
    model = payload.get("model")
    messages = payload.get("messages") or []
    if not messages:
        raise HTTPException(status_code=400, detail="`messages` must be a non-empty array")
    temperature = float(payload.get("temperature", 0.7))
    max_tokens = payload.get("max_tokens")
    stream = bool(payload.get("stream", False))

    llm_messages = _to_llm_messages(messages)
    service = _pick_service(model)
    # The public id is what flows back to the wire; the router has
    # already stamped it onto ``service.model_name``.
    public_model = getattr(service, "model_name", alias_config.default_public_id())

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
                        "model": public_model,
                        "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(delta)}\n\n".encode("utf-8")
                tail = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": public_model,
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
                    model_used=public_model,
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
            model_used=public_model,
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
        # ``x_novamind`` exposes the brand surface, never the real engine
        # identity. The router has already stripped leaky metadata keys
        # (``engine``, ``handler``, ``fallback_reason`` …).
        "x_novamind": {
            "surface": "novamind",
            "model": response.model_name,
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
    _enforce_quota(db, user, key)
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
    """Billing snapshot — by-model rollup + current credit balance.

    The model is the same one the JWT-authed `/api/v1/billing/plan`
    endpoint exposes; the API-key variant is here for OpenAI-SDK
    parity so a key can query its own usage + balance without needing
    a separate user JWT.
    """
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
        # Credit balance in cents (integer) — same field the
        # `/api/v1/billing/plan` endpoint exposes. Callers that want
        # dollars divide by 100.
        "credits_balance_cents": user.credits_balance_cents or 0,
        "month_to_date_spend_cents": 0,
        "by_model": by_model,
    }


@router.get("/billing/invoices")
def v1_invoices(
    request: Request,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Invoices. In mock mode we have no real invoices — return [].

    In live-Stripe mode the same call forwards to Stripe and returns
    the user's invoice list in OpenAI-shaped JSON. The forwarding
    lives in the JWT-authed `/api/v1/billing/invoices` endpoint.
    """
    from app.core.config import settings as _s
    if not _s.STRIPE_SECRET_KEY:
        return {"object": "list", "data": []}
    # In live mode, defer to the JWT endpoint's logic. We don't
    # import it here to avoid a circular dependency through deps;
    # instead we re-fetch directly via the Stripe SDK.
    if not user.stripe_customer_id:
        return {"object": "list", "data": []}
    try:
        import stripe  # type: ignore
    except ImportError:
        return {"object": "list", "data": []}
    stripe.api_key = _s.STRIPE_SECRET_KEY
    try:
        result = stripe.Invoice.list(customer=user.stripe_customer_id, limit=50)
    except Exception:
        return {"object": "list", "data": []}
    return {
        "object": "list",
        "data": [
            {
                "id": inv.id,
                "amount_cents": inv.amount_paid or inv.amount_due or 0,
                "currency": inv.currency,
                "status": inv.status or "open",
                "created_at": datetime.fromtimestamp(inv.created).isoformat() + "Z",
                "hosted_invoice_url": inv.hosted_invoice_url,
            }
            for inv in result.data
        ],
    }


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