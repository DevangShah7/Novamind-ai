# Deployment & Tunneling

This directory contains the scripts that keep the NovaMind backend publicly
reachable and the helpers that push the frontend to Vercel.

## Quick reference

| What you want to do | Run this |
|---|---|
| Start the FastAPI backend on `127.0.0.1:8000` | `pwsh -File scripts\start-backend.ps1` |
| Keep the backend + public tunnel alive (auto-restart on crash) | `pwsh -File scripts\watch-tailscale-funnel.ps1` |
| Point the deployed Vercel frontend at a new backend URL | `pwsh -File scripts\update-vercel-api-url.ps1` (needs `VERCEL_TOKEN`) |
| Deploy the frontend to Vercel Production | `pwsh -File scripts\deploy-and-verify.ps1` (needs `VERCEL_TOKEN`) |
| One-shot login fix (asks for the token, then does everything) | `pwsh -File scripts\fix-login.ps1` |

## Public backend URL

The backend is exposed via **Tailscale Funnel**, not Cloudflare Quick Tunnel.

- Public URL: `https://novamind.taile50f6f.ts.net`
- Full API base: `https://novamind.taile50f6f.ts.net/api/v1`
- Health check: `https://novamind.taile50f6f.ts.net/health`

### Why Tailscale Funnel and not Cloudflare Quick Tunnel?

Cloudflare Quick Tunnels (`*.trycloudflare.com`) assign a **new random hostname
on every restart**. That made the frontend's `NEXT_PUBLIC_API_URL` invalid
every time the tunnel bounced, which manifested as
`ERR_NAME_NOT_RESOLVED` on every login attempt.

Tailscale Funnel gives us a **stable hostname** that survives reboots. The
URL never changes, so the Vercel env var is set once and stays correct
indefinitely.

### Tailscale requirements

- Tailscale installed (service is `Running`/`Automatic`, so it survives
  reboots)
- The `novamind` machine name is set with `tailscale set --hostname=novamind`
- Funnel is enabled on the tailnet (one-time, via the Tailscale admin
  console)
- `tailscale funnel --bg 8000` is what exposes the backend

### Backups / alternatives

If Tailscale is down, the legacy Cloudflare Quick Tunnel scripts are still
in this directory (`scripts\start-quick-tunnel.bat`,
`scripts\watch-quick-tunnel.ps1`, `scripts\setup-permanent-tunnel.ps1`).
They work but suffer from URL rotation; not recommended for production use.

## Watchdog behavior

`scripts\watch-tailscale-funnel.ps1` polls every 15 seconds and:

1. Checks `http://127.0.0.1:8000/health` — if not 200, runs
   `start-backend.ps1` to relaunch.
2. Runs `tailscale funnel status` — if Funnel is off, runs
   `tailscale funnel reset` then `tailscale funnel --bg 8000`.
3. Logs every state change to `logs\watchdog.out.log` and `logs\watchdog.err.log`.

## Vercel env contract

The frontend reads `NEXT_PUBLIC_API_URL` at build time. The value must
match the format `https://<host>/api/v1` (no trailing slash).

| Where | Value |
|---|---|
| `web\.env.local` (local dev) | `https://novamind.taile50f6f.ts.net/api/v1` |
| Vercel Project Settings → Environment Variables → Production | `https://novamind.taile50f6f.ts.net/api/v1` |
| Vercel Project Settings → Environment Variables → Preview (optional) | `https://novamind.taile50f6f.ts.net/api/v1` |
| Vercel Project Settings → Environment Variables → Development (optional) | `https://novamind.taile50f6f.ts.net/api/v1` |

Project ID: `prj_RGN8AqrCFqJJggNorZxroCVC4uRu`
Env var ID: `nvSFbxe6xeCB4arK`