# build-apk.ps1 - PowerShell wrapper that does what build-apk.bat was trying
# to do, without cmd's $variable-mangling, ^-continuation, and errorlevel
# bugs. Produces app\build\outputs\$OutFileName (default: NovaMind-<alias>.apk).
#
# Parameterized on keystore so the same script can build both debug-signed
# (sideload) and release-signed (distribution) APKs from one source tree.
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$KeystorePath,
    [Parameter(Mandatory)] [string]$KeystorePass,
    [Parameter(Mandatory)] [string]$KeyAlias,
    [string]$OutFileName = "NovaMind-$KeyAlias.apk"
)

$ErrorActionPreference = 'Stop'
$env:ANDROID_HOME = 'C:\Users\DEVANG\AppData\Local\Android\Sdk'
$env:JAVA_HOME   = 'C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot'
$env:PATH        = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\build-tools\35.0.0;$env:ANDROID_HOME\platform-tools;$env:PATH"

$Root  = Split-Path -Parent $PSCommandPath
$Build = Join-Path $Root 'app\build'
$Out   = Join-Path $Build "outputs\$OutFileName"

if (-not (Test-Path $KeystorePath)) { throw "Keystore not found: $KeystorePath" }

# Step 1 -- aapt2 compile
Write-Host '=== [1/7] Compile resources with aapt2 ==='
if (Test-Path "$Build\compiled") { Remove-Item "$Build\compiled" -Recurse -Force }
New-Item -ItemType Directory -Force -Path "$Build\compiled" | Out-Null
if (Test-Path "$Build\compiled-res.zip") { Remove-Item "$Build\compiled-res.zip" -Force }
& aapt2 compile --dir "$Root\app\src\main\res" -o "$Build\compiled-res.zip"
if ($LASTEXITCODE -ne 0) { throw "aapt2 compile failed" }
Expand-Archive -Path "$Build\compiled-res.zip" -DestinationPath "$Build\compiled" -Force

# Step 2 -- aapt2 link
Write-Host '=== [2/7] Link resources ==='
if (Test-Path "$Build\linked-res.apk") { Remove-Item "$Build\linked-res.apk" -Force }
$flat = Get-ChildItem "$Build\compiled" -Filter '*.flat' | ForEach-Object { $_.FullName }
& aapt2 link `
    -I "$env:ANDROID_HOME\platforms\android-36\android.jar" `
    --manifest "$Root\app\src\main\AndroidManifest.xml" `
    --java "$Build\gen" `
    --min-sdk-version 19 `
    --target-sdk-version 30 `
    --version-code 1 `
    --version-name 1.0.0 `
    -o "$Build\linked-res.apk" `
    @flat
if ($LASTEXITCODE -ne 0) { throw "aapt2 link failed" }

# Step 3 -- javac
Write-Host '=== [3/7] Compile MainActivity.java ==='
if (-not (Test-Path "$Build\classes")) { New-Item -ItemType Directory -Force -Path "$Build\classes" | Out-Null }
if (-not (Test-Path "$Build\bh-extract")) { New-Item -ItemType Directory -Force -Path "$Build\bh-extract" | Out-Null }
if (Test-Path "$Build\bh-extract\classes.jar") { Remove-Item "$Build\bh-extract\classes.jar" -Force }
Expand-Archive -Path "$Root\browserhelper.aar" -DestinationPath "$Build\bh-extract" -Force
# aar files don't extract with Expand-Archive on older PS; fall back to .NET zip
if (-not (Test-Path "$Build\bh-extract\classes.jar")) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory("$Root\browserhelper.aar", "$Build\bh-extract")
}
& javac -source 1.8 -target 1.8 `
    -bootclasspath "$env:ANDROID_HOME\platforms\android-36\android.jar" `
    -cp "$Build\bh-extract\classes.jar" `
    -d "$Build\classes" `
    "$Root\app\src\main\java\ai\novamind\app\MainActivity.java"
if ($LASTEXITCODE -ne 0) { throw "javac failed" }

# Step 4 -- d8 dex
Write-Host '=== [4/7] Dex classes ==='
if (-not (Test-Path "$Build\dex")) { New-Item -ItemType Directory -Force -Path "$Build\dex" | Out-Null }
if (Test-Path "$Build\dex\classes.dex") { Remove-Item "$Build\dex\classes.dex" -Force }
& d8 --min-api 19 --output "$Build\dex" `
    "$Build\classes\ai\novamind\app\MainActivity.class" `
    "$Build\bh-extract\classes.jar"
if ($LASTEXITCODE -ne 0) { throw "d8 failed" }
if (-not (Test-Path "$Build\dex\classes.dex")) { throw "d8 produced no classes.dex" }

# Step 5 -- inject classes.dex into the APK
Write-Host '=== [5/7] Add classes.dex to APK ==='
# Only remove the *current target* APK (not sibling APKs from a different
# keystore flavor). Each build produces one APK; siblings stay.
if (-not (Test-Path "$Build\outputs")) { New-Item -ItemType Directory -Force -Path "$Build\outputs" | Out-Null }
if (Test-Path "$Build\outputs\$OutFileName") { Remove-Item "$Build\outputs\$OutFileName" -Force }
$OutIdsig = "$Build\outputs\$OutFileName.idsig"
if (Test-Path $OutIdsig) { Remove-Item $OutIdsig -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$z = [System.IO.Compression.ZipFile]::Open("$Build\linked-res.apk", 'Update')
try {
    $e = $z.CreateEntry('classes.dex')
    $w = New-Object System.IO.BinaryWriter($e.Open())
    try { $w.Write([System.IO.File]::ReadAllBytes("$Build\dex\classes.dex")) }
    finally { $w.Close() }
} finally { $z.Dispose() }
Copy-Item "$Build\linked-res.apk" "$Build\unaligned.apk" -Force

# Step 6 -- zipalign
Write-Host '=== [6/7] Zipalign ==='
if (Test-Path "$Build\aligned.apk") { Remove-Item "$Build\aligned.apk" -Force }
& zipalign -f -p 4 "$Build\unaligned.apk" "$Build\aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "zipalign failed" }

# Step 7 -- apksigner (it's a .bat; cmd resolves it)
Write-Host '=== [7/7] Sign with apksigner ==='
if (Test-Path $Out) { Remove-Item $Out -Force }
& apksigner sign `
    --ks "$KeystorePath" `
    --ks-pass "pass:$KeystorePass" `
    --key-pass "pass:$KeystorePass" `
    --ks-key-alias "$KeyAlias" `
    --out $Out `
    "$Build\aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "apksigner failed" }

Write-Host ''
Write-Host '=== BUILD SUCCEEDED ===' -ForegroundColor Green
Write-Host "APK:    $Out"
Write-Host "Signed: $KeystorePath (alias=$KeyAlias)" -ForegroundColor Cyan
Write-Host ''
Write-Host 'SHA-256 of signing cert (for assetlinks.json):' -ForegroundColor Cyan
& keytool -list -v -keystore "$KeystorePath" -storepass "$KeystorePass" 2>$null |
    Select-String -Pattern 'SHA256:' | ForEach-Object { $_.Line }
