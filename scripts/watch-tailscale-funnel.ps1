# watch-tailscale-funnel.ps1
# Keep the NovaMind backend + Tailscale Funnel tunnel alive.
#
# - Restarts the FastAPI backend on 127.0.0.1:8000 if it crashes.
# - Re-asserts `tailscale funnel --bg 8000` if the funnel listener
#   drops.
# - Logs every state change to logs/tailscale-watchdog.log.
#
# Tailscale itself runs as a Windows service (StartType=Automatic)
# so the tunnel-to-tailnet link survives reboots without us doing
# anything. This watchdog only handles the backend + the public
# funnel exposure, both of which Tailscale does not manage.
#
# Usage:
#   pwsh -File scripts\watch-tailscale-funnel.ps1
#
# For a permanent install, see scripts/install-services.ps1 which
# can NSSM-wrap this script as a Windows service.

[CmdletBinding()]
param(
    [string]$BackendHealth = 'http://127.0.0.1:8000/health',
    [string]$BackendScript = "$PSScriptRoot\start-backend.ps1",
    [int]   $Port           = 8000,
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
        $r = Invoke-WebRequest -Uri $BackendHealth -UseBasicParsing -TimeoutSec 3
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Test-FunnelUp {
    # `tailscale funnel status` exits 0 with "Funnel on" when active.
    try {
        $out = & $Tailscale funnel status 2>&1 | Out-String
        return ($out -match 'Funnel on')
    } catch { return $false }
}

function Start-Backend {
    Write-Log "starting backend via $BackendScript"
    try {
        & pwsh -File $BackendScript 2>&1 | Out-Null
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Seconds 1
            if (Test-BackendUp) { Write-Log "backend healthy on port $Port" 'OK'; return $true }
        }
        Write-Log "backend did not respond within 20s" 'ERROR'
        return $false
    } catch {
        Write-Log "backend start threw: $($_.Exception.Message)" 'ERROR'
        return $false
    }
}

function Start-Funnel {
    Write-Log "re-enabling Tailscale Funnel on port $Port"
    # `tailscale funnel reset` then `--bg` avoids the
    # `foreground listener already exists` error if state is stale.
    try { & $Tailscale funnel reset 2>&1 | Out-Null } catch {}
    Start-Sleep -Seconds 1
    try {
        & $Tailscale funnel --bg $Port 2>&1 | Out-Null
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
Write-Log "backend:  $BackendHealth"
Write-Log "tailscale: $Tailscale"
Write-Log "poll:     ${PollSeconds}s"

# Initial bring-up — backend first (funnel has nothing to expose otherwise).
if (-not (Test-BackendUp))  { Start-Backend | Out-Null }
if (-not (Test-FunnelUp))   { Start-Funnel | Out-Null }

while ($true) {
    Start-Sleep -Seconds $PollSeconds

    $backend = Test-BackendUp
    $funnel  = Test-FunnelUp
    $status  = if ($backend -and $funnel) { 'OK' } else { 'DEGRADED' }

    if ($backend -and $funnel) {
        Write-Log "backend+funnel $status" 'OK'
    } else {
        Write-Log "backend=$backend funnel=$funnel -> recovering" 'WARN'
        if (-not $backend) { Start-Backend  | Out-Null }
        if (-not $funnel)  { Start-Funnel   | Out-Null }
    }
}
