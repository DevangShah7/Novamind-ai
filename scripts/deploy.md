# NovaMind AI — Self-Hosted Backend + Cloudflare Tunnels + Vercel Web

Generated 2026-06-28. Architecture for this path:

```
[Browser] ──► [Vercel: Next.js frontend (web-ivory-eta-87.vercel.app)]
                  │
                  │  HTTPS (NEXT_PUBLIC_API_URL)
                  ▼
[Cloudflare tunnel A] ──► [localhost:8000 — FastAPI on this Windows box]
                                  │
                                  │  HTTP (OLLAMA_BASE_URL)
                                  ▼
                          [localhost:11434 — Ollama on this Windows box]

         (Cloudflare tunnel B) ──► [localhost:11434 — Ollama]
                     ▲
                     │
       The web frontend talks DIRECTLY to tunnel B
       for /v1/* streaming (OpenAI-compatible surface).
       The backend talks to tunnel B for /api/v1/chat completions.
```

Why two tunnels? Two different endpoints need to be reachable from the
public internet — the FastAPI backend (for the main app) and Ollama (for
any direct `/v1/*` streaming the frontend might do). Ollama has no auth,
so we keep both tunnels restricted via `OLLAMA_ORIGINS` and
`BACKEND_CORS_ORIGINS`.

---

## Step 1 — Generate a real SECRET_KEY

In PowerShell, from the repo root:

```
cd backend
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy the output. You'll paste it into `backend\.env` in Step 3.

Pre-generated for convenience (use this OR generate your own):

```
wZA8UmaUK2dnIiqL8eqVZa9hZ55vCegd14AeJ-iA2NUDbDdN7TupuuGdlwyNu0Ya2izA1_KhEZswclwDmbb1hg
```

---

## Step 2 — Install cloudflared (Windows)

If you don't already have it:

```
winget install Cloudflare.cloudflared
```

Or download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
and put `cloudflared.exe` somewhere on PATH.

Verify:

```
cloudflared --version
```

---

## Step 3 — Create backend\.env (DO NOT commit)

Create `C:\Users\DEVANG\novamind-ai\backend\.env` with these contents:

```ini
# REQUIRED — paste your secret from Step 1
SECRET_KEY=wZA8UmaUK2dnIiqL8eqVZa9hZ55vCegd14AeJ-iA2NUDbDdN7TupuuGdlwyNu0Ya2izA1_KhEZswclwDmbb1hg

# SQLite lives in ./novamind.db (the repo's backend folder).
# Docker compose uses /app/data/novamind.db instead — see Step 4.
DATABASE_URL=sqlite:///./novamind.db

# CORS — must include the final Vercel web URL. Use 127.0.0.1:3000 for
# local dev too. ALLOW_VERCEL_PREVIEWS=1 lets preview deploys hit us.
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ALLOW_VERCEL_PREVIEWS=1

# Ollama on this same machine.
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT_S=300

# Not running on Vercel serverless — set False so we don't try to
# auto-migrate on every uvicorn reload.
RUN_DB_MIGRATIONS=True
VERCEL=0

# Redis / Chroma — optional, defaults to in-memory shim.
# REDIS_URL=redis://localhost:6379
# REDIS_REQUIRED=False
LOG_LEVEL=INFO
```

`.env` is already in `.gitignore` — do not commit it.

---

## Step 4 — Start the backend (Docker recommended)

Docker Desktop on Windows gives you a real Linux container with the
existing Dockerfile + docker-compose.yml. SQLite persists via the named
volume `novamind-data`.

From the repo root:

```
docker compose up -d --build backend
docker compose logs -f backend
```

You should see uvicorn start on `http://0.0.0.0:8000`. Ctrl-C out of
the log tail (the container stays up).

Verify on the host:

```
curl http://localhost:8000/health
```

Expected: `{"status":"ok","version":"0.1.0","db":"ok"}`

If `db: down`, the SQLite path is bad — see troubleshooting at the end.

