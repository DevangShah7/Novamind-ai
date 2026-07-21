# watch-services.ps1
# Forever-alive watchdog for the named-tunnel era.
#
# Cloudflare's named tunnels (api.your-subdomain.duckdns.org) have FIXED URLs --
# the DNS record never rotates. So unlike the old quick-tunnel watchdog
# (scripts/watch-tunnel.ps1) which had to re-deploy Vercel every time the URL
# changed, this script's only jobs are:
#
#   1. Make sure cloudflared (the tunnel) is running.
#   2. Make sure uvicorn (the FastAPI backend) is running on localhost:8000.
#   3. Make sure ollama (the LLM server) is running on localhost:11434.
#   4. Health-check the public URL every 30s and log a warning if it 5xxes.
#
# It does NOT:
#   - Redeploy Vercel. The URL is fixed; there's nothing to rebake.
#   - Touch .env.local. The URL is in cloudflared's config.yml, not in Vercel.
#   - Kill the watchdog on transient errors. Every loop is wrapped in try/catch.
#
# Stop with Ctrl-C. Designed to run forever in a visible PowerShell window
# (or, for true fire-and-forget, install as a Scheduled Task -- see
# scripts/install-services.ps1).
#
# Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File scripts\watch-services.ps1

$ErrorActionPreference = 'Stop'

# ---- Config ----------------------------------------------------------------

$RepoRoot       = (Resolve-Path "$PSScriptRoot\..").Path
$BackendDir     = Join-Path $RepoRoot 'backend'
$LogFile        = Join-Path $BackendDir 'services-watchdog.log'
$StateFile      = Join-Path $BackendDir 'services-state.json'

# Public URL of your named tunnel. SET THIS ONCE after you finish the
# scripts/deploy-permanent-tunnel.md walkthrough. Example:
#   $PublicUrl = 'https://api.novamind-shah.duckdns.org'
# Leave $null if you don't have one yet -- the watchdog still keeps the
# three local services alive; it just skips the public probe.
$PublicUrl      = $env:NOVAMIND_PUBLIC_URL  # read from env, optional

$BackendPort    = 8000
$OllamaPort     = 11434
$BackendUrl     = "http://127.0.0.1:$BackendPort"
$OllamaUrl      = "http://127.0.0.1:$OllamaPort"
$CloudflaredExe = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$UvicornExe     = (Get-Command python.exe -ErrorAction Stop).Source
$OllamaExe      = (Get-Command ollama.exe -ErrorAction SilentlyContinue).Source

# How often the main loop runs. 30s is fine for a personal demo.
$LoopEverySec   = 30

# A service must fail THIS many consecutive probes before we restart it.
# At 30s/loop that's 60s of confirmed downtime -- short enough that the
# public URL doesn't appear "down" for long, long enough that a single
# transient blip (uvicorn GC pause, brief Ollama model swap) doesn't
# trigger a needless restart.
$FailureThreshold = 2

# ---- Logging ---------------------------------------------------------------

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0:yyyy-MM-dd HH:mm:ss}] [{1}] {2}" -f (Get-Date), $Level, $Message
    try { Add-Content -Path $LogFile -Value $line -ErrorAction Stop } catch { }
    Write-Host $line
}

if (Test-Path $LogFile) { Remove-Item $LogFile -Force }

Write-Log "watch-services.ps1 starting"
Write-Log "Repo root:        $RepoRoot"
Write-Log "Backend:          $BackendUrl"
Write-Log "Ollama:           $OllamaUrl"
Write-Log "Public URL:       $(if ($PublicUrl) { $PublicUrl } else { '(none -- env NOVAMIND_PUBLIC_URL not set)' })"
Write-Log "Loop interval:    ${LoopEverySec}s"
Write-Log "Failure thresh:   $FailureThreshold (=$($LoopEverySec * $FailureThreshold)s of downtime tolerated)"

