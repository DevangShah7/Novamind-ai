try:
    # Try to import from pydantic-settings (newer versions)
    from pydantic_settings import BaseSettings
except ImportError:
    # Fall back to pydantic (older versions). Some 1.x builds ship a
    # `BaseSettings` shim on the pydantic root; if neither resolves,
    # import the shim last so the error is meaningful.
    try:
        from pydantic import BaseSettings
    except ImportError as exc:  # pragma: no cover - explicit guidance
        raise ImportError(
            "Neither `pydantic_settings` nor `pydantic.BaseSettings` is "
            "available. Run `pip install pydantic-settings>=2`."
        ) from exc

import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "NovaMind AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # SECURITY: override this in production via the SECRET_KEY env var.
    # A placeholder is shipped so `uvicorn app.main:app` boots in dev.
    SECRET_KEY: str = "dev-only-change-me-in-production-9f8e7d6c5b4a3210"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # SQLite is the default for free-tier single-user deployments.
    # Switch to a postgresql:// URL when you have Postgres available.
    DATABASE_URL: str = "sqlite:///./novamind.db"

    # Redis URL — the app falls back to an in-memory shim if unreachable.
    # Set REDIS_REQUIRED=1 to fail fast instead.
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_REQUIRED: bool = False

    # ChromaDB (long-term vector memory) — optional; memory.py handles absence.
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000

    # Google OAuth (optional — auth still works without these)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # CORS: comma-separated allowlist. The Vercel preview regex is opt-in
    # (default off) so production deploys aren't accidentally wildcard-open.
    # Set ALLOW_VERCEL_PREVIEWS=1 to allow any *.vercel.app subdomain.
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"
    ALLOW_VERCEL_PREVIEWS: bool = False

    # Rate limit (per-minute) for unauthenticated and JWT-authenticated traffic.
    # Auth endpoints get a separate, tighter limit via RATELIMIT_AUTH_PER_MIN.
    RATELIMIT_DEFAULT_PER_MIN: int = 100
    RATELIMIT_AUTH_PER_MIN: int = 10

    # Logging: standard log level names (DEBUG / INFO / WARNING / ERROR).
    LOG_LEVEL: str = "INFO"

    # When True, run Base.metadata.create_all() + idempotent ALTERs + admin seed
    # on the first lifespan startup. Set False after the first deploy succeeds
    # to keep cold-starts fast on Vercel.
    RUN_DB_MIGRATIONS: bool = True

    # Auto-detect Vercel via its env var so we can branch logic later if needed.
    # Always False locally unless you set VERCEL=1 in your shell.
    VERCEL: bool = bool(os.environ.get("VERCEL"))

    # Ollama timeout — Vercel Pro caps at 60s, free at 10s. The chat endpoint
    # raises HTTP 504 when this fires so clients know to retry instead of
    # letting the platform hard-cut the request at its own (lower) limit.
    OLLAMA_TIMEOUT_S: float = 55.0

    class Config:
        case_sensitive = True


settings = Settings()
