# Get a permanent NovaMind URL (no more hourly tunnel deaths)

## What we're doing

Switching from Cloudflare's **quick tunnels** (random `*.trycloudflare.com` URLs that die every hour) to a **named tunnel** with a stable hostname. Result: a fixed URL like `https://api.your-domain.com` that stays up 24/7/365 with no rotations.

The architecture becomes:

```
Internet → api.your-domain.com (Cloudflare edge)
              ↓
          named tunnel (cloudflared as a service, autostart on boot)
              ↓
          localhost:8000 (FastAPI backend, runs as a service)
              ↓
          backend/novamind.db (SQLite, persistent)
              ↓
          localhost:11434 (Ollama, runs as a service)
```

Once this is done, the live site (`web-ivory-eta-87.vercel.app`) just needs ONE redeploy with the new `NEXT_PUBLIC_API_URL` baked in — and the URL never changes again.

## The two things you need to do (interactive, ~20 min total)

### Step 1 — Get a free domain on Cloudflare (~15 min)

1. **Pick one of these free-domain providers** and register a hostname:
   - **eu.org** (https://nic.eu.org) — most reputable, but approval takes 1-14 days. Not great for "right now".
   - **DuckDNS** (https://www.duckdns.org) — instant, free, gives you `yourname.duckdns.org`. Recommended for this use case.
   - **freedns.afraid.org** — instant, free.
   - **No-IP** (https://www.noip.com) — free tier exists, but wants you to confirm monthly.

   **Recommendation: DuckDNS.** Sign in with Google/GitHub, claim any subdomain (e.g. `novamind-shah.duckdns.org`).

2. **Add the domain to Cloudflare**:
   - Go to https://dash.cloudflare.com → "+ Add a Site"
   - Enter `duckdns.org` (NOT your subdomain — Cloudflare needs the apex domain)
   - Select **Free plan**
   - Cloudflare will give you 2 nameservers (something like `celia.ns.cloudflare.com`, `sid.ns.cloudflare.com`)
   - Go to DuckDNS → your subdomain → "update" the nameservers to Cloudflare's two
   - Wait 5-30 min for Cloudflare to detect the nameservers. Status will go from "Pending" to "Active".

### Step 2 — Create the named tunnel + DNS record (1 command each, on YOUR machine)

Once the domain shows "Active" in Cloudflare, run these in **PowerShell as Administrator**:

```powershell
# Login to Cloudflare (opens a browser tab; pick the duckdns.org account)
cloudflared tunnel login

# Create a named tunnel. UUID is generated automatically.
cloudflared tunnel create novamind
# Output: Created tunnel novamind with id a1b2c3d4-... and a credentials file at
#         C:\Users\DEVANG\.cloudflared\<UUID>.json

# Create a DNS record: api.your-subdomain.duckdns.org -> the tunnel
# (replace 'novamind-shah.duckdns.org' with YOUR subdomain from Step 1)
cloudflared tunnel route dns novamind api.novamind-shah.duckdns.org
```

That gives you a **permanent URL**: `https://api.novamind-shah.duckdns.org`

### Step 3 — Configure the tunnel to point at the backend (I'll do this)

Once you tell me the URL from Step 2, I write `~/.cloudflared/config.yml`:

```yaml
tunnel: novamind
credentials-file: C:\Users\DEVANG\.cloudflared\<UUID>.json

ingress:
  - hostname: api.novamind-shah.duckdns.org
    service: http://localhost:8000
  - service: http_status:404
```

### Step 4 — Install cloudflared as a Windows service (I'll do this)

```powershell
cloudflared service install
```

This registers cloudflared as a Windows service that:
- Starts automatically on boot
- Restarts on crash (within ~10 seconds)
- Runs under the SYSTEM account
- Survives logouts, reboots, power blips

After install:
```powershell
Start-Service cloudflared
```

### Step 5 — Update the watchdog so it doesn't try to redeploy Vercel on URL change (I'll do this)

The current `scripts/watch-tunnel.ps1` was written for quick tunnels and runs `vercel --prod` on every URL change. With a named tunnel, the URL is FIXED, so the watchdog just needs to:
- Restart `cloudflared` if it dies
- Restart `uvicorn` if the backend dies
- Health-check every 30s

I'll rewrite it to be both simpler and more robust (a single `Start-Service` for both, plus a health loop).

### Step 6 — Rebake the Vercel build (I'll do this)

One final deploy:
```bash
cd web
vercel --prod -b NEXT_PUBLIC_API_URL=https://api.novamind-shah.duckdns.org/api/v1 -b NEXT_PUBLIC_USE_MOCK=false
```

After this, the live site at `https://web-ivory-eta-87.vercel.app` works against the permanent URL and never breaks again.

## What "forever alive" actually means

Once everything is set up:
- **Power outage** → Windows boots → cloudflared service starts → backend (also a service) starts → Ollama (also a service) starts. All within 30 seconds of boot.
- **Backend crashes** → watchdog detects via /health, restarts uvicorn within 60s.
- **Tunnel dies** → cloudflared service restarts itself (built into the Windows service wrapper). DNS stays the same.
- **URL rotates** → impossible. Named tunnels have fixed DNS.
- **Windows updates reboot the box** → everything comes back up automatically.

## What I can do right now (without your interactive steps)

Done — all three of these are now implemented:

- `scripts/watch-services.ps1` — simpler watchdog for the named-tunnel era. No Vercel redeploy (URL is fixed), no trycloudflare URL parsing. Just restarts `cloudflared` / `uvicorn` / `ollama` if any of them die.
- `scripts/install-services.ps1` — registers `novamind-backend` (uvicorn) and `novamind-ollama` (ollama) as Windows services with auto-start-on-boot and restart-on-crash. Run once as Administrator: `powershell -ExecutionPolicy Bypass -File scripts\install-services.ps1`
- `scripts/backup-db.ps1` — SQLite backup with rotation, used by the `NovaMind-DB-Backup` scheduled task the installer registers. Snapshots `backend/novamind.db` to OneDrive every 6 hours, keeps last 20 copies.

## Out of scope (be honest about limits)

- A free DuckDNS subdomain needs renewal every 30 days (DuckDNS sends an email). If you forget to renew, the URL stops resolving. **eu.org is permanent** but takes 1-14 days to approve. Pick DuckDNS for now, migrate to a paid domain later.
- Cloudflare's free tier has no SLA. In practice uptime is excellent, but if Cloudflare has an outage, the site is down. No way around that on free.
- The DB backup goes to OneDrive (or `Documents\NovaMind-Backups` if OneDrive isn't signed in). It's a snapshot, not real-time replication — there can be up to 6 hours of data loss in a worst-case disk failure.
