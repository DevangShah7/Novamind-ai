# watch-tunnel.ps1
# Watches the Cloudflare quick-tunnel fronting the local FastAPI backend.
# When the tunnel dies (Cloudflare's quick-tunnel URLs are not stable -- the
# Mumbai edge in particular flaps hourly), this script:
#   1. Kills the dead cloudflared.exe
#   2. Starts a fresh one
#   3. Reads the new trycloudflare.com URL from the log
#   4. Updates web/.env.local so local dev points at the new tunnel
#   5. Triggers `vercel --prod` with the new URL baked in as NEXT_PUBLIC_API_URL
#   6. Writes tunnel-state.json for any other tool to consume
#
# Stop the script with Ctrl-C. It does not exit on its own.
#
# Prereqs (all already met on this machine):
#   - cloudflared installed at "C:\Program Files (x86)\cloudflared\cloudflared.exe"
#   - FastAPI running on http://127.0.0.1:8000 (uvicorn or docker compose)
#   - Vercel CLI logged in as you (run `vercel login` once)
#
# Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File scripts\watch-tunnel.ps1

$ErrorActionPreference = 'Stop'

# ---- Config -----------------------------------------------------------------

$RepoRoot       = (Resolve-Path "$PSScriptRoot\..").Path
$BackendDir     = Join-Path $RepoRoot 'backend'
$WebDir         = Join-Path $RepoRoot 'web'
$CloudflaredExe = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$LogFile        = Join-Path $BackendDir 'tunnel-watchdog.log'
$StateFile      = Join-Path $BackendDir 'tunnel-state.json'
$TunnelLog      = Join-Path $BackendDir 'tunnel-watchdog-instance.log'

$BackendUrl       = 'http://127.0.0.1:8000'
$ProbeEverySec    = 10
$FailureThreshold = 6          # 6 fails * 10s = 60s before we restart
$RedeployCooldown = 300        # Don't redeploy more than once per 5 min

# ---- Logging ----------------------------------------------------------------

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0:yyyy-MM-dd HH:mm:ss}] [{1}] {2}" -f (Get-Date), $Level, $Message
    # Add-Content in Windows PowerShell 5.1 has no -Lock parameter (that's
    # PowerShell 7+). On the rare chance two watchdogs ran at once they
    # would race, but the worst case is a missing log line. Swallow
    # errors so a transient IO blip never kills the watchdog.
    try { Add-Content -Path $LogFile -Value $line -ErrorAction Stop }
    catch { }
    Write-Host $line
}

# Roll the log on each start so it doesn't grow forever.
if (Test-Path $LogFile) { Remove-Item $LogFile -Force }

Write-Log "watch-tunnel.ps1 starting"
Write-Log "Repo root:        $RepoRoot"
Write-Log "Backend URL:      $BackendUrl"
Write-Log "Probe interval:   ${ProbeEverySec}s"
Write-Log "Failure thresh:   $FailureThreshold (= ${ProbeEverySec}s * $FailureThreshold = $($ProbeEverySec * $FailureThreshold)s of downtime tolerated)"
Write-Log "Vercel dir:       $WebDir"

# ---- Helpers ----------------------------------------------------------------

function Get-CurrentTunnelUrl {
    # Reads the most recent trycloudflare.com URL written to the tunnel instance log
    # OR its sibling stderr log. PowerShell's Start-Process refuses same-file redirects
    # for both streams, so we write them separately.
    #
    # Cloudflare occasionally logs https://api.trycloudflare.com in the startup
    # output before the real tunnel URL appears -- that's Cloudflare's own API
    # docs URL, not our tunnel. Skip it.
    $candidates = @($TunnelLog, "$TunnelLog.err")
    foreach ($path in $candidates) {
        if (-not (Test-Path $path)) { continue }
        $m = Select-String -Path $path -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -List
        if ($null -ne $m) {
            $url = $m.Matches[0].Value
            if ($url -ne 'https://api.trycloudflare.com') { return $url }
        }
    }
    return $null
}

