# Deploy the FastAPI backend to Vercel (free, permanent)

The frontend on Vercel currently can't reach the FastAPI service because
the old Cloudflare Quick Tunnel URL died and Vercel has no env vars set.
This guide deploys the backend to Vercel's free tier as a **second
project** alongside the frontend, gives it a stable URL, and wires the
frontend to it.

Why Vercel for the backend:

- You already have the Vercel CLI authenticated and the deploy flow
  working — no new platform to learn.
- The repo is already wired: `backend/vercel.json` builds the
  `api/index.py` Mangum entrypoint, `backend/api/index.py` re-exports
  `handler` from `app.main`, and `mangum` is in `requirements.txt`.
- The same `BACKEND_CORS_ORIGINS` allowlist + `ALLOW_VERCEL_PREVIEWS=1`
  already in the code works for both projects.
- Free tier covers a small FastAPI service. The 10s function timeout on
  the free plan is fine for login / chat because the stealth router falls
  back to the in-process rule engine when Ollama is unreachable.

The repo is already deployment-ready for Vercel:

- `backend/vercel.json` — `@vercel/python` builder for `api/index.py`
- `backend/api/index.py` — re-exports `handler` from `app.main`
- `backend/app/main.py` — wraps the ASGI app in `Mangum(app, lifespan="off")`
- `backend/requirements.txt` — `mangum==0.17.0` already pinned

---

## 1. Create a free Postgres database

The default `sqlite:///./novamind.db` doesn't work on Vercel — the
filesystem is read-only except for `/tmp`, so any data you write there is
lost between cold starts. Use a managed Postgres.

The repo is already set up to work with one:
`backend/app/core/database.py:18-23` uses `pool_pre_ping=True` and
`pool_recycle=280` to survive Neon's 5-minute idle disconnect.

