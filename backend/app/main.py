import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

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
    from app.models.user import ensure_user_columns
    from app.models.billing import ensure_billing_columns, seed_plans

    logger.info("Running Base.metadata.create_all()")
    Base.metadata.create_all(bind=engine)
    # Idempotent ALTER for developer-platform columns added 2026-06.
    ensure_api_key_columns(engine)
    # Idempotent ALTER for the new email-verification, password-reset,
    # lockout, and token-version columns added 2026-07.
    ensure_user_columns(engine)
    # Idempotent ALTER for the new billing columns (plan_id,
    # stripe_customer_id, credits_balance_cents) added 2026-07. The
    # plans / subscriptions / credit_ledger tables are created by
    # `create_all` above; this helper only handles backfill on the
    # existing `users` table.
    ensure_billing_columns(engine)
    # Idempotently seed the three default plans. Cheap query first so we
    # never rewrite operator-edited prices.
    db = SessionLocal()
    try:
        seed_plans(db=db)
    except Exception as exc:  # pragma: no cover - operational
        logger.warning("Plan seed failed: %s", exc)
    finally:
        db.close()

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
    # Ensure the local NovaMind foundation-model package is importable when
    # the chat handlers run ``from novamind import …`` (they live in
    # ``backend/app/services`` but the package itself is at the repo-root
    # sibling ``novamind-llm/``). Prepending it to sys.path is a no-op when
    # the package is already on PYTHONPATH (e.g. installed via pip).
    _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _novamind_llm = os.path.join(_repo_root, "novamind-llm")
    if os.path.isdir(_novamind_llm) and _novamind_llm not in sys.path:
        sys.path.insert(0, _novamind_llm)
        logger.info("Added %s to sys.path for local-novamind imports", _novamind_llm)
    # Propagate the local-novamind engine settings into ``os.environ`` so the
    # chat handlers (which read these directly via ``os.environ.get``) agree
    # with pydantic-settings. Without this, ``.env`` only feeds the Settings
    # model and ``neural_reachable()``/``get_local_llm()`` see nothing.
    for _key in (
        "NOVA_LOCAL_ENABLED",
        "NOVA_LOCAL_WEIGHTS",
        "NOVA_LOCAL_TOKENIZER",
        "NOVA_LOCAL_CONFIG",
        "NOVA_LOCAL_MAX_TOKENS",
        "NOVA_LOCAL_TEMPERATURE",
    ):
        _val = getattr(settings, _key, None)
        if _val not in (None, "", False):
            os.environ.setdefault(_key, str(_val))
    if settings.NOVA_LOCAL_ENABLED:
        logger.info(
            "NovaMind-Neural enabled (weights=%s, config=%s)",
            settings.NOVA_LOCAL_WEIGHTS, settings.NOVA_LOCAL_CONFIG,
        )
    if settings.RUN_DB_MIGRATIONS:
        try:
            _bootstrap_database()
        except Exception as exc:  # pragma: no cover - keep app alive even if seed fails
            logger.error("DB bootstrap failed (continuing anyway): %s", exc)

    # Warm the SDXL pipeline on a worker thread so the first image
    # request doesn't pay the ~10s torch + diffusers import cost in
    # the request path. Fire-and-forget — the app serves traffic
    # immediately while the warmup runs in the background.
    try:
        import asyncio
        from app.api.endpoints.documents_image import warm_sdxl_pipeline
        asyncio.get_event_loop().run_in_executor(None, warm_sdxl_pipeline)
        logger.info("sdxl warmup scheduled on background thread")
    except Exception as exc:  # pragma: no cover - best-effort warmup
        logger.warning("sdxl warmup scheduling failed: %s", exc)

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


# Safe RequestValidationError handler.
#
# Default FastAPI handler calls ``jsonable_encoder`` on the parsed
# request body to attach it to the 422 response. That encoder calls
# ``bytes.decode('utf-8')`` on any bytes value, which crashes with
# UnicodeDecodeError when the body is binary (e.g. a PNG uploaded to
# an endpoint that expected JSON). The crash surfaces as a 500 with
# the connection half-closed, which browsers report as ``ERR_FAILED``.
#
# This handler walks the validation errors and replaces any bytes
# input with a short, safe marker before serializing, so the 422
# goes out cleanly with a useful message. The end user still sees
# the correct status code; we just don't include the unreadable
# binary blob in the response payload.
@app.exception_handler(RequestValidationError)
async def _safe_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    safe_errors = []
    for err in exc.errors():
        err_copy = dict(err)
        # ``ctx`` may carry the offending value; sanitize it.
        ctx = err_copy.get("ctx")
        if isinstance(ctx, dict):
            new_ctx = {}
            for k, v in ctx.items():
                if isinstance(v, (bytes, bytearray)):
                    new_ctx[k] = (
                        f"<{len(v)} bytes of binary data - "
                        f"this endpoint expects {err_copy.get('loc', ['?'])[-1]} "
                        f"as JSON, not a file upload>"
                    )
                else:
                    new_ctx[k] = v
            err_copy["ctx"] = new_ctx
        # ``input`` may also carry the raw value. Replace bytes with
        # a placeholder so JSON serialization never tries to decode.
        if isinstance(err_copy.get("input"), (bytes, bytearray)):
            err_copy["input"] = (
                f"<{len(err_copy['input'])} bytes of binary data>"
            )
        safe_errors.append(err_copy)
    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors},
    )


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


