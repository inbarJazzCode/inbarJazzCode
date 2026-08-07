@echo off
REM Transparent wrapper around the unified Python launcher.
REM Usage:
REM   run_windows.bat            (defaults to the Streamlit UI on localhost)
REM   run_windows.bat smoke      (run the offline smoke test)
REM   run_windows.bat integrity  (database integrity check)
REM   run_windows.bat desktop    (Tkinter desktop UI)

setlocal
if "%~1"=="" (
    python main.py streamlit
) else (
    python main.py %*
)
endlocal
