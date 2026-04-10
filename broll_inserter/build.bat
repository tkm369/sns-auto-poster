@echo off
echo ===================================
echo B-Roll Auto Inserter - .exe ビルド
echo ===================================

REM 必要なライブラリをインストール
pip install -r requirements.txt
pip install pyinstaller

REM .exeをビルド（1ファイルにまとめる）
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "BRollAutoInserter" ^
  --icon NONE ^
  main.py

echo.
echo ビルド完了！ dist\BRollAutoInserter.exe を確認してください。
pause
