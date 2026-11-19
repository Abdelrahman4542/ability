@echo off
setlocal
cd /d "%~dp0"
title AbilityBridge AI
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo ERROR: Python environment not found.
    echo Run setup_windows.bat first.
    pause
    exit /b 1
)
"%VENV_PY%" "%~dp0main.py"
if errorlevel 1 (
    echo.
    echo The application closed with an error. Copy the traceback above.
    pause
)
