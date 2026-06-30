@echo off
setlocal

call scripts\test-fast.bat
if errorlevel 1 exit /b 1

set "PYTHON=.\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Python virtual environment not found at "%PYTHON%".
    exit /b 1
)

echo [full] Running complete backend suite...
"%PYTHON%" -m unittest discover backend\tests
if errorlevel 1 exit /b 1

echo [full] Passed.
exit /b 0
