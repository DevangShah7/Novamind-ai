"""CRUD for Webhook + WebhookDelivery."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import Webhook, WebhookDelivery


# ---------- Webhook ----------

def create_webhook(
    db: Session,
    *,
    user_id: int,
    url: str,
    events: Optional[List[str]] = None,
    description: Optional[str] = None,
) -> Webhook:
    obj = Webhook(
        user_id=user_id,
        url=url,
        events=events or [],
        description=description,
        is_active=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_webhook(db: Session, webhook_id: int, user_id: int) -> Optional[Webhook]:
    return (
        db.query(Webhook)
        .filter(Webhook.id == webhook_id, Webhook.user_id == user_id)
        .first()
    )


def list_webhooks(db: Session, user_id: int) -> List[Webhook]:
    return (
        db.query(Webhook)
        .filter(Webhook.user_id == user_id)
        .order_by(Webhook.created_at.desc())
        .all()
    )


def update_webhook(
    db: Session,
    webhook: Webhook,
    *,
    url: Optional[str] = None,
    events: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
    description: Optional[str] = None,
) -> Webhook:
    if url is not None:
        webhook.url = url
    if events is not None:
        webhook.events = events
    if is_active is not None:
        webhook.is_active = is_active
    if description is not None:
        webhook.description = description
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


def delete_webhook(db: Session, webhook: Webhook) -> None:
    db.delete(webhook)
    db.commit()


# ---------- WebhookDelivery ----------

def record_delivery(
    db: Session,
    *,
    webhook_id: int,
    event_type: str,
    payload: Dict[str, Any],
    attempt: int,
    status: str,
    http_status: Optional[int],
    last_error: Optional[str],
    delivered_at: Optional[datetime],
) -> WebhookDelivery:
    row = WebhookDelivery(
        webhook_id=webhook_id,
        event_type=event_type,
        payload=payload,
        attempt=attempt,
        status=status,
        http_status=http_status,
        last_error=last_error,
        delivered_at=delivered_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_deliveries(db: Session, webhook_id: int, limit: int = 50) -> List[WebhookDelivery]:
    return (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
        .all()
    )