function Save-State {
    param($Backend, $Ollama, $Tunnel, $Public, [string]$Status)
    $obj = @{
        backend    = $Backend
        ollama     = $Ollama
        tunnel     = $Tunnel
        public     = $Public
        status     = $Status
        updated_at = (Get-Date).ToString('o')
    }
    try { $obj | ConvertTo-Json | Set-Content -Path $StateFile } catch { }
}

# ---- Probes ----------------------------------------------------------------

function Test-Backend {
    try {
        $r = Invoke-WebRequest -Uri "$BackendUrl/health" -TimeoutSec 5 -UseBasicParsing
        return ($r.StatusCode -eq 200 -and $r.Content -match '"db":"ok"')
    } catch { return $false }
}

function Test-Ollama {
    try {
        $r = Invoke-WebRequest -Uri "$OllamaUrl/" -TimeoutSec 5 -UseBasicParsing
        return ($r.StatusCode -eq 200 -and $r.Content -match 'Ollama is running')
    } catch { return $false }
}

function Test-Cloudflared {
    # Process check, not URL check. The tunnel can be alive even when /health
    # is briefly slow (cold start, edge hiccup). Process-alive is the right
    # signal for "is the tunnel software up".
    return $null -ne (Get-Process -Name cloudflared -ErrorAction SilentlyContinue)
}

function Test-Public {
    # Only meaningful when a named-tunnel URL is configured.
    if (-not $PublicUrl) { return $true }
    try {
        $r = Invoke-WebRequest -Uri "$PublicUrl/health" -TimeoutSec 8 -UseBasicParsing
        return ($r.StatusCode -eq 200 -and $r.Content -match '"db":"ok"')
    } catch { return $false }
}

# ---- Restarters ------------------------------------------------------------

function Restart-Cloudflared {
    # cloudflared is installed as a Windows service (by scripts/install-services.ps1)
    # so it should be auto-restarting on its own. If it isn't, our service
    # check at boot is broken -- call that out, don't try to fix it here.
    if ($null -eq $OllamaExe -and $null -eq (Get-Service cloudflared -ErrorAction SilentlyContinue)) {
        Write-Log "cloudflared process not running AND not a service -- install it with scripts/install-services.ps1" 'ERROR'
        return $false
    }
    # Try the service first (if installed)
    $svc = Get-Service cloudflared -ErrorAction SilentlyContinue
    if ($svc) {
        try {
            Write-Log "Restarting cloudflared service"
            Restart-Service cloudflared -Force -ErrorAction Stop
            return $true
        } catch {
            Write-Log "Restart-Service cloudflared failed: $_" 'ERROR'
            return $false
        }
    }
    # Fallback: start the process manually using the named-tunnel config.
    # This is what would run if the user hasn't yet installed the service
    # but has a working cloudflared config.
    if (-not (Test-Path $CloudflaredExe)) {
        Write-Log "cloudflared.exe not at $CloudflaredExe" 'ERROR'
        return $false
    }
    Write-Log "Starting cloudflared with named-tunnel config (no service installed yet)"
    $configFile = Join-Path $env:USERPROFILE '.cloudflared\config.yml'
    if (-not (Test-Path $configFile)) {
        Write-Log "No config at $configFile -- run scripts/deploy-permanent-tunnel.md first" 'ERROR'
        return $false
    }
    Start-Process -FilePath $CloudflaredExe -WindowStyle Hidden
    return $true
}