function Test-BackendAlive {
    # Tunnel can be dead even when local backend is fine -- Cloudflare edge issue.
    # So we probe THROUGH the tunnel, not directly.
    param([string]$Url)
    try {
        $r = Invoke-WebRequest -Uri "$Url/health" -TimeoutSec 8 -UseBasicParsing -Headers @{'Cache-Control'='no-cache'}
        return ($r.StatusCode -eq 200 -and $r.Content -match '"db":"ok"')
    } catch {
        return $false
    }
}

function Test-LocalBackendAlive {
    # Probe the FastAPI on 127.0.0.1:8000 directly. Used to distinguish
    # 'tunnel dead, backend alive' from 'backend dead, tunnel alive'.
    # Returns $true / $false (never throws).
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3 -UseBasicParsing
        return ($r.StatusCode -eq 200 -and $r.Content -match '"db":"ok"')
    } catch {
        return $false
    }
}

function Start-Backend {
    # Mirror deploy-now.ps1's uvicorn-launch. Idempotent: if uvicorn is
    # already running, this is a no-op.
    $venvPy = Join-Path $BackendDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        Write-Log "venv python missing at $venvPy -- run scripts\deploy-now.ps1 once to create it" 'ERROR'
        return $false
    }

    # If something is already listening on 8000, leave it alone.
    if (Test-LocalBackendAlive) {
        Write-Log "Backend already healthy on 127.0.0.1:8000 -- not restarting"
        return $true
    }

    # Kill any orphaned python.exe bound to 8000 (taskkill tolerates no-match).
    $saveEAP = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & taskkill.exe /F /T /IM python.exe 2>&1 | Out-Null
    $ErrorActionPreference = $saveEAP
    Start-Sleep -Seconds 1

    # Set the env vars the backend expects (config.py requires SECRET_KEY).
    $env:PYTHONUNBUFFERED     = '1'
    $env:PYTHONIOENCODING     = 'utf-8'
    $env:ALLOW_DEV_SECRET_KEY = '1'
    $env:RUN_DB_MIGRATIONS    = '1'
    $dotenvPath = Join-Path $BackendDir '.env'
    if (Test-Path $dotenvPath) {
        Get-Content $dotenvPath | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith('#')) { return }
            $eq = $line.IndexOf('=')
            if ($eq -lt 1) { return }
            $k = $line.Substring(0, $eq).Trim()
            $v = $line.Substring($eq + 1).Trim()
            if ($k -in @('SECRET_KEY','ALLOW_DEV_SECRET_KEY','RUN_DB_MIGRATIONS')) { return }
            Set-Item -Path "Env:$k" -Value $v
        }
    }
    $SecretKeyFile = Join-Path $BackendDir '.secret-key'
    if (Test-Path $SecretKeyFile) {
        $env:SECRET_KEY = (Get-Content $SecretKeyFile -Raw).Trim()
    } else {
        $env:SECRET_KEY = (& $venvPy -c "import secrets; print(secrets.token_urlsafe(64))")
        Set-Content -Path $SecretKeyFile -Value $env:SECRET_KEY -NoNewline
    }

    $uvicornLog = Join-Path $BackendDir 'uvicorn.log'
    Start-Process -FilePath 'powershell' `
        -ArgumentList @(
            '-ExecutionPolicy','Bypass','-NoProfile',
            '-Command', "cd '$BackendDir'; & '$venvPy' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 | Tee-Object -FilePath '$uvicornLog'"
        ) `
        -WindowStyle Hidden | Out-Null

    Write-Log "Spawned uvicorn -- waiting for /health"
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-LocalBackendAlive) {
            Write-Log "Backend healthy after uvicorn spawn"
            return $true
        }
    }
    Write-Log "Backend did NOT come up within 30s -- check backend\uvicorn.log" 'ERROR'
    return $false
}

function Save-State {
    param([string]$Url, [string]$Status)
    $obj = @{
        url        = $Url
        status     = $Status
        updated_at = (Get-Date).ToString('o')
    }
    $obj | ConvertTo-Json | Set-Content -Path $StateFile
}

function Get-SecondsSinceRedeploy {
    param($LastRedeploy)
    if ($null -ne $LastRedeploy -and $LastRedeploy -is [DateTime] -and $LastRedeploy.Year -gt 1) {
        try {
            return ((Get-Date) - $LastRedeploy).TotalSeconds
        } catch {
            return $RedeployCooldown + 1
        }
    }
    # Treat null / MinValue as "ages ago" so we always redeploy on first run.
    return $RedeployCooldown + 1
}

