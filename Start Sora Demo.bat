@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Follow README.md to create the virtual environment.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" pose_test.py --demo
pause
