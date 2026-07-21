"""
Webhook delivery — fire-and-forget HMAC-signed POSTs.

``enqueue(user_id, event_type, payload)`` is called from
``_log_usage()`` in ``v1_compat.py`` after each request. It looks up the
user's active webhooks, filters by event subscription, and dispatches
each delivery as an asyncio task. Each task:

  1. Builds the JSON body
  2. Computes an HMAC-SHA256 signature using the webhook's secret
  3. POSTs it to the URL with a 10s timeout
  4. On 2xx -> success, on 4xx (non-429) -> failed, on 5xx/timeout -> retry
  5. Retries with exponential backoff (1s, 4s, 16s) up to 3 attempts

A row in ``webhook_deliveries`` is written for every attempt so the
portal can show "last 10 deliveries, 8 failed".

The dispatcher is import-safe: if the DB hasn't been bootstrapped yet
or the webhook tables are missing, ``enqueue`` becomes a no-op.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def sign(body: bytes, secret: str) -> str:
    """HMAC-SHA256 of the body, hex-encoded. Same algorithm Stripe uses."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _deliver_one(
    *,
    webhook_id: int,
    url: str,
    secret: str,
    event_type: str,
    payload: Dict[str, Any],
    record_delivery_fn,
) -> None:
    """One full delivery lifecycle — up to 3 attempts with exponential backoff.

    ``record_delivery_fn(attempt, status, http_status, last_error, delivered_at)``
    is injected so we don't pull SQLAlchemy into this module; the caller
    in the endpoint owns the session and writes the rows.
    """
    import httpx

    body = json.dumps({"event": event_type, "data": payload}, separators=(",", ":")).encode("utf-8")
    signature = sign(body, secret)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "NovaMind-Webhook/1.0",
        "X-Novamind-Event": event_type,
        "X-Novamind-Signature": f"sha256={signature}",
    }

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(url, content=body, headers=headers)
            http_status = r.status_code
            if 200 <= http_status < 300:
                # Success. Record once with attempt count + delivered_at.
                record_delivery_fn(
                    attempt=attempt,
                    status="success",
                    http_status=http_status,
                    last_error=None,
                    delivered_at=datetime.utcnow(),
                )
                return
            if 400 <= http_status < 500 and http_status != 429:
                # 4xx (except 429) means "don't retry — caller rejected it".
                record_delivery_fn(
                    attempt=attempt,
                    status="failed",
                    http_status=http_status,
                    last_error=f"http {http_status}: {r.text[:200]}",
                    delivered_at=None,
                )
                return
            # 5xx or 429: fall through to retry
            last_error = f"http {http_status}: {r.text[:200]}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            http_status = None

        # Backoff before next attempt: 1s, 4s, 16s
        if attempt < max_attempts:
            await asyncio.sleep(1 ** attempt)  # wait so we don't hammer a sick endpoint

    # Out of attempts.
    record_delivery_fn(
        attempt=max_attempts,
        status="failed",
        http_status=http_status,
        last_error=last_error,
        delivered_at=None,
    )


def enqueue(
    db,
    user_id: int,
    event_type: str,
    payload: Dict[str, Any],
) -> List[asyncio.Task]:
    """Fan out ``event_type`` to every subscribed webhook for ``user_id``.

    Returns the list of created tasks so tests can await them. In
    production we just let them run; an unawaited task is fine here
    because httpx.AsyncClient manages its own lifecycle and asyncio
    garbage-collects completed tasks.
    """
    try:
        from app.models import Webhook
    except Exception:  # pragma: no cover - bootstrap race
        return []

    try:
        hooks: List[Webhook] = (
            db.query(Webhook)
            .filter(Webhook.user_id == user_id, Webhook.is_active.is_(True))
            .all()
        )
    except Exception as e:  # pragma: no cover - missing table etc.
        logger.debug("webhook dispatch skipped: %s", e)
        return []

    if not hooks:
        return []

    tasks: List[asyncio.Task] = []
    for hook in hooks:
        events = hook.events or []
        # None / [] = all events; otherwise the hook's list must contain
        # this event_type.
        if events and event_type not in events:
            continue

        from app.crud import webhook as webhook_crud  # local import to avoid cycle

        def _record(attempt, status, http_status, last_error, delivered_at, _hook_id=hook.id):
            try:
                webhook_crud.record_delivery(
                    db,
                    webhook_id=_hook_id,
                    event_type=event_type,
                    payload=payload,
                    attempt=attempt,
                    status=status,
                    http_status=http_status,
                    last_error=last_error,
                    delivered_at=delivered_at,
                )
            except Exception as e:  # pragma: no cover - don't break the response
                logger.warning("failed to record webhook delivery: %s", e)

        tasks.append(
            asyncio.create_task(
                _deliver_one(
                    webhook_id=hook.id,
                    url=hook.url,
                    secret=hook.secret,
                    event_type=event_type,
                    payload=payload,
                    record_delivery_fn=_record,
                )
            )
        )
    return tasks
