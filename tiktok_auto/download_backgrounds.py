"""
download_backgrounds.py - Pexelsからエモい背景動画をダウンロード

実行方法:
    python download_backgrounds.py

環境変数 PEXELS_API_KEY が必要。
"""
import os
import sys
import json
import urllib.request

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
BACKGROUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backgrounds")

# エモい動画の検索キーワード
SEARCH_QUERIES = [
    "rain window night",
    "foggy forest aesthetic",
    "night city bokeh",
    "aesthetic sunset",
    "dark rainy street",
]

TARGET_COUNT = 10  # ダウンロードする動画数


def search_videos(query: str, per_page: int = 5) -> list[dict]:
    """Pexels APIで動画を検索"""
    url = f"https://api.pexels.com/videos/search?query={urllib.request.quote(query)}&per_page={per_page}&orientation=portrait"
    req = urllib.request.Request(url, headers={"Authorization": PEXELS_API_KEY, "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read())
            return data.get("videos", [])
    except Exception as e:
        print(f"  検索失敗 ({query}): {e}")
        return []


def get_best_video_url(video: dict) -> str | None:
    """HD以上の動画URLを取得（縦型優先）"""
    files = video.get("video_files", [])
    # 縦型（portrait）のHD動画を優先
    portrait = [f for f in files if f.get("width", 0) < f.get("height", 0)]
    hd = sorted(portrait or files, key=lambda f: f.get("height", 0), reverse=True)
    for f in hd:
        if f.get("height", 0) >= 720:
            return f.get("link")
    return hd[0].get("link") if hd else None


def download_video(url: str, save_path: str) -> bool:
    """動画をダウンロード"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as res:
            data = res.read()
        with open(save_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  ダウンロード失敗: {e}")
        return False


def main():
    if not PEXELS_API_KEY:
        print("エラー: PEXELS_API_KEY が設定されていません")
        sys.exit(1)

    os.makedirs(BACKGROUNDS_DIR, exist_ok=True)

    # すでにある動画を確認
    existing = [f for f in os.listdir(BACKGROUNDS_DIR) if f.endswith(".mp4")]
    print(f"既存の背景動画: {len(existing)}件")

    if len(existing) >= TARGET_COUNT:
        print(f"すでに{TARGET_COUNT}件以上あります。スキップします。")
        return

    downloaded = 0
    seen_ids = set()

    for query in SEARCH_QUERIES:
        if downloaded + len(existing) >= TARGET_COUNT:
            break

        print(f"\n検索中: {query}")
        videos = search_videos(query, per_page=5)

        for video in videos:
            if downloaded + len(existing) >= TARGET_COUNT:
                break

            vid_id = video.get("id")
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)

            video_url = get_best_video_url(video)
            if not video_url:
                continue

            save_path = os.path.join(BACKGROUNDS_DIR, f"bg_{vid_id}.mp4")
            if os.path.exists(save_path):
                print(f"  スキップ（既存）: {vid_id}")
                continue

            print(f"  ダウンロード中: {vid_id} ...", end="", flush=True)
            if download_video(video_url, save_path):
                print(f" 完了 ({os.path.getsize(save_path)//1024}KB)")
                downloaded += 1
            else:
                print(" 失敗")

    total = len([f for f in os.listdir(BACKGROUNDS_DIR) if f.endswith(".mp4")])
    print(f"\n完了。背景動画: 合計{total}件")


if __name__ == "__main__":
    main()
