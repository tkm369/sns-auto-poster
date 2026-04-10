@echo off
cd /d "%~dp0"
echo ============================================
echo  Cookie Update (Firefox)
echo ============================================
echo.
python export_cookies.py
echo.
pause
