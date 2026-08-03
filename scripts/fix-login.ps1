# fix-login.ps1
# One command, one paste, login works.
#
# What this does:
#   1. Asks you for a Vercel token (vbs_...) - one prompt.
#   2. Patches NEXT_PUBLIC_API_URL on Vercel for Production.
#   3. Triggers a production redeploy.
#   4. Waits for the deployment to be READY.
#   5. Smoke-tests the new frontend and the backend.
#
# How to get the token (30 seconds):
#   - Open https://vercel.com/account/tokens
#   - Click "Create Token", name it anything, scope to your project
#   - Copy the token (starts with vbs_)
#   - Paste it when this script asks
#
# How to run:
#   pwsh -File scripts\fix-login.ps1
#
# You only have to do this ONCE. After that, the URL never changes
# again because Tailscale Funnel gives us a permanent hostname.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$PublicBackendUrl = 'https://novamind.taile50f6f.ts.net'
$VercelProjectId  = 'prj_RGN8AqrCFqJJggNorZxroCVC4uRu'
$EnvVarId         = 'nvSFbxe6xeCB4arK'
$LogDir           = Join-Path (Resolve-Path "$PSScriptRoot\..") 'logs'
$LogFile          = Join-Path $LogDir 'fix-login.log'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

function Say {
    param([string]$Msg, [string]$Color = 'Cyan')
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Msg
    Add-Content -Path $LogFile -Value $line
    Write-Host $line -ForegroundColor $Color
}

# --- Step 0: get + validate the token ----------------------------------
Say 'NovaMind one-shot login fix.' Cyan
Say "backend URL: $PublicBackendUrl" DarkGray
Say '' Cyan

# Use existing env var if set, otherwise prompt once
$token = $env:VERCEL_TOKEN
if (-not $token) {
    Say 'I need a Vercel token. Get one at https://vercel.com/account/tokens' Yellow
    Say 'The token starts with vbs_ and is ~24 chars of letters/numbers.' Yellow
    Say '' Yellow
    $secure = Read-Host 'Paste your Vercel token (vbs_...)'
    if (-not $secure) {
        Say 'no token entered, aborting' Red
        exit 1
    }
    $token = $secure.Trim()
    # clear the local copy of the secure string after we've copied it out
    $secure = $null
}

if ($token -notmatch '^vbs_[A-Za-z0-9]{20,}$') {
    Say "this does not look like a Vercel token (got '$($token.Substring(0,[Math]::Min(8,$token.Length)))...')" Red
    Say 'expected format: vbs_ followed by ~24 alphanumeric chars' Yellow
    Say 'get one at https://vercel.com/account/tokens' Yellow
    exit 1
}
Say "token accepted (length $($token.Length))" Green

# --- Step 1: patch Vercel env -----------------------------------------
$apiUrl = "$PublicBackendUrl/api/v1"
$body   = @{ value = $apiUrl; target = @('production','preview','development') } | ConvertTo-Json
Say "patching Vercel env NEXT_PUBLIC_API_URL -> $apiUrl" Cyan
try {
    Invoke-RestMethod -Method Patch `
        -Uri "https://api.vercel.com/v10/projects/$VercelProjectId/env/$EnvVarId" `
        -Headers @{ Authorization = "Bearer $token" } `
        -ContentType 'application/json' -Body $body -TimeoutSec 20 | Out-Null
    Say 'env patched for production, preview, and development' Green
} catch {
    Say "patch failed: $($_.Exception.Message)" Red
    if ($_.Exception.Response) {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        Say $reader.ReadToEnd() Red
    }
    Say '' Yellow
    Say 'common causes:' Yellow
    Say '  - token expired (mint a new one)' Yellow
    Say '  - wrong project ID (this script uses prj_RGN8AqrCFqJJggNorZxroCVC4uRu)' Yellow
    Say '  - wrong env var ID (this script uses nvSFbxe6xeCB4arK)' Yellow
    exit 1
}

# --- Step 2: trigger production deploy --------------------------------
$WebDir = Join-Path (Resolve-Path "$PSScriptRoot\..") 'web'
Say "triggering production deploy from $WebDir" Cyan
Push-Location $WebDir
$deployOut = ''
try {
    $deployOut = & npx --no-install vercel deploy --prod --yes --token $token 2>&1 | Out-String
    Add-Content -Path $LogFile -Value $deployOut
} finally {
    Pop-Location
}

$deployUrl = ($deployOut -split "`n" |
    Where-Object { $_ -match '^https://[a-z0-9-]+\.vercel\.app/?\s*$' } |
    Select-Object -Last 1).Trim()

