"""
twitter_dm.py - Twitter/X へ Playwright で DM を送信
"""
import time
import random
from playwright.sync_api import Page


def send_twitter_dm(page: Page, username: str, message: str) -> bool:
    """
    指定ユーザーにDMを送信する。
    成功: True / 失敗: False
    """
    try:
        page.goto(f"https://twitter.com/{username}", timeout=20000)
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 4))

        # 「メッセージ」ボタンをクリック
        msg_btn = page.query_selector('[data-testid="sendDMFromProfile"]')
        if not msg_btn:
            # フォロバされていない場合など、ボタンがないことがある
            print(f"  [SKIP] @{username} : DMボタンが見つかりません")
            return False

        msg_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(1.5, 3))

        # テキスト入力欄
        input_el = page.query_selector('[data-testid="dmComposerTextInput"]')
        if not input_el:
            print(f"  [SKIP] @{username} : 入力欄が見つかりません")
            return False

        input_el.click()
        # 日本語も確実に入力できるよう clipboard 経由
        page.evaluate(
            "(text) => { const el = document.querySelector('[data-testid=\"dmComposerTextInput\"]'); el.focus(); }",
            None
        )
        input_el.fill(message)
        time.sleep(random.uniform(0.5, 1.5))

        # 送信ボタン
        send_btn = page.query_selector('[data-testid="dmComposerSendButton"]')
        if not send_btn:
            print(f"  [SKIP] @{username} : 送信ボタンが見つかりません")
            return False

        send_btn.click()
        time.sleep(random.uniform(1, 2))
        print(f"  [OK]   @{username} へ DM 送信完了")
        return True

    except Exception as e:
        print(f"  [ERR]  @{username} : {e}")
        return False
