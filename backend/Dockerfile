# Multi-stage isn't useful here — requirements.txt is small and a single
# stage keeps the Dockerfile honest. python:3.11-slim gives us a recent
# enough CPython for Pydantic 2 + FastAPI 0.95 without the size of full Debian.

FROM python:3.11-slim AS runtime

# Faster, deterministic installs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so the layer caches across code changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source last.
COPY . .

# Non-root user for the running process. UID 10001 is in the high range
# so it doesn't collide with host users on bind mounts.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin novamind \
    && mkdir -p /app/logs /app/data \
    && chown -R novamind:novamind /app
USER novamind

EXPOSE 8000

# Healthcheck hits the app's own /health route. The container is "healthy"
# only when uvicorn is accepting traffic AND the DB round-trip succeeds —
# exactly the signal a load balancer needs.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# Single worker by default — SQLite + uvicorn --workers >1 don't share state.
# Set UVICORN_WORKERS in compose for Postgres-backed multi-worker setups.
ENV UVICORN_WORKERS=1
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
