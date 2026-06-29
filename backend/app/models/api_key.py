from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)

    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="api_keys")

    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)

    # --- Developer-platform extensions (added 2026-06) ---
    # JSON arrays of strings. Empty / null means no restriction.
    ip_allowlist = Column(JSON, nullable=True)
    domain_allowlist = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    # Soft-disable without deleting: lets ops quarantine a key.
    is_disabled = Column(Boolean, default=False, nullable=False)
    disable_reason = Column(String, nullable=True)
    # Per-key caps; 0/null = unlimited.
    monthly_token_limit = Column(Integer, nullable=True)
    monthly_request_limit = Column(Integer, nullable=True)
    # Aggregates (refreshed on usage write).
    monthly_token_count = Column(Integer, nullable=True, default=0)
    monthly_request_count = Column(Integer, nullable=True, default=0)
    monthly_cost_usd = Column(Integer, nullable=True, default=0)  # store cents to avoid float drift
    organization = Column(String, nullable=True)

    # Usage logs
    usage_logs = relationship("ApiUsage", back_populates="api_key", cascade="all, delete-orphan")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


def ensure_api_key_columns(engine) -> None:
    """Idempotent ALTER TABLE for the new developer-platform columns.

    The original SQLite DB shipped before these columns existed. We try each
    ADD COLUMN individually and swallow the "duplicate column name" error so
    re-runs are safe. Production deployments on Postgres should use Alembic;
    this helper exists so existing local dev DBs keep working.
    """
    from sqlalchemy import text

    new_cols = [
        ("ip_allowlist", "JSON"),
        ("domain_allowlist", "JSON"),
        ("tags", "JSON"),
        ("is_disabled", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("disable_reason", "VARCHAR"),
        ("monthly_token_limit", "INTEGER"),
        ("monthly_request_limit", "INTEGER"),
        ("monthly_token_count", "INTEGER DEFAULT 0"),
        ("monthly_request_count", "INTEGER DEFAULT 0"),
        ("monthly_cost_usd", "INTEGER DEFAULT 0"),
        ("organization", "VARCHAR"),
    ]
    with engine.begin() as conn:
        for name, decl in new_cols:
            try:
                conn.execute(text(f"ALTER TABLE api_keys ADD COLUMN {name} {decl}"))
            except Exception:
                # Column already exists (or backend doesn't support the
                # ALTER). Either way: move on.
                pass