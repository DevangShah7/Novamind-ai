"""
Billing models: Plan, Subscription, CreditLedger.

Three plans (free, pro, business) are seeded on first boot. Users get a
free plan by default; upgrading requires Stripe (or the local mock
checkout). CreditLedger is append-only — it's the only writer to
`users.credits_balance_cents`, so the balance is reconstructable from
the ledger + every entry is idempotent against a Stripe event id
(stripe_event_id UNIQUE).
"""
from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    # 'free' | 'pro' | 'business' — the slug is the public contract.
    # Must match `web/lib/plans.ts` and `web/lib/billing.ts` PlanInfo.
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    # Prices are stored in cents to avoid float drift.
    price_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String, nullable=False, default="usd")
    # 0 / -1 = unlimited.
    monthly_token_limit = Column(Integer, nullable=True)
    monthly_request_limit = Column(Integer, nullable=True)
    # Free-form feature list shown on the pricing page. JSON array of
    # strings. Edited only by the seed; not user-mutable.
    features = Column(JSON, nullable=True)
    # Stripe price id. Empty when running in mock mode.
    stripe_price_id = Column(String, nullable=True)
    # Soft-disable a plan without deleting it. New subscriptions can't
    # be created on a disabled plan; existing ones keep working.
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    # 'active' | 'trialing' | 'past_due' | 'canceled' | 'unpaid'
    status = Column(String, nullable=False, default="active")
    # Stripe's subscription id (sub_...). Empty in mock mode.
    stripe_subscription_id = Column(String, unique=True, nullable=True, index=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    # When the user pressed "Cancel" — the subscription stays active
    # until current_period_end. NULL = not canceling.
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)

    plan = relationship("Plan", back_populates="subscriptions")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CreditLedger(Base):
    """Append-only credit ledger — the source of truth for credit balance.

    `users.credits_balance_cents` is a denormalized cache, recomputable
    from SUM(delta_cents) over this table. `stripe_event_id` UNIQUE
    makes the webhook idempotent: replaying the same event is a no-op
    instead of double-credited.
    """
    __tablename__ = "credit_ledger"
    __table_args__ = (UniqueConstraint("stripe_event_id", name="uq_credit_ledger_stripe_event_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Positive = credit added. Negative = credit consumed. Never zero
    # (a zero-delta row is meaningless and would just bloat the index).
    delta_cents = Column(Integer, nullable=False)
    # 'topup' | 'subscription_refund' | 'promo' | 'consume'
    # 'consume' is reserved for future metered billing; not written today.
    reason = Column(String, nullable=False)
    # Human-readable note, surfaced in the billing UI.
    description = Column(Text, nullable=True)
    # For Stripe-driven entries: the originating event id. UNIQUE so a
    # replayed webhook hits a constraint violation instead of double-crediting.
    # NULL for non-Stripe entries (mock-mode confirms, promos, etc.).
    stripe_event_id = Column(String, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------- Idempotent column adds ----------

def ensure_billing_columns(engine) -> None:
    """ALTER TABLE for the billing columns on `users` and `plans`.

    Same pattern as `ensure_user_columns` / `ensure_api_key_columns`:
    add one at a time and swallow "already exists" so re-runs are safe.
    Local dev only — production should use Alembic.
    """
    from sqlalchemy import text

    user_cols = [
        ("plan_id", "INTEGER"),
        ("stripe_customer_id", "VARCHAR"),
        ("credits_balance_cents", "INTEGER DEFAULT 0 NOT NULL"),
    ]
    with engine.begin() as conn:
        for name, decl in user_cols:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {decl}"))
            except Exception:
                # Column already exists, or backend doesn't support
                # the ALTER. Either way: move on.
                pass


# ---------- Seed ----------

# Three plans, hard-coded. Slug MUST match `web/lib/plans.ts` /
# `web/lib/billing.ts`. Token / request limits mirror the free-tier
# defaults in the frontend mock so quota gates work even when Stripe
# isn't configured.
_DEFAULT_PLANS = [
    {
        "slug": "free",
        "name": "Free",
        "price_cents": 0,
        "monthly_token_limit": 50_000,
        "monthly_request_limit": 500,
        "features": [
            "50,000 tokens per month",
            "500 requests per month",
            "Standard rate limits",
            "Community support",
        ],
    },
    {
        "slug": "pro",
        "name": "Pro",
        "price_cents": 1_900,  # $19.00
        "monthly_token_limit": 1_000_000,
        "monthly_request_limit": 10_000,
        "features": [
            "1,000,000 tokens per month",
            "10,000 requests per month",
            "Higher rate limits",
            "Email support",
        ],
    },
    {
        "slug": "business",
        "name": "Business",
        "price_cents": 9_900,  # $99.00
        "monthly_token_limit": 10_000_000,
        "monthly_request_limit": 100_000,
        "features": [
            "10,000,000 tokens per month",
            "100,000 requests per month",
            "Custom rate limits",
            "Priority support",
            "SLA",
        ],
    },
]


def seed_plans(db) -> None:
    """Idempotently insert the default plans.

    Existing rows are left alone — `slug` is the key, but we don't
    overwrite an operator's edits to a price or feature list. New
    slugs are inserted. Safe to call on every boot.
    """
    from app.models.billing import Plan  # local import to avoid cycle

    existing = {p.slug for p in db.query(Plan).all()}
    added = False
    for spec in _DEFAULT_PLANS:
        if spec["slug"] in existing:
            continue
        db.add(Plan(
            slug=spec["slug"],
            name=spec["name"],
            price_cents=spec["price_cents"],
            currency="usd",
            monthly_token_limit=spec["monthly_token_limit"],
            monthly_request_limit=spec["monthly_request_limit"],
            features=spec["features"],
            stripe_price_id=None,  # wired in via STRIPE_PRICE_* env when configured
            is_active=True,
        ))
        added = True
    if added:
        db.commit()
