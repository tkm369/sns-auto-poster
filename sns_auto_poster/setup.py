"""
APIキーをまとめて設定するセットアップスクリプト
実行: python setup.py
設定値は .env ファイルに保存されます（GitHubにはpushしないこと）
"""

import os
import subprocess
import sys


ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

KEYS = [
    ("GEMINI_API_KEY",         "Gemini APIキー (aistudio.google.com で取得)"),
    ("X_API_KEY",              "X API Key (developer.twitter.com で取得)"),
    ("X_API_SECRET",           "X API Secret"),
    ("X_ACCESS_TOKEN",         "X Access Token"),
    ("X_ACCESS_TOKEN_SECRET",  "X Access Token Secret"),
    ("THREADS_ACCESS_TOKEN",   "Threads Access Token (developers.facebook.com で取得)"),
    ("THREADS_USER_ID",        "Threads User ID"),
    ("AFFILIATE_LINK",         "アフィリエイトURL"),
]


def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def save_env(env):
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("# SNS自動投稿システム APIキー設定\n")
        f.write("# このファイルはGitHubにpushしないこと！\n\n")
        for k, v in env.items():
            f.write(f"{k}={v}\n")


def push_secrets_to_github(env):
    """GitHub Secrets に一括登録（gh CLI が必要）"""
    try:
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("\n[!] gh CLI が見つかりません。手動でGitHub Secretsに登録してください。")
            return
    except FileNotFoundError:
        print("\n[!] gh CLI が見つかりません。手動でGitHub Secretsに登録してください。")
        return

    print("\nGitHub Secrets に登録中...")
    for k, v in env.items():
        if v:
            cmd = ["gh", "secret", "set", k, "--body", v]
            r = subprocess.run(cmd, capture_output=True, text=True,
                               cwd=os.path.dirname(os.path.dirname(__file__)))
            if r.returncode == 0:
                print(f"  ✅ {k}")
            else:
                print(f"  ❌ {k}: {r.stderr.strip()}")


def main():
    print("=" * 50)
    print("  SNS自動投稿システム セットアップ")
    print("=" * 50)
    print("Enterで現在の値をそのまま使います\n")

    env = load_env()

    for key, description in KEYS:
        current = env.get(key, "")
        display = f"[現在: {current[:10]}...]" if len(current) > 10 else f"[現在: {current}]" if current else "[未設定]"
        value = input(f"{description}\n{display} > ").strip()
        if value:
            env[key] = value
        elif current:
            env[key] = current  # 既存値を維持

    save_env(env)
    print(f"\n✅ .env に保存しました: {ENV_FILE}")

    # GitHub Secrets への自動登録を試みる
    push = input("\nGitHub Secrets にも自動登録しますか？ (y/N) > ").strip().lower()
    if push == "y":
        push_secrets_to_github(env)

    print("\n設定完了！テスト投稿を実行しますか？")
    test = input("(y/N) > ").strip().lower()
    if test == "y":
        # .env を読み込んで main.py を実行
        for k, v in env.items():
            os.environ[k] = v
        sys.path.insert(0, os.path.dirname(__file__))
        from main import main as run_post
        run_post()


if __name__ == "__main__":
    main()
