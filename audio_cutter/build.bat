@echo off
echo ===================================
echo Audio Auto Cutter - .exe ビルド
echo （外注渡し用・フル同梱版）
echo ===================================

pip install pyinstaller faster-whisper pydub static-ffmpeg google-generativeai

echo.
echo [1/3] .exe をビルド中...

pyinstaller ^
  --onedir ^
  --windowed ^
  --name "AudioAutoCutter" ^
  --hidden-import "faster_whisper" ^
  --hidden-import "ctranslate2" ^
  --hidden-import "tokenizers" ^
  --hidden-import "huggingface_hub" ^
  --hidden-import "pydub" ^
  --hidden-import "pydub.audio_segment" ^
  --hidden-import "static_ffmpeg" ^
  --collect-data "faster_whisper" ^
  --collect-data "static_ffmpeg" ^
  --collect-binaries "ctranslate2" ^
  --collect-binaries "static_ffmpeg" ^
  --hidden-import "google.generativeai" ^
  --collect-data "google.generativeai" ^
  gui.py

echo.
echo [2/3] Whisper モデルをダウンロード中...
echo      （medium: 約1.5GB、初回のみ時間がかかります）

python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', download_root='dist/AudioAutoCutter/models')"

echo.
echo [3/3] フォルダを圧縮中...

powershell -command "Compress-Archive -Path 'dist\AudioAutoCutter' -DestinationPath 'dist\AudioAutoCutter_配布用.zip' -Force"

echo.
echo ─────────────────────────────────────
echo ビルド完了！
echo.
echo 外注先への渡し方:
echo   dist\AudioAutoCutter_配布用.zip を渡すだけ
echo.
echo 外注先の操作:
echo   1. zip を解凍
echo   2. AudioAutoCutter.exe をダブルクリック
echo   3. 完了（モデルDL・ffmpegのセットアップ不要）
echo ─────────────────────────────────────
pause
