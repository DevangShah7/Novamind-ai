# deploy-now.ps1
# One-shot deploy: start backend, start watchdog (which starts the tunnel
# and triggers `vercel --prod` with the new URL baked in), then smoke-test.
#
# # Run from the repo root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\deploy-now.ps1

# Requires PowerShell 7+ for `Start-Process -Environment`. On Windows
# PowerShell 5.1 we set env vars in the current process instead --
# children spawned via Start-Process inherit them.

$ErrorActionPreference = 'Stop'

$RepoRoot   = (Resolve-Path "$PSScriptRoot\..").Path
$BackendDir = Join-Path $RepoRoot 'backend'
$WebDir     = Join-Path $RepoRoot 'web'
$LogDir     = Join-Path $RepoRoot 'logs'
$StateFile  = Join-Path $BackendDir 'tunnel-state.json'

# Use the venv if it exists. The project's .python-version pins 3.11 and
# requirements.txt is pinned to versions that won't run on Python 3.14.
# Fall back to system python only if there's no venv (and hope for the best).
$VenvPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
} else {
    $PythonExe = (Get-Command python.exe -ErrorAction Stop).Source
    Write-Host "WARNING: no backend\.venv found -- using $PythonExe (probably 3.14, may fail)" -ForegroundColor Yellow
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-Step {
    param([string]$Msg)
    Write-Host ""
    Write-Host "=== $Msg ===" -ForegroundColor Cyan
}

function Run-Native {
    # Run an exe with non-zero tolerance (taskkill returns 128 when no match).
    param([string]$Exe, [string[]]$Args)
    $saveEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Exe @Args 2>&1 | Out-Null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $saveEAP
    $global:LASTEXITCODE = 0
    return $code
}

# ---- 1. Start FastAPI backend on localhost:8000 ----------------------------

Write-Step "Step 1: Start FastAPI backend"

# Kill any stale backend.
Run-Native 'taskkill.exe' @('/F','/T','/IM','python.exe') | Out-Null
Start-Sleep -Seconds 2

$backendLog = Join-Path $LogDir 'backend.log'
if (Test-Path $backendLog) { Remove-Item $backendLog -Force }

# Launch uvicorn in a hidden window. Use the venv's python so we get the
# pinned versions (fastapi 0.95.2, pydantic 1.10.13, etc.) on Python 3.11.
#
# The Settings class in config.py doesn't declare env_file=.env, so
# BaseSettings only reads OS env. Without an explicit SECRET_KEY,
# startup fails with "Refusing to start: SECRET_KEY is a placeholder".
# We load the .env file here and set those vars in the current process
# so the Start-Process child inherits them.
$env:PYTHONUNBUFFERED     = '1'
$env:PYTHONIOENCODING     = 'utf-8'
$env:ALLOW_DEV_SECRET_KEY = '1'
# First-boot idempotent migration, then flip to 0 after a successful boot.
$env:RUN_DB_MIGRATIONS    = '1'

# Load everything from backend/.env (skipping the placeholder SECRET_KEY
# and the keys we already set above).
$dotenvPath = Join-Path $BackendDir '.env'
if (Test-Path $dotenvPath) {
    Get-Content $dotenvPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { return }
        $k = $line.Substring(0, $eq).Trim()
        $v = $line.Substring($eq + 1).Trim()
        if ($k -eq 'SECRET_KEY')            { return }  # generated below
        if ($k -eq 'ALLOW_DEV_SECRET_KEY')  { return }  # already set
        if ($k -eq 'RUN_DB_MIGRATIONS')     { return }  # already set
        Set-Item -Path "Env:$k" -Value $v
    }
}

# Generate a real SECRET_KEY for this boot. Stable across runs (saved
# to backend/.secret-key, .gitignored) so JWT sessions survive restarts.
$SecretKeyFile = Join-Path $BackendDir '.secret-key'
if (Test-Path $SecretKeyFile) {
    $env:SECRET_KEY = (Get-Content $SecretKeyFile -Raw).Trim()
} else {
    $env:SECRET_KEY = (& $PythonExe -c "import secrets; print(secrets.token_urlsafe(64))")
    Set-Content -Path $SecretKeyFile -Value $env:SECRET_KEY -NoNewline
}

