@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AbilityBridge AI - Setup

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "LOG_FILE=%PROJECT_DIR%setup_log.txt"

>"%LOG_FILE%" echo AbilityBridge AI setup log
>>"%LOG_FILE%" echo Project: %PROJECT_DIR%

echo ==========================================
echo        AbilityBridge AI - Setup
echo ==========================================
echo Project folder: "%PROJECT_DIR%"
echo Log file: "%LOG_FILE%"
echo.

set "BASE_PYTHON="

REM First choice: Python Launcher (py.exe)
where py >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "BASE_PYTHON=%%I"
)

REM Second choice: python.exe on PATH
if not defined BASE_PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "BASE_PYTHON=%%I"
    )
)

REM Third choice: path used on the developer's original machine
if not defined BASE_PYTHON if exist "C:\Users\L O Q\python.exe" set "BASE_PYTHON=C:\Users\L O Q\python.exe"

if not defined BASE_PYTHON (
    echo ERROR: Could not find Python automatically.
    echo Install Python 3.12 x64, then run this file again.
    echo Or add python.exe to PATH.
    >>"%LOG_FILE%" echo ERROR: Python executable not found.
    goto :failed
)

echo Found Python: "%BASE_PYTHON%"
"%BASE_PYTHON%" -c "import sys; print('Python version:', sys.version); assert sys.version_info[0] == 3 and sys.version_info[1] == 12"
if errorlevel 1 (
    echo ERROR: This project requires Python 3.12.x (64-bit).
    >>"%LOG_FILE%" echo ERROR: Wrong Python version: %BASE_PYTHON%
    goto :failed
)

if not exist "%VENV_PY%" (
    echo.
    echo [1/4] Creating virtual environment...
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
    "%BASE_PYTHON%" -m venv "%VENV_DIR%" >>"%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment. See setup_log.txt
        goto :failed
    )
) else (
    echo Existing virtual environment found.
)

if not exist "%VENV_PY%" (
    echo ERROR: .venv was not created correctly. See setup_log.txt
    goto :failed
)

echo.
echo [2/4] Preparing pip...
"%VENV_PY%" -m ensurepip --upgrade >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: ensurepip failed. See setup_log.txt
    goto :failed
)

echo.
echo [3/4] Updating pip...
"%VENV_PY%" -m pip install --upgrade pip >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: pip update failed. Check internet and setup_log.txt
    goto :failed
)

echo.
echo [4/4] Installing project dependencies...
"%VENV_PY%" -m pip install -r "%PROJECT_DIR%requirements.txt" >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Dependency installation failed. See setup_log.txt
    goto :failed
)

echo.
echo Running project diagnostics...
"%VENV_PY%" "%PROJECT_DIR%scripts\check_project.py" >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Project diagnostics failed. See setup_log.txt
    goto :failed
)

echo.
echo SETUP COMPLETED SUCCESSFULLY.
echo Now run run_app.bat.
>>"%LOG_FILE%" echo SETUP COMPLETED SUCCESSFULLY.
echo.
pause
exit /b 0

:failed
echo.
echo SETUP FAILED. The detailed error is saved in setup_log.txt
 echo.
pause
exit /b 1
