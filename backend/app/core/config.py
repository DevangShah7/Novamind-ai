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

from pydantic import ConfigDict

import os


# pydantic 1.x's BaseSettings does NOT auto-read .env (only the v2
# `pydantic_settings` does). Since this project pins pydantic 1.x and
# pydantic-settings requires pydantic>=2.3 (see requirements.txt), we
# explicitly load the .env file with python-dotenv BEFORE Settings() is
# constructed so BACKEND_CORS_ORIGINS, ALLOW_VERCEL_PREVIEWS, etc.
# actually take effect. python-dotenv is already pinned at
# requirements.txt:29; `override=False` (the default) means real
# process env wins over .env, which is the safe behaviour.
try:
    from dotenv import load_dotenv

    # Look for .env next to the working directory, then walk up to the
    # repo root, then fall back to whatever dotenv finds. Missing files
    # are silently skipped (python-dotenv default).
    _here = os.path.dirname(os.path.abspath(__file__))
    _candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(_here), "..", ".env"),  # backend/.env
        os.path.join(os.path.dirname(_here), "..", "..", ".env"),  # repo root
    ]
    for _path in _candidates:
        if os.path.exists(_path):
            load_dotenv(_path, override=False)
            break
except ImportError:
    # python-dotenv not installed; nothing we can do. Real prod deploys
    # are expected to set env vars via the platform anyway.
    pass


class Settings(BaseSettings):
    PROJECT_NAME: str = "NovaMind AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # SECURITY: override this in production via the SECRET_KEY env var.
    # A placeholder is shipped so `uvicorn app.main:app` boots in dev.
    # In production, leaving this default is a startup error unless
    # `ALLOW_DEV_SECRET_KEY=1` is set explicitly. See
    # `_enforce_production_secret_key()` below.
    SECRET_KEY: str = "dev-only-change-me-in-production-9f8e7d6c5b4a3210"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    # Set to "1" to bypass the production SECRET_KEY guard. Use only
    # for local dev; do NOT set this in any deployed environment.
    ALLOW_DEV_SECRET_KEY: bool = False

    # ---------- Email / SMTP ----------
    # When SMTP_HOST is empty, the mailer falls back to a dev stub that
    # writes sent messages to `logs/dev-mail.log` so verification / reset
    # URLs are visible to the developer. Set all of these in `.env` to
    # send real mail from a deployment.
    #
    # The default SMTP_HOST is `smtp.gmail.com` (with STARTTLS on 587)
    # because Gmail is the genuinely-free path for solo developers
    # (Google account → 2-Step Verification → App password). To use
    # SendGrid / Mailgun / SES / Postmark, override SMTP_HOST and the
    # credentials below; the mailer treats the SMTP creds opaquely.
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    SMTP_FROM: str = "noreply@novamind.ai"
    SMTP_FROM_NAME: str = "NovaMind"

    # Gmail-friendly aliases. These mirror the SMTP_* fields but use
    # Google's own naming so a developer can copy-paste the two values
    # straight from the Google account page without translating.
    #   GMAIL_ADDRESS     -> SMTP_USERNAME
    #   GMAIL_APP_PASSWORD -> SMTP_PASSWORD
    # Setting the GMAIL_* pair overrides the SMTP_* pair at construction.
    GMAIL_ADDRESS: str = ""
    GMAIL_APP_PASSWORD: str = ""

    # ---------- Stripe (billing) ----------
    # Empty STRIPE_SECRET_KEY puts the billing endpoints into "mock mode":
    # checkout sessions resolve to an in-app `/billing/mock-checkout` page
    # and webhooks are simulated by clicking "Confirm" there. Set all
    # three of these to switch to real Stripe (test mode is fine).
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_BUSINESS: str = ""
    # Where Stripe should redirect back to after a successful checkout.
    # Defaults to the Vercel production URL; override in dev.
    PUBLIC_SITE_URL: str = "https://web-ivory-eta-87.vercel.app"

    # ---------- AI models ----------
    # The default public NovaMind model id for chat when the user
    # doesn't pick one. The actual engine is resolved by
    # ``alias_config``; this value is just the brand id surfaced
    # on the wire. List the public ids at `GET /api/v1/models`.
    DEFAULT_MODEL: str = "NovaMind-Chat"

    # ---------- Frontend (for email link generation) ----------
    # Where the email verification / password reset links point.
    # Defaults to localhost for dev; set this to your deployed
    # Vercel URL (or tunnel URL) in production so the links work
    # end-to-end.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

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

    # Ollama base URL — where the backend dispatches chat completions.
    # Default to localhost; override in `.env` when Ollama runs on a
    # different host (a managed backend points this at a remote Ollama
    # service, e.g. http://ollama.internal:11434 or a paid inference API).
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # pydantic-settings v2 reads .env from `model_config`, not the
    # legacy `class Config:` block (which only worked in pydantic v1).
    # We point at `.env` in the cwd so a `python -m uvicorn app.main:app`
    # invocation picks it up. Pydantic ignores missing files, so the
    # defaults still apply if `.env` doesn't exist. `extra="ignore"`
    # keeps the boot forgiving if `.env` contains keys we haven't
    # modeled yet (e.g. ALLOW_VERCEL_PREVIEWS being added without a
    # matching Settings field).
    model_config = ConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Known placeholder keys. Keeping the list here (not in the model body)
# makes the production guard self-documenting.
_PLACEHOLDER_SECRET_KEYS = {
    "dev-only-change-me-in-production-9f8e7d6c5b4a3210",
    "your-secret-key-here",
    "",
}


def _enforce_production_secret_key(s: "Settings") -> None:
    """Refuse to boot with a placeholder SECRET_KEY in production.

    The check is intentionally conservative: a placeholder key only
    blocks startup when BOTH `RUN_DB_MIGRATIONS` is true AND
    `ALLOW_DEV_SECRET_KEY` is not set. That keeps the developer
    experience (run uvicorn, get a working app) intact while making
    a real prod deploy require either a real key or an explicit
    acknowledgement via the env var.
    """
    if s.SECRET_KEY in _PLACEHOLDER_SECRET_KEYS:
        # Dev escape hatch: when explicitly allowed, print a one-time
        # warning so a misconfigured prod is still visible in logs.
        if s.ALLOW_DEV_SECRET_KEY:
            import warnings
            warnings.warn(
                "ALLOW_DEV_SECRET_KEY is set and SECRET_KEY is a "
                "placeholder. This is unsafe for production.",
                RuntimeWarning,
            )
            return
        if s.RUN_DB_MIGRATIONS:
            raise RuntimeError(
                "Refusing to start: SECRET_KEY is a placeholder. "
                "Set a real value in .env, or set ALLOW_DEV_SECRET_KEY=1 "
                "for local dev only."
            )


_enforce_production_secret_key(Settings())


def _apply_gmail_aliases(s: "Settings") -> "Settings":
    """If GMAIL_ADDRESS / GMAIL_APP_PASSWORD are set, mirror them onto
    SMTP_USERNAME / SMTP_PASSWORD so the mailer can stay SMTP-agnostic.

    This runs after `Settings()` so the two GMAIL_* fields win over any
    SMTP_* values the developer also set. Keeping the alias at the
    config layer (rather than inside `mailer.send_email`) means tests
    that build a `Settings()` directly get the same behavior.
    """
    if s.GMAIL_ADDRESS:
        s.SMTP_USERNAME = s.GMAIL_ADDRESS
    if s.GMAIL_APP_PASSWORD:
        s.SMTP_PASSWORD = s.GMAIL_APP_PASSWORD
    return s


settings = _apply_gmail_aliases(Settings())