$proc = Start-Process -FilePath 'powershell' `
    -ArgumentList @(
        '-ExecutionPolicy','Bypass',
        '-Command',
        "cd '$BackendDir'; & '$PythonExe' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 | Tee-Object -FilePath '$backendLog'"
    ) `
    -WindowStyle Hidden `
    -PassThru
Write-Host "Backend launching (PID $($proc.Id)). Using $PythonExe"

# Wait up to 30s for /health.
$backendReady = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 4 -UseBasicParsing
        if ($r.StatusCode -eq 200 -and $r.Content -match '"db":"ok"') {
            Write-Host "Backend healthy: $($r.Content)"
            $backendReady = $true
            break
        }
    } catch { }
}
if (-not $backendReady) {
    Write-Host "Backend failed to come up in 30s. Last log lines:" -ForegroundColor Red
    if (Test-Path $backendLog) { Get-Content $backendLog -Tail 30 | ForEach-Object { Write-Host "  $_" } }
    exit 1
}

# ---- 2. Start the tunnel watchdog ------------------------------------------

Write-Step "Step 2: Start tunnel watchdog"

$running = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -match 'watch-tunnel\.ps1' }
if ($running) {
    Write-Host "Watchdog already running (PID $($running.ProcessId)) -- not double-starting."
} else {
    Start-Process -FilePath 'powershell' `
        -ArgumentList @('-ExecutionPolicy','Bypass','-File',(Join-Path $RepoRoot 'scripts\start-watchdog.ps1')) `
        -WindowStyle Hidden
    Write-Host "Watchdog launched (detached)."
}

# ---- 3. Wait for a healthy tunnel URL --------------------------------------

Write-Step "Step 3: Wait for a healthy tunnel URL"

$url = $null
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 2
    if (-not (Test-Path $StateFile)) { continue }
    try {
        $state = Get-Content $StateFile -Raw | ConvertFrom-Json
    } catch { continue }
    if ($state.status -eq 'healthy' -and $state.url) {
        $url = $state.url
        Write-Host "Tunnel healthy: $url"
        break
    }
    if ($state.status -and ($i % 5) -eq 0) {
        Write-Host "  ... waiting (status=$($state.status), url=$($state.url))"
    }
}

if (-not $url) {
    Write-Host "Tunnel did not become healthy in 180s. State:" -ForegroundColor Red
    if (Test-Path $StateFile) { Get-Content $StateFile } else { Write-Host "  (state file not written yet)" }
    Write-Host "Watchdog log:" -ForegroundColor Red
    if (Test-Path (Join-Path $BackendDir 'tunnel-watchdog.log')) {
        Get-Content (Join-Path $BackendDir 'tunnel-watchdog.log') -Tail 30 | ForEach-Object { Write-Host "  $_" }
    }
    exit 1
}

# Validate the URL really serves /health through Cloudflare.
try {
    $probe = Invoke-WebRequest -Uri "$url/health" -TimeoutSec 10 -UseBasicParsing -Headers @{'Cache-Control'='no-cache'}
    if ($probe.StatusCode -ne 200 -or $probe.Content -notmatch '"db":"ok"') {
        throw "unexpected: $($probe.StatusCode) $($probe.Content)"
    }
    Write-Host "Tunnel probe OK: $($probe.Content)"
} catch {
    Write-Host "Tunnel URL $url did not respond to /health: $_" -ForegroundColor Red
    exit 1
}

# ---- 4. Set Vercel env var + ensure deploy is queued -----------------------

Write-Step "Step 4: Set NEXT_PUBLIC_API_URL on Vercel (production)"

$frontendUrl = "$url/api/v1"
Write-Host "Value: $frontendUrl"

# Non-interactive env add. Pipe the value on stdin.
$envValue = $frontendUrl
$vercelCmd = (Get-Command vercel.cmd -ErrorAction Stop).Source
$vercelArgs = @('env','add','NEXT_PUBLIC_API_URL','production','--non-interactive','--yes')

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $vercelCmd
$psi.Arguments = ($vercelArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
$psi.RedirectStandardInput  = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
# On PowerShell 5.1 (Windows PowerShell), StandardInputEncoding is a
# read-only property of ProcessStartInfo (the encoding is taken from the
# shell's current Console.OutputEncoding). On pwsh 7+ the setters exist.
# We don't actually need to override UTF8 -- Vercel expects UTF-8 stdin
# which is the default everywhere we run.
$psi.WorkingDirectory = $WebDir

$p = [System.Diagnostics.Process]::Start($psi)
$p.StandardInput.WriteLine($envValue)
$p.StandardInput.Close()
$stdout = $p.StandardOutput.ReadToEnd()
$stderr = $p.StandardError.ReadToEnd()
$p.WaitForExit()
if ($stdout) { Write-Host "vercel stdout: $stdout" }
if ($stderr) { Write-Host "vercel stderr: $stderr" -ForegroundColor Yellow }

# If env var already exists, the above errors out with "already exists". In
# that case we update instead.
if ($p.ExitCode -ne 0 -and ($stderr -match 'already exists' -or $stdout -match 'already exists')) {
    Write-Host "Env var already exists -- updating instead." -ForegroundColor Yellow
    $updateArgs = @('env','update','NEXT_PUBLIC_API_URL','production','--non-interactive','--yes')
    $psi2 = New-Object System.Diagnostics.ProcessStartInfo
    $psi2.FileName = $vercelCmd
    $psi2.Arguments = ($updateArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
    $psi2.RedirectStandardInput  = $true
    $psi2.RedirectStandardOutput = $true
    $psi2.RedirectStandardError  = $true
    $psi2.UseShellExecute = $false
    $psi2.CreateNoWindow = $true
    $psi2.StandardInputEncoding  = [System.Text.Encoding]::UTF8
    $psi2.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi2.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
    $psi2.WorkingDirectory = $WebDir
    $p2 = [System.Diagnostics.Process]::Start($psi2)
    $p2.StandardInput.WriteLine($envValue)
    $p2.StandardInput.Close()
    $stdout2 = $p2.StandardOutput.ReadToEnd()
    $stderr2 = $p2.StandardError.ReadToEnd()
    $p2.WaitForExit()
    if ($stdout2) { Write-Host "vercel update stdout: $stdout2" }
    if ($stderr2) { Write-Host "vercel update stderr: $stderr2" -ForegroundColor Yellow }
    if ($p2.ExitCode -ne 0) {
        Write-Host "vercel env update exited with code $($p2.ExitCode)" -ForegroundColor Red
        exit 1
    }
} elseif ($p.ExitCode -ne 0) {
    Write-Host "vercel env add exited with code $($p.ExitCode)" -ForegroundColor Red
    exit 1
}
Write-Host "NEXT_PUBLIC_API_URL set on Vercel."

# ---- 5. Smoke test ---------------------------------------------------------

Write-Step "Step 5: Smoke-test login through the tunnel"

try {
    $login = Invoke-WebRequest -Uri "$url/api/v1/auth/login" `
        -Method POST `
        -ContentType 'application/json' `
        -Body '{"email":"demo@novamind.ai","password":"demo123"}' `
        -TimeoutSec 15 `
        -UseBasicParsing
    Write-Host "Login: HTTP $($login.StatusCode) -- $($login.Content)"
} catch {
    Write-Host "Login probe failed (expected if demo account not seeded): $_" -ForegroundColor Yellow
}

# ---- Done -----------------------------------------------------------------

Write-Step "DONE"
Write-Host "Backend public URL:  $url"
Write-Host "Frontend env:       NEXT_PUBLIC_API_URL = $frontendUrl"
Write-Host "Watchdog log:       $BackendDir\tunnel-watchdog.log"
Write-Host "Backend log:        $backendLog"
Write-Host ""
Write-Host "The watchdog will rebuild web automatically on every tunnel restart."
Write-Host "Open: https://novamind-4zx31p7gb-devangshah7s-projects.vercel.app/login"