if (-not $deployUrl) {
    Say 'deploy did not return a vercel.app URL.' Red
    Say 'full output:' Red
    Write-Host $deployOut -ForegroundColor Red
    exit 1
}
Say "deploy URL: $deployUrl" Green

# --- Step 3: wait for READY -------------------------------------------
Say 'waiting for deployment to reach READY state (up to 5 minutes)' Cyan
$ready = $false
$deadline = (Get-Date).AddMinutes(5)
while (-not $ready -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    try {
        $resp = Invoke-RestMethod `
            -Uri "https://api.vercel.com/v6/deployments?projectId=$VercelProjectId&limit=1" `
            -Headers @{ Authorization = "Bearer $token" } `
            -TimeoutSec 10
        $state = $resp.deployments[0].readyState
        Say "  poll: $state" DarkGray
        if ($state -eq 'READY')  { $ready = $true; break }
        if ($state -eq 'ERROR' -or $state -eq 'CANCELED') {
            Say "deployment ended in state $state - check https://vercel.com/dashboard" Red
            exit 1
        }
    } catch {
        Say "  poll failed: $($_.Exception.Message)" Yellow
    }
}
if (-not $ready) {
    Say 'deployment did not reach READY within 5 minutes' Red
    Say 'check https://vercel.com/dashboard for status' Yellow
    exit 1
}
Say 'deployment is READY' Green

# --- Step 4: smoke tests ----------------------------------------------
Say "smoke-testing $deployUrl" Cyan
try {
    $r = Invoke-WebRequest -Uri $deployUrl -UseBasicParsing -TimeoutSec 15
    Say "  frontend: HTTP $($r.StatusCode), $($r.Content.Length) bytes" Green
} catch { Say "  frontend: $($_.Exception.Message)" Yellow }

Say "smoke-testing backend $PublicBackendUrl/health" Cyan
try {
    $r = Invoke-WebRequest -Uri "$PublicBackendUrl/health" -UseBasicParsing -TimeoutSec 15
    Say "  backend: HTTP $($r.StatusCode) -> $($r.Content)" Green
} catch { Say "  backend: $($_.Exception.Message)" Red }

Say "smoke-testing login endpoint" Cyan
try {
    $r = Invoke-WebRequest -Uri "$PublicBackendUrl/api/v1/auth/login" `
        -Method POST -UseBasicParsing -TimeoutSec 15 `
        -ContentType 'application/json' -Body '{}'
    Say "  login route: HTTP $($r.StatusCode)" Yellow
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 422) {
        Say '  login route: HTTP 422 (request reached the API correctly)' Green
    } else {
        Say "  login route: HTTP $code - $($_.Exception.Message)" Red
    }
}

# --- done --------------------------------------------------------------
Say '' Green
Say 'DONE.' Green
Say "  frontend: $deployUrl" Green
Say "  backend:  $PublicBackendUrl" Green
Say "  api:      $PublicBackendUrl/api/v1" Green
Say "  full log: $LogFile" Green
Say '' Green
Say 'next: open your production URL in an incognito/private browser window' Cyan
Say '      and try logging in. cache is the #1 cause of "still broken" after a deploy.' Cyan