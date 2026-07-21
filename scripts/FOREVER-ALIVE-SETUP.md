# Forever-alive setup — interactive steps

The 5 things you need to do (interactive). Everything else is already done.

## What's already running (right now, in this session)

- ✅ `uvicorn` is up on `http://127.0.0.1:8000` — backend responding to `/health`
- ✅ `ollama` is up on `http://127.0.0.1:11434` — LLM server responding
- ✅ `watch-services.ps1` is running detached, monitoring all 3 services
- ✅ `nssm` is installed (path needs a new shell to refresh)
- ✅ `cloudflared.exe` is at `C:\Program Files (x86)\cloudflared\cloudflared.exe`

## What's pending (you)

### Step 1 — Register a free DuckDNS subdomain (2 min)

1. Open https://www.duckdns.org
2. Sign in with Google or GitHub
3. Type a name in the "create subdomain" box — e.g. `novamind-devang`
4. Click "add domain"
5. **Write down the subdomain** (e.g. `novamind-devang`)

### Step 2 — Add `duckdns.org` to Cloudflare (5–15 min, mostly waiting)

1. Open https://dash.cloudflare.com → "+ Add a Site"
2. Enter **exactly** `duckdns.org` (the apex, NOT your subdomain) → Free plan
3. Cloudflare shows 2 nameservers (something like `celia.ns.cloudflare.com` and `sid.ns.cloudflare.com`)
4. Go back to DuckDNS → your subdomain → in the "update" box, paste the two nameservers (one per line) → click "update"
5. Wait 5–30 min for Cloudflare to detect them. Status flips from "Pending" to "Active" when ready.

### Step 3 — Create the named tunnel (2 min, in **Admin** PowerShell)

Open a fresh **Administrator** PowerShell and run:

```powershell
cloudflared tunnel login
# (browser opens; pick the duckdns.org Cloudflare account)
cloudflared tunnel create novamind
# Output: Created tunnel novamind with id a1b2c3d4-...
#         (the UUID is also the filename of the credentials file in C:\Users\DEVANG\.cloudflared\)
cloudflared tunnel route dns novamind api.novamind-devang.duckdns.org
# (replace novamind-devang with YOUR subdomain from Step 1)
```

**Write down:**
- The **UUID** (e.g. `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
- Your **subdomain** (e.g. `novamind-devang`)

### Step 4 — Hand off to me

Tell me the UUID and the subdomain. I'll run:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\DEVANG\novamind-ai\scripts\setup-permanent-tunnel.ps1 `
    -TunnelId <UUID> `
    -Subdomain <your-subdomain> `
    -PublicUrl https://api.<your-subdomain>.duckdns.org
```

That one command will:
- Write `~/.cloudflared/config.yml`
- Install `cloudflared` as a Windows service (auto-start on boot, auto-restart on crash)
- Start the service and verify the public URL is healthy
- Update `web/.env.local` with the new URL

### Step 5 — Rebake Vercel (one last time, ~30 sec)

The script will print the final command — just paste it:

```powershell
cd C:\Users\DEVANG\novamind-ai\web
vercel --prod -b NEXT_PUBLIC_API_URL=https://api.<your-subdomain>.duckdns.org/api/v1 -b NEXT_PUBLIC_USE_MOCK=false
```

After that, **the URL never changes again**.

## Auto-restart matrix (all true after the steps above)

| Service | Auto-starts on boot? | Auto-restarts on crash? | How |
|---|---|---|---|
| cloudflared | ✅ | ✅ (within 5s) | Windows service via `cloudflared service install` |
| uvicorn | ✅ | ✅ (within 5s) | Windows service via nssm — see Step 4b below |
| ollama | ✅ | ✅ (within 5s) | Windows service via nssm — see Step 4b below |
| SQLite backup | n/a | n/a | Scheduled task, every 6h, copies to OneDrive |

## Step 4b (recommended, right after Step 4) — register uvicorn + ollama as services

In the same **Admin** PowerShell, after Step 4 completes:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\DEVANG\novamind-ai\scripts\install-services.ps1
```

This registers `novamind-backend` (uvicorn) and `novamind-ollama` (ollama) as Windows services, plus a scheduled task for SQLite backup every 6h.

## What "forever alive" actually means

- **Power outage / reboot** → Windows boots → cloudflared service starts → uvicorn service starts → ollama service starts. All within 30s of boot.
- **Backend crashes** → Windows service restarts uvicorn within 5s.
- **Tunnel dies** → Windows service restarts cloudflared within 5s. DNS stays the same.
- **URL rotates** → impossible. Named tunnels have fixed DNS.
- **Windows updates reboot the box** → everything comes back automatically.
