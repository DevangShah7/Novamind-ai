# Deploy the FastAPI backend to Fly.io (free, permanent)

The frontend on Vercel currently can't reach the FastAPI service because
the old Cloudflare Quick Tunnel URL died and Vercel has no env vars set.
This guide deploys the backend to Fly.io's free tier, gives it a stable
public URL, and wires the Vercel frontend to it.

Fly.io's free tier gives you 3 shared VMs that can run 24/7 for $0
(plus 3 GB of persistent volume storage if you need it). The URL
(`https://<app-name>.fly.dev`) is permanent as long as the account
stays in good standing — no 30-day trial, no surprise charges.

The repo is already deployment-ready:

- `backend/Dockerfile` — Python 3.11-slim, non-root user, healthcheck on `/health`
- `backend/fly.toml` — app name, region, [build] block, [services] listener on port 8000, http_check on `/health`
- `backend/.dockerignore` — keeps the build context clean

The backend uses `Base.metadata.create_all()` on startup when
`RUN_DB_MIGRATIONS=1`, so a fresh Postgres database needs no Alembic
migrations before the first deploy.

---

## 1. Install the Fly CLI and sign in

```bash
# macOS / Linux
curl -L https://fly.io/install.sh | sh

# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex

fly auth login
```

## 2. Create a free Postgres database

Fly's own Postgres is paid. The free path is a managed Postgres from
[Neon](https://neon.tech) (recommended — 0.5 GB free, never sleeps,
great SQLAlchemy 1.4 compat) or [Supabase](https://supabase.com) (500 MB
free, sleep after 1 week of inactivity).

For Neon:
1. Sign in with GitHub.
2. **New Project** → region nearest you (Mumbai `ap-south-1` is fine) → Postgres 16.
3. Copy the **connection string** from the dashboard. It looks like:
   `postgresql://user:pass@ep-xxx-xxx.ap-south-1.aws.neon.tech/neondb?sslmode=require`
4. **Important**: turn off "Auto-suspend" if you want the connection
   pool to stay warm. Free tier still has it disabled by default;
   leaving it on costs nothing extra but the first request after a
   quiet period will be slow.

Keep that URL handy — you'll paste it as a Fly secret in step 4.

## 3. Create the Fly app

From the repo root:

```bash
cd backend
fly launch --no-deploy --copy-config
```

`--copy-config` makes Fly use the existing `fly.toml` instead of
generating a fresh one. When prompted:
- **App name**: `novamind-api` (or anything unique; if the name is taken
  Fly will tell you, then edit `app = "..."` at the top of `fly.toml`).
- **Region**: `bom` (Mumbai) or whatever is closest to your users.
- **Postgres**: say **No** — we use Neon.
- **Redis**: say **No** — not needed.

This creates the app on Fly without deploying yet. It also provisions
a `.fly/` directory and may add a `fly.toml` section for the deploy
secrets; review the diff with `git diff backend/fly.toml` and commit
anything sensible.

## 4. Set the secrets

Fly secrets are environment variables that aren't visible in the public
app config. Set them all in one command:

```bash
fly secrets set \
  SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  DATABASE_URL="postgresql://user:pass@ep-xxx.ap-south-1.aws.neon.tech/neondb?sslmode=require" \
  BACKEND_CORS_ORIGINS="https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app,http://localhost:3000" \
  ALLOW_VERCEL_PREVIEWS="1" \
  FRONTEND_BASE_URL="https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app" \
  PUBLIC_SITE_URL="https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app"
```

Notes:
- `SECRET_KEY` is mandatory. The startup guard in
  `backend/app/core/config.py` refuses to boot with the default
  placeholder key.
- `DATABASE_URL` is the Neon connection string from step 2.
- `BACKEND_CORS_ORIGINS` is a comma-separated allowlist. The vercel.app
  regex is enabled via `ALLOW_VERCEL_PREVIEWS=1`, so you don't need to
  list every preview URL.
- `OLLAMA_BASE_URL` is intentionally **not** set. The stealth router
  falls back to the rule engine when Ollama is unreachable, so chat
  works; only LLM-powered responses degrade.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are intentionally **not**
  set. The frontend already renders a disabled "Google sign-in (not
  configured)" placeholder when the client ID is empty.
