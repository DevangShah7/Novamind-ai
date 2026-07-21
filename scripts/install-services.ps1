# install-services.ps1
# Make NovaMind's local processes survive reboots by registering them as
# Windows services. Run this ONCE, in an Administrator PowerShell:
#
#   powershell -ExecutionPolicy Bypass -File scripts\install-services.ps1
#
# It will:
#   1. Register 'novamind-backend' (uvicorn FastAPI) as a Windows service
#      that auto-starts on boot and restarts on crash.
#   2. Register 'novamind-ollama' (ollama serve) as a Windows service, if
#      ollama is on PATH. Skipped silently otherwise.
#   3. Print the next steps for cloudflared (which has to be installed
#      interactively as 'cloudflared service install' -- it prompts for
#      the tunnel ID).
#
# Why services (not just nohup / Task Scheduler):
#   - Services start before any user logs in, so a power blip that brings
#     the box back up unattended still gets the site online.
#   - Services have built-in crash recovery (start_type=auto, recovery=
#     restart-on-failure-after-5s) -- no watchdog needed for the
#     "process died" case.
#   - Services are visible in `services.msc` and `Get-Service`, so you can
#     check status without remembering background-task IDs.
#
# Idempotent -- safe to re-run; it removes any existing service first.

$ErrorActionPreference = 'Stop'

# Must be Administrator
$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell -> 'Run as administrator', then re-run." -ForegroundColor Red
    exit 1
}

$RepoRoot    = (Resolve-Path "$PSScriptRoot\..").Path
$BackendDir  = Join-Path $RepoRoot 'backend'

# The 'python.exe' on PATH via the Microsoft Store stub at
# C:\Users\DEVANG\AppData\Local\Microsoft\WindowsApps\python.exe is a UWP
# shim that ONLY works when invoked from a Microsoft Store context -- nssm
# launching it from a service context fails with "permission denied". Find
# the real Python install (the one with the full site-packages tree) by
# checking the common locations explicitly.
$PythonExe = $null
$pythonCandidates = @(
    'C:\Python313\python.exe',
    'C:\Python312\python.exe',
    'C:\Python311\python.exe',
    'C:\Python310\python.exe',
    'C:\Program Files\Python313\python.exe',
    'C:\Program Files\Python312\python.exe',
    'C:\Program Files\Python311\python.exe',
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Python\bin\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Python\bin\python3.exe')
)
foreach ($c in $pythonCandidates) {
    if ($c -and (Test-Path $c)) {
        # Verify it actually has uvicorn (the one we care about) before
        # accepting it. The WindowsApps stub passes Test-Path but can't
        # import any third-party packages.
        & $c -c "import uvicorn" 2>$null
        if ($LASTEXITCODE -eq 0) { $PythonExe = $c; break }
    }
}
if (-not $PythonExe) {
    Write-Host "ERROR: Could not find a real Python with uvicorn installed." -ForegroundColor Red
    Write-Host "Tried: $($pythonCandidates -join ', ')" -ForegroundColor Red
    Write-Host "Fix: install Python from python.org (not the Store stub) and pip install uvicorn." -ForegroundColor Red
    exit 1
}
Write-Host "Using Python: $PythonExe" -ForegroundColor Green

$OllamaExe   = (Get-Command ollama.exe -ErrorAction SilentlyContinue).Source

# nssm (the Non-Sucking Service Manager) is the standard way to wrap a
# console process (python, ollama) as a Windows service. The Python
# `win32serviceutil` is another option but nssm is simpler and battle-tested.
# Check for nssm; if missing, prompt the user to install it via winget/choco,
# or fall back to SC.EXE which is built-in but uglier.
$nssm = Get-Command nssm.exe -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "nssm.exe not on PATH. Installing via winget..." -ForegroundColor Yellow
    try {
        & winget install --id nssm.nssm --accept-package-agreements --accept-source-agreements
        $nssm = Get-Command nssm.exe -ErrorAction SilentlyContinue
    } catch { }
}
if (-not $nssm) {
    Write-Host "nssm install via winget failed. Install manually:" -ForegroundColor Red
    Write-Host "  winget install nssm.nssm" -ForegroundColor Red
    Write-Host "  OR choco install nssm" -ForegroundColor Red
    Write-Host "  OR download from https://nssm.cc/download" -ForegroundColor Red
    exit 1
}
$nssm = (Get-Command nssm.exe).Source
Write-Host "Using nssm: $nssm" -ForegroundColor Green

# ---- Backend service -------------------------------------------------------

$backendName = 'novamind-backend'
$backendDisplay = 'NovaMind Backend (FastAPI on port 8000)'

# Remove any existing service with the same name (idempotent)
$existing = Get-Service $backendName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing $backendName service..." -ForegroundColor Yellow
    & nssm.exe stop $backendName 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    & nssm.exe remove $backendName confirm 2>&1 | Out-Null
    Start-Sleep -Seconds 1
}

Write-Host "Installing $backendName..." -ForegroundColor Cyan
& nssm.exe install $backendName $PythonExe
& nssm.exe set $backendName AppDirectory $BackendDir
& nssm.exe set $backendName AppParameters '-m uvicorn app.main:app --host 127.0.0.1 --port 8000'
& nssm.exe set $backendName DisplayName $backendDisplay
& nssm.exe set $backendName Description 'FastAPI backend for NovaMind. Auto-starts on boot, restarts on crash.'
& nssm.exe set $backendName Start SERVICE_AUTO_START
& nssm.exe set $backendName AppStdout (Join-Path $BackendDir 'uvicorn-stdout.log')
& nssm.exe set $backendName AppStderr (Join-Path $BackendDir 'uvicorn-stderr.log')
& nssm.exe set $backendName AppRotateFiles 1
& nssm.exe set $backendName AppRotateBytes 10485760
# Restart on crash, after 5 seconds, forever
& nssm.exe set $backendName AppExit Default Restart
& nssm.exe set $backendName AppRestartDelay 5000
& nssm.exe set $backendName AppStdoutCreationDisposition 4
& nssm.exe set $backendName AppStderrCreationDisposition 4

