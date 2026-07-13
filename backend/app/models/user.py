from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)  # nullable for OAuth-only users
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)  # nullable for OAuth-only users
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

    # OAuth fields
    google_id = Column(String, unique=True, index=True, nullable=True)
    avatar_url = Column(String, nullable=True)

    # Profile & Preferences
    full_name = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    preferences = Column(JSON, nullable=True)  # Store user preferences, AI settings, etc.

    # Usage & Analytics
    total_chats = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    last_active = Column(DateTime(timezone=True), onupdate=func.now())

    # API Keys
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")

    # API Usage
    api_usage = relationship("ApiUsage", back_populates="user", cascade="all, delete-orphan")

    # Chats
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")

    # ---------- Email verification ----------
    # `email_verification_token` is a URL-safe random string, set on
    # register, cleared when the user clicks the link. `expires` is a
    # 24h window from issue time. Both are nullable because OAuth users
    # are marked verified at creation and never see this flow.
    email_verification_token = Column(String, unique=True, index=True, nullable=True)
    email_verification_expires = Column(DateTime(timezone=True), nullable=True)

    # ---------- Password reset ----------
    # Same shape as verification: a one-shot token with a 1h expiry.
    password_reset_token = Column(String, unique=True, index=True, nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)

    # ---------- Brute-force protection ----------
    # Incremented on every failed login. Lockout (15 min) triggers when
    # the count crosses 5 within a 15-min sliding window. `lockout_until`
    # is set when the threshold is hit; cleared on next successful login.
    failed_login_count = Column(Integer, default=0, nullable=False)
    lockout_until = Column(DateTime(timezone=True), nullable=True)

    # ---------- Token versioning (forced logout / change-password) ----------
    # Bumped on logout and password change. Every JWT carries a `tv`
    # claim; `get_current_user` rejects tokens whose `tv` doesn't match
    # the current `token_version`. So calling /auth/logout (or rotating
    # the password) invalidates every other active JWT for the user
    # without needing a server-side token store.
    token_version = Column(Integer, default=0, nullable=False)

    # ---------- Billing (added 2026-07) ----------
    # `plan_id` references `plans.id`. NULL means "use the free plan
    # implicitly" (we resolve it on read so the FK stays optional).
    # `stripe_customer_id` is `cus_...` once the user starts a real
    # checkout; empty in mock mode. `credits_balance_cents` is the
    # pay-as-you-go top-up balance; the credit ledger is the source
    # of truth and this column is a denormalized cache.
    plan_id = Column(Integer, nullable=True)
    stripe_customer_id = Column(String, nullable=True, index=True)
    credits_balance_cents = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


def ensure_user_columns(engine) -> None:
    """Idempotent ALTER TABLE for the new auth-flow columns.

    Mirrors `ensure_api_key_columns`: try each ADD COLUMN, swallow the
    duplicate-column error so re-runs are safe. New columns are
    nullable or have defaults, so existing rows survive the migration
    without backfill. Production deployments on Postgres should
    eventually use Alembic; this helper keeps local dev working.
    """
    from sqlalchemy import text

    new_cols = [
        ("email_verification_token", "VARCHAR"),
        ("email_verification_expires", "TIMESTAMP"),
        ("password_reset_token", "VARCHAR"),
        ("password_reset_expires", "TIMESTAMP"),
        ("failed_login_count", "INTEGER DEFAULT 0 NOT NULL"),
        ("lockout_until", "TIMESTAMP"),
        ("token_version", "INTEGER DEFAULT 0 NOT NULL"),
    ]
    with engine.begin() as conn:
        for name, decl in new_cols:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {decl}"))
            except Exception:
                # Column already exists, or backend doesn't support the
                # ALTER. Either way: move on.
                pass