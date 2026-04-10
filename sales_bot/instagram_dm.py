"""
instagram_dm.py - Instagram へ Playwright で DM を送信
"""
import time
import random
from playwright.sync_api import Page


def send_instagram_dm(page: Page, username: str, message: str) -> bool:
    """
    指定ユーザーにDMを送信する。
    成功: True / 失敗: False
    """
    try:
        page.goto(f"https://www.instagram.com/{username}/", timeout=20000)
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 4))

        # 「メッセージを送る」ボタン
        msg_btn = page.query_selector('div[role="button"]:has-text("メッセージを送る"), '
                                      'button:has-text("Message"), '
                                      'button:has-text("メッセージ")')
        if not msg_btn:
            print(f"  [SKIP] @{username} : DMボタンが見つかりません")
            return False

        msg_btn.click()
        time.sleep(random.uniform(2, 4))

        # メッセージ入力欄 (DM画面が開く)
        input_el = page.query_selector(
            'textarea[placeholder], '
            'div[contenteditable="true"][role="textbox"]'
        )
        if not input_el:
            print(f"  [SKIP] @{username} : 入力欄が見つかりません")
            return False

        input_el.click()
        input_el.fill(message)
        time.sleep(random.uniform(0.5, 1.5))

        # 送信 (Enter または送信ボタン)
        send_btn = page.query_selector('button:has-text("送信"), button[type="submit"]')
        if send_btn:
            send_btn.click()
        else:
            input_el.press("Enter")

        time.sleep(random.uniform(1, 2))
        print(f"  [OK]   @{username} へ Instagram DM 送信完了")
        return True

    except Exception as e:
        print(f"  [ERR]  @{username} : {e}")
        return False
