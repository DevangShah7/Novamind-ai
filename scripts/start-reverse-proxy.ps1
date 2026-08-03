# start-reverse-proxy.ps1
# Start the tiny path-based reverse proxy on 127.0.0.1:7000.
# Routes /api/v1/* -> backend (8000) and everything else -> frontend (3000),
# preserving the /api/v1 prefix (Tailscale Funnel's --set-path strips it,
# which would break FastAPI's prefix-based routing).
#
# Used by deploy-full-stack.ps1 and the watchdog.

$ErrorActionPreference = 'Stop'
$port    = 7000
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Script  = Join-Path $RepoRoot 'scripts\reverse-proxy.py'
$LogDir  = Join-Path $RepoRoot 'logs'
$OutLog  = Join-Path $LogDir 'proxy.out.log'
$ErrLog  = Join-Path $LogDir 'proxy.err.log'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

# Stop any existing listener
Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "[start-reverse-proxy] killing PID $($_.OwningProcess) on port $port"
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }

Write-Host "[start-reverse-proxy] launching $Script on 127.0.0.1:$port" -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    Start-Process -FilePath 'python' `
        -ArgumentList @($Script) `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError  $ErrLog `
        -WindowStyle Hidden
}
finally { Pop-Location }

# Wait for /health probe via the proxy (200 = up)
$ok = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        # The proxy doesn't expose /health of its own; ping through it.
        $r = Invoke-WebRequest "http://127.0.0.1:$port/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { $ok = $true; break }
    } catch { }
}

if ($ok) {
    Write-Host "[start-reverse-proxy] up on http://127.0.0.1:$port" -ForegroundColor Green
} else {
    Write-Host "[start-reverse-proxy] did not respond within 15s; tail of err log:" -ForegroundColor Yellow
    Get-Content $ErrLog -Tail 15
}
