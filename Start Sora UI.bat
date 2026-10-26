@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -B sora_ui.py 
) else (
  echo Run Setup Sora UI.bat in this folder first.
)
pause
