@echo off
set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "PYTHONW=%PROJECT_DIR%.venv\Scripts\pythonw.exe"
set "SYSTEM_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "REQ_MARKER=%PROJECT_DIR%.venv\requirements.txt"

cd /d "%PROJECT_DIR%"
if not exist "%PYTHON%" (
  echo Creating Python virtual environment...
  if exist "%SYSTEM_PYTHON%" (
    "%SYSTEM_PYTHON%" -m venv .venv
  ) else if exist "%CODEX_PYTHON%" (
    "%CODEX_PYTHON%" -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
  if errorlevel 1 (
    echo Failed to create .venv. Install Python 3.12 or make sure the Codex Python runtime is available.
    pause
    exit /b 1
  )
)

fc /b "%PROJECT_DIR%requirements.txt" "%REQ_MARKER%" >nul 2>nul
if errorlevel 1 (
  echo Installing/updating dependencies...
  "%PYTHON%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
  )
  copy /y "%PROJECT_DIR%requirements.txt" "%REQ_MARKER%" >nul
)

"%PYTHON%" "%PROJECT_DIR%desktop_app.py"
if errorlevel 1 pause
