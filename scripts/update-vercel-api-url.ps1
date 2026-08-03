# update-vercel-api-url.ps1
# Patch the deployed Vercel frontend's NEXT_PUBLIC_API_URL to the
# current Tailscale Funnel URL.
#
# Usage:
#   $env:VERCEL_TOKEN = '<your token from vercel.com/account/tokens>'
#   pwsh -File scripts\update-vercel-api-url.ps1
#
# After patching, redeploy the Vercel project (the env change alone
# does NOT trigger a redeploy for production). The fastest way is:
#   vercel --prod
# from the web/ directory, or click "Redeploy" in the Vercel
# dashboard on the latest deployment.

[CmdletBinding()]
param(
    [string]$Url              = 'https://novamind.taile50f6f.ts.net',
    [string]$VercelProjectId  = 'prj_RGN8AqrCFqJJggNorZxroCVC4uRu',
    [string]$EnvVarId         = 'nvSFbxe6xeCB4arK',
    [string]$VercelToken      = $env:VERCEL_TOKEN
)

$ErrorActionPreference = 'Stop'

if (-not $VercelToken) {
    Write-Host 'ERROR: $env:VERCEL_TOKEN is empty.' -ForegroundColor Red
    Write-Host 'Get a token at https://vercel.com/account/tokens, then:' -ForegroundColor Yellow
    Write-Host '  $env:VERCEL_TOKEN = "vbs_..."' -ForegroundColor Yellow
    Write-Host '  pwsh -File scripts\update-vercel-api-url.ps1' -ForegroundColor Yellow
    exit 1
}

$apiUrl = "$Url/api/v1"
$body   = @{ value = $apiUrl; target = @('production','preview','development') } | ConvertTo-Json

Write-Host "Patching Vercel project $VercelProjectId env $EnvVarId -> $apiUrl" -ForegroundColor Cyan

try {
    $resp = Invoke-RestMethod -Method Patch `
        -Uri "https://api.vercel.com/v10/projects/$VercelProjectId/env/$EnvVarId" `
        -Headers @{ Authorization = "Bearer $VercelToken" } `
        -ContentType 'application/json' -Body $body -TimeoutSec 20

    Write-Host "OK. Vercel env updated to: $apiUrl" -ForegroundColor Green
    Write-Host ''
    Write-Host 'Next step: trigger a production redeploy so the new env is baked into the bundle:' -ForegroundColor Yellow
    Write-Host '  cd web; vercel --prod' -ForegroundColor Yellow
} catch {
    Write-Host "PATCH failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        Write-Host $reader.ReadToEnd() -ForegroundColor Red
    }
    exit 1
}
