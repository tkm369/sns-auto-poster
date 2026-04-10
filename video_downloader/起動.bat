@echo off
cd /d "%~dp0"

python --version > nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python.
    pause
    exit /b
)

python downloader.py
echo.
echo === Done. Press any key to close. ===
pause > nul
