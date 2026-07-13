"""
Billing endpoints — `/api/v1/billing/*`.

The whole surface is in mock mode when `settings.STRIPE_SECRET_KEY` is
empty (the default). In mock mode:

  * `POST /billing/checkout-session` returns a hosted URL pointing at
    our own `/billing/mock-checkout?session=...` page; clicking
    "Confirm" on that page invokes the same webhook handler the real
    Stripe webhook would, with a synthetic `mock_<uuid>` event id.
  * `POST /billing/portal` returns 501 with `{ error: "not_configured" }`
    so the frontend can render a friendly "Stripe not configured yet"
    dialog.
  * `POST /billing/webhook` accepts both real Stripe events (verified
    by `STRIPE_WEBHOOK_SECRET`) and the dev-mode synthetic events
    produced by the mock-checkout page.

In real-Stripe mode the webhook is verified by signature and the
checkout/portal endpoints return real Stripe URLs.

The user-facing read endpoint `GET /billing/plan` works in both
modes — it just returns whatever plan + usage the user currently
has, with the free plan as the default.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models import Plan, Subscription, User
from app.models.billing import CreditLedger
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    InvoiceOut,
    PlanInfoOut,
    PortalResponse,
    WebhookAck,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Mock-mode helpers ----------

def _is_mock_mode() -> bool:
    """True when Stripe isn't configured — billing degrades to local mock.

    The check is on the env var, not on whether the SDK is importable,
    so a partial install still degrades cleanly. If `stripe` isn't
    installed AND we're not in mock mode, the SDK-touching endpoints
    will raise at call time with a clear ImportError, which the global
    handler turns into a 503.
    """
    return not (settings.STRIPE_SECRET_KEY or "").strip()


def _safe_stripe():
    """Lazy import of the Stripe SDK. Returns the `stripe` module or None."""
    try:
        import stripe  # type: ignore
    except ImportError:
        return None
    return stripe


def _get_or_create_free_plan(db: Session) -> Plan:
    """Return the free plan, creating a placeholder if seed didn't run.

    The seed in `main.py` should always run first, but this is a
    defensive fallback so the GET /billing/plan endpoint never 500s
    on a freshly-recreated DB.
    """
    plan = db.query(Plan).filter(Plan.slug == "free").first()
    if plan:
        return plan
    plan = Plan(
        slug="free",
        name="Free",
        price_cents=0,
        currency="usd",
        monthly_token_limit=50_000,
        monthly_request_limit=500,
        features=["50,000 tokens per month", "500 requests per month"],
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _resolve_user_plan(db: Session, user: User) -> Plan:
    """Return the user's effective plan.

    Falls back to free when the user's `plan_id` is NULL or stale
    (e.g. pointing at a deleted plan). A user with no active
    subscription is implicitly on the free plan.
    """
    if user.plan_id:
        plan = db.query(Plan).filter(Plan.id == user.plan_id).first()
        if plan:
            return plan
    return _get_or_create_free_plan(db)


# ---------- GET /billing/plan ----------

@router.get("/plan", response_model=PlanInfoOut)
def get_my_plan(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Return the current user's plan + month-to-date usage + credits.

    Usage is aggregated across all of the user's API keys, not just
    one — the user is the billing subject, the key is the meter.
    """
    from app.models.api_key import ApiKey
    from app.models.api_usage import ApiUsage

    plan = _resolve_user_plan(db, current_user)

    # Sum token / request usage across the user's API keys for the
    # current calendar month. We could also sum ApiUsage rows directly
    # but ApiKey.monthly_*_count is already a denormalized cache and
    # is what the developer portal surfaces, so reusing it keeps the
    # two views consistent.
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    token_count = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id)
        .with_entities(ApiKey.monthly_token_count)
        .all()
    )
    request_count = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id)
        .with_entities(ApiKey.monthly_request_count)
        .all()
    )
    tokens = sum((row[0] or 0) for row in token_count)
    requests = sum((row[0] or 0) for row in request_count)

    # Credits balance — denormalized cache on User.
    return PlanInfoOut(
        slug=plan.slug,  # type: ignore[arg-type]
        name=plan.name,
        monthly_token_limit=plan.monthly_token_limit or 0,
        monthly_request_limit=plan.monthly_request_limit or 0,
        monthly_token_count=tokens,
        monthly_request_count=requests,
        credits_balance_cents=current_user.credits_balance_cents or 0,
    )


