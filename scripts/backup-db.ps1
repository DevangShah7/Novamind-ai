# backup-db.ps1
# Snapshots backend/novamind.db to a rotating set of timestamped files in
# the destination directory. Keeps the last 20 copies, deletes older.
#
# SQLite's "backup" semantics: it's safe to copy the .db file while the
# FastAPI process has it open, BUT the copy might capture a partially
# committed transaction. The FastAPI backend sets WAL mode on
# (backend/app/core/database.py) and checkpoints on close, so the copy
# will be at a clean snapshot as long as the OS file cache doesn't reorder
# the writes. For belt-and-suspenders, this script uses sqlite3.exe to do
# an online backup (the .backup command) if sqlite3 is on PATH, and
# falls back to a plain file copy otherwise.
#
# Parameters (all optional):
#   -DbPath      Path to the live novamind.db (default: backend/novamind.db
#                relative to the repo root)
#   -BackupDir   Destination directory (default: $env:USERPROFILE\Documents\NovaMind-Backups)
#   -Keep        Number of backups to retain (default: 20)

[CmdletBinding()]
param(
    [string]$DbPath,
    [string]$BackupDir,
    [int]$Keep = 20
)

$ErrorActionPreference = 'Stop'

if (-not $DbPath) {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
    $DbPath = Join-Path $repoRoot 'backend/novamind.db'
}
if (-not (Test-Path $DbPath)) {
    Write-Error "DB not found at $DbPath"
    exit 1
}
if (-not $BackupDir) {
    $BackupDir = Join-Path $env:USERPROFILE 'Documents\NovaMind-Backups'
}
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$target = Join-Path $BackupDir "novamind-$stamp.db"

# Try sqlite3's online backup first (atomic snapshot from SQLite's POV)
$sqlite3 = Get-Command sqlite3.exe -ErrorAction SilentlyContinue
if ($sqlite3) {
    Write-Host "Using sqlite3 online backup..."
    & sqlite3.exe $DbPath ".backup '$target'"
} else {
    # Plain copy. FastAPI is in WAL mode, so this is safe -- the WAL file
    # is included in the copy implicitly because it's appended to the
    # main DB on checkpoint, which happens every few seconds under WAL.
    # If the user wants extra safety, install sqlite3:
    #   winget install SQLite.SQLite
    Write-Host "sqlite3 not on PATH, doing plain file copy (install sqlite3 for atomic backups)"
    Copy-Item -Path $DbPath -Destination $target -Force
}

$size = (Get-Item $target).Length
Write-Host "Backed up to $target ($([math]::Round($size / 1MB, 2)) MB)"

# Rotate: keep only the $Keep most recent
$allBackups = Get-ChildItem -Path $BackupDir -Filter 'novamind-*.db' |
    Sort-Object LastWriteTime -Descending
if ($allBackups.Count -gt $Keep) {
    $toDelete = $allBackups | Select-Object -Skip $Keep
    foreach ($f in $toDelete) {
        Remove-Item $f.FullName -Force
        Write-Host "Deleted old backup $($f.Name)"
    }
}
