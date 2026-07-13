"""Pydantic schemas for the billing endpoints.

These match the shape of `web/lib/billing.ts` PlanInfo / Invoice so the
frontend doesn't have to map field names. All currency fields are in
cents (integer) to avoid float drift across the wire.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


# ---------- Plan ----------

class PlanOut(BaseModel):
    slug: str
    name: str
    price_cents: int
    currency: str
    # 0 = unlimited (we treat 0 and NULL identically on the wire).
    monthly_token_limit: int
    monthly_request_limit: int
    features: List[str] = Field(default_factory=list)

    class Config:
        orm_mode = True


# ---------- Subscription ----------

class SubscriptionOut(BaseModel):
    id: int
    plan_slug: str
    status: str
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool

    class Config:
        orm_mode = True


# ---------- Plan + usage bundle ----------

class PlanInfoOut(BaseModel):
    """The current user's plan + month-to-date usage + credit balance.

    Returned by `GET /billing/plan` and rendered into the AppShell's
    plan badge. Mock-mode returns the free plan with zero usage.
    """
    slug: Literal["free", "pro", "business"]
    name: str
    monthly_token_limit: int
    monthly_request_limit: int
    monthly_token_count: int
    monthly_request_count: int
    credits_balance_cents: int


# ---------- Checkout ----------

class CheckoutRequest(BaseModel):
    plan: Literal["pro", "business"] = Field(..., description="Plan slug to subscribe to")


class CheckoutResponse(BaseModel):
    """Hosted checkout URL.

    In real-Stripe mode, this is a `https://checkout.stripe.com/...`
    URL the browser redirects to. In mock mode, this is
    `/billing/mock-checkout?session=<id>&plan=<slug>` — the frontend
    routes there and shows the dev "Confirm" button.
    """
    url: str
    mock: bool = False
    session_id: Optional[str] = None


# ---------- Invoices ----------

class InvoiceOut(BaseModel):
    id: str
    amount_cents: int
    currency: str
    # 'paid' | 'open' | 'void'
    status: str
    created_at: datetime
    hosted_invoice_url: Optional[str] = None

    class Config:
        orm_mode = True


# ---------- Portal ----------

class PortalResponse(BaseModel):
    url: str
    mock: bool = False


# ---------- Webhook ----------

class WebhookAck(BaseModel):
    received: bool
    # The event id we processed, for traceability. May be None for
    # events we deliberately ignored (e.g. test pings).
    event_id: Optional[str] = None
