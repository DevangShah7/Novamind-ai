# setup-permanent-tunnel.ps1
# After you finish the DuckDNS + `cloudflared tunnel create` + `cloudflared tunnel
# route dns` steps in scripts/deploy-permanent-tunnel.md, run THIS script to
# wire the named tunnel to localhost:8000 and install cloudflared as a service
# that auto-starts on boot and auto-restarts on crash.
#
# Usage (in an Administrator PowerShell):
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup-permanent-tunnel.ps1 `
#       -TunnelId a1b2c3d4-...      (UUID from `cloudflared tunnel create`) `
#       -Subdomain novamind-devang  (your DuckDNS subdomain) `
#       -PublicUrl https://api.novamind-devang.duckdns.org
#
# It will:
#   1. Write ~/.cloudflared/config.yml
#   2. Run `cloudflared service install <UUID>` (auto-starts on boot)
#   3. Start the cloudflared service
#   4. Probe the public URL until it returns 200, then write the new URL into
#      web/.env.local so the next `vercel --prod` picks it up
#   5. Print the final rebake command for you to run

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [string] $TunnelId,
    [Parameter(Mandatory=$true)] [string] $Subdomain,
    [Parameter(Mandatory=$true)] [string] $PublicUrl
)

$ErrorActionPreference = 'Stop'

# Must be Administrator -- `cloudflared service install` registers a
# Windows service under HKLM and writes to %ProgramData%.
$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell -> 'Run as administrator', then re-run." -ForegroundColor Red
    exit 1
}

# Sanity-check the public URL matches the subdomain the user claimed.
$expectedHost = "api.$Subdomain.duckdns.org"
if ($PublicUrl -notmatch "api\.$([regex]::Escape($Subdomain))\.duckdns\.org") {
    Write-Host "WARN: PublicUrl ($PublicUrl) does not contain api.$Subdomain.duckdns.org" -ForegroundColor Yellow
    Write-Host "      Did you claim a different DuckDNS subdomain?" -ForegroundColor Yellow
    $resp = Read-Host "Continue anyway? [y/N]"
    if ($resp -ne 'y') { exit 1 }
}

# cloudflared.exe -- which install?
$cf = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
if (-not $cf) {
    Write-Host "cloudflared not on PATH. Try: C:\Program Files (x86)\cloudflared\cloudflared.exe" -ForegroundColor Red
    exit 1
}
$cfExe = $cf.Source
Write-Host "cloudflared: $cfExe" -ForegroundColor Green

# Verify the credentials file exists. cloudflared creates it on
# `cloudflared tunnel create`. If the user skipped that step, fail now.
$credPath = Join-Path $env:USERPROFILE ".cloudflared\$TunnelId.json"
if (-not (Test-Path $credPath)) {
    Write-Host "ERROR: credentials file not found at $credPath" -ForegroundColor Red
    Write-Host "Run: cloudflared tunnel create novamind" -ForegroundColor Yellow
    Write-Host "It writes the UUID-named JSON to %USERPROFILE%\.cloudflared\." -ForegroundColor Yellow
    exit 1
}

# 1. Write config.yml ------------------------------------------------------
$cfgDir = Join-Path $env:USERPROFILE ".cloudflared"
$cfgPath = Join-Path $cfgDir "config.yml"
$cfg = @"
# Written by scripts\setup-permanent-tunnel.ps1
# Named tunnel: novamind
# Permanent URL: $PublicUrl (api.$Subdomain.duckdns.org)

tunnel: $TunnelId
credentials-file: $credPath

ingress:
  - hostname: api.$Subdomain.duckdns.org
    service: http://127.0.0.1:8000
  - service: http_status:404
"@
Set-Content -Path $cfgPath -Value $cfg -Encoding UTF8
Write-Host "Wrote $cfgPath" -ForegroundColor Green

# 2. Install as service ---------------------------------------------------
# cloudflared service install asks no questions if the tunnel ID is given.
# If the service already exists, remove it first (idempotent).
$existing = Get-Service cloudflared -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Existing cloudflared service found -- removing for clean reinstall" -ForegroundColor Yellow
    & $cfExe service uninstall 2>&1 | Out-Null
    Start-Sleep -Seconds 2
}
Write-Host "Installing cloudflared service..." -ForegroundColor Cyan
& $cfExe service install $TunnelId
if ($LASTEXITCODE -ne 0) {
    Write-Host "cloudflared service install exited $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

# 3. Start the service ----------------------------------------------------
Start-Service cloudflared
Start-Sleep -Seconds 3
$svc = Get-Service cloudflared
Write-Host "cloudflared service status: $($svc.Status)" -ForegroundColor $(if ($svc.Status -eq 'Running') { 'Green' } else { 'Yellow' })

# 4. Probe the public URL -------------------------------------------------
Write-Host "`nProbing $PublicUrl/health (up to 30s)..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest "$PublicUrl/health" -TimeoutSec 5 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
            $ok = $true
            Write-Host "Public URL is healthy: $($r.Content)" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "  attempt $($i+1): $($_.Exception.Message)" -ForegroundColor DarkGray
    }
}
if (-not $ok) {
    Write-Host "WARN: public URL not reachable yet. The DNS record may still be propagating." -ForegroundColor Yellow
    Write-Host "      Re-run this check later: Invoke-WebRequest $PublicUrl/health" -ForegroundColor Yellow
}

# 5. Update web/.env.local ------------------------------------------------
$webEnv = Join-Path (Resolve-Path "$PSScriptRoot\..\web").Path ".env.local"
if (Test-Path $webEnv) {
    $content = Get-Content $webEnv
    $newLine = "NEXT_PUBLIC_API_URL=$PublicUrl/api/v1"
    $found = $false
    $newContent = $content | ForEach-Object {
        if ($_ -match '^NEXT_PUBLIC_API_URL=') {
            $found = $true
            $newLine
        } else { $_ }
    }
    if (-not $found) { $newContent += @("") + $newLine }
    Set-Content -Path $webEnv -Value $newContent -Encoding UTF8
    Write-Host "Updated $webEnv with $newLine" -ForegroundColor Green
} else {
    Write-Host "WARN: $webEnv not found -- skipping env update" -ForegroundColor Yellow
}

# 6. Final instructions ---------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Done. To rebake the Vercel frontend with the new URL:" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  cd web" -ForegroundColor White
Write-Host "  vercel --prod -b NEXT_PUBLIC_API_URL=$PublicUrl/api/v1 -b NEXT_PUBLIC_USE_MOCK=false" -ForegroundColor Yellow
Write-Host ""
Write-Host "After that, the live site is permanently wired to:" -ForegroundColor White
Write-Host "  $PublicUrl" -ForegroundColor Green
Write-Host ""
Write-Host "Auto-restart matrix (all should be 'Running'):" -ForegroundColor Cyan
Get-Service cloudflared, novamind-backend, novamind-ollama -ErrorAction SilentlyContinue |
    Format-Table Name, Status, StartType -AutoSize
