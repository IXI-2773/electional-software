@echo off
set "PROJECT_DIR=%~dp0"
set "PYTHON=C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

cd /d "%PROJECT_DIR%"
"%PYTHON%" "%PROJECT_DIR%desktop_app.py"
if errorlevel 1 pause