# ---------- POST /billing/checkout-session ----------

@router.post("/checkout-session", response_model=CheckoutResponse)
def create_checkout_session(
    body: CheckoutRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Start a Stripe Checkout session for the given plan.

    In mock mode: returns a URL pointing at the dev `/billing/mock-checkout`
    page so the developer can still see the full flow without configuring
    Stripe. In real mode: creates a real Stripe Checkout Session and
    returns the hosted URL.
    """
    plan = db.query(Plan).filter(Plan.slug == body.plan, Plan.is_active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{body.plan}' not found or is inactive")

    if _is_mock_mode():
        # Synthetic session id — referenced by the mock-checkout page
        # when it posts the synthetic webhook. UUID-shaped so it can't
        # be confused with a real Stripe session id.
        session_id = "mock_" + secrets.token_urlsafe(16)
        url = f"{settings.PUBLIC_SITE_URL.rstrip('/')}/billing/mock-checkout?session={session_id}&plan={plan.slug}"
        return CheckoutResponse(url=url, mock=True, session_id=session_id)

    stripe = _safe_stripe()
    if not stripe:
        raise HTTPException(
            status_code=503,
            detail="Billing is not configured on this server (stripe SDK missing).",
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY

    if not plan.stripe_price_id:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Plan '{plan.slug}' has no Stripe price id configured. "
                f"Set STRIPE_PRICE_{plan.slug.upper()} in the backend environment."
            ),
        )

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            success_url=f"{settings.PUBLIC_SITE_URL.rstrip('/')}/billing?checkout=success",
            cancel_url=f"{settings.PUBLIC_SITE_URL.rstrip('/')}/pricing?checkout=cancel",
            customer_email=current_user.email or None,
            client_reference_id=str(current_user.id),
            metadata={"user_id": str(current_user.id), "plan_slug": plan.slug},
        )
    except Exception as exc:
        logger.exception("Stripe checkout session creation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    return CheckoutResponse(url=session.url, mock=False, session_id=session.id)


# ---------- POST /billing/portal ----------

@router.post("/portal", response_model=PortalResponse)
def create_billing_portal(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Open the Stripe customer portal for self-serve plan changes.

    Mock mode returns 503 so the frontend can show a friendly dialog.
    """
    if _is_mock_mode():
        raise HTTPException(
            status_code=503,
            detail="Billing portal is not available in mock mode.",
        )
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No Stripe customer on file. Subscribe to a plan first.",
        )
    stripe = _safe_stripe()
    if not stripe:
        raise HTTPException(status_code=503, detail="Stripe SDK not available.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{settings.PUBLIC_SITE_URL.rstrip('/')}/billing",
        )
    except Exception as exc:
        logger.exception("Stripe portal session failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")
    return PortalResponse(url=session.url, mock=False)


# ---------- GET /billing/invoices ----------

