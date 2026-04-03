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
        from requests_oauthlib import OAuth1Session
        oauth = OAuth1Session(
            X_API_KEY, client_secret=X_API_SECRET,
            resource_owner_key=X_ACCESS_TOKEN,
            resource_owner_secret=X_ACCESS_TOKEN_SECRET,
        )
        # クレデンシャル確認
        me = oauth.get("https://api.twitter.com/2/users/me")
        print(f"  [X] /users/me HTTP {me.status_code}: {me.text[:200]}")
        if me.status_code != 200:
            return None
        # 投稿
        resp = oauth.post(
            "https://api.twitter.com/2/tweets",
            json={"text": text},
        )
        print(f"  [X] POST /tweets HTTP {resp.status_code}: {resp.text[:400]}")
        if resp.status_code == 201:
            tweet_id = str(resp.json()["data"]["id"])
            print(f"  [X] 投稿成功 → https://x.com/i/web/status/{tweet_id}")
            return tweet_id
        return None
    except Exception as e:
        print(f"  [X] 投稿失敗: {type(e).__name__}: {e}")
        return None


def post_to_threads(text):
    """Threadsに投稿する"""
    if not all([THREADS_ACCESS_TOKEN, THREADS_USER_ID]):
        print("  [Threads] APIキーが未設定のためスキップ")
        return None
    try:
        # Step1: メディアコンテナ作成
        container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
        container_res = requests.post(container_url, params={
            "media_type": "TEXT",
            "text": text,
            "access_token": THREADS_ACCESS_TOKEN,
        })
        container_data = container_res.json()
        container_id = container_data.get("id")

        if not container_id:
            print(f"  [Threads] コンテナ作成失敗: {container_data}")
            return False

        # Step2: 公開 (API推奨の待機)
        time.sleep(3)

        publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
        publish_res = requests.post(publish_url, params={
            "creation_id": container_id,
            "access_token": THREADS_ACCESS_TOKEN,
        })

        if publish_res.status_code == 200:
            post_id = str(publish_res.json().get("id", ""))
            print(f"  [Threads] 投稿成功 (ID: {post_id})")
            return post_id if post_id else None
        else:
            print(f"  [Threads] 公開失敗: {publish_res.text}")
            return None

    except Exception as e:
        print(f"  [Threads] 投稿失敗: {e}")
        return None
