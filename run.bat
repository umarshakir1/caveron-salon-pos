@echo off
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
    echo Python 3.10 or newer is required. Install it from python.org and try again.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Creating a local Python environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Installing CAVERON dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Installation failed.
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo.
    echo CAVERON closed with an error. See logs\caveron.log
    pause
)