**Without Docker** (if you don't have Docker Desktop), run it directly:

```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Either path works. Docker is recommended because it isolates Python deps
and gives you a clean restart story.

---

## Step 5 — Start Cloudflare tunnel A (backend)

Open a NEW PowerShell window and leave it running:

```
cloudflared tunnel --url http://localhost:8000 --no-autoupdate
```

Wait for the line:

```
Your quick tunnel has been created! Visit it at:
https://random-words-1234.trycloudflare.com
```

**Copy that URL.** This is your public backend URL. Leave the window
open — closing it kills the tunnel.

---

## Step 6 — Start Cloudflare tunnel B (Ollama)

Open ANOTHER new PowerShell window and leave it running:

```
cloudflared tunnel --url http://localhost:11434 --no-autoupdate
```

Same thing — copy the `https://random-words.trycloudflare.com` URL it
prints. This is your public Ollama URL.

You now have two tunnels open. Both will rotate their URLs if you
restart them, so don't restart unless you have to.

---

## Step 7 — Paste both URLs back to Claude

Reply with:

```
BACKEND_TUNNEL: https://xxxx.trycloudflare.com
OLLAMA_TUNNEL:   https://yyyy.trycloudflare.com
```

Claude will:
1. Commit the in-progress changes (`ollama_service.py`, `audit_logging.py`,
   `config.py`, `database.py`, `llm_service.py`, `redis.py`, `main.py`,
   `requirements.txt`, frontend `AppShell.tsx` / `MessageList.tsx` /
   `_app.tsx` / `chat/[id].tsx` / `types.ts` / `next.config.js`,
   and the new `backend/api/`, `backend/app/api/`,
   `backend/app/core/ollama_service.py`, etc.)
2. Push to `main`.
3. Print the exact env vars for Vercel (web project) including the
   final `NEXT_PUBLIC_API_URL`.
4. Print the `vercel --prod` command for web.

---

## Step 8 — Set Vercel env vars + deploy web

For the **web** project (`web-ivory-eta-87`):

1. https://vercel.com/dashboard → **web-ivory-eta-87** → **Settings** →
   **Environment Variables**.
2. Set:

   | Name | Value |
   |------|-------|
   | `NEXT_PUBLIC_USE_MOCK` | `false` |
   | `NEXT_PUBLIC_API_URL` | *(the BACKEND_TUNNEL URL from Step 7)* + `/api/v1` |

3. Save both for **Production** environment (Preview and Development
   are optional — only needed if you want preview URLs to work).

Then deploy:

```
cd web
vercel login            # first time only
vercel link             # link to web-ivory-eta-87
vercel --prod
```

Vercel prints the new production URL. Visit it. You should see the
**indigo** "Powered by NovaMind local engine" banner, not the amber
"Demo mode" one. If you see amber, `NEXT_PUBLIC_USE_MOCK` is still `true`
somewhere — check the Vercel dashboard and the `.env.local` in `web/`.

---

## Step 9 — Smoke test the full stack

1. Open the Vercel-deployed web URL in a fresh browser (incognito is
   cleanest for the first test).
2. Sign up with email + password.
3. Send a chat message. Latency should be ~5-20s per response
   (CPU-only Ollama is slow but correct).
4. Refresh the page → your chat is still there (proves SQLite +
   Cloudflare tunnel + Vercel are all wired together).
5. Open the same URL on your phone (WiFi or LTE) → log in with the
   same account → your chats appear there too.

If any of these fail, jump to the troubleshooting section.

---

## Ongoing operations

### Restarting tunnels

Every time you reboot the Windows machine, the two `cloudflared`
processes die. After reboot:

1. Restart Ollama (Start Menu → Ollama, or `ollama serve`).
2. Re-run the two `cloudflared tunnel --url ...` commands in separate
   PowerShell windows.
3. The URLs WILL have changed. You have to update
   `NEXT_PUBLIC_API_URL` on Vercel AND redeploy web.

**To avoid this**, set up a **named tunnel** on Cloudflare (free, takes
~15 min, requires a Cloudflare account but NOT a domain):

- `cloudflared tunnel login`
- `cloudflared tunnel create novamind-backend`
- `cloudflared tunnel route dns novamind-backend api.novamind.cfargotunnel.com`
- (edit `~/.cloudflared/config.yml` to map `api.novamind.cfargotunnel.com` → `http://localhost:8000`)
- `cloudflared tunnel run novamind-backend`

This gives you a **stable URL forever**. Claude can do this with you
later — for the first deploy, random URLs are fine.

### Updating the backend

```
git pull
cd backend
docker compose up -d --build backend
```

### Backup the SQLite DB

```
copy backend\novamind.db backend\novamind.db.bak
```

Or in Docker:

```
docker compose exec backend sqlite3 /app/data/novamind.db ".backup /app/data/novamind.db.bak"
docker compose cp backend:/app/data/novamind.db.bak ./novamind.db.bak
```

Run this weekly if you care about the data.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/health` returns `db: down` | SQLite path wrong or `data/` dir not writable in Docker | For Docker: `docker compose exec backend ls -la /app/data`. For local: check `backend/` is writable |
| Frontend shows "Backend unreachable" | Tunnel A is down OR Vercel has wrong `NEXT_PUBLIC_API_URL` | Re-check `cloudflared` window A is still open. Curl the tunnel URL from a different machine: `curl https://xxxx.trycloudflare.com/health` |
| Sign-up works but chat returns `504` | Tunnel B is down OR Ollama isn't running | Re-check `cloudflared` window B is open. Test locally: `curl http://localhost:11434/api/tags` |
| Browser console: `CORS policy` error | `BACKEND_CORS_ORIGINS` doesn't include your web URL | Edit `backend\.env`, add the exact `https://web-xxx.vercel.app` URL, restart backend |
| Chat hangs 60s then `504` (Vercel only — shouldn't happen here) | Wrong config — you shouldn't be on Vercel for the backend | Confirm `vercel.json` is NOT in `backend/` (it should only be at repo root if anywhere) |
| `docker compose` says "Cannot connect to Docker daemon" | Docker Desktop not running | Start Docker Desktop, wait for whale icon to settle, retry |
| Ollama responses take 20s+ | CPU-only inference (no GPU) | Expected on Windows laptops. Use smaller models (`llama3.2:1b`, `qwen2.5:1.5b`) or accept the latency |
| `module 'app' not found` when running uvicorn directly | You ran from the wrong directory | `cd backend` first, then `uvicorn app.main:app` |
| Backend container keeps restarting | `SECRET_KEY` empty OR `DATABASE_URL` malformed | `docker compose logs backend` — look for the actual exception |
