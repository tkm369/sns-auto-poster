@echo off
echo === Audio Auto Cutter セットアップ (GPU版) ===
echo.

REM ffmpegの確認
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [警告] ffmpegが見つかりません
    echo  インストール方法: winget install ffmpeg
    echo.
)

REM CUDA対応PyTorchをインストール（CUDA 12.x 対応）
echo [1/2] PyTorch (CUDA 12.4) をインストール中...
pip install torch --index-url https://download.pytorch.org/whl/cu124

REM faster-whisper と他の依存関係
echo [2/2] faster-whisper と依存ライブラリをインストール中...
pip install -r requirements.txt

echo.
echo セットアップ完了！
echo.
echo 動作確認:
echo   python -c "import torch; print('CUDA:', torch.cuda.is_available())"
echo.
echo GUIの起動:
echo   python gui.py
echo.
echo CLIの起動:
echo   python main.py 動画ファイル.mp4
echo   python main.py 動画ファイル.mp4 --preview
echo.
pause
