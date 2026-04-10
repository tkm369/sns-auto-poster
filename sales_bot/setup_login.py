"""
setup_login.py - Twitter/Instagram に一度だけログインしてセッションを保存

実行:
    python setup_login.py twitter
    python setup_login.py instagram
"""
import sys
import os
from playwright.sync_api import sync_playwright
from config import (
    TWITTER_PROFILE_DIR, INSTAGRAM_PROFILE_DIR,
    CROWDWORKS_PROFILE_DIR, LANCERS_PROFILE_DIR,
)

TARGETS = {
    "twitter": {
        "url":     "https://twitter.com/login",
        "check":   "https://twitter.com/home",
        "profile": TWITTER_PROFILE_DIR,
        "name":    "Twitter/X",
    },
    "instagram": {
        "url":     "https://www.instagram.com/accounts/login/",
        "check":   "https://www.instagram.com/",
        "profile": INSTAGRAM_PROFILE_DIR,
        "name":    "Instagram",
    },
    "crowdworks": {
        "url":     "https://crowdworks.jp/login",
        "check":   "https://crowdworks.jp/",
        "profile": CROWDWORKS_PROFILE_DIR,
        "name":    "クラウドワークス",
    },
    "lancers": {
        "url":     "https://www.lancers.jp/login",
        "check":   "https://www.lancers.jp/",
        "profile": LANCERS_PROFILE_DIR,
        "name":    "ランサーズ",
    },
}


def setup(target_name: str):
    if target_name not in TARGETS:
        print(f"不明なターゲット: {target_name}")
        print("使い方: python setup_login.py twitter")
        print("        python setup_login.py instagram")
        print("        python setup_login.py crowdworks")
        print("        python setup_login.py lancers")
        sys.exit(1)

    cfg = TARGETS[target_name]
    os.makedirs(cfg["profile"], exist_ok=True)

    print(f"{'='*50}")
    print(f"{cfg['name']} ログインセットアップ")
    print(f"{'='*50}")
    print(f"プロファイル保存先: {cfg['profile']}")
    print()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=cfg["profile"],
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = context.new_page() if not context.pages else context.pages[0]
        page.goto(cfg["url"], timeout=30000)

        print(f"ブラウザが開きました。{cfg['name']} にログインしてください。")
        print("ログイン完了後、ここで Enter を押してください...")
        input()

        page.goto(cfg["check"], timeout=15000)
        page.wait_for_load_state("networkidle")
        print(f"✓ ログイン完了！セッションを保存しました。")
        print(f"次回から python main.py {target_name} で自動営業が動きます。")
        context.close()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "twitter"
    setup(target)
