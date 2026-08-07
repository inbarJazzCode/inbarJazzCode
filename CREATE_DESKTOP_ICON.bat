@echo off
REM ===================================================================
REM  Creates a proper Desktop icon for the app.
REM  Double-click this ONCE. After that, launch from the Desktop icon.
REM ===================================================================
setlocal
cd /d "%~dp0"
title Create Desktop icon

echo.
echo  ============================================================
echo   Invest-System  -  create Desktop icon
echo  ============================================================

if not exist "%~dp0START_WINDOWS.bat" (
  echo.
  echo  [X] START_WINDOWS.bat is not in this folder.
  echo      Keep this file next to it and try again.
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\make_shortcut.ps1"

if errorlevel 1 (
  echo.
  echo  [X] Could not create the shortcut.
  echo      Try running this as your normal user, not as Administrator.
  echo.
  pause
  exit /b 1
)

pause
endlocal
