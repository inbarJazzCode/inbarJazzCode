@echo off
REM ===================================================================
REM  Statistics & Investment Eco-System  --  one-click start (Windows)
REM  Double-click this file. It does everything: checks Python, installs
REM  what it needs the first time, then opens the app in your browser.
REM ===================================================================
setlocal
cd /d "%~dp0"
title Statistics ^& Investment Eco-System

echo.
echo  ============================================================
echo   Statistics ^& Investment Eco-System
echo   Starting up. The first run takes 2-3 minutes.
echo  ============================================================
echo.

REM --- 1. Is Python installed? ---------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
  echo  [X] Python is not installed, or not on your PATH.
  echo.
  echo      Install it from:  https://www.python.org/downloads/
  echo      IMPORTANT: tick "Add Python to PATH" on the first screen.
  echo      Then double-click this file again.
  echo.
  pause
  exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYV=%%v
echo  [OK] Python %PYV% found.

REM --- 2. Create the private environment (first run only) ------------
if not exist ".venv\Scripts\python.exe" (
  echo  [..] Creating a private environment ^(first run only^)...
  python -m venv .venv
  if errorlevel 1 (
    echo  [X] Could not create the environment. Try running as your normal user.
    pause
    exit /b 1
  )
)
echo  [OK] Environment ready.

REM --- 3. Install dependencies (first run only) ----------------------
if not exist ".venv\.installed" (
  echo  [..] Installing required packages. This is the slow part, once.
  .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
  .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
  if errorlevel 1 (
    echo  [X] Installation failed. Check your internet connection.
    pause
    exit /b 1
  )
  echo installed > .venv\.installed
)
echo  [OK] Packages installed.

REM --- 4. Self-check --------------------------------------------------
echo  [..] Running the built-in self-check...
.venv\Scripts\python.exe main.py smoke
if errorlevel 1 (
  echo.
  echo  [!] The self-check reported a problem. The app may still run.
  echo.
)

REM --- 5. Launch ------------------------------------------------------
echo.
echo  ============================================================
echo   Opening the app at  http://localhost:8501
echo   Leave THIS WINDOW OPEN while you use the app.
echo   To stop: close this window, or press Ctrl+C.
echo  ============================================================
echo.
start "" http://localhost:8501
.venv\Scripts\python.exe main.py streamlit

pause
endlocal
