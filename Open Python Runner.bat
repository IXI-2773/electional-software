@echo off
setlocal
set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "PYTHONW=%PROJECT_DIR%.venv\Scripts\pythonw.exe"

cd /d "%PROJECT_DIR%" || exit /b 1
call "%PROJECT_DIR%Run Desktop App.bat" --setup-only >nul 2>nul
if errorlevel 1 (
  call "%PROJECT_DIR%Run Desktop App.bat" --setup-only
  exit /b %errorlevel%
)

if exist "%PYTHONW%" (
  start "Electional Python Runner" /D "%PROJECT_DIR%" "%PYTHONW%" -m idlelib -i -c "print('Electional Software Python Runner'); print('Project:', r'%PROJECT_DIR%'); print('Tip: from backend.electional.chart import build_snapshot')"
) else (
  start "Electional Python Runner" /D "%PROJECT_DIR%" "%PYTHON%" -m idlelib -i -c "print('Electional Software Python Runner'); print('Project:', r'%PROJECT_DIR%'); print('Tip: from backend.electional.chart import build_snapshot')"
)
exit /b 0
