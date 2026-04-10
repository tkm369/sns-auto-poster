"""
youtube_uploader.py — YouTube Data API v3 でMP4をアップロード

初回実行時: ブラウザが開いてOAuth認証が必要。
認証後は token.json にトークンが保存され、以降は自動更新される。

必要パッケージ:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional

from config import (
    YOUTUBE_CLIENT_SECRET_PATH,
    YOUTUBE_CATEGORY_ID,
    YOUTUBE_PRIVACY,
)

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_TOKEN_FILE = Path(__file__).parent / "token.json"
_API_SERVICE_NAME = "youtube"
_API_VERSION = "v3"


def _get_credentials():
    """OAuth2認証トークンを取得・更新"""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_secret = Path(YOUTUBE_CLIENT_SECRET_PATH)
            if not client_secret.exists():
                raise FileNotFoundError(
                    f"YouTube OAuthクライアントシークレットが見つかりません: {client_secret}\n"
                    "Google Cloud Consoleからダウンロードして配置してください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), _SCOPES)
            creds = flow.run_local_server(port=0)

        with open(_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def _get_youtube_service():
    from googleapiclient.discovery import build
    creds = _get_credentials()
    return build(_API_SERVICE_NAME, _API_VERSION, credentials=creds)


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: Optional[str] = None,
    privacy: Optional[str] = None,
    thumbnail_path: Optional[str] = None,
) -> str:
    """
    動画をYouTubeにアップロードする。

    Returns:
        アップロードされた動画のYouTube ID
    """
    from googleapiclient.http import MediaFileUpload

    youtube = _get_youtube_service()

    body = {
        "snippet": {
            "title":       title[:100],        # YouTube上限100文字
            "description": description[:5000],
            "tags":        tags[:500],          # タグ上限500文字
            "categoryId":  category_id or YOUTUBE_CATEGORY_ID,
        },
        "status": {
            "privacyStatus":          privacy or YOUTUBE_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10MB chunk
    )

    print(f"[YouTube] アップロード開始: {title}")
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"[YouTube] アップロード進捗: {pct}%")

    video_id = response["id"]
    print(f"[YouTube] 完了: https://www.youtube.com/watch?v={video_id}")

    # サムネイル設定（任意）
    if thumbnail_path and Path(thumbnail_path).exists():
        _set_thumbnail(youtube, video_id, thumbnail_path)

    return video_id


def _set_thumbnail(youtube, video_id: str, thumbnail_path: str) -> None:
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
    print(f"[YouTube] サムネイル設定完了")


def revoke_token() -> None:
    """保存されたトークンを削除（再認証が必要になる）"""
    if _TOKEN_FILE.exists():
        _TOKEN_FILE.unlink()
        print("[YouTube] token.json を削除しました")


if __name__ == "__main__":
    # 動作テスト
    import sys
    if len(sys.argv) < 2:
        print("Usage: python youtube_uploader.py <video.mp4> [title]")
        sys.exit(1)
    video_path = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "テスト動画"
    vid_id = upload_video(
        video_path=video_path,
        title=title,
        description="スピ系テスト投稿",
        tags=["スピリチュアル", "テスト"],
        privacy="private",
    )
    print(f"Video ID: {vid_id}")
