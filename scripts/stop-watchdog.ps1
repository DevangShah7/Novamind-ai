# stop-watchdog.ps1
# Stops the running watch-tunnel.ps1 instance (if any) and any cloudflared it started.

$ErrorActionPreference = 'SilentlyContinue'
Get-Process -Name powershell -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'watch-tunnel\.ps1' } |
    ForEach-Object {
        Write-Host "Stopping watchdog PID $($_.Id)"
        Stop-Process -Id $_.Id -Force
    }
Get-Process -Name cloudflared -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "Stopping cloudflared PID $($_.Id)"
        Stop-Process -Id $_.Id -Force
    }
Write-Host "Done."