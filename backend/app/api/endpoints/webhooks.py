"""
/v1/webhooks — developer-portal webhook management.

CRUD over the user's webhooks plus a /ping endpoint that fires a test
event. The webhook signing secret is returned only on create; subsequent
GETs return a fingerprint instead so the secret never leaks via list view.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app.api import deps
from app.api.endpoints.v1_compat import (
    _log_usage,
    get_user_from_api_key,
)
from app.crud import webhook as webhook_crud
from app.models import User

router = APIRouter()


# ---------- Pydantic schemas ----------

class WebhookCreate(BaseModel):
    url: HttpUrl
    events: Optional[List[str]] = Field(
        None, example=["api.request.completed", "billing.invoice.paid"],
        description="Event names to subscribe to. Empty/None = all events.",
    )
    description: Optional[str] = None


class WebhookUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class WebhookOut(BaseModel):
    id: int
    url: str
    events: Optional[List[str]] = None
    is_active: bool
    description: Optional[str] = None
    created_at: datetime
    # SHA-256 fingerprint of the secret, so the portal can display "key
    # starts with whsec_xxxx" without ever exposing the full secret.
    secret_fingerprint: str
    # Only present on the create response.
    secret: Optional[str] = None

    class Config:
        orm_mode = True


class WebhookDeliveryOut(BaseModel):
    id: int
    event_type: str
    attempt: int
    status: str
    http_status: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ---------- helpers ----------

def _fingerprint(secret: str) -> str:
    """First 8 chars of SHA-256, hex. Stable, non-reversible, enough
    to tell two webhooks apart on the portal UI."""
    import hashlib
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def _to_out(w, *, include_secret: bool = False) -> Dict[str, Any]:
    return {
        "id": w.id,
        "url": w.url,
        "events": w.events or [],
        "is_active": w.is_active,
        "description": w.description,
        "created_at": w.created_at,
        "secret_fingerprint": _fingerprint(w.secret),
        "secret": w.secret if include_secret else None,
    }


# ---------- endpoints ----------

@router.get("/webhooks", response_model=List[WebhookOut])
def list_webhooks(
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    return [_to_out(w) for w in webhook_crud.list_webhooks(db, user_id=user.id)]


@router.post("/webhooks", response_model=WebhookOut)
def create_webhook(
    payload: WebhookCreate,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    w = webhook_crud.create_webhook(
        db,
        user_id=user.id,
        url=str(payload.url),
        events=payload.events or [],
        description=payload.description,
    )
    return _to_out(w, include_secret=True)


@router.get("/webhooks/{webhook_id}", response_model=WebhookOut)
def get_webhook(
    webhook_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    w = webhook_crud.get_webhook(db, webhook_id=webhook_id, user_id=user.id)
    if not w:
        raise HTTPException(status_code=404, detail="webhook not found")
    return _to_out(w)


@router.patch("/webhooks/{webhook_id}", response_model=WebhookOut)
def update_webhook(
    webhook_id: int,
    payload: WebhookUpdate,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    w = webhook_crud.get_webhook(db, webhook_id=webhook_id, user_id=user.id)
    if not w:
        raise HTTPException(status_code=404, detail="webhook not found")
    w = webhook_crud.update_webhook(
        db, w,
        url=str(payload.url) if payload.url else None,
        events=payload.events,
        is_active=payload.is_active,
        description=payload.description,
    )
    return _to_out(w)


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(
    webhook_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    w = webhook_crud.get_webhook(db, webhook_id=webhook_id, user_id=user.id)
    if not w:
        raise HTTPException(status_code=404, detail="webhook not found")
    webhook_crud.delete_webhook(db, w)
    return {"object": "webhook.deleted", "id": webhook_id}


@router.get("/webhooks/{webhook_id}/deliveries", response_model=List[WebhookDeliveryOut])
def list_deliveries(
    webhook_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
    limit: int = 50,
):
    user, _ = auth
    w = webhook_crud.get_webhook(db, webhook_id=webhook_id, user_id=user.id)
    if not w:
        raise HTTPException(status_code=404, detail="webhook not found")
    return webhook_crud.list_deliveries(db, webhook_id=webhook_id, limit=min(max(limit, 1), 200))


@router.post("/webhooks/{webhook_id}/ping")
async def ping_webhook(
    webhook_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    """Send a one-off test event so the developer can verify the URL is reachable."""
    user, _ = auth
    w = webhook_crud.get_webhook(db, webhook_id=webhook_id, user_id=user.id)
    if not w:
        raise HTTPException(status_code=404, detail="webhook not found")

    from app.core import webhook_dispatcher
    tasks = webhook_dispatcher.enqueue(
        db, user_id=user.id,
        event_type="webhook.ping",
        payload={"webhook_id": w.id, "test": True},
    )
    return {
        "object": "webhook.ping",
        "webhook_id": w.id,
        "dispatched": len(tasks),
    }
