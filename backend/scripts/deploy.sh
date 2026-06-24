#!/usr/bin/env bash
# Production start script for NovaMind AI backend on a Linux VM (Oracle Cloud Always-Free).
# Idempotent: safe to re-run on existing deployments.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/novamind}"
APP_USER="${APP_USER:-novamind}"
APP_PORT="${APP_PORT:-8000}"

cd "$APP_DIR"

# Pull latest code (best-effort; ignore failures if no remote configured).
if git remote get-url origin >/dev/null 2>&1; then
  echo "[+] git pull"
  sudo -u "$APP_USER" git pull --ff-only || echo "    (pull skipped — no new commits)"
fi

# Use a venv so system Python stays clean.
if [ ! -d ".venv" ]; then
  echo "[+] creating venv"
  sudo -u "$APP_USER" python3 -m venv .venv
fi

sudo -u "$APP_USER" .venv/bin/pip install --upgrade pip wheel >/dev/null

# Install only the required deps (SQLite-only deployment).
sudo -u "$APP_USER" .venv/bin/pip install -r requirements.txt

# Restart via systemd.
echo "[+] restarting novamind.service"
systemctl restart novamind.service
sleep 1
systemctl --no-pager status novamind.service | head -n 5

echo "[+] listening on :$APP_PORT"
ss -ltnp 2>/dev/null | grep ":$APP_PORT" || true

echo "[✓] deploy complete"