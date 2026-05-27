@echo off
set "PROJECT_DIR=%~dp0"
set "PYTHONW=%PROJECT_DIR%.venv\Scripts\pythonw.exe"

cd /d "%PROJECT_DIR%"
if not exist "%PYTHONW%" (
  echo Python virtual environment not found.
  echo Run: "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
start "Electional Python Runner" "%PYTHONW%" -m idlelib -i -t "Electional Software Python Runner" "desktop_app.py" "backend\electional\desktop.py" "backend\electional\chart.py"