# ---- Tunnel lifecycle -------------------------------------------------------

function Start-NewTunnel {
    try {
        Write-Log "Killing any existing cloudflared processes..."
        # Use taskkill /F /T to force-kill cloudflared and any children. On
        # Windows, Stop-Process -Force can hang for many seconds if the
        # process has open file handles, and the hang is silent under
        # $ErrorActionPreference = Stop. taskkill /F /T is reliable and fast.
        # We don't capture the output -- it goes to the console only.
        # taskkill exits non-zero when there's nothing to kill, which under
        # $ErrorActionPreference=Stop would throw. Use the .exe path and
        # explicitly run it inside a -ErrorAction Continue scope, then
        # clear $LASTEXITCODE so it doesn't poison later steps.
        $saveEAP = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & taskkill.exe /F /T /IM cloudflared.exe 2>&1 | Out-Null
        $ErrorActionPreference = $saveEAP
        # 128 = ERROR_NO_MORE_FILES (taskkill: "process not found") -- normal.
        # Most other non-zero codes are still concerning but we don't want to
        # die over them; the next Start-Process will reveal the real state.
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 128) {
            Write-Log "taskkill exited with unexpected code $LASTEXITCODE -- continuing" 'WARN'
        }
        $global:LASTEXITCODE = 0  # Reset to prevent downstream surprises.
        # Give the OS a moment to release any file handles the old cloudflared held.
        Start-Sleep -Seconds 3

        # Empty the instance log so Get-CurrentTunnelUrl reads only the new URL.
        # On Windows, deleting a file with an open handle fails silently -- we
        # swallow the error rather than crash.
        if (Test-Path $TunnelLog) { Remove-Item $TunnelLog -Force -ErrorAction SilentlyContinue }
        if (Test-Path "$TunnelLog.err") { Remove-Item "$TunnelLog.err" -Force -ErrorAction SilentlyContinue }

        Write-Log "Starting fresh cloudflared tunnel -> $BackendUrl"
        # PowerShell's Start-Process rejects same-file stdout+stderr redirects, so
        # we send stderr to a sibling log and merge them on read.
        $TunnelLogErr = "$TunnelLog.err"
        if (Test-Path $TunnelLogErr) { Remove-Item $TunnelLogErr -Force -ErrorAction SilentlyContinue }
        $proc = Start-Process -FilePath $CloudflaredExe `
            -ArgumentList @('tunnel','--url',$BackendUrl,'--no-autoupdate') `
            -RedirectStandardOutput $TunnelLog `
            -RedirectStandardError  $TunnelLogErr `
            -WindowStyle Hidden `
            -PassThru
        Write-Log "Started cloudflared PID $($proc.Id)"

        # Wait up to 30s for the URL to appear in the log.
        $deadline = (Get-Date).AddSeconds(30)
        $url = $null
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 2
            $url = Get-CurrentTunnelUrl
            if ($url) { break }
        }
        if (-not $url) {
            Write-Log "Failed to get URL from cloudflared within 30s" 'ERROR'
            Save-State -Url '' -Status 'failed_to_start'
            return $null
        }

        Write-Log "New tunnel URL: $url"
        Save-State -Url $url -Status 'starting'

        # Give Cloudflare's edge time to actually route to us before probing.
        # Mumbai edge in particular can take 30-60s to make a fresh tunnel reachable.
        Start-Sleep -Seconds 10

        # Verify the tunnel actually serves /health. Be patient -- 8 attempts * 5s = 40s.
        $probeOk = $false
        for ($i = 0; $i -lt 8; $i++) {
            if (Test-BackendAlive -Url $url) { $probeOk = $true; break }
            Start-Sleep -Seconds 5
        }
        if (-not $probeOk) {
            Write-Log "Tunnel started but /health probe failed after 40s" 'ERROR'
            Save-State -Url $url -Status 'probe_failed'
            return $url
        }

        Save-State -Url $url -Status 'healthy'
        Write-Log "Tunnel healthy"
        return $url
    } catch {
        Write-Log "Start-NewTunnel crashed: $_" 'ERROR'
        Save-State -Url '' -Status 'crashed'
        return $null
    }
}

function Update-LocalEnv {
    param([string]$Url)
    $envFile = Join-Path $WebDir '.env.local'
    if (-not (Test-Path $envFile)) {
        Write-Log "No .env.local at $envFile -- skipping local env update" 'WARN'
        return
    }
    $content = Get-Content $envFile -Raw
    $newUrl  = "$Url/api/v1"
    $pattern  = '(?m)^NEXT_PUBLIC_API_URL=.*$'
    $replacement = "NEXT_PUBLIC_API_URL=$newUrl"
    if ($content -match $pattern) {
        $content = $content -replace $pattern, $replacement
    } else {
        $content += "`n$replacement`n"
    }
    Set-Content -Path $envFile -Value $content -NoNewline
    Write-Log "Updated $envFile with NEXT_PUBLIC_API_URL=$newUrl"
}

function Redeploy-Vercel {
    param([string]$Url)
    Write-Log "Triggering vercel --prod with new build-time URL..."
    $prevLocation = (Get-Location).Path
    try {
        Set-Location $WebDir
        # Use the .cmd shim, NOT plain `vercel`. PowerShell's execution policy
        # blocks `vercel.ps1` unless -ExecutionPolicy Bypass is set, and there's
        # no clean way to pass that through here. The .cmd shim calls node directly.
        $vercelCmd = (Get-Command vercel.cmd -ErrorAction Stop).Source
        $vercelArgs = @('--prod','--yes') + @(
            '-b', "NEXT_PUBLIC_API_URL=$Url/api/v1",
            '-b', "NEXT_PUBLIC_USE_MOCK=false"
        )
        # Capture stdout and stderr separately so we can filter out the
        # claude-code-hint noise that Claude Code's plugin system prepends
        # to every command's stderr.
        #
        # Windows PowerShell 5.1's Process class doesn't expose the
        # `add_OutputReceived` / `add_ErrorReceived` methods (.NET Core only),
        # and Register-ObjectEvent runs its action in a separate runspace so
        # its $Event.MessageData isn't visible to the caller. Instead we poll
        # the Process's StandardOutput / StandardError streams in a loop
        # until the process exits. Simple, no eventing, no runspace gaps.
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $vercelCmd
        $psi.Arguments = ($vercelArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError  = $true
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        # stderr must not block if the process fills the pipe buffer -- that
        # would deadlock Vercel on long uploads.
        $psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        # CRITICAL: run vercel from web/, not the repo root. Without this,
        # the watchdog (which is started from the repo root) would invoke
        # vercel --prod with the *full repo* as the upload source, blowing
        # past Vercel's 2 GiB upload cap because backend/.venv, logs/, etc.
        # are still on disk and web/.vercelignore can't reach them. Setting
        # WorkingDirectory explicitly means vercel reads web/.vercelignore
        # AND only uploads web/'s working tree.
        $psi.WorkingDirectory = $WebDir
        $p = [System.Diagnostics.Process]::Start($psi)
        $outLines = [System.Collections.ArrayList]::new()
        $errLines = [System.Collections.ArrayList]::new()
        # Read each stream on its own background task so neither blocks on
        # the other filling up. .ReadLineAsync returns "" on EOF, $null only
        # if we read past EOF before checking HasExited.
        $outTask = $p.StandardOutput.ReadLineAsync()
        $errTask = $p.StandardError.ReadLineAsync()
        while (-not $p.HasExited) {
            if ($outTask.IsCompleted) {
                $line = $outTask.Result
                if ($null -ne $line -and $line -notmatch '<claude-code-hint') { [void]$outLines.Add($line) }
                if ($null -ne $line) { $outTask = $p.StandardOutput.ReadLineAsync() } else { $outTask = $null }
            }
            if ($errTask.IsCompleted) {
                $line = $errTask.Result
                if ($null -ne $line -and $line -notmatch '<claude-code-hint') { [void]$errLines.Add($line) }
                if ($null -ne $line) { $errTask = $p.StandardError.ReadLineAsync() } else { $errTask = $null }
            }
            if ($null -eq $outTask -and $null -eq $errTask) { break }
            Start-Sleep -Milliseconds 50
        }
        # Drain any final lines the process emitted after our last poll.
        if ($outTask) {
            while ($true) {
                $line = $outTask.Result
                if ($null -eq $line) { break }
                if ($line -notmatch '<claude-code-hint') { [void]$outLines.Add($line) }
                $outTask = $p.StandardOutput.ReadLineAsync()
            }
        }
        if ($errTask) {
            while ($true) {
                $line = $errTask.Result
                if ($null -eq $line) { break }
                if ($line -notmatch '<claude-code-hint') { [void]$errLines.Add($line) }
                $errTask = $p.StandardError.ReadLineAsync()
            }
        }
        $vercelExit = $p.ExitCode
        if ($outLines.Count -gt 0) {
            $tail = ($outLines | Select-Object -Last 25) -join "`n"
            Write-Log "vercel output (last 25 lines):`n$tail"
        }
        if ($errLines.Count -gt 0) {
            $tail = ($errLines | Select-Object -Last 25) -join "`n"
            Write-Log "vercel stderr (last 25 lines):`n$tail" 'WARN'
        }
        if ($vercelExit -ne 0) {
            Write-Log "vercel --prod exited with code $vercelExit" 'ERROR'
            return $false
        }
        Write-Log "vercel --prod completed"
        return $true
    } catch {
        # Don't let transient stream-reader issues kill the watchdog. The
        # <claude-code-hint> exception text is from a plugin injection,
        # not a real deploy failure -- if the process exited cleanly the
        # exit code check above would have caught true errors.
        $msg = "$_"
        if ($msg -match '<claude-code-hint') {
            Write-Log "vercel deploy emitted plugin hint (non-fatal): $msg" 'WARN'
            return $true
        }
        Write-Log "vercel deploy failed: $_" 'ERROR'
        return $false
    } finally {
        Set-Location $prevLocation
    }
}