- `SMTP_*` are intentionally **not** set. The mailer falls back to
  writing verification emails to `logs/dev-mail.log`. That file is
  ephemeral on Fly (the VM's disk resets on every deploy), so for
  real verification emails you'd add a managed SMTP later.

## 5. Deploy

```bash
fly deploy
```

Watch the logs:

```bash
fly logs
```

Look for:
- `Application startup complete.`
- `Uvicorn running on http://0.0.0.0:8000`
- `Running Base.metadata.create_all()` (first deploy only)
- `Created initial admin user admin@novamind.ai` (first deploy only)

If the boot fails with `Refusing to start: SECRET_KEY is a placeholder`,
you forgot the `SECRET_KEY` secret. If you see Postgres connection
errors, double-check the `DATABASE_URL` — Neon requires `?sslmode=require`.

## 6. Flip `RUN_DB_MIGRATIONS` to 0

After the first successful boot, the `users` table exists. Stop
re-running `create_all()` on every deploy:

```bash
fly secrets unset RUN_DB_MIGRATIONS
# (the env block in fly.toml already has RUN_DB_MIGRATIONS = "1";
# change it to "0" and re-deploy)
```

Or simpler: just edit `backend/fly.toml` to flip `RUN_DB_MIGRATIONS = "0"`
and re-run `fly deploy`. Subsequent deploys skip the create_all
round-trip and boot faster.

## 7. Smoke-test the backend

From your local machine:

```bash
# Root returns 200 (FastAPI's default / handler)
curl -i https://novamind-api.fly.dev/

# CORS preflight echoes the Vercel origin
curl -i -X OPTIONS \
  -H "Origin: https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app" \
  -H "Access-Control-Request-Method: POST" \
  https://novamind-api.fly.dev/api/v1/auth/login
```

The second command should return
`Access-Control-Allow-Origin: https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app`.

## 8. Wire the Vercel frontend to the new backend

```bash
cd web
vercel env add NEXT_PUBLIC_API_URL production
# paste: https://novamind-api.fly.dev/api/v1
vercel env add NEXT_PUBLIC_USE_MOCK false production
vercel --prod
```

After the redeploy, the production login page should:
- Stop logging `ERR_NAME_NOT_RESOLVED`
- Stop throwing React #418/#423
- Successfully POST to `/api/v1/auth/login` and route to `/chat` on success

## 9. Update local development

In `web/.env.local` and `backend/.env`, replace the dead Cloudflare
tunnel URL with the new Fly URL so local dev talks to the same
backend as production.

`web/.env.local`:
```
NEXT_PUBLIC_API_URL=https://novamind-api.fly.dev/api/v1
NEXT_PUBLIC_USE_MOCK=false
```

`backend/.env`:
```
FRONTEND_BASE_URL=https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app
PUBLIC_SITE_URL=https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app
BACKEND_CORS_ORIGINS=https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app,https://*.vercel.app,http://localhost:3000,http://127.0.0.1:3000
ALLOW_VERCEL_PREVIEWS=1
```

## What this fixes and what it doesn't

**Fixed:**
- The login form on `https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app/login` reaches a real backend.
- React #418/#423 hydration errors stop firing (the `?demo=demo&go=1` auto-click path is wrapped in try/catch).
- The `favicon.ico` 404 is gone.
- The backend URL is permanent as long as your Fly account is active.

**Not in scope (deferred):**
- Real SMTP so verification emails actually deliver instead of being written to ephemeral logs.
- `GOOGLE_CLIENT_ID` for the deployed frontend (the disabled placeholder still works).
- Custom domains on Vercel or Fly.
- LLM-powered chat responses. The stealth router falls back to the rule engine when `OLLAMA_BASE_URL` is unset, so the chat surface stays usable, but you won't get real model output until you point it at a hosted Ollama.

## Rolling back

If a deploy breaks something:
- `fly releases` lists prior releases; `fly releases rollback <id>` reverts to a known-good one.
- For the frontend, `vercel rollback` from inside `web/` reverts to the prior Vercel deployment.
