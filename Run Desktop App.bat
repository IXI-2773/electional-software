@echo off
setlocal
set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "PYTHONW=%PROJECT_DIR%.venv\Scripts\pythonw.exe"
set "SYSTEM_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "REQ_MARKER=%PROJECT_DIR%.venv\.requirements.stamp"
set "APP_ENTRY=%PROJECT_DIR%desktop_app.py"

cd /d "%PROJECT_DIR%" || exit /b 1
call :ensure_venv || goto :error
call :ensure_requirements || goto :error

if /i "%~1"=="--setup-only" (
  exit /b 0
)

if /i "%~1"=="--console" (
  "%PYTHON%" "%APP_ENTRY%"
  exit /b %errorlevel%
)

if exist "%PYTHONW%" (
  start "Electional Software" /D "%PROJECT_DIR%" "%PYTHONW%" "%APP_ENTRY%"
) else (
  start "Electional Software" /D "%PROJECT_DIR%" "%PYTHON%" "%APP_ENTRY%"
)
exit /b 0

:ensure_venv
if exist "%PYTHON%" exit /b 0
echo Creating Python virtual environment...
if exist "%SYSTEM_PYTHON%" (
  "%SYSTEM_PYTHON%" -m venv .venv
) else if exist "%CODEX_PYTHON%" (
  "%CODEX_PYTHON%" -m venv .venv
) else (
  py -3 -m venv .venv
)
exit /b %errorlevel%

:ensure_requirements
if not exist "%PYTHON%" exit /b 1
fc /b "%PROJECT_DIR%requirements.txt" "%REQ_MARKER%" >nul 2>nul
if not errorlevel 1 exit /b 0
echo Installing/updating dependencies...
"%PYTHON%" -m pip install -r requirements.txt || exit /b 1
copy /y "%PROJECT_DIR%requirements.txt" "%REQ_MARKER%" >nul
exit /b 0

:error
echo.
echo Electional Software could not start.
echo Project: "%PROJECT_DIR%"
echo Try running: "Run Desktop App.bat" --console
echo To only rebuild the environment, run: "Run Desktop App.bat" --setup-only
echo Or rebuild dependencies with:
echo   "%SYSTEM_PYTHON%" -m venv .venv
echo   ".venv\Scripts\python.exe" -m pip install -r requirements.txt
pause
exit /b 1
