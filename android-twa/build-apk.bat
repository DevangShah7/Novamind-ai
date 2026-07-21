@echo off
REM Build a TWA APK for NovaMind — no Gradle, no Android Studio.
REM Output: app/build/outputs/NovaMind-release.apk

setlocal enabledelayedexpansion

set "ANDROID_HOME=C:\Users\DEVANG\AppData\Local\Android\Sdk"
set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\build-tools\35.0.0;%PATH%"

set "ROOT=%~dp0"
set "BUILD=%ROOT%app\build"
set "OUT=%BUILD%\outputs\NovaMind-release.apk"

echo === [1/7] Compile resources with aapt2 ===
del /s /q "%BUILD%\compiled" 2>nul
mkdir "%BUILD%\compiled" 2>nul
del /q "%BUILD%\compiled-res.zip" 2>nul
aapt2 compile --dir "%ROOT%app\src\main\res" -o "%BUILD%\compiled-res.zip"
if errorlevel 1 goto :fail
unzip -o "%BUILD%\compiled-res.zip" -d "%BUILD%\compiled" >nul

echo === [2/7] Link resources ===
del /q "%BUILD%\linked-res.apk" 2>nul
aapt2 link ^
  -I "%ANDROID_HOME%\platforms\android-36\android.jar" ^
  --manifest "%ROOT%app\src\main\AndroidManifest.xml" ^
  --java "%BUILD%\gen" ^
  --min-sdk-version 19 ^
  --target-sdk-version 30 ^
  --version-code 1 ^
  --version-name 1.0.0 ^
  -o "%BUILD%\linked-res.apk" ^
  "%BUILD%\compiled\values_colors.arsc.flat" ^
  "%BUILD%\compiled\values_strings.arsc.flat" ^
  "%BUILD%\compiled\values_styles.arsc.flat" ^
  "%BUILD%\compiled\drawable_ic_launcher_foreground.png.flat" ^
  "%BUILD%\compiled\mipmap-mdpi_ic_launcher.png.flat" ^
  "%BUILD%\compiled\mipmap-hdpi_ic_launcher.png.flat" ^
  "%BUILD%\compiled\mipmap-xhdpi_ic_launcher.png.flat" ^
  "%BUILD%\compiled\mipmap-xxhdpi_ic_launcher.png.flat" ^
  "%BUILD%\compiled\mipmap-xxxhdpi_ic_launcher.png.flat"
if errorlevel 1 goto :fail

echo === [3/7] Compile MainActivity.java ===
mkdir "%BUILD%\classes" 2>nul
mkdir "%BUILD%\bh-extract" 2>nul
del /q "%BUILD%\bh-extract\classes.jar" 2>nul
unzip -o "%ROOT%browserhelper.aar" classes.jar -d "%BUILD%\bh-extract" >nul
javac ^
  -source 1.8 -target 1.8 ^
  -bootclasspath "%ANDROID_HOME%\platforms\android-36\android.jar" ^
  -cp "%BUILD%\bh-extract\classes.jar" ^
  -d "%BUILD%\classes" ^
  "%ROOT%app\src\main\java\ai\novamind\app\MainActivity.java"
if errorlevel 1 goto :fail

echo === [4/7] Dex classes ===
if not exist "%BUILD%\dex" mkdir "%BUILD%\dex"
del /q "%BUILD%\dex\classes.dex" 2>nul
d8 ^
  --min-api 19 ^
  --output "%BUILD%\dex" ^
  "%BUILD%\classes\ai\novamind\app\MainActivity.class" ^
  "%BUILD%\bh-extract\classes.jar"
if errorlevel 1 goto :fail
if not exist "%BUILD%\dex\classes.dex" (
  echo ERROR: dex did not produce classes.dex
  goto :fail
)
echo CHECKPOINT: dex done, before step 5

echo === [5/7] Add classes.dex to APK ===
del /q "%BUILD%\classes.dex" 2>nul
del /q "%BUILD%\unaligned.apk" 2>nul
copy /b "%BUILD%\dex\classes.dex" "%BUILD%\classes.dex" >nul
REM Inject classes.dex into the zip via a separate .ps1 file. Inline
REM PowerShell from cmd strips $variables when the path contains
REM special characters, so a .ps1 file is the only reliable form.
powershell -NoProfile -ExecutionPolicy Bypass -File "%BUILD%\inject-dex.ps1" -ApkPath "%BUILD%\linked-res.apk" -DexPath "%BUILD%\dex\classes.dex"
if errorlevel 1 goto :fail
if not exist "%BUILD%\outputs" mkdir "%BUILD%\outputs"
copy /y "%BUILD%\linked-res.apk" "%BUILD%\unaligned.apk" >nul
if errorlevel 1 goto :fail

echo === [6/7] Zipalign ===
del /q "%BUILD%\aligned.apk" 2>nul
zipalign -f -p 4 "%BUILD%\unaligned.apk" "%BUILD%\aligned.apk"
if errorlevel 1 goto :fail

echo === [7/7] Sign with apksigner ===
del /q "%OUT%" 2>nul
REM apksigner is apksigner.bat on this build-tools; cmd resolves it
REM via PATHEXT. We do NOT call apksigner.exe directly because the
REM real binary is the .bat wrapper, which sets up classpath first.
apksigner sign ^
  --ks "%ROOT%debug.keystore" ^
  --ks-pass pass:android ^
  --key-pass pass:android ^
  --ks-key-alias androiddebugkey ^
  --out "%OUT%" ^
  "%BUILD%\aligned.apk"
if errorlevel 1 goto :fail

echo.
echo === BUILD SUCCEEDED ===
echo APK: %OUT%
echo.
echo Print the SHA-256 fingerprint of the signing certificate for the digital asset links file:
keytool -list -v -keystore "%ROOT%debug.keystore" -storepass android 2>nul | findstr /i "SHA256"
goto :eof

:fail
echo.
echo === BUILD FAILED ===
exit /b 1
