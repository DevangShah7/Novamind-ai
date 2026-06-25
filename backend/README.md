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

`rich` (in `requirements-optional.txt`) gives the CLI nicer colours and panels.

## Local Engine

The default model behind `/api/v1/chats/{id}/messages` is `NovaMindLocal` —
a deterministic, rule-based engine that runs entirely in-process. It is
**not** a foundation model: it does not call any external API and ships
no model weights. It handles:

- greetings, "what can you do" / "help"
- time/date questions ("what day is tomorrow", "next monday")
- safe arithmetic via AST whitelisting (no `eval`, no name lookups)
- FAQ lookup against `backend/data/novamind_faq.json` (~30 hand-written entries)
- code-snippet recall against `backend/data/code_snippets.json` (Python, JS, SQL, Bash)
- conversation meta ("summarise our chat", "what did I say earlier")
- honest fallback that lists capabilities when nothing else matches

Swap to a different engine by changing the default in
`app/core/llm_service.py` (`get_llm_service("local")` is the current default).

## Terminal CLI

Run the same backend from a terminal:

```bash
# From the repo root
python -m backend.cli chat --user admin@novamind.ai --password admin123

# Or against any other NovaMind backend
python -m backend.cli chat \
  --api-url https://your-backend.example.com/api/v1 \
  --user you@example.com --password ********
```

Slash commands inside the REPL: `/help`, `/clear`, `/history`, `/chats`,
`/new [title]`, `/model`, `/logout`, `/quit`. Press Ctrl+C mid-stream to
cancel the current reply without exiting. Token is cached to
`~/.novamind/token`; conversation history to `~/.novamind/history.json`.
