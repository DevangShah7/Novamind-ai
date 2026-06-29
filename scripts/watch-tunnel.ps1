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
$ProbeEverySec    = 30
$FailureThreshold = 3          # 3 fails * 30s = 90s before we restart
$RedeployCooldown = 300        # Don't redeploy more than once per 5 min

# ---- Logging ----------------------------------------------------------------

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0:yyyy-MM-dd HH:mm:ss}] [{1}] {2}" -f (Get-Date), $Level, $Message
    Add-Content -Path $LogFile -Value $line
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
    $candidates = @($TunnelLog, "$TunnelLog.err")
    foreach ($path in $candidates) {
        if (-not (Test-Path $path)) { continue }
        $m = Select-String -Path $path -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -List
        if ($null -ne $m) { return $m.Matches[0].Value }
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
    Write-Log "Killing any existing cloudflared processes..."
    Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2

    # Empty the instance log so Get-CurrentTunnelUrl reads only the new URL.
    if (Test-Path $TunnelLog) { Remove-Item $TunnelLog -Force }

    Write-Log "Starting fresh cloudflared tunnel -> $BackendUrl"
    # PowerShell's Start-Process rejects same-file stdout+stderr redirects, so
    # we send stderr to a sibling log and merge them on read.
    $TunnelLogErr = "$TunnelLog.err"
    if (Test-Path $TunnelLogErr) { Remove-Item $TunnelLogErr -Force }
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

    # Give Cloudflare's edge a moment to actually route to us before probing.
    Start-Sleep -Seconds 5

    # Verify the tunnel actually serves /health.
    $probeOk = $false
    for ($i = 0; $i -lt 5; $i++) {
        if (Test-BackendAlive -Url $url) { $probeOk = $true; break }
        Start-Sleep -Seconds 3
    }
    if (-not $probeOk) {
        Write-Log "Tunnel started but /health probe failed" 'ERROR'
        Save-State -Url $url -Status 'probe_failed'
        return $url
    }

    Save-State -Url $url -Status 'healthy'
    Write-Log "Tunnel healthy"
    return $url
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
    # Tail the existing instance log (if any) for the URL.
    $existingLog = Get-ChildItem -Path $BackendDir -Filter 'tunnel-*.log' -ErrorAction SilentlyContinue |
                   Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($existingLog) {
        Copy-Item $existingLog.FullName $TunnelLog -Force
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
    $currentUrl = Start-NewTunnel
    if (-not $currentUrl) {
        Write-Log "Initial tunnel start failed. Will retry on next loop." 'ERROR'
    }
}
if ($currentUrl) {
    Update-LocalEnv -Url $currentUrl
    # If the URL changed from what Vercel last had, redeploy web now.
    # On the very first boot there's nothing deployed yet, but Redeploy-Vercel
    # is idempotent -- the URL either matches (skip via cooldown) or doesn't (redeploy).
    if ((Get-SecondsSinceRedeploy -LastRedeploy $lastRedeploy) -ge $RedeployCooldown) {
        if (Redeploy-Vercel -Url $currentUrl) {
            $lastRedeploy = Get-Date
        }
    }
}

$failCount = 0
$lastRedeploy = $null

while ($true) {
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
}