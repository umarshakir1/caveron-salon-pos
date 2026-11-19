@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" -c "from PySide6.QtWidgets import QApplication; import sys; app=QApplication(sys.argv); from ui.theme import load_fonts; load_fonts(); from ui.branding import ensure_brand_assets; ensure_brand_assets()"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm caveron.spec
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)
echo.
echo Built dist\CAVERON.exe
echo Put that file in its own folder. The database, logo, and backups are created beside it.
pause
