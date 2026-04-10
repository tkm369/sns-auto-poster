import requests
import os
from typing import Callable, Optional


def download_video(
    url: str,
    output_path: str,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> bool:
    """
    動画ファイルをダウンロードする。
    progress_callback(percent: int) が渡された場合、進捗を通知する。
    成功したらTrue、失敗したらFalseを返す。
    """
    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total:
                            pct = int(downloaded / total * 100)
                            progress_callback(pct)

        return True
    except Exception as e:
        # 失敗したら不完全なファイルを削除
        if os.path.exists(output_path):
            os.remove(output_path)
        raise
