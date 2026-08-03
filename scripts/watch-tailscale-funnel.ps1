# watch-tailscale-funnel.ps1
# Keep the NovaMind stack alive behind Tailscale Funnel:
#
#   - Backend (FastAPI on 127.0.0.1:8000)
#   - Frontend (Next.js on 127.0.0.1:3000)
#   - Reverse proxy (scripts/reverse-proxy.py on 127.0.0.1:7000)
#       Fans out /api/v1/* -> backend, /* -> frontend
#   - Tailscale Funnel on https://novamind.taile50f6f.ts.net
#       Single listener at 7000; the proxy handles path routing
#       (Funnel's --set-path strips the mount prefix, which would
#       break FastAPI's prefix-based routing, so we fan out via the
#       reverse proxy instead).
#
# The watchdog:
#   1. Polls /api/v1/health on the proxy (verifies backend reachable).
#   2. Verifies /  on the proxy (verifies frontend reachable).
#   3. Verifies /api/v1/health on 127.0.0.1:8000 (verifies backend).
#   4. Verifies `tailscale funnel status` is "Funnel on".
#   5. Restarts whatever's down.
#   6. Logs every state change to logs/tailscale-watchdog.log.
#
# Tailscale itself runs as a Windows service (StartType=Automatic)
# so the tunnel-to-tailnet link survives reboots.
#
# Usage:
#   pwsh -File scripts\watch-tailscale-funnel.ps1
#
# For a permanent install, see scripts/install-services.ps1.

[CmdletBinding()]
param(
    [int]   $BackendPort  = 8000,
    [int]   $FrontendPort = 3000,
    [int]   $ProxyPort    = 7000,
    [string]$BackendScript  = "$PSScriptRoot\start-backend.ps1",
    [string]$FrontendScript = "$PSScriptRoot\start-frontend.ps1",
    [string]$ProxyScript    = "$PSScriptRoot\start-reverse-proxy.ps1",
    [string]$Tailscale      = 'C:\Program Files\Tailscale\tailscale.exe',
    [int]   $PollSeconds    = 15
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$LogDir   = Join-Path $RepoRoot 'logs'
$LogFile  = Join-Path $LogDir 'tailscale-watchdog.log'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

function Write-Log {
    param([string]$Msg, [string]$Level = 'INFO')
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Msg
    Add-Content -Path $LogFile -Value $line
    $color = switch ($Level) {
        'ERROR' { 'Red' }
        'WARN'  { 'Yellow' }
        'OK'    { 'Green' }
        default { 'Cyan' }
    }
    Write-Host $line -ForegroundColor $color
}

function Test-BackendUp {
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$BackendPort/health")
        $req.Timeout = 3000
        $req.Method = 'GET'
        $resp = $req.GetResponse()
        $code = [int]$resp.StatusCode
        $resp.Close()
        return $code -eq 200
    } catch [System.Net.WebException] {
        # HttpWebRequest doesn't throw on 4xx; it returns a response.
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            return $code -ge 200 -and $code -lt 500
        }
        return $false
    } catch { return $false }
}

# Frontend has no /health; probe /login (HEAD). Any HTTP response
# means the Next.js listener is alive.
function Test-FrontendUp {
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$FrontendPort/login")
        $req.Timeout = 3000
        $req.Method = 'HEAD'
        $req.AllowAutoRedirect = $false
        $resp = $req.GetResponse()
        $code = [int]$resp.StatusCode
        $resp.Close()
        return $code -ge 200 -and $code -lt 500
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            return $code -ge 200 -and $code -lt 500
        }
        return $false
    } catch { return $false }
}

# The proxy preserves the backend's /api/v1 prefix; probe a known
# backend route. Any HTTP response (401 / 422 / etc.) means proxy+backend
# both reachable.
function Test-ProxyUp {
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$ProxyPort/api/v1/auth/login")
        $req.Timeout = 3000
        $req.Method = 'POST'
        $req.ContentLength = 0
        $resp = $req.GetResponse()
        $code = [int]$resp.StatusCode
        $resp.Close()
        return $code -ge 200 -and $code -lt 500
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            return $code -ge 200 -and $code -lt 500
        }
        return $false
    } catch { return $false }
}

function Test-FunnelUp {
    try {
        $out = & $Tailscale funnel status 2>&1 | Out-String
        return ($out -match 'Funnel on')
    } catch { return $false }
}

function Test-FunnelPointsToProxy {
    # Verify the Funnel listener is actually pointed at the proxy port.
    # If something reassigned it to 8000 or 443, we need to fix it.
    try {
        $out = & $Tailscale funnel status 2>&1 | Out-String
        return ($out -match "127\.0\.0\.1:$ProxyPort")
    } catch { return $false }
}

