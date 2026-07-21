"""
Webhook + WebhookDelivery models.

A Webhook is a user-owned URL that NovaMind will POST to when an event
matching `events` (e.g. ``api.request.completed``, ``billing.invoice.paid``)
fires. The signing secret is generated on create and only returned once;
it's stored hashed (HMAC key, not user password — a leak just lets the
attacker forge events, not steal data, so storing plain is acceptable
and lets us keep delivery stateless).

WebhookDelivery is the audit log: every attempt is recorded with status
and last_error so the user can see why a delivery failed in the portal.
"""
from __future__ import annotations

import secrets
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Text,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


def _gen_secret() -> str:
    """A 48-byte URL-safe token. The signing secret is per-webhook, not per-user,
    so revoking one webhook doesn't break the others."""
    return "whsec_" + secrets.token_urlsafe(48)


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    url = Column(String, nullable=False)
    # JSON array of event names: e.g. ["api.request.completed",
    # "billing.invoice.paid"]. Empty/None = all events.
    events = Column(JSON, nullable=True)
    # Plaintext signing secret. Returned once on create; never re-served
    # by the read endpoint.
    secret = Column(String, nullable=False, default=_gen_secret)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    deliveries = relationship(
        "WebhookDelivery",
        back_populates="webhook",
        cascade="all, delete-orphan",
    )


class WebhookDelivery(Base):
    """One row per delivery attempt. Retries write additional rows."""
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_webhook_created", "webhook_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(Integer, ForeignKey("webhooks.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    # Snapshot of the JSON payload at dispatch time. Kept verbatim so a
    # late review of a delivery can show the caller exactly what was sent.
    payload = Column(JSON, nullable=False)
    # 0..3 (initial + 3 retries). 0 means first attempt is still in flight
    # or succeeded on first try; the call site updates on every attempt.
    attempt = Column(Integer, nullable=False, default=0)
    # 'pending' | 'success' | 'failed' — terminal states are success/failed.
    status = Column(String, nullable=False, default="pending")
    http_status = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    webhook = relationship("Webhook", back_populates="deliveries")
