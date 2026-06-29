# stop-watchdog.ps1
# Stops the running watch-tunnel.ps1 instance (if any) and any cloudflared it started.
#
# Uses Win32_Process via CIM to inspect CommandLine because Get-Process's
# CommandLine property requires elevation that interactive shells may not have.

$ErrorActionPreference = 'SilentlyContinue'
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -match 'watch-tunnel\.ps1' } |
    ForEach-Object {
        Write-Host "Stopping watchdog PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }
Get-Process -Name cloudflared -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "Stopping cloudflared PID $($_.Id)"
        Stop-Process -Id $_.Id -Force
    }
Write-Host "Done."