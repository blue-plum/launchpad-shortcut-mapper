@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or newer from https://python.org
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Setting up Launchpad Shortcut Mapper for the first time...
  py -3 -m venv .venv
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
)

".venv\Scripts\pythonw.exe" app.py
exit /b 0

:failed
echo.
echo Setup failed. Check your internet connection and try again.
pause
exit /b 1

