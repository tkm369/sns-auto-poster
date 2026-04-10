@echo off
chcp 65001 > nul
cd /d "%~dp0"
python shorts_tool.py
pause
