import requests
from typing import Optional, Dict, List


class PexelsClient:
    SEARCH_URL = "https://api.pexels.com/videos/search"

    BUILTIN_KEYS = [
        "IHhgwnm3SCQ6vin7dQzT1WD6OssQYfG4W9iCgPAvrar4s9kSmuA6tEoz",
        "2NM5ny7VP1oNybd6k8gwf3Hj3e0G8ed5UKM7HYGu9encdKvV3aG3Spwo",
        "LWNdXFzHkeutuBU1MDcAPg4IAVRnqlUQpTSDwkxjBLKJ01Gnlg2Ey12B",
        "WNHUKIPhSIv6sxEEgCoww7PtN0R5ak4IydjZkYz81BBmaUcLtiZBcxJC",
        "YeKg8FPdpsnBcCG8AJev9UaK8vgCSIoPDk814w3uT9krGOGpucB62yxg",
        "pCXm0ocelWYTIj2xAfrDwPjVHgDOOZQGEFO0LwYkSi36v7NJqUDosVEC",
    ]

    def __init__(self, keys: Optional[List[str]] = None):
        self.keys = keys if keys else self.BUILTIN_KEYS
        self._index = 0  # 現在使用中のキーのインデックス

    @property
    def current_key(self) -> str:
        return self.keys[self._index]

    @property
    def current_key_label(self) -> str:
        return f"APIキー {self._index + 1}/{len(self.keys)}"

    def _next_key(self) -> bool:
        """次のキーに切り替える。全部使い切ったらFalseを返す"""
        if self._index + 1 < len(self.keys):
            self._index += 1
            return True
        return False

    def search(self, query: str, per_page: int = 5) -> Optional[Dict]:
        """クエリで動画を検索。レート制限時は自動でキーをローテーション"""
        while True:
            headers = {"Authorization": self.current_key}
            try:
                resp = requests.get(
                    self.SEARCH_URL,
                    headers=headers,
                    params={
                        "query": query,
                        "per_page": per_page,
                        "orientation": "landscape",
                        "size": "medium",
                    },
                    timeout=15,
                )

                if resp.status_code == 429:
                    # レート制限 → 次のキーへ
                    if self._next_key():
                        continue  # リトライ
                    else:
                        raise RuntimeError("全APIキーの月間上限に達しました")

                if resp.status_code == 401:
                    # 無効なキー → 次のキーへ
                    if self._next_key():
                        continue
                    else:
                        raise ValueError("有効なAPIキーがありません")

                resp.raise_for_status()
                data = resp.json()
                videos = data.get("videos", [])
                return videos[0] if videos else None

            except (RuntimeError, ValueError):
                raise
            except Exception as e:
                raise RuntimeError(f"検索エラー: {e}")

    def get_download_url(self, video: Dict, prefer_hd: bool = True) -> Optional[str]:
        files: List[Dict] = video.get("video_files", [])
        if not files:
            return None
        quality_order = ["hd", "sd"] if prefer_hd else ["sd", "hd"]
        for quality in quality_order:
            for f in files:
                if f.get("quality") == quality and "video/" in f.get("file_type", ""):
                    return f["link"]
        return files[0].get("link")
