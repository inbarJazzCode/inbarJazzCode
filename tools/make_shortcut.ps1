# Creates a Desktop shortcut for the Statistics & Investment Eco-System.
#
# GetFolderPath('Desktop') returns the *real* Desktop even when OneDrive has
# redirected it — which is why this works where a hand-typed
# C:\Users\<name>\Desktop path silently points at the wrong folder.

$ErrorActionPreference = 'Stop'

# Project root = parent of this script's folder (tools\)
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root 'START_WINDOWS.bat'
$icon = Join-Path $root 'assets\statinvest.ico'

if (-not (Test-Path $target)) {
    Write-Host " [X] Could not find START_WINDOWS.bat in: $root" -ForegroundColor Red
    exit 1
}

$desktop = [Environment]::GetFolderPath('Desktop')
if ([string]::IsNullOrWhiteSpace($desktop)) {
    Write-Host ' [X] Could not determine your Desktop folder.' -ForegroundColor Red
    exit 1
}

$link = Join-Path $desktop 'Investment Eco-System.lnk'

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($link)
$sc.TargetPath        = $target
$sc.WorkingDirectory  = $root
$sc.Description       = 'Statistics & Investment Eco-System - OLS, Logistic & Poisson'
if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
$sc.Save()

Write-Host ''
Write-Host ' [OK] Desktop icon created.' -ForegroundColor Green
Write-Host ''
Write-Host "      Name    : Investment Eco-System"
Write-Host "      Desktop : $desktop"
Write-Host "      Launches: $target"
Write-Host ''
Write-Host ' Double-click the azure chart icon on your Desktop to start the app.'
Write-Host ''