# ---- Main loop --------------------------------------------------------------

# Boot: ensure the local backend is up. If not, the script is pointless.
try {
    $r = Invoke-WebRequest -Uri "$BackendUrl/health" -TimeoutSec 5 -UseBasicParsing
    if ($r.StatusCode -ne 200) { throw "Backend returned $($r.StatusCode)" }
    Write-Log "Local backend alive at $BackendUrl"
} catch {
    Write-Log "Local backend not responding at $BackendUrl. Start it first (uvicorn or docker compose up -d backend)." 'ERROR'
    Save-State -Url '' -Status 'backend_down'
    exit 1
}

# Boot: start a tunnel. If one is already running and healthy, keep it.
$currentUrl = $null
$existing = Get-Process -Name cloudflared -ErrorAction SilentlyContinue
if ($existing) {
    Write-Log "Existing cloudflared PID $($existing.Id) -- checking its URL..."
    # Tail the existing instance log (if any) for the URL. We need to look
    # for logs from PREVIOUS cloudflared instances (e.g. tunnel-backend.log,
    # tunnel-backend-2.log), but skip our own files:
    #   tunnel-watchdog.log (this script's output)
    #   tunnel-watchdog-instance.log (+ .err) (current cloudflared's stdout)
    # If the search picked up the latter two, Copy-Item would try to copy a
    # file onto itself and throw "Cannot overwrite with itself" -- fatal
    # under $ErrorActionPreference = 'Stop'.
    $existingLog = Get-ChildItem -Path $BackendDir -Filter 'tunnel-*.log' -ErrorAction SilentlyContinue |
                       Where-Object { $_.Name -notlike 'tunnel-watchdog*' } |
                       Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($existingLog) {
        Copy-Item $existingLog.FullName $TunnelLog -Force -ErrorAction SilentlyContinue
        $currentUrl = Get-CurrentTunnelUrl
        if ($currentUrl -and (Test-BackendAlive -Url $currentUrl)) {
            Write-Log "Existing tunnel is healthy: $currentUrl"
            Save-State -Url $currentUrl -Status 'healthy'
        } else {
            Write-Log "Existing tunnel URL present but unhealthy -- will restart"
            $currentUrl = $null
        }
    }
}
if (-not $currentUrl) {
    try {
        $currentUrl = Start-NewTunnel
    } catch {
        Write-Log "Initial tunnel start crashed: $_" 'ERROR'
        $currentUrl = $null
    }
    if (-not $currentUrl) {
        Write-Log "Initial tunnel start failed. Will retry on next loop." 'ERROR'
    }
}
if ($currentUrl) {
    try {
        Update-LocalEnv -Url $currentUrl
        # If the URL changed from what Vercel last had, redeploy web now.
        # On the very first boot there's nothing deployed yet, but Redeploy-Vercel
        # is idempotent -- the URL either matches (skip via cooldown) or doesn't (redeploy).
        if ((Get-SecondsSinceRedeploy -LastRedeploy $lastRedeploy) -ge $RedeployCooldown) {
            if (Redeploy-Vercel -Url $currentUrl) {
                $lastRedeploy = Get-Date
            }
        }
    } catch {
        Write-Log "Boot-time redeploy crashed: $_" 'ERROR'
    }
}

