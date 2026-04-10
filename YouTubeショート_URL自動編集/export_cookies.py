#!/usr/bin/env python3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUTPUT = Path(__file__).parent / "cookies.txt"

try:
    import yt_dlp
except ImportError:
    print("yt-dlp not found")
    sys.exit(1)


class _Logger:
    def debug(self, msg):   pass
    def warning(self, msg): print(f"  WARN: {msg}")
    def error(self, msg):   print(f"  ERROR: {msg}")


def export_firefox():
    print("Firefox から cookie を取得中...")
    try:
        ydl_opts = {
            "quiet": True,
            "cookiesfrombrowser": ("firefox",),
            "logger": _Logger(),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            cookiejar = ydl.cookiejar

        targets = [
            c for c in cookiejar
            if "youtube.com" in c.domain or "google.com" in c.domain
        ]
        if not targets:
            return 0

        with open(OUTPUT, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for c in targets:
                domain = c.domain
                sub    = "TRUE" if domain.startswith(".") else "FALSE"
                secure = "TRUE" if c.secure else "FALSE"
                exp    = int(c.expires) if c.expires else 0
                if c.name and c.value:
                    f.write(f"{domain}\t{sub}\t{c.path}\t{secure}\t{exp}\t{c.name}\t{c.value}\n")
        return len(targets)
    except Exception as e:
        print(f"  Failed: {e}")
        return 0


def main():
    count = export_firefox()

    if count == 0:
        print("cookie を取得できませんでした")
        print("Firefox で youtube.com にログインしてから再実行してください")
        sys.exit(1)

    # LOGIN_INFO 確認
    text = OUTPUT.read_text(encoding="utf-8", errors="replace")
    has_login = "LOGIN_INFO" in text
    print(f"完了: {count} 件保存")
    print(f"YouTube ログイン状態: {'OK' if has_login else 'NG (YouTubeにログインしてください)'}")

    if not has_login:
        sys.exit(1)


if __name__ == "__main__":
    main()