function Restart-Uvicorn {
    Write-Log "Starting uvicorn on $BackendUrl"
    $args = @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$BackendPort")
    $logPath = Join-Path $BackendDir 'uvicorn-stdout.log'
    $errPath = Join-Path $BackendDir 'uvicorn-stderr.log'
    if (Test-Path $logPath) { Remove-Item $logPath -Force }
    if (Test-Path $errPath) { Remove-Item $errPath -Force }
    $proc = Start-Process -FilePath $UvicornExe `
        -ArgumentList $args `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $logPath `
        -RedirectStandardError $errPath `
        -WindowStyle Hidden `
        -PassThru
    Write-Log "uvicorn started PID $($proc.Id) -- logs at $logPath"
    return $true
}

function Restart-Ollama {
    if (-not $OllamaExe) {
        Write-Log "ollama.exe not on PATH -- skipping" 'WARN'
        return $false
    }
    # Try the service first
    $svc = Get-Service ollama -ErrorAction SilentlyContinue
    if ($svc) {
        try {
            Write-Log "Restarting ollama service"
            Restart-Service ollama -Force -ErrorAction Stop
            return $true
        } catch {
            Write-Log "Restart-Service ollama failed: $_" 'ERROR'
            return $false
        }
    }
    # Fallback: launch the binary in background
    Write-Log "Starting ollama serve (no service installed yet)"
    Start-Process -FilePath $OllamaExe -ArgumentList @('serve') -WindowStyle Hidden
    return $true
}

# ---- Main loop -------------------------------------------------------------

# Boot-time startup: bring everything up if it's down.
Write-Log "--- Boot-time checks ---"
if (-not (Test-Backend)) {
    Write-Log "Backend not responding -- starting it"
    Restart-Uvicorn | Out-Null
    Start-Sleep -Seconds 3
}
if (-not (Test-Ollama)) {
    Write-Log "Ollama not responding -- starting it"
    Restart-Ollama | Out-Null
    Start-Sleep -Seconds 3
}
if (-not (Test-Cloudflared)) {
    Write-Log "cloudflared not running -- starting it"
    Restart-Cloudflared | Out-Null
    Start-Sleep -Seconds 5
}

$backendFails = 0
$ollamaFails  = 0
$tunnelFails  = 0
$publicFails  = 0

while ($true) {
    try {
        Start-Sleep -Seconds $LoopEverySec

        # Backend
        $backendOk = Test-Backend
        if (-not $backendOk) {
            $backendFails++
            Write-Log "Backend down ($backendFails / $FailureThreshold)" 'WARN'
            if ($backendFails -ge $FailureThreshold) {
                $backendFails = 0
                Restart-Uvicorn
                Start-Sleep -Seconds 5
            }
        } else {
            if ($backendFails -gt 0) { Write-Log "Backend recovered" }
            $backendFails = 0
        }

        # Ollama (only matters for chat features; don't alarm if it's not installed)
        if ($OllamaExe) {
            $ollamaOk = Test-Ollama
            if (-not $ollamaOk) {
                $ollamaFails++
                Write-Log "Ollama down ($ollamaFails / $FailureThreshold)" 'WARN'
                if ($ollamaFails -ge $FailureThreshold) {
                    $ollamaFails = 0
                    Restart-Ollama
                    Start-Sleep -Seconds 5
                }
            } else {
                if ($ollamaFails -gt 0) { Write-Log "Ollama recovered" }
                $ollamaFails = 0
            }
        } else { $ollamaOk = $true }

        # Tunnel
        $tunnelOk = Test-Cloudflared
        if (-not $tunnelOk) {
            $tunnelFails++
            Write-Log "cloudflared not running ($tunnelFails / $FailureThreshold)" 'WARN'
            if ($tunnelFails -ge $FailureThreshold) {
                $tunnelFails = 0
                Restart-Cloudflared
                Start-Sleep -Seconds 10
            }
        } else {
            if ($tunnelFails -gt 0) { Write-Log "cloudflared recovered" }
            $tunnelFails = 0
        }

        # Public URL (optional)
        $publicOk = Test-Public
        if (-not $publicOk -and $PublicUrl) {
            $publicFails++
            Write-Log "Public URL $PublicUrl unhealthy ($publicFails / $FailureThreshold)" 'WARN'
        } else {
            $publicFails = 0
        }

        $overallOk = $backendOk -and $ollamaOk -and $tunnelOk -and $publicOk
        $status = if ($overallOk) { 'healthy' } else { 'degraded' }
        Save-State -Backend $backendOk -Ollama $ollamaOk -Tunnel $tunnelOk -Public $publicOk -Status $status
    } catch {
        Write-Log "Unhandled exception in main loop: $_" 'ERROR'
    }
}
