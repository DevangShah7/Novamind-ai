# NovaMind AI Backend

FastAPI service for the NovaMind AI OS.

## Local Development

```bash
# From repo root
docker-compose up backend
# Or
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Production Deployment

Two free options:

### Option A — Oracle Cloud Always-Free (permanent, recommended)
SQLite + in-memory cache. Truly free, runs 24/7, no card needed after signup.
See **[DEPLOY_ORACLE_FREE.md](../DEPLOY_ORACLE_FREE.md)** at repo root.

### Option B — Railway / Render (managed, free trial)
Postgres + Redis + ChromaDB. Easier setup, but eventually requires a card.
See `railway.json` / `railway.toml` + the older `DEPLOYMENT_GUIDE.md`.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **yes** (in prod) | dev fallback | JWT signing secret. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DATABASE_URL` | no | `sqlite:///./novamind.db` | SQLAlchemy URL. Use `postgresql://...` for Postgres. |
| `BACKEND_CORS_ORIGINS` | no | `http://localhost:3000` | Comma-separated allowed origins |
| `REDIS_URL` | no | `redis://localhost:6379` | Falls back to in-memory shim if unreachable |
| `REDIS_REQUIRED` | no | `false` | Set to `1` to crash on Redis unavailability |
| `CHROMA_HOST` | no | `localhost` | Optional; memory features degrade if absent |
| `CHROMA_PORT` | no | `8000` | ChromaDB HTTP port |
| `GOOGLE_CLIENT_ID` | no | empty | OAuth (optional) |
| `GOOGLE_CLIENT_SECRET` | no | empty | OAuth (optional) |
| `GOOGLE_REDIRECT_URI` | no | localhost | OAuth callback URL |
| `AUDIT_LOG_DIR` | no | `/app/logs` or `./logs` | Where audit logs are written |

## Endpoints

API root: `/api/v1`
OpenAPI docs: `/docs`

## Optional Dependencies

For ChromaDB-based long-term memory on a real deployment:

```bash
pip install -r requirements-optional.txt
```
