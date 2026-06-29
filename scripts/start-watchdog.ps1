# start-watchdog.ps1
# Launches watch-tunnel.ps1 detached so it survives this terminal closing.
# Logs to scripts\watchdog-launcher.log.

$ErrorActionPreference = 'Stop'
$Script = Join-Path $PSScriptRoot 'watch-tunnel.ps1'
$Log    = Join-Path $PSScriptRoot 'watchdog-launcher.log'

if (-not (Test-Path $Script)) {
    Write-Host ("watch-tunnel.ps1 not found at " + $Script)
    exit 1
}

# If a watchdog is already running, don't double-start.
$running = Get-Process -Name powershell -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'watch-tunnel\.ps1' }
if ($running) {
    $pidList = ($running.Id -join ', ')
    Write-Host ("watchdog already running (PIDs: " + $pidList + ")")
    exit 0
}

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Add-Content -Path $Log -Value ("[" + $stamp + "] starting watchdog detached")
Write-Host ("Starting watchdog (detached). See " + $Log + " and backend\tunnel-watchdog.log")

Start-Process -FilePath 'powershell' `
    -ArgumentList @('-ExecutionPolicy','Bypass','-File',$Script) `
    -WindowStyle Hidden
Write-Host 'Started. To stop run: powershell -File scripts\stop-watchdog.ps1'