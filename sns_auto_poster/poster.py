import time
import requests
import tweepy
from config import (
    X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET,
    THREADS_ACCESS_TOKEN, THREADS_USER_ID,
)


def post_to_x(text):
    """Xに投稿する"""
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
        print("  [X] APIキーが未設定のためスキップ")
        return None
    try:
        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET,
        )
        response = client.create_tweet(text=text)
        tweet_id = str(response.data["id"])
        print(f"  [X] 投稿成功 → https://x.com/i/web/status/{tweet_id}")
        return tweet_id
    except Exception as e:
        err_str = str(e)
        if "402" in err_str or "Payment Required" in err_str or "453" in err_str:
            print("  [X] 有料プランが必要なためスキップ")
        else:
            print(f"  [X] 投稿失敗: {e}")
        return None


THREADS_MAX_CHARS = 500

def post_to_threads(text, image_url=None):
    # Threads APIの上限を超えていたら切り詰め
    if len(text) > THREADS_MAX_CHARS:
        print(f"  ⚠️ テキスト{len(text)}文字 → {THREADS_MAX_CHARS}文字に切り詰め")
        text = text[:THREADS_MAX_CHARS - 1] + "…"
    """Threadsに投稿する（テキストのみ or 画像付き）"""
    if not all([THREADS_ACCESS_TOKEN, THREADS_USER_ID]):
        print("  [Threads] APIキーが未設定のためスキップ")
        return None
    try:
        # Step1: メディアコンテナ作成
        container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
        if image_url:
            params = {
                "media_type": "IMAGE",
                "image_url": image_url,
                "text": text,
                "access_token": THREADS_ACCESS_TOKEN,
            }
        else:
            params = {
                "media_type": "TEXT",
                "text": text,
                "access_token": THREADS_ACCESS_TOKEN,
            }

        container_res = requests.post(container_url, params=params)
        container_data = container_res.json()
        container_id = container_data.get("id")

        if not container_id:
            if image_url:
                print(f"  [Threads] 画像付き投稿失敗: {container_data}、テキストのみで再試行")
                return post_to_threads(text, image_url=None)
            print(f"  [Threads] コンテナ作成失敗: {container_data}")
            return None

        # Step2: 公開 (API推奨の待機)
        time.sleep(3)

        publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
        publish_res = requests.post(publish_url, params={
            "creation_id": container_id,
            "access_token": THREADS_ACCESS_TOKEN,
        })

        if publish_res.status_code == 200:
            post_id = str(publish_res.json().get("id", ""))
            mode = "画像付き" if image_url else "テキスト"
            print(f"  [Threads] 投稿成功 ({mode}, ID: {post_id})")
            return post_id if post_id else None
        else:
            print(f"  [Threads] 公開失敗: {publish_res.text}")
            return None

    except Exception as e:
        print(f"  [Threads] 投稿失敗: {e}")
        return None
