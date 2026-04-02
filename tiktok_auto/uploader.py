"""
uploader.py - TikTok への自動アップロード

tiktok-uploader ライブラリを使用してボット検出を回避。
認証: TIKTOK_SESSION_ID 環境変数 or config.py
"""

import os
import logging

import config

logger = logging.getLogger(__name__)


def _session_id() -> str:
    return os.environ.get("TIKTOK_SESSION_ID", "") or config.TIKTOK_SESSION_ID


def _cookies_list():
    """sessionid を tiktok-uploader が受け付けるcookieリスト形式に変換"""
    sid = _session_id()
    if not sid or sid == "your_tiktok_session_id":
        return None
    return [
        {
            "name": "sessionid",
            "value": sid,
            "domain": ".tiktok.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
        }
    ]


def upload_to_tiktok(
    video_path: str,
    caption: str,
    headless: bool = True,
) -> bool:
    """
    TikTok に動画をアップロード。
    tiktok-uploader ライブラリ経由でボット検出を回避。
    戻り値: 成功 True / 失敗 False
    """
    if not os.path.exists(video_path):
        logger.error(f"動画ファイルが見つかりません: {video_path}")
        return False

    cookies = _cookies_list()
    if not cookies:
        logger.error("TIKTOK_SESSION_ID が設定されていません")
        return False

    try:
        from tiktok_uploader.upload import upload_video
        logger.info(f"tiktok-uploader でアップロード開始: {video_path}")
        logger.info(f"キャプション: {caption[:50]}...")

        results = upload_video(
            filename=video_path,
            description=caption,
            cookies=cookies,
            headless=headless,
            browser="chrome",
        )

        # results は list of UploadResult
        if results and results[0].success:
            logger.info("投稿完了!")
            return True
        else:
            err = results[0].error if results else "不明なエラー"
            logger.error(f"アップロード失敗: {err}")
            return False

    except Exception as e:
        logger.error(f"アップロード中にエラー: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# --- 動作確認用 ---
if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 3:
        print("使い方: python uploader.py <video.mp4> <キャプション>")
        sys.exit(1)
    ok = upload_to_tiktok(sys.argv[1], sys.argv[2], headless=False)
    print("成功" if ok else "失敗")