# NovaMind Apps — serve compiled app files straight off disk for the
# preview iframe.  Mounted at ``/apps/preview/{app_id}/{rel:path}`` so it
# sits OUTSIDE the JWT-protected ``/api/v1/*`` surface — the iframe
# needs to load assets without an Authorization header.  ``storage.read_file``
# already enforces path-traversal safety, so the route is a thin shell.
from fastapi import HTTPException, Request
from fastapi.responses import Response
from app.services import apps as apps_svc
from app.services.apps.storage import file_path as _app_file_path


@app.get("/apps/preview/{app_id}/{rel:path}")
def preview_app_file(app_id: str, rel: str):
    """Serve a single compiled app file.  404s if the app is gone."""
    if apps_svc.get_app(app_id) is None:
        raise HTTPException(status_code=404, detail="App not found")
    try:
        body = apps_svc.read_file(app_id, rel)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if body is None:
        # Fall back to index.html so the iframe can survive deep links.
        body = apps_svc.read_file(app_id, "index.html")
        rel = "index.html"
        if body is None:
            raise HTTPException(status_code=404, detail="File not found")
    # Map common extensions so the browser interprets them sensibly.
    ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
    media_type = {
        "html": "text/html; charset=utf-8",
        "css": "text/css; charset=utf-8",
        "js": "application/javascript; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "svg": "image/svg+xml",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "ico": "image/x-icon",
        "txt": "text/plain; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
    }.get(ext, "application/octet-stream")
    return Response(content=body, media_type=media_type)

# OpenAI-compatible surface — mounted at /v1/* (NOT /api/v1/v1/*) so SDKs
# that target OpenAI's base URL can talk to NovaMind with just a base-URL swap.
from app.api.endpoints.v1_compat import router as v1_compat_router
app.include_router(v1_compat_router, prefix="/v1", tags=["v1-compat"])

# Product surface — /v1/responses, /v1/vision, /v1/images/generations,
# /v1/audio/*, /v1/video/generations, /v1/documents. Same engine pool,
# same auth, same quota gate as the compat surface above.
from app.api.endpoints.v1_products import router as v1_products_router
app.include_router(v1_products_router, prefix="/v1", tags=["v1-products"])

# Webhook + organization management — also under /v1/* with API-key auth.
from app.api.endpoints.webhooks import router as webhooks_router
app.include_router(webhooks_router, prefix="/v1", tags=["v1-webhooks"])
from app.api.endpoints.organizations import router as organizations_router
app.include_router(organizations_router, prefix="/v1", tags=["v1-organizations"])


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
    # Engine health — distinct from "backend up" because Ollama can be
    # down while the backend still serves traffic (it just falls back
    # to NovaMindLocal). The UI surfaces this in the model picker.
    try:
        from app.core.ollama_service import ollama_reachable
        payload["engines"] = {
            "ollama": "up" if ollama_reachable() else "down",
            "local": "up",
        }
    except Exception as exc:  # pragma: no cover - operational
        payload["engines"] = {"ollama": "unknown", "local": "up", "error": str(exc)}
    return payload


@app.get("/ready")
def ready():
    """Readiness probe — returns 200 only when the backend AND at least
    one LLM engine are reachable. For Railway / Render / k8s healthcheck
    targets that should gate traffic on engine availability, not just
    process liveness.

    NovaMindLocal is always available (in-process), so readiness
    collapses to "DB reachable" in practice — but we still probe
    Ollama so operators can see engine status in the 200 payload.
    """
    db_ok = True
    try:
        from sqlalchemy import text
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        db_ok = False
    ollama_up = False
    try:
        from app.core.ollama_service import ollama_reachable
        ollama_up = ollama_reachable()
    except Exception:
        pass
    if db_ok:
        return {"ready": True, "db": "ok", "ollama": "up" if ollama_up else "down", "local": "up"}
    from fastapi import HTTPException
    raise HTTPException(
        status_code=503,
        detail={"ready": False, "db": "down", "ollama": "up" if ollama_up else "down"},
    )


# Vercel serverless entrypoint. Mangum wraps our ASGI app into the AWS
# Lambda-style handler Vercel invokes. Locally uvicorn imports `app` directly.
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")  # lifespan handled above explicitly
except ImportError:  # pragma: no cover - mangum only needed on Vercel
    handler = None