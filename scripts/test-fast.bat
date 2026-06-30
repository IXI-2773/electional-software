@echo off
setlocal

set "PYTHON=.\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Python virtual environment not found at "%PYTHON%".
    exit /b 1
)

echo [fast] Compiling core modules...
"%PYTHON%" -m py_compile ^
    backend\electional\session.py ^
    backend\electional\judgment.py ^
    backend\electional\engine\scoring.py ^
    backend\electional\engine\search.py ^
    backend\electional\engine\chart.py ^
    backend\electional\reports\text_report.py ^
    backend\tests\test_desktop_ui.py
if errorlevel 1 exit /b 1

echo [fast] Running focused backend tests...
"%PYTHON%" -m unittest ^
    backend.tests.test_calendar_export ^
    backend.tests.test_constellations ^
    backend.tests.test_electional_core ^
    backend.tests.test_python_chart_engine ^
    backend.tests.test_desktop_ui
if errorlevel 1 exit /b 1

echo [fast] Passed.
exit /b 0