function Start-Backend {
    Write-Log "starting backend via $BackendScript"
    try {
        & pwsh -File $BackendScript 2>&1 | Out-Null
        for ($i = 0; $i -lt 25; $i++) {
            Start-Sleep -Seconds 1
            if (Test-BackendUp) { Write-Log "backend healthy on port $BackendPort" 'OK'; return $true }
        }
        Write-Log "backend did not respond within 25s" 'ERROR'
        return $false
    } catch {
        Write-Log "backend start threw: $($_.Exception.Message)" 'ERROR'
        return $false
    }
}

function Start-Frontend {
    Write-Log "starting frontend via $FrontendScript"
    try {
        & pwsh -File $FrontendScript 2>&1 | Out-Null
        for ($i = 0; $i -lt 35; $i++) {
            Start-Sleep -Seconds 1
            if (Test-FrontendUp) { Write-Log "frontend healthy on port $FrontendPort" 'OK'; return $true }
        }
        Write-Log "frontend did not respond within 35s" 'ERROR'
        return $false
    } catch {
        Write-Log "frontend start threw: $($_.Exception.Message)" 'ERROR'
        return $false
    }
}

function Start-Proxy {
    Write-Log "starting reverse proxy via $ProxyScript"
    try {
        & pwsh -File $ProxyScript 2>&1 | Out-Null
        for ($i = 0; $i -lt 15; $i++) {
            Start-Sleep -Seconds 1
            if (Test-ProxyUp) { Write-Log "proxy healthy on port $ProxyPort" 'OK'; return $true }
        }
        Write-Log "proxy did not respond within 15s" 'ERROR'
        return $false
    } catch {
        Write-Log "proxy start threw: $($_.Exception.Message)" 'ERROR'
        return $false
    }
}

function Start-Funnel {
    Write-Log "re-enabling Tailscale Funnel -> 127.0.0.1:$ProxyPort"
    try { & $Tailscale funnel reset 2>&1 | Out-Null } catch {}
    Start-Sleep -Seconds 1
    try {
        # Run from a path without spaces — Tailscale's --set-path on
        # Windows treats relative paths as cwd-relative, and a path
        # with spaces breaks the parser.
        Push-Location 'C:\temp'
        try {
            & $Tailscale funnel --bg "http://127.0.0.1:$ProxyPort" 2>&1 | Out-Null
        } finally { Pop-Location }
        Start-Sleep -Seconds 2
        if (Test-FunnelUp) { Write-Log 'funnel restored' 'OK'; return $true }
        Write-Log 'funnel still not active after restart' 'ERROR'
        return $false
    } catch {
        Write-Log "funnel start threw: $($_.Exception.Message)" 'ERROR'
        return $false
    }
}

Write-Log 'watchdog starting'
Write-Log "backend:  127.0.0.1:$BackendPort  ($BackendScript)"
Write-Log "frontend: 127.0.0.1:$FrontendPort  ($FrontendScript)"
Write-Log "proxy:    127.0.0.1:$ProxyPort  ($ProxyScript)"
Write-Log "funnel:   $Tailscale"
Write-Log "poll:     ${PollSeconds}s"

# Initial bring-up order: backend, frontend, proxy, then funnel.
if (-not (Test-BackendUp))  { Start-Backend  | Out-Null }
if (-not (Test-FrontendUp)) { Start-Frontend | Out-Null }
if (-not (Test-ProxyUp))    { Start-Proxy    | Out-Null }
if (-not (Test-FunnelUp) -or -not (Test-FunnelPointsToProxy)) {
    Start-Funnel | Out-Null
}

while ($true) {
    Start-Sleep -Seconds $PollSeconds

    $backend  = Test-BackendUp
    $frontend = Test-FrontendUp
    $proxy    = Test-ProxyUp
    $funnel   = Test-FunnelUp
    $fptp     = Test-FunnelPointsToProxy

    $allOk = $backend -and $frontend -and $proxy -and $funnel -and $fptp
    $status = if ($allOk) { 'OK' } else { 'DEGRADED' }

    if ($allOk) {
        Write-Log "stack $status (backend+frontend+proxy+funnel)" 'OK'
    } else {
        Write-Log "backend=$backend frontend=$frontend proxy=$proxy funnel=$funnel funnel->proxy=$fptp -> recovering" 'WARN'
        if (-not $backend)  { Start-Backend  | Out-Null }
        if (-not $frontend) { Start-Frontend | Out-Null }
        if (-not $proxy)    { Start-Proxy    | Out-Null }
        if (-not $funnel -or -not $fptp) { Start-Funnel | Out-Null }
    }
}