Recommended: **Neon** (https://neon.tech) — 0.5 GB free, never sleeps,
great SQLAlchemy 1.4 compat. Or Supabase if you want a UI on top.

For Neon:
1. Sign in with GitHub.
2. **New Project** → region nearest you → Postgres 16.
3. Copy the **connection string** from the dashboard:
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`
4. Keep that URL handy — you'll paste it as a Vercel env var in step 3.

## 2. Create a second Vercel project for the backend

Open the Vercel dashboard at https://vercel.com/dashboard and:

1. Click **+ Add New** → **Project**.
2. Import the same `novamind-ai` GitHub repo.
3. On the configure screen:
   - **Project Name**: `novamind-api` (or anything unique).
   - **Root Directory**: click **Edit** and set it to `backend`. This is
     critical — Vercel needs to build from `backend/` so it sees
     `vercel.json` and `api/index.py` at the root of the build context.
   - **Framework Preset**: leave as **Other** (Vercel will read
     `backend/vercel.json` and pick `@vercel/python`).
4. Don't deploy yet. Click **Environment Variables** (still on the
   configure screen) and add each of the vars from step 3.
5. Click **Deploy**.

If Vercel says "No framework detected", it's because Root Directory
isn't set to `backend` — go back and fix that.

## 3. Set the environment variables

In the backend project's **Settings** → **Environment Variables** page,
add each of these (one per row, with values matching the desired
environment — Production, Preview, Development):

| Key | Value | Why |
|---|---|---|
| `SECRET_KEY` | A fresh random string | Generate with `python -c "import secrets;print(secrets.token_urlsafe(48))"`. The startup guard in `backend/app/core/config.py:179-198` refuses to boot with the default placeholder. |
| `DATABASE_URL` | The Neon connection string from step 1 | The backend uses SQLAlchemy; the `postgresql://…?sslmode=require` URL works out of the box. |
| `BACKEND_CORS_ORIGINS` | `https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app,http://localhost:3000` | Comma-separated. The vercel.app regex is enabled via the next row, so preview URLs work without redeploying. |
| `ALLOW_VERCEL_PREVIEWS` | `1` | So future preview URLs (`*.vercel.app`) work without redeploying the backend. |
| `FRONTEND_BASE_URL` | `https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app` | Used in email verification / password reset links. |
| `PUBLIC_SITE_URL` | `https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app` | Used in Stripe redirects (set even if Stripe is in mock mode). |
| `RUN_DB_MIGRATIONS` | `1` (first deploy only) | Tells the app to run `Base.metadata.create_all()` on boot. Flip to `0` after a successful first deploy. |
| `OLLAMA_BASE_URL` | *(leave empty)* | The stealth router falls back to the rule engine when Ollama is unreachable. Set this only if you have a hosted Ollama. |
| `GOOGLE_CLIENT_ID` | *(leave empty)* | Google sign-in stays disabled but the page still works. |
| `GOOGLE_CLIENT_SECRET` | *(leave empty)* | Same. |
| `SMTP_HOST` / `SMTP_USERNAME` / `SMTP_PASSWORD` | *(leave empty)* | Mail falls back to logging in `logs/dev-mail.log` (transient on Vercel, fine for dev). Real SMTP setup is out of scope for this fix. |

**After the first deploy succeeds**, edit `RUN_DB_MIGRATIONS` to `0` and
redeploy — keeps cold starts fast.

## 4. Smoke-test the backend

Once the deploy finishes, Vercel gives the backend a URL like
`https://novamind-api.vercel.app`. From your local PowerShell:

```powershell
# Root returns 200 (FastAPI's default / handler)
curl -i https://novamind-api.vercel.app/

# CORS preflight echoes the Vercel frontend origin
curl -i -X OPTIONS `
  -H "Origin: https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app" `
  -H "Access-Control-Request-Method: POST" `
  https://novamind-api.vercel.app/api/v1/auth/login
```

The second command should return
`Access-Control-Allow-Origin: https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app`.

If you get a 404 on the first call, check the **Root Directory** setting
in the Vercel project — it must be `backend`, not the repo root.

## 5. Wire the Vercel frontend to the new backend

In the **frontend** Vercel project (`novamind-ai`):

```powershell
cd E:\novamind-ai\web
vercel env add NEXT_PUBLIC_API_URL production
# paste: https://novamind-api.vercel.app/api/v1
vercel env add NEXT_PUBLIC_USE_MOCK false production
vercel --prod
```

After the redeploy, the production login page should:
- Stop logging `ERR_NAME_NOT_RESOLVED`
- Stop throwing React #418/#423
- Successfully POST to `/api/v1/auth/login` and route to `/chat` on success

## 6. Update local development

In `web/.env.local` and `backend/.env`, replace the dead Cloudflare
tunnel URL with the new Vercel URL so local dev talks to the same
backend as production.

`web/.env.local`:
```
NEXT_PUBLIC_API_URL=https://novamind-api.vercel.app/api/v1
NEXT_PUBLIC_USE_MOCK=false
```

`backend/.env`:
```
DATABASE_URL=postgresql://neondb_owner:<password>@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
FRONTEND_BASE_URL=https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app
PUBLIC_SITE_URL=https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app
BACKEND_CORS_ORIGINS=https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app,https://*.vercel.app,http://localhost:3000,http://127.0.0.1:3000
ALLOW_VERCEL_PREVIEWS=1
ALLOW_DEV_SECRET_KEY=1
SECRET_KEY=any-local-dev-string
```

## What this fixes and what it doesn't

**Fixed:**
- The login form on `https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app/login` reaches a real backend.
- React #418/#423 hydration errors stop firing (the `?demo=demo&go=1` auto-click path is wrapped in try/catch).
- The `favicon.ico` 404 is gone.
- The backend URL is permanent as long as your Vercel account is active.

**Not in scope (deferred):**
- Real SMTP so verification emails actually deliver.
- `GOOGLE_CLIENT_ID` for the deployed frontend.
- Custom domains.
- LLM-powered chat responses. The stealth router falls back to the rule engine when `OLLAMA_BASE_URL` is unset, so the chat surface stays usable, but you won't get real model output until you point it at a hosted Ollama.
- Vercel free tier has a 10-second function timeout. The rule engine is fast, so login / chat / list-chats are all under that. Anything that proxies to Ollama would need Vercel Pro (60s).

## Alternative platforms (if you change your mind later)

`backend/fly.toml` and `backend/.dockerignore` are also in the repo if
you want to deploy to Fly.io instead. To use them, follow the Fly.io
deployment steps in the commit history of `DEPLOY_BACKEND_FREE.md`.

## Rolling back

- Frontend: `vercel rollback` from inside `web/` reverts to the prior Vercel deployment.
- Backend: Vercel dashboard → Deployments tab → click the prior deployment → **Promote to Production**.
