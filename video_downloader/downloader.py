"""
Instagram / TikTok / YouTube など動画URLを貼り付けるとダウンロードするツール
"""
import sys
import os
from pathlib import Path
import yt_dlp

DOWNLOAD_DIR = Path(__file__).parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)
COOKIES_FILE = Path(__file__).parent / "cookies.txt"


def detect_platform(url: str) -> str:
    if "tiktok.com" in url:
        return "TikTok"
    if "instagram.com" in url:
        return "Instagram"
    if "youtube.com" in url or "youtu.be" in url:
        return "YouTube"
    return "Unknown"


def build_opts(use_cookies_file=False, use_browser_cookies=False):
    opts = {
        "outtmpl": str(DOWNLOAD_DIR / "%(uploader)s_%(id)s.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    }
    if use_cookies_file and COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    elif use_browser_cookies:
        opts["cookiesfrombrowser"] = ("chrome",)
    return opts


def download(url: str):
    platform = detect_platform(url)
    print(f"[{platform}] ダウンロード中...")

    # 試行順: 1) クッキーなし, 2) cookies.txt, 3) Chromeクッキー
    attempts = [
        ("クッキーなし", build_opts()),
    ]
    if COOKIES_FILE.exists():
        attempts.append(("cookies.txt使用", build_opts(use_cookies_file=True)))
    attempts.append(("Chromeクッキー使用", build_opts(use_browser_cookies=True)))

    last_error = None
    for label, opts in attempts:
        try:
            print(f"  試行: {label}")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "unknown")
                print(f"\n完了: {title}")
                print(f"保存先: {DOWNLOAD_DIR}")
                return
        except yt_dlp.utils.DownloadError as e:
            last_error = str(e)
            continue

    print(f"\nダウンロード失敗: {last_error}")
    print()
    print("【Instagramでログインが必要な場合の対処法】")
    print("1. Chromeに拡張機能「Get cookies.txt LOCALLY」をインストール")
    print("   https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc")
    print("2. Instagram にログインした状態で拡張機能を開き Export")
    print(f"3. ダウンロードした cookies.txt をこのフォルダに置く: {Path(__file__).parent}")
    print("4. 再度URLを貼り付ける")


def main():
    if len(sys.argv) > 1:
        for url in sys.argv[1:]:
            download(url)
    else:
        print("=" * 50)
        print("  Video Downloader (TikTok / Instagram / YouTube)")
        print("=" * 50)
        print(f"Save to: {DOWNLOAD_DIR}")
        if COOKIES_FILE.exists():
            print(f"cookies.txt: found")
        else:
            print(f"cookies.txt: not found (needed for private Instagram)")
        print("Type 'q' to quit\n")

        while True:
            try:
                url = input("URL > ").strip()
                if not url or url.lower() == "q":
                    print("Bye.")
                    break
                if not url.startswith("http"):
                    print("Please enter a valid URL")
                    continue
                download(url)
                print()
            except KeyboardInterrupt:
                print("\nBye.")
                break


if __name__ == "__main__":
    main()