$failCount = 0
# NOTE: $lastRedeploy is intentionally left UNDEFINED here. On first reference
# it will be $null and Get-SecondsSinceRedeploy treats $null as "ages ago" so
# the first redeploy goes through. Reassigning to $null here would reset any
# value set during the boot-time redeploy and break the cooldown.

# Wrap the entire main loop in try/catch so a transient error (a logging
# race, a Save-State IO blip, an unreachable tunnel during a probe) logs and
# continues instead of killing the watchdog silently.
while ($true) {
    try {
        Start-Sleep -Seconds $ProbeEverySec
        $url = Get-CurrentTunnelUrl
        if (-not $url) {
            # No URL known -- try to start one.
            $failCount++
            Write-Log "No tunnel URL known ($failCount / $FailureThreshold)" 'WARN'
            if ($failCount -ge $FailureThreshold) {
                $failCount = 0
                $currentUrl = Start-NewTunnel
                if ($currentUrl) {
                    Update-LocalEnv -Url $currentUrl
                    $secondsSince = Get-SecondsSinceRedeploy -LastRedeploy $lastRedeploy
                    if ($secondsSince -ge $RedeployCooldown) {
                        if (Redeploy-Vercel -Url $currentUrl) {
                            $lastRedeploy = Get-Date
                        }
                    } else {
                        Write-Log "Skipping redeploy -- cooldown $($RedeployCooldown - $secondsSince)s remaining"
                    }
                }
            }
            continue
        }

        $ok = Test-BackendAlive -Url $url
        if ($ok) {
            if ($failCount -gt 0) {
                Write-Log "Tunnel recovered after $failCount failed probes"
            }
            $failCount = 0
            Save-State -Url $url -Status 'healthy'
            continue
        }

        $failCount++
        Write-Log "Probe failed ($failCount / $FailureThreshold) for $url" 'WARN'
        if ($failCount -ge $FailureThreshold) {
            $failCount = 0
            # Distinguish: was the backend dead, or just the tunnel?
            $backendOk = Test-LocalBackendAlive
            if (-not $backendOk) {
                Write-Log "Local backend (127.0.0.1:8000) is DOWN -- restarting uvicorn first"
                Start-Backend | Out-Null
                # Give uvicorn a moment to come up before probing again.
                Start-Sleep -Seconds 3
                if (Test-LocalBackendAlive) {
                    Write-Log "Backend recovered; looping without restarting the tunnel"
                    continue
                }
            }
            Write-Log "Tunnel declared dead -- restarting"
            $currentUrl = Start-NewTunnel
            if ($currentUrl) {
                Update-LocalEnv -Url $currentUrl
                $secondsSince = Get-SecondsSinceRedeploy -LastRedeploy $lastRedeploy
                if ($secondsSince -ge $RedeployCooldown) {
                    if (Redeploy-Vercel -Url $currentUrl) {
                        $lastRedeploy = Get-Date
                    }
                } else {
                    Write-Log "Skipping redeploy -- cooldown $($RedeployCooldown - $secondsSince)s remaining"
                }
            }
        }
    } catch {
        # Never let the watchdog die silently. Log and continue.
        Write-Log "Unhandled exception in main loop: $_" 'ERROR'
    }
}