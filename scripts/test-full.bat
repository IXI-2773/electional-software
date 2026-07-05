@echo off
setlocal

set "PYTHON=.\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Python virtual environment not found at "%PYTHON%".
    exit /b 1
)

if not "%ALLOW_FULL_SUITE%"=="1" (
    echo [full] Broad project-wide test suites are disabled by default.
    echo [full] Set ALLOW_FULL_SUITE=1 only after an explicit user request.
    exit /b 2
)

call scripts\test-fast.bat
if errorlevel 1 exit /b 1

echo [full] Running complete backend suite after explicit opt-in...
"%PYTHON%" -m unittest discover backend\tests
if errorlevel 1 exit /b 1

echo [full] Passed.
exit /b 0