Write-Host "Starting $backendName..." -ForegroundColor Green
& nssm.exe start $backendName
Start-Sleep -Seconds 3
$svc = Get-Service $backendName
Write-Host "$backendName status: $($svc.Status)" -ForegroundColor $(if ($svc.Status -eq 'Running') { 'Green' } else { 'Yellow' })

# ---- Ollama service (if installed) -----------------------------------------

if ($OllamaExe) {
    $ollamaName = 'novamind-ollama'
    $ollamaDisplay = 'NovaMind Ollama (local LLM server on port 11434)'

    $existing = Get-Service $ollamaName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Removing existing $ollamaName service..." -ForegroundColor Yellow
        & nssm.exe stop $ollamaName 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        & nssm.exe remove $ollamaName confirm 2>&1 | Out-Null
        Start-Sleep -Seconds 1
    }

    Write-Host "Installing $ollamaName..." -ForegroundColor Cyan
    & nssm.exe install $ollamaName $OllamaExe
    & nssm.exe set $ollamaName AppDirectory (Split-Path $OllamaExe -Parent)
    & nssm.exe set $ollamaName AppParameters 'serve'
    & nssm.exe set $ollamaName DisplayName $ollamaDisplay
    & nssm.exe set $ollamaName Description 'Ollama local LLM server. Auto-starts on boot, restarts on crash.'
    & nssm.exe set $ollamaName Start SERVICE_AUTO_START
    & nssm.exe set $ollamaName AppStdout (Join-Path $BackendDir 'ollama-stdout.log')
    & nssm.exe set $ollamaName AppStderr (Join-Path $BackendDir 'ollama-stderr.log')
    & nssm.exe set $ollamaName AppRotateFiles 1
    & nssm.exe set $ollamaName AppRotateBytes 10485760
    & nssm.exe set $ollamaName AppExit Default Restart
    & nssm.exe set $ollamaName AppRestartDelay 5000
    & nssm.exe set $ollamaName AppStdoutCreationDisposition 4
    & nssm.exe set $ollamaName AppStderrCreationDisposition 4

    Write-Host "Starting $ollamaName..." -ForegroundColor Green
    & nssm.exe start $ollamaName
    Start-Sleep -Seconds 3
    $svc = Get-Service $ollamaName
    Write-Host "$ollamaName status: $($svc.Status)" -ForegroundColor $(if ($svc.Status -eq 'Running') { 'Green' } else { 'Yellow' })
} else {
    Write-Host "ollama not on PATH -- skipping. (Install later with: winget install Ollama.Ollama)" -ForegroundColor Yellow
}

# ---- DB backup scheduled task ----------------------------------------------

# SQLite is the only persistence layer. If the disk dies, so does all user
# data. Backing up backend/novamind.db to OneDrive (which the user almost
# certainly has running) every 6 hours is a cheap insurance policy.
$oneDrive = $env:OneDrive
$backupDir = $null
if ($oneDrive -and (Test-Path $oneDrive)) {
    $backupDir = Join-Path $oneDrive 'NovaMind-Backups'
} else {
    # Fallback: user-profile backed-up folder
    $backupDir = Join-Path $env:USERPROFILE 'Documents\NovaMind-Backups'
}
if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
$dbPath = Join-Path $BackendDir 'novamind.db'
$backupScript = Join-Path $RepoRoot 'scripts\backup-db.ps1'

Write-Host ""
Write-Host "DB backup location: $backupDir" -ForegroundColor Cyan
Write-Host "DB backup script:   $backupScript (writes to: $backupDir\novamind-YYYYMMDD-HHMM.db)" -ForegroundColor Cyan

# Create the scheduled task
$taskName = 'NovaMind-DB-Backup'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-ExecutionPolicy Bypass -File `"$backupScript`" -DbPath `"$dbPath`" -BackupDir `"$backupDir`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 6) `
    -RepetitionDuration (New-TimeSpan -Days 3650)  # 10 years -- effectively forever
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Copy backend/novamind.db to $backupDir every 6 hours. Keeps last 20 copies." `
    -User 'SYSTEM' -RunLevel Highest | Out-Null
Write-Host "Scheduled task '$taskName' registered (every 6h)" -ForegroundColor Green

# ---- Cloudflared -----------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Next step: install cloudflared as a service" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "The cloudflared service installer is interactive (it asks which tunnel" -ForegroundColor White
Write-Host "to attach to), so you have to run it yourself, in an Administrator" -ForegroundColor White
Write-Host "PowerShell. ONE command:" -ForegroundColor White
Write-Host ""
Write-Host "  cloudflared service install <UUID-of-your-tunnel>" -ForegroundColor Yellow
Write-Host ""
Write-Host "Where <UUID> is the file name (minus .json) of the file in" -ForegroundColor White
Write-Host "C:\Users\DEVANG\.cloudflared\ -- created by 'cloudflared tunnel create novamind'." -ForegroundColor White
Write-Host ""
Write-Host "After it installs:" -ForegroundColor White
Write-Host "  Start-Service cloudflared" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "All set. You can now run scripts\watch-services.ps1 to monitor," -ForegroundColor Green
Write-Host "but the services will survive reboots on their own." -ForegroundColor Green
