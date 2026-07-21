@echo off
REM Start a quick cloudflared tunnel pointing at the local backend.
REM Writes the assigned trycloudflare.com URL to %TUNNEL_URL_FILE%
REM (default: C:\Users\DEVANG\novamind-ai\backend\tunnel-url.txt) and
REM keeps running until killed.
setlocal
set "CLOUDFLARED=C:\Program Files (x86)\cloudflared\cloudflared.exe"
set "URL_FILE=C:\Users\DEVANG\novamind-ai\backend\tunnel-url.txt"
del /q "%URL_FILE%" 2>nul
"%CLOUDFLARED%" tunnel --url http://localhost:8000 --no-autoupdate 2>&1 | tee "%URL_FILE%.log"
