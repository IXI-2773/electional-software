@echo off
set "PROJECT_DIR=%~dp0"
set "PYTHONW=C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"

cd /d "%PROJECT_DIR%"
start "Electional Python Runner" "%PYTHONW%" -m idlelib -i -t "Electional Software Python Runner" "desktop_app.py" "backend\electional\desktop.py" "backend\electional\chart.py"
