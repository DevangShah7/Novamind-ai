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

## Production

Backend is deployed on Railway. See `railway.json` / `railway.toml`.

Required environment variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL URL, e.g. `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Redis URL, e.g. `redis://host:6379` |
| `CHROMA_HOST` | ChromaDB host |
| `CHROMA_PORT` | ChromaDB port |
| `SECRET_KEY` | JWT signing secret (random, long) |
| `BACKEND_CORS_ORIGINS` | Comma-separated allowed origins (e.g. `https://web-ivory-eta-87.vercel.app`) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (optional) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret (optional) |
| `GOOGLE_REDIRECT_URI` | OAuth callback (optional) |

## Endpoints

API root: `/api/v1`
OpenAPI docs: `/docs`
