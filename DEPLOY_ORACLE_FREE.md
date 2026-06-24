# Deploy NovaMind AI Backend — Oracle Cloud Always-Free (Permanent, Free)

This guide deploys the FastAPI backend on a free Oracle Cloud VM that
runs 24/7 forever (no credit card required after signup, no sleep, no
time limit). Uses SQLite so you don't need a separate database.

**What you get for $0/month, permanently:**
- 1× VM (1 GB RAM, 1/8 OCPU, 50 GB storage on the Always-Free tier)
- HTTPS via Caddy (Let's Encrypt auto-cert) or Cloudflare Tunnel (free)
- systemd auto-restart on crash
- 24/7 uptime (Oracle has guaranteed Always-Free since 2019)

**Trade-offs vs. managed platforms:**
- Single VM — if it dies, your app is down (until Oracle recovers it)
- 1 GB RAM — fine for <100 concurrent users
- SQLite — single-writer; if you grow, migrate to Postgres later

---

## Step 1: Create the Oracle Cloud account

1. Go to **https://cloud.oracle.com/** → Sign Up
2. Choose a **Home Region** carefully — VMs are pinned to the region you pick (e.g. `us-ashburn-1`, `eu-frankfurt-1`).
3. You'll need a credit card for identity verification, but **you won't be charged** if you stay on Always-Free resources. Oracle emails a $300 trial credit; ignore it.
4. Wait ~10 minutes for account provisioning. You'll get a "Get Started with Oracle Cloud" email.

## Step 2: Create a free VM

1. From the **OCI dashboard** (cloud.oracle.com), click **☰ menu → Compute → Instances → Create Instance**
2. **Name**: `novamind-backend`
3. **Placement**: leave default (any AD)
4. **Image**: click **Edit** → **Oracle Linux 9** (or **Ubuntu 22.04** if you prefer)
5. **Shape**: click **Edit** → **VM.Standard.E2.1.Micro** (AMD) — **always-free**. (ARM Ampere A1 also free but capacity is limited.)
6. **Networking**: create a new VCN (`Create new virtual cloud network`). Use the defaults.
7. **SSH keys**: either upload your public key (`~/.ssh/id_rsa.pub`) or have Oracle generate one (download both keys — you'll need the `.key` file).
8. Click **Create**. Wait ~2 minutes for the VM to provision.
9. **Copy the public IP** shown on the instance page — this is your server's address.

## Step 3: Open port 8000 in the firewall

By default Oracle blocks everything except SSH (port 22). You need to open 8000 (and optionally 80/443 for HTTPS later).

1. On the instance page, click the **Subnet** link (under "Primary VNIC")
2. Click the **Default Security List** for that subnet
3. Click **Add Ingress Rules**:
   - **Source CIDR**: `0.0.0.0/0`
   - **Protocol**: TCP
   - **Destination Port**: `8000`
4. Save. (Repeat for 80 and 443 if you'll set up HTTPS later.)

## Step 4: SSH into the VM

```bash
# From your laptop (Git Bash on Windows / Terminal on Mac/Linux)
ssh -i ~/.ssh/your-key.key opc@<PUBLIC_IP>
```

You should land in the home directory as the `opc` user.

## Step 5: Run the one-time setup script

This installs Python, creates a non-root user, and clones the repo. **Copy/paste the entire block**:

```bash
sudo dnf update -y
sudo dnf install -y git python3 python3-pip python3-devel gcc openssl-devel

# Create a non-root user for the app.
sudo useradd -m -s /bin/bash novamind
sudo mkdir -p /opt/novamind /var/log/novamind
sudo chown novamind:novamind /opt/novamind /var/log/novamind

# Clone your repo.
cd /opt
sudo -u novamind git clone https://github.com/DevangShah7/Novamind-ai.git novamind
sudo -u novamind git config --global --add safe.directory /opt/novamind
```

## Step 6: Configure environment + secrets

```bash
# Generate a strong JWT secret.
SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
echo "Your SECRET_KEY: $SECRET"

# Write the env file.
sudo -u novamind bash -c "cat > /opt/novamind/backend/.env <<EOF
SECRET_KEY=$SECRET
DATABASE_URL=sqlite:///./novamind.db
BACKEND_CORS_ORIGINS=https://web-ivory-eta-87.vercel.app,http://localhost:3000
EOF"
chmod 600 /opt/novamind/backend/.env
```

## Step 7: Install the systemd service

```bash
sudo cp /opt/novamind/backend/scripts/novamind.service /etc/systemd/system/novamind.service
sudo systemctl daemon-reload
sudo systemctl enable novamind.service

sudo chmod +x /opt/novamind/backend/scripts/deploy.sh
```

## Step 8: First deploy

```bash
sudo /opt/novamind/backend/scripts/deploy.sh
```

Expected output (last lines):

```
[+] listening on :8000
[✓] deploy complete
```

## Step 9: Verify it's running

```bash
# Service status.
sudo systemctl status novamind.service

# API responds locally.
curl http://localhost:8000/
# Expected: {"message":"Welcome to NovaMind AI"}

# API responds publicly (if you opened the firewall).
curl http://<PUBLIC_IP>:8000/
```

## Step 10: Set up HTTPS (recommended)

Oracle's VM gives you a public IP but no TLS. Easiest path:

### Option A: Caddy (auto-TLS via Let's Encrypt)

Buy a cheap domain (Namecheap, ~$5/yr) and point an A record at your VM's public IP. Then:

```bash
sudo dnf install -y caddy
sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
your-domain.com {
    reverse_proxy 127.0.0.1:8000
}
EOF
sudo systemctl enable --now caddy
```

Caddy auto-issues a Let's Encrypt cert.

### Option B: Cloudflare Tunnel (free, no domain purchase)

```bash
# On your laptop
brew install cloudflared   # or: scoop install cloudflared on Windows
cloudflared tunnel login
cloudflared tunnel create novamind
cloudflared tunnel route dns novamind api.your-domain.com
cloudflared tunnel run novamind
```

Free `https://api.your-domain.com` without opening firewall ports.

### Option C: Skip HTTPS for now

Just use `http://<PUBLIC_IP>:8000` — fine for testing, but Vercel may block mixed content on production.

## Step 11: Wire the Vercel frontend

Once you have a public URL (e.g. `https://api.novamind.your-domain.com`):

```bash
# From your laptop
vercel env add NEXT_PUBLIC_API_URL production
# Paste: https://api.novamind.your-domain.com/api/v1
vercel --prod
```

I can also do this part for you — just give me the backend URL.

## Updating the app later

```bash
# On the Oracle VM
sudo /opt/novamind/backend/scripts/deploy.sh
```

`git pull`s the latest, reinstalls deps, and restarts the service. ~30 seconds of downtime.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `permission denied` on git pull | `sudo chown -R novamind:novamind /opt/novamind` |
| Service won't start | `sudo journalctl -u novamind.service -n 50` |
| `ModuleNotFoundError: No module named 'app'` | Check `WorkingDirectory=/opt/novamind/backend` in service file |
| CORS errors in browser | `BACKEND_CORS_ORIGINS` must include Vercel URL with `https://` and no trailing slash |
| Port 8000 unreachable | Re-check security list ingress rule (Step 3) |
| VM stopped after a week | Oracle rarely recycles idle Always-Free VMs. Keep `systemd` enabled and don't manually shut it down. |

## Cost summary

| Resource | Cost |
|----------|------|
| 1× VM.Standard.E2.1.Micro | **$0** (always-free) |
| 50 GB block storage | **$0** |
| Outbound data transfer (10 TB/month) | **$0** |
| Domain name (optional) | **~$5/year** |
| **Total** | **~$5/year** (only if you want a domain) |
