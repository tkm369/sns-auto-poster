"""
read_chrome_cookies.py
ChromeのCookieデータベースからTikTokのCookieを読み取り、
GitHub Secretに保存する。

注意: Chromeを閉じてから実行してください（DBロック対策）
"""

import os
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile

CHROME_COOKIE_PATH = os.path.expandvars(
    r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies"
)
REPO = "tkm369/sns-auto-poster"


def read_tiktok_cookies():
    """ChromeのCookieDBからTikTok Cookieを読む（コピーして読む）"""
    if not os.path.exists(CHROME_COOKIE_PATH):
        print(f"Cookieファイルが見つかりません: {CHROME_COOKIE_PATH}")
        sys.exit(1)

    # ロック回避のため一時コピーして読む
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(CHROME_COOKIE_PATH, tmp)

    try:
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()
        cur.execute("""
            SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly
            FROM cookies
            WHERE host_key LIKE '%tiktok.com%'
        """)
        rows = cur.fetchall()
        conn.close()
    finally:
        os.unlink(tmp)

    cookies = []
    for name, value, host, path, expires, secure, httponly in rows:
        # Chrome暗号化Cookieはvalue=""でencrypted_valueに入っている場合がある
        # 平文で取れたものだけ使う
        if value:
            cookies.append({
                "name": name,
                "value": value,
                "domain": host,
                "path": path,
                "secure": bool(secure),
                "httpOnly": bool(httponly),
            })

    return cookies


def main():
    print("ChromeのCookieからTikTokセッションを取得中...")
    print("※ Chromeが開いている場合はDBがロックされる可能性があります")
    print()

    cookies = read_tiktok_cookies()

    if not cookies:
        print("TikTok Cookieが取得できませんでした。")
        print("ChromeでTikTokにログインしているか確認してください。")
        sys.exit(1)

    print(f"{len(cookies)}件のCookieを取得:")
    for c in cookies:
        print(f"  {c['name']}: {c['value'][:20]}...")

    session = next((c for c in cookies if c["name"] == "sessionid"), None)
    if not session:
        print("\n警告: sessionidが見つかりません。TikTokにログインし直してください。")
        sys.exit(1)

    print(f"\nsessionid: {session['value'][:16]}...")

    # GitHub Secretに保存
    cookies_json = json.dumps(cookies)
    print(f"\nGitHub Secret 'TIKTOK_COOKIES_JSON' を {REPO} に設定中...")
    result = subprocess.run(
        ["gh", "secret", "set", "TIKTOK_COOKIES_JSON", "--body", cookies_json, "--repo", REPO],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("完了! Cookieを保存しました。")
    else:
        print(f"エラー: {result.stderr}")
        sys.exit(1)

    # sessionidも個別に保存（後方互換）
    subprocess.run(
        ["gh", "secret", "set", "TIKTOK_SESSION_ID", "--body", session["value"], "--repo", REPO],
        capture_output=True, text=True,
    )
    print("TIKTOK_SESSION_IDも更新しました。")


if __name__ == "__main__":
    main()
