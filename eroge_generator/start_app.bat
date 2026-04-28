@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo =============================================
echo   エロゲ自動生成パイプライン WebUI
echo   http://localhost:7863 で起動します
echo =============================================
"C:\Users\inoue\AppData\Local\Programs\Python\Python311\python.exe" app.py
pause
