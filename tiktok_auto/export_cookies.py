"""
export_cookies.py - ローカルのbrowser_profileからTikTokのCookieをエクスポートし
                    GitHub Secretに TIKTOK_COOKIES_JSON として保存する
"""

import json
import subprocess
import sys
import os
from playwright.sync_api import sync_playwright

PROFILE_DIR = os.environ.get("TIKTOK_PROFILE_DIR", r"C:\tiktok_profile")
REPO = "tkm369/sns-auto-poster"


def export_and_save():
    print("browser_profileからTikTok Cookieを取得中...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            args=["--no-sandbox"],
        )
        # tiktok.comのCookieだけ抽出
        all_cookies = context.cookies(["https://www.tiktok.com"])
        context.close()

    if not all_cookies:
        print("Cookieが取得できませんでした。setup_login.pyでログインしてください。")
        sys.exit(1)

    print(f"{len(all_cookies)}件のCookieを取得しました。")
    # sessionidが含まれているか確認
    names = [c["name"] for c in all_cookies]
    if "sessionid" not in names:
        print("警告: sessionidが見つかりません。再ログインが必要かもしれません。")
    else:
        print(f"sessionid: {next(c['value'][:8] for c in all_cookies if c['name']=='sessionid')}...")

    cookies_json = json.dumps(all_cookies)

    # GitHub Secretに保存
    print(f"\nGitHub Secret 'TIKTOK_COOKIES_JSON' を {REPO} に設定中...")
    result = subprocess.run(
        ["gh", "secret", "set", "TIKTOK_COOKIES_JSON", "--body", cookies_json, "--repo", REPO],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("完了! GitHub SecretにCookieを保存しました。")
    else:
        print(f"エラー: {result.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    export_and_save()
