@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt
if errorlevel 1 goto :failed
echo Setup complete. Open Start Sora UI.bat.
pause
exit /b 0
:failed
echo Setup failed. Install Python with tkinter, then run this file again.
pause
exit /b 1
