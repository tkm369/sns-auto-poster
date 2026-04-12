"""
uploader.py - TikTok への自動アップロード（subprocess方式）

実際のChromeをCDP経由で操作することでbot検出を回避。
uploader_worker.py を子プロセスとして実行し、タイムアウト時はプロセスごと強制終了する。
"""

import os
import sys
import json
import subprocess
import logging

import config

logger = logging.getLogger(__name__)

UPLOAD_TIMEOUT = 300  # 5分でタイムアウト
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploader_worker.py")
PYTHON = sys.executable


GET_SESSION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get_session.py")


def _session_id() -> str:
    sid = os.environ.get("TIKTOK_SESSION_ID", "") or config.TIKTOK_SESSION_ID
    if sid and sid != "your_tiktok_session_id":
        return sid
    # 環境変数未設定の場合、get_session.py で直接取得
    try:
        result = subprocess.run(
            [PYTHON, GET_SESSION],
            capture_output=True, text=True, timeout=30
        )
        val = result.stdout.strip()
        if val and val not in ("NOT_FOUND", ""):
            logger.info("get_session.py からセッションIDを取得しました")
            os.environ["TIKTOK_SESSION_ID"] = val
            return val
    except Exception as e:
        logger.warning(f"get_session.py 失敗: {e}")
    return ""


def upload_to_tiktok(video_path: str, caption: str, headless: bool = False) -> bool:
    if not os.path.exists(video_path):
        logger.error(f"動画ファイルが見つかりません: {video_path}")
        return False

    sid = _session_id()
    if not sid or sid == "your_tiktok_session_id":
        logger.error("TIKTOK_SESSION_ID が設定されていません")
        return False

    env = os.environ.copy()

    # キャプションをUTF-8の一時ファイル経由で渡す（コマンドライン引数のcp932変換を回避）
    import tempfile
    caption_file = tempfile.mktemp(suffix=".txt")
    with open(caption_file, "w", encoding="utf-8") as f:
        f.write(caption)
    try:
        result = subprocess.run(
            [PYTHON, WORKER, video_path, "--caption-file", caption_file],
            timeout=UPLOAD_TIMEOUT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        output = result.stdout.strip()
        for line in output.splitlines():
            logger.info(f"[worker] {line}")
        if result.returncode == 2 or "SESSION_EXPIRED" in output:
            logger.error("=== TikTokセッションID期限切れ ===\nChrome で TikTok にログインし直してください。")
            return False
        if result.returncode == 0 and "OK:" in output:
            return True
        else:
            err = result.stderr.strip()
            if err:
                logger.error(f"[worker stderr] {err[:500]}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"アップロードが{UPLOAD_TIMEOUT}秒でタイムアウトしました")
        return False
    except Exception as e:
        logger.error(f"uploader起動エラー: {e}")
        return False
    finally:
        try:
            os.unlink(caption_file)
        except Exception:
            pass


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    if len(sys.argv) < 3:
        print("使い方: python uploader.py <video.mp4> <キャプション>")
        sys.exit(1)
    ok = upload_to_tiktok(sys.argv[1], sys.argv[2])
    print("成功" if ok else "失敗")
