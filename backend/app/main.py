import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


# Structured-ish logging: a stable format that puts level/timestamp first so
# production log shippers (CloudWatch, Loki, Datadog) can parse without regex.
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s :: %(message)s"
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format=LOG_FORMAT,
)
logger = logging.getLogger("novamind")


def _bootstrap_database() -> None:
    """Create tables, run idempotent ALTERs, seed the admin user.

    Imports are inside the function to keep the module-level import graph
    fast (matters for serverless cold-starts), and to avoid circular
    imports between `database`, `models`, and `security`.
    """
    from app.core.database import Base, engine, SessionLocal
    from app.models.api_key import ensure_api_key_columns

    logger.info("Running Base.metadata.create_all()")
    Base.metadata.create_all(bind=engine)
    # Idempotent ALTER for developer-platform columns added 2026-06.
    ensure_api_key_columns(engine)

    # Seed initial admin only when the users table is empty. Cheap COUNT(*) so
    # we never reseed on a warm restart.
    from app.models.user import User
    from app.core.security import get_password_hash
    from app.schemas.user import UserCreate

    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin_in = UserCreate(
                email="admin@novamind.ai",
                password="admin123",
                username="admin",
                full_name="System Administrator",
                is_admin=True,
            )
            db.add(User(
                email=admin_in.email,
                username=admin_in.username,
                full_name=admin_in.full_name,
                hashed_password=get_password_hash(admin_in.password),
                is_admin=True,
                is_active=True,
                is_verified=True,
            ))
            db.commit()
            logger.info("Created initial admin user admin@novamind.ai")
    except Exception as exc:  # pragma: no cover - operational
        logger.warning("Initial admin seed failed: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifecycle: optional DB bootstrap, then yield, then dispose engine.

    On Vercel/serverless the lifespan fires once per cold-start. The bootstrap
    is gated by RUN_DB_MIGRATIONS so production deploys can flip it off after
    the first successful boot — saves ~1s of cold-start latency.
    """
    logger.info(
        "NovaMind starting up (vercel=%s, migrations=%s, log_level=%s)",
        settings.VERCEL, settings.RUN_DB_MIGRATIONS, settings.LOG_LEVEL,
    )
    if settings.RUN_DB_MIGRATIONS:
        try:
            _bootstrap_database()
        except Exception as exc:  # pragma: no cover - keep app alive even if seed fails
            logger.error("DB bootstrap failed (continuing anyway): %s", exc)

    yield

    logger.info("NovaMind shutting down — closing DB engine")
    try:
        from app.core.database import engine
        engine.dispose()
    except Exception as exc:  # pragma: no cover - best-effort cleanup
        logger.warning("DB engine dispose failed: %s", exc)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS: BACKEND_CORS_ORIGINS is a comma-separated allowlist. The Vercel preview
# regex is opt-in via ALLOW_VERCEL_PREVIEWS — keep it off in production.
_cors_origins = [o.strip() for o in settings.BACKEND_CORS_ORIGINS.split(",") if o.strip()]
_cors_kwargs = dict(
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.ALLOW_VERCEL_PREVIEWS:
    _cors_kwargs["allow_origin_regex"] = r"https://.*\.vercel\.app"
app.add_middleware(CORSMiddleware, **_cors_kwargs)

# Initialize audit logger — paths are platform-aware:
#   /tmp/audit.log    on Vercel (only writable directory)
#   /app/logs/        in Docker
#   ./logs/           in local dev
_log_dir = (
    "/tmp" if settings.VERCEL else
    os.environ.get("AUDIT_LOG_DIR") or
    ("/app/logs" if os.path.isdir("/app") and os.access("/app", os.W_OK) else "./logs")
)
os.makedirs(_log_dir, exist_ok=True)
from app.core.audit_logging import init_audit_logger
init_audit_logger(os.path.join(_log_dir, "audit.log"))

# Rate limiting middleware (env-driven defaults via Settings).
from app.core.rate_limiting import RateLimitMiddleware
app.add_middleware(
    RateLimitMiddleware,
    times=settings.RATELIMIT_DEFAULT_PER_MIN,
    seconds=60,
    auth_times=settings.RATELIMIT_AUTH_PER_MIN,
    exclude_paths=["/docs", "/redoc", "/openapi.json", "/health"],
)

# Usage logging middleware (per-endpoint counters, billing).
from app.core.usage_logging import UsageLoggingMiddleware
app.add_middleware(
    UsageLoggingMiddleware,
    exclude_paths=["/docs", "/redoc", "/openapi.json", "/favicon.ico"],
)

from app.api.v1 import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)

# OpenAI-compatible surface — mounted at /v1/* (NOT /api/v1/v1/*) so SDKs
# that target OpenAI's base URL can talk to NovaMind with just a base-URL swap.
from app.api.endpoints.v1_compat import router as v1_compat_router
app.include_router(v1_compat_router, prefix="/v1", tags=["v1-compat"])


@app.get("/")
def root():
    return {
        "message": "Welcome to NovaMind AI",
        "api": settings.API_V1_STR,
        "v1_compat": "/v1",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Liveness/readiness probe — never raises, never blocks.

    Used by load balancers and `docker compose ps` to detect a wedged process.
    Pings the DB with a SELECT 1 so a stale connection pool fails fast instead
    of hanging the next request.
    """
    db_ok = True
    db_error = None
    try:
        from sqlalchemy import text
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - operational
        db_ok = False
        db_error = str(exc)

    status = "ok" if db_ok else "degraded"
    payload = {"status": status, "version": settings.VERSION, "db": "ok" if db_ok else "down"}
    if db_error and not db_ok:
        payload["db_error"] = db_error
    return payload


# Vercel serverless entrypoint. Mangum wraps our ASGI app into the AWS
# Lambda-style handler Vercel invokes. Locally uvicorn imports `app` directly.
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")  # lifespan handled above explicitly
except ImportError:  # pragma: no cover - mangum only needed on Vercel
    handler = None