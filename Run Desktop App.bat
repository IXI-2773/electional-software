@echo off
set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"

cd /d "%PROJECT_DIR%"
if not exist "%PYTHON%" (
  echo Python virtual environment not found.
  echo Run: "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
"%PYTHON%" "%PROJECT_DIR%desktop_app.py"
if errorlevel 1 pause
