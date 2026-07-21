# watch-quick-tunnel.ps1
# Keep the cloudflared quick tunnel alive. If it dies, restart it,
# capture the new *.trycloudflare.com URL, and write it to
# backend/tunnel-url.txt. Also PATCHes the Vercel project env
# (NEXT_PUBLIC_API_URL) so the deployed frontend picks up the new
# URL automatically.
#
# Free, no account, but URL changes on every restart (a permanent
# tunnel via real domain is better — see scripts/setup-permanent-tunnel.ps1).
#
# Usage (in any PowerShell, can run unattended):
#   powershell -ExecutionPolicy Bypass -File scripts\watch-quick-tunnel.ps1

[CmdletBinding()]
param(
    [string]$BackendHealth  = 'http://localhost:8000/health',
    [string]$VercelProjectId = 'prj_RGN8AqrCFqJJggNorZxroCVC4uRu',
    [string]$EnvVarId        = 'nvSFbxe6xeCB4arK',
    [string]$VercelToken     = $env:VERCEL_TOKEN
)

$ErrorActionPreference = 'Stop'
$RepoRoot    = (Resolve-Path "$PSScriptRoot\..").Path
$StartScript = Join-Path $RepoRoot 'scripts\start-quick-tunnel.bat'
$UrlFile     = Join-Path $RepoRoot 'backend\tunnel-url.txt'
$LogFile     = Join-Path $RepoRoot 'backend\tunnel-watch.log'

function Get-TunnelUrl {
    if (Test-Path $UrlFile) {
        $line = Get-Content $UrlFile -TotalCount 1 -ErrorAction SilentlyContinue
        if ($line -match 'https://[a-z0-9-]+\.trycloudflare\.com') { return $matches[0] }
    }
    return $null
}

function Update-VercelEnv {
    param([string]$Url)
    if (-not $VercelToken) {
        Write-Host '[watch] VERCEL_TOKEN not set; skipping Vercel env update' -ForegroundColor Yellow
        return
    }
    $apiUrl = "$Url/api/v1"
    $body = @{ value = $apiUrl; target = @('production') } | ConvertTo-Json
    try {
        $resp = Invoke-RestMethod -Method Patch `
            -Uri "https://api.vercel.com/v10/projects/$VercelProjectId/env/$EnvVarId" `
            -Headers @{ Authorization = "Bearer $VercelToken" } `
            -ContentType 'application/json' -Body $body -TimeoutSec 15
        Write-Host "[watch] Vercel env updated to $apiUrl" -ForegroundColor Green
    } catch {
        Write-Host "[watch] Vercel env update failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Test-BackendHealthy {
    try {
        $r = Invoke-WebRequest $BackendHealth -TimeoutSec 5 -UseBasicParsing
        return $r.StatusCode -eq 200
    } catch { return $false }
}

Write-Host "[watch] starting quick-tunnel watchdog" -ForegroundColor Cyan
Write-Host "[watch] backend:  $BackendHealth"
Write-Host "[watch] URL file: $UrlFile"
Write-Host "[watch] log file: $LogFile"

# Initial start
if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host '[watch] no cloudflared running; starting it' -ForegroundColor Yellow
    Start-Process -FilePath $StartScript -WindowStyle Hidden
    # wait for the URL to appear
    $url = $null
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        $url = Get-TunnelUrl
        if ($url) { break }
    }
    if ($url) {
        Write-Host "[watch] tunnel up: $url" -ForegroundColor Green
        Update-VercelEnv -Url $url
    } else {
        Write-Host '[watch] tunnel did not come up in 30s' -ForegroundColor Red
    }
} else {
    Write-Host '[watch] cloudflared already running' -ForegroundColor Green
}

# Main loop
while ($true) {
    Start-Sleep -Seconds 30
    $cloudflared = Get-Process cloudflared -ErrorAction SilentlyContinue
    if (-not $cloudflared) {
        Write-Host "[watch] $(Get-Date -Format 'HH:mm:ss') cloudflared died; restarting" -ForegroundColor Red
        Start-Process -FilePath $StartScript -WindowStyle Hidden
        $url = $null
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            $url = Get-TunnelUrl
            if ($url) { break }
        }
        if ($url) {
            Write-Host "[watch] new URL: $url" -ForegroundColor Green
            Update-VercelEnv -Url $url
        } else {
            Write-Host '[watch] tunnel did not come up after restart' -ForegroundColor Red
        }
    } else {
        $url = Get-TunnelUrl
        if ($url) {
            $healthy = Test-BackendHealthy
            $status = if ($healthy) { 'OK' } else { 'BACKEND DOWN' }
            Write-Host "[watch] $(Get-Date -Format 'HH:mm:ss') tunnel=$url backend=$status" -ForegroundColor $(if ($healthy) { 'DarkGray' } else { 'Red' })
        }
    }
}