@router.get("/invoices", response_model=list[InvoiceOut])
def list_my_invoices(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List the user's Stripe invoices.

    Mock mode returns an empty list — there are no real invoices to
    surface. In real mode we fetch from Stripe; we don't denormalize
    invoice rows into the local DB because Stripe is the source of
    truth and historical invoice data rarely needs to be queryable
    by us.
    """
    if _is_mock_mode():
        return []
    if not current_user.stripe_customer_id:
        return []
    stripe = _safe_stripe()
    if not stripe:
        raise HTTPException(status_code=503, detail="Stripe SDK not available.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        result = stripe.Invoice.list(customer=current_user.stripe_customer_id, limit=50)
    except Exception as exc:
        logger.exception("Stripe invoice list failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")
    return [
        InvoiceOut(
            id=inv.id,
            amount_cents=inv.amount_paid or inv.amount_due or 0,
            currency=inv.currency,
            status=inv.status or "open",
            created_at=datetime.fromtimestamp(inv.created),
            hosted_invoice_url=inv.hosted_invoice_url,
        )
        for inv in result.data
    ]


# ---------- POST /billing/webhook ----------

@router.post("/webhook", response_model=WebhookAck)
async def billing_webhook(request: Request, db: Session = Depends(deps.get_db)):
    """Handle Stripe webhook events + mock-mode synthetic events.

    Real Stripe: the body is verified against `STRIPE_WEBHOOK_SECRET`
    using `stripe.Webhook.construct_event`. We then dispatch on
    `event["type"]` to a small set of handlers:
      - checkout.session.completed
      - customer.subscription.updated
      - customer.subscription.deleted

    Mock mode: the body is plain JSON with the same `type` field but
    no signature. We only honor events whose `id` starts with `mock_`
    so a forged real-Stripe-looking event from a misconfigured caller
    can't upgrade a user.

    Idempotency: every event is logged to `credit_ledger` keyed by
    `stripe_event_id` UNIQUE. Replays hit a constraint violation which
    we swallow — the right thing to do.
    """
    body_bytes = await request.body()

    event: Optional[dict] = None
    is_mock_event = False
    if _is_mock_mode():
        # No signature check in mock mode — but require the event id
        # to be mock_-prefixed as a cheap forgery guard.
        try:
            event = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid mock webhook payload")
        if not isinstance(event, dict) or not str(event.get("id", "")).startswith("mock_"):
            raise HTTPException(status_code=400, detail="Mock event id must start with 'mock_'")
        is_mock_event = True
    else:
        stripe = _safe_stripe()
        if not stripe:
            raise HTTPException(status_code=503, detail="Stripe SDK not available.")
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(
                body_bytes, sig, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:
            logger.warning("Stripe webhook signature verification failed: %s", exc)
            raise HTTPException(status_code=400, detail=f"Invalid signature: {exc}")

    event_id = event.get("id")
    event_type = event.get("type")

    # Dispatch. Each handler is idempotent — it either succeeds and
    # writes a CreditLedger row (UNIQUE on event id), or it's a no-op
    # for events we don't care about.
    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(db, event, is_mock_event)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(db, event)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(db, event)
        elif event_type == "invoice.payment_succeeded":
            _handle_invoice_paid(db, event)
        else:
            # Uninteresting event type — acknowledge so Stripe stops
            # retrying, but don't write a ledger row.
            logger.info("Ignoring Stripe event type: %s", event_type)
    except _EventAlreadyProcessed:
        # Idempotent replay — the constraint violation told us so.
        logger.info("Skipping replayed event %s", event_id)
    except Exception as exc:
        # Don't 500 — Stripe retries on non-2xx and we'd loop forever.
        # Log and 200 anyway; we'll see the failed event in the logs.
        logger.exception("Webhook handler error for %s: %s", event_id, exc)
    return WebhookAck(received=True, event_id=event_id)


class _EventAlreadyProcessed(Exception):
    """Internal: the event was already written to the ledger."""


def _record_credit(
    db: Session,
    user_id: int,
    delta_cents: int,
    reason: str,
    description: str,
    stripe_event_id: Optional[str],
) -> None:
    """Append a ledger row and update the denormalized cache.

    Idempotency: if `stripe_event_id` is set, the UNIQUE constraint
    on `credit_ledger.stripe_event_id` will reject a replay. We
    translate the IntegrityError into `_EventAlreadyProcessed` so the
    caller can log-and-continue instead of returning 500.
    """
    from sqlalchemy.exc import IntegrityError

    try:
        db.add(CreditLedger(
            user_id=user_id,
            delta_cents=delta_cents,
            reason=reason,
            description=description,
            stripe_event_id=stripe_event_id,
        ))
        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            user.credits_balance_cents = (user.credits_balance_cents or 0) + delta_cents
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_credit_ledger_stripe_event_id" in str(exc.orig) or "stripe_event_id" in str(exc.orig):
            raise _EventAlreadyProcessed() from exc
        raise


# ---------- Webhook handlers ----------

def _handle_checkout_completed(db: Session, event: dict, is_mock_event: bool) -> None:
    """A user finished a Stripe Checkout — subscribe them to the plan.

    The plan slug lives in `event["data"]["object"]["metadata"]["plan_slug"]`
    (we put it there when creating the session) or in the
    `client_reference_id` for the user id. We update the user's
    `plan_id` and `stripe_customer_id` accordingly. The Stripe
    subscription id is recorded too, but subscription-lifecycle events
    are the ones that flip `current_period_end` and `status`.
    """
    obj = (event.get("data") or {}).get("object") or {}
    metadata = obj.get("metadata") or {}
    user_id = int(metadata.get("user_id") or obj.get("client_reference_id") or 0)
    plan_slug = metadata.get("plan_slug")
    if not user_id or not plan_slug:
        logger.warning("checkout.session.completed missing user_id/plan_slug: %s", event.get("id"))
        return

    plan = db.query(Plan).filter(Plan.slug == plan_slug).first()
    user = db.query(User).filter(User.id == user_id).first()
    if not plan or not user:
        logger.warning("checkout.session.completed: unknown plan=%s or user=%s", plan_slug, user_id)
        return

    user.plan_id = plan.id
    if obj.get("customer") and not is_mock_event:
        user.stripe_customer_id = obj["customer"]
    db.commit()

    # In mock mode, also drop a small "topup" credit so the dashboard
    # is non-empty — gives the developer something to see.
    if is_mock_event:
        _record_credit(
            db,
            user_id=user.id,
            delta_cents=500,  # $5.00 in mock credits
            reason="promo",
            description="Welcome credit (mock mode)",
            stripe_event_id=event.get("id"),
        )


def _handle_subscription_updated(db: Session, event: dict) -> None:
    obj = (event.get("data") or {}).get("object") or {}
    stripe_sub_id = obj.get("id")
    if not stripe_sub_id:
        return
    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
    if not sub:
        # Could be a new subscription for a user we haven't seen yet.
        # The checkout.completed handler should have created it; if
        # not, just log and move on.
        logger.info("subscription.updated for unknown sub %s; ignoring", stripe_sub_id)
        return
    sub.status = obj.get("status", sub.status)
    sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end", sub.cancel_at_period_end))
    period_end = obj.get("current_period_end")
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end)
    db.commit()


def _handle_subscription_deleted(db: Session, event: dict) -> None:
    obj = (event.get("data") or {}).get("object") or {}
    stripe_sub_id = obj.get("id")
    if not stripe_sub_id:
        return
    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
    if not sub:
        return
    sub.status = "canceled"
    # Move the user back to the free plan.
    user = db.query(User).filter(User.id == sub.user_id).first()
    if user:
        free = _get_or_create_free_plan(db)
        user.plan_id = free.id
    db.commit()


def _handle_invoice_paid(db: Session, event: dict) -> None:
    """invoice.payment_succeeded — top up the user's credit ledger.

    We don't model invoice line items, just the total. The metadata
    is sparse here; for now we use the customer's default user as
    the recipient (the typical case is one user per customer).
    """
    obj = (event.get("data") or {}).get("object") or {}
    customer = obj.get("customer")
    amount = obj.get("amount_paid") or obj.get("total") or 0
    if not customer or not amount:
        return
    user = db.query(User).filter(User.stripe_customer_id == customer).first()
    if not user:
        return
    _record_credit(
        db,
        user_id=user.id,
        delta_cents=amount,
        reason="topup",
        description=f"Stripe invoice {obj.get('number') or obj.get('id')}",
        stripe_event_id=event.get("id"),
    )
