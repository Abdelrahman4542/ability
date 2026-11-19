@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)
if not exist "datasets\sign_language\ArASL_Database_54K_Final" (
  echo ArASL 54K dataset folder was not found.
  echo Expected: datasets\sign_language\ArASL_Database_54K_Final
  pause
  exit /b 1
)
echo Training the 32-class ArASL CNN. This may take a while.
.venv\Scripts\python.exe train_cnn.py
if errorlevel 1 (
  echo Training failed. The existing model checkpoint was not replaced.
  pause
  exit /b 1
)
echo Training completed. Restart AbilityBridge AI to load the new 32-class model.
pause
