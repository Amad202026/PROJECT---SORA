@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment missing. Follow README.md first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" pose_test.py
pause
