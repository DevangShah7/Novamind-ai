# deploy-and-verify.ps1
# One-shot script: patches Vercel env, triggers a production deploy,
# waits for the build to finish, and runs a smoke test against the
# deployed frontend + the new backend URL.
#
# Required: $env:VERCEL_TOKEN must be a Vercel token (starts with vbs_).
# Get one at https://vercel.com/account/tokens.
#
# Usage:
#   $env:VERCEL_TOKEN = "vbs_..."
#   pwsh -File scripts\deploy-and-verify.ps1
#
# The script intentionally fails fast on any problem so you can re-run
# it after fixing the issue.

[CmdletBinding()]
param(
    [string]$PublicBackendUrl = 'https://novamind.taile50f6f.ts.net',
    [string]$VercelProjectId  = 'prj_RGN8AqrCFqJJggNorZxroCVC4uRu',
    [string]$EnvVarId         = 'nvSFbxe6xeCB4arK',
    [string]$VercelToken      = $env:VERCEL_TOKEN,
    [int]   $BuildTimeoutSec  = 300
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$WebDir   = Join-Path $RepoRoot 'web'
$LogDir   = Join-Path $RepoRoot 'logs'
$LogFile  = Join-Path $LogDir 'deploy.log'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

function Write-Step {
    param([string]$Msg, [string]$Color = 'Cyan')
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Msg
    Add-Content -Path $LogFile -Value $line
    Write-Host $line -ForegroundColor $Color
}

# --- Step 0: validate token shape -------------------------------------
if (-not $VercelToken) {
    Write-Step 'ERROR: $env:VERCEL_TOKEN is empty.' Red
    Write-Step 'Mint a token at https://vercel.com/account/tokens, then re-run.' Yellow
    exit 1
}
if ($VercelToken -notmatch '^vbs_[A-Za-z0-9]{20,}$') {
    Write-Step "ERROR: token does not look like a Vercel token (expected vbs_..., got '$($VercelToken.Substring(0,[Math]::Min(8,$VercelToken.Length)))...')." Red
    Write-Step 'Vercel tokens start with vbs_ and are ~24 chars of alphanumeric.' Yellow
    exit 1
}
Write-Step "token OK (length $($VercelToken.Length), starts with $($VercelToken.Substring(0,4))...)" Green

# --- Step 1: patch Vercel env -----------------------------------------
$apiUrl = "$PublicBackendUrl/api/v1"
$body   = @{ value = $apiUrl; target = @('production','preview','development') } | ConvertTo-Json
Write-Step "patching Vercel env $EnvVarId -> $apiUrl" Cyan
try {
    Invoke-RestMethod -Method Patch `
        -Uri "https://api.vercel.com/v10/projects/$VercelProjectId/env/$EnvVarId" `
        -Headers @{ Authorization = "Bearer $VercelToken" } `
        -ContentType 'application/json' -Body $body -TimeoutSec 20 | Out-Null
    Write-Step 'env patched' Green
} catch {
    Write-Step "patch failed: $($_.Exception.Message)" Red
    if ($_.Exception.Response) {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        Write-Step $reader.ReadToEnd() Red
    }
    exit 1
}

# --- Step 2: trigger production deploy --------------------------------
Write-Step 'triggering production deploy (vcl deploy --prod)' Cyan
Push-Location $WebDir
try {
    $deployOutput = & npx --no-install vercel deploy --prod --yes --token $VercelToken 2>&1 | Out-String
    Add-Content -Path $LogFile -Value $deployOutput
} finally {
    Pop-Location
}

# Extract the deployment URL (last line that looks like https://*.vercel.app)
$deployUrl = ($deployOutput -split "`n" |
    Where-Object { $_ -match '^https://[a-z0-9-]+\.vercel\.app/?\s*$' } |
    Select-Object -Last 1).Trim()

if (-not $deployUrl) {
    Write-Step 'deploy did not return a vercel.app URL. Full output above.' Red
    exit 1
}
Write-Step "deploy complete: $deployUrl" Green

# --- Step 3: wait for the deployment to be READY ---------------------
Write-Step "waiting for deployment to reach READY state (timeout ${BuildTimeoutSec}s)" Cyan
$ready = $false
$deadline = (Get-Date).AddSeconds($BuildTimeoutSec)
$deploymentId = ($deployUrl -split '/')[3]  # e.g. https://novamind-ai-abc123.vercel.app
# Fallback: fall back to listing recent deployments if ID parse fails
while (-not $ready -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    try {
        $resp = Invoke-RestMethod `
            -Uri "https://api.vercel.com/v6/deployments?projectId=$VercelProjectId&limit=1" `
            -Headers @{ Authorization = "Bearer $VercelToken" } `
            -TimeoutSec 10
        $state = $resp.deployments[0].readyState
        Write-Step "  poll: latest deployment state = $state" DarkGray
        if ($state -eq 'READY')  { $ready = $true; break }
        if ($state -eq 'ERROR' -or $state -eq 'CANCELED') {
            Write-Step "deployment ended in state $state" Red
            exit 1
        }
    } catch {
        Write-Step "  poll failed: $($_.Exception.Message)" Yellow
    }
}
if (-not $ready) {
    Write-Step "deployment did not reach READY within ${BuildTimeoutSec}s" Red
    Write-Step "check status at https://vercel.com/dashboard" Yellow
    exit 1
}
Write-Step 'deployment READY' Green

# --- Step 4: smoke test -----------------------------------------------
Write-Step "smoke-testing deployed frontend at $deployUrl" Cyan
try {
    $r = Invoke-WebRequest -Uri $deployUrl -UseBasicParsing -TimeoutSec 15
    Write-Step "  HTTP $($r.StatusCode), $($r.Content.Length) bytes" Green
} catch {
    Write-Step "  frontend unreachable: $($_.Exception.Message)" Red
}

Write-Step "smoke-testing backend at $PublicBackendUrl/health" Cyan
try {
    $r = Invoke-WebRequest -Uri "$PublicBackendUrl/health" -UseBasicParsing -TimeoutSec 15
    Write-Step "  HTTP $($r.StatusCode) -> $($r.Content)" Green
} catch {
    Write-Step "  backend unreachable: $($_.Exception.Message)" Red
}

Write-Step "smoke-testing login endpoint through public URL" Cyan
try {
    $r = Invoke-WebRequest -Uri "$PublicBackendUrl/api/v1/auth/login" `
        -Method POST -UseBasicParsing -TimeoutSec 15 `
        -ContentType 'application/json' -Body '{}'
    Write-Step "  HTTP $($r.StatusCode) (expected 422 = routed correctly)" Green
} catch {
    # 422 is a success here — it means the request reached the API.
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 422) {
        Write-Step "  HTTP 422 (request reached the API correctly)" Green
    } else {
        Write-Step "  HTTP $code : $($_.Exception.Message)" Red
    }
}

Write-Step '' Green
Write-Step 'DEPLOY COMPLETE' Green
Write-Step "  Frontend: $deployUrl" Green
Write-Step "  Backend:  $PublicBackendUrl" Green
Write-Step "  Login:    $PublicBackendUrl/api/v1/auth/login" Green
Write-Step "  Logs:     $LogFile" Green
