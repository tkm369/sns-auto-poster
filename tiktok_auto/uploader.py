"""
uploader.py - TikTok への自動アップロード

ローカル実行: browser_profile/ にセッションを保存して使用
GitHub Actions: 環境変数 TIKTOK_SESSION_ID を使用
"""

import os
import time
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import config

logger = logging.getLogger(__name__)

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile")

# GitHub Actions など CI環境かどうか
_IN_CI = bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def _session_id() -> str:
    """環境変数 → config の順で sessionid を取得"""
    return os.environ.get("TIKTOK_SESSION_ID", "") or config.TIKTOK_SESSION_ID


def _is_logged_in() -> bool:
    if _IN_CI:
        return bool(_session_id() and _session_id() != "your_tiktok_session_id")
    return os.path.isdir(PROFILE_DIR) and any(True for _ in os.scandir(PROFILE_DIR))


def upload_to_tiktok(
    video_path: str,
    caption: str,
    headless: bool = True,
) -> bool:
    """
    TikTok に動画をアップロード。
    CI環境: sessionid Cookie を注入
    ローカル: 永続プロファイルを使用
    戻り値: 成功 True / 失敗 False
    """
    if not os.path.exists(video_path):
        logger.error(f"動画ファイルが見つかりません: {video_path}")
        return False

    if not _is_logged_in():
        logger.error("TikTokにログインしていません。setup_login.py を実行するか TIKTOK_SESSION_ID を設定してください")
        return False

    with sync_playwright() as p:
        if _IN_CI:
            # CI: sessionid Cookieを注入してブラウザを起動
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            context.add_cookies([{
                "name":   "sessionid",
                "value":  _session_id(),
                "domain": ".tiktok.com",
                "path":   "/",
            }])
        else:
            # ローカル: 永続プロファイル
            context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                viewport={"width": 1280, "height": 800},
            )

        page = context.new_page()

        try:
            # ---- TikTok Studio 投稿ページへ移動 (複数URLを試す) ----
            upload_urls = [
                "https://www.tiktok.com/tiktokstudio/upload",
                "https://www.tiktok.com/creator-center/upload",
            ]
            for upload_url in upload_urls:
                logger.info(f"TikTok Studio を開いています: {upload_url}")
                page.goto(upload_url, timeout=30000)
                time.sleep(4)
                if "login" not in page.url.lower():
                    logger.info(f"ページ到達: {page.url}")
                    break
            else:
                logger.error("セッションが切れています。TIKTOK_SESSION_ID を更新してください。")
                return False

            # ---- 動画ファイルをアップロード -------------------------
            logger.info(f"動画をアップロード中: {video_path}")
            # file inputは非表示のことがあるので force=True で対応
            upload_input = page.locator('input[type="file"]').first
            upload_input.wait_for(state="attached", timeout=30000)
            page.evaluate("el => el.style.display = 'block'",
                          upload_input.element_handle())
            upload_input.set_input_files(video_path)

            # アップロード処理完了を待つ (最大3分)
            logger.info("アップロード処理中... (最大3分)")
            _wait_for_upload(page, timeout=180)

            # ---- キャプション入力 -----------------------------------
            logger.info("キャプションを入力中...")
            _fill_caption(page, caption)

            # ---- 投稿ボタンをクリック --------------------------------
            logger.info("投稿ボタンをクリック...")
            post_btn = page.locator('button:has-text("Post"), button:has-text("投稿")').last
            post_btn.wait_for(timeout=10000)
            post_btn.click()

            time.sleep(5)
            logger.info("投稿完了!")
            return True

        except Exception as e:
            logger.error(f"アップロード中にエラー: {e}")
            debug_path = os.path.join(config.SCREENSHOTS_DIR, "upload_error.png")
            try:
                page.screenshot(path=debug_path)
                logger.info(f"エラー時のスクショ: {debug_path}")
            except Exception:
                pass
            return False

        finally:
            context.close()
            if _IN_CI:
                browser.close()


def _wait_for_upload(page, timeout: int = 180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        uploading = page.locator('[class*="progress"], [class*="uploading"], text="Uploading"')
        if uploading.count() == 0:
            return
        time.sleep(2)
    raise TimeoutError("動画アップロードがタイムアウトしました")


def _fill_caption(page, caption: str):
    try:
        caption_box = page.locator('[contenteditable="true"]').first
        caption_box.wait_for(timeout=10000)
        caption_box.click()
        time.sleep(0.5)
        page.evaluate(
            """(text) => {
                const el = document.querySelector('[contenteditable="true"]');
                if (el) {
                    el.innerText = text;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }""",
            caption,
        )
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"キャプション入力に失敗: {e}")


# --- 動作確認用 ---
if __name__ == "__main__":
    import sys, logging
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 3:
        print("使い方: python uploader.py <video.mp4> <キャプション>")
        sys.exit(1)
    ok = upload_to_tiktok(sys.argv[1], sys.argv[2], headless=False)
    print("成功" if ok else "失敗")
