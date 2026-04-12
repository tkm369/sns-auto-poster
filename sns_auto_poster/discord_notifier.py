"""
Discord通知モジュール
- 投稿成功・失敗・quota超過をDiscordに通知
- noteの記事確認通知（チェックOKなら承認）
"""
import os
import json
import requests
from datetime import datetime

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


def _send(payload: dict) -> bool:
    """WebhookにJSONを送信"""
    if not WEBHOOK_URL:
        print("  [Discord] DISCORD_WEBHOOK_URL未設定、スキップ")
        return False
    try:
        res = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if res.status_code in (200, 204):
            return True
        print(f"  [Discord] 送信失敗: {res.status_code} {res.text[:100]}")
        return False
    except Exception as e:
        print(f"  [Discord] 送信失敗: {e}")
        return False


def notify_post_success(platform: str, post_type: str, text: str, post_id: str = ""):
    """投稿成功通知"""
    preview = text[:80] + "…" if len(text) > 80 else text
    payload = {
        "embeds": [{
            "title": "✅ 投稿成功",
            "color": 0x00C851,
            "fields": [
                {"name": "プラットフォーム", "value": platform, "inline": True},
                {"name": "投稿タイプ", "value": post_type, "inline": True},
                {"name": "内容プレビュー", "value": preview},
            ],
            "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M JST")},
        }]
    }
    _send(payload)


def notify_post_skip(reason: str):
    """投稿スキップ通知"""
    payload = {
        "embeds": [{
            "title": "⏭️ 投稿スキップ",
            "color": 0xFFBB33,
            "description": reason,
            "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M JST")},
        }]
    }
    _send(payload)


def notify_quota_exceeded():
    """Gemini quota超過通知"""
    payload = {
        "embeds": [{
            "title": "⚠️ Gemini quota超過",
            "color": 0xFF4444,
            "description": "本日のGemini APIクォータを超過しました。\nJST 09:00頃に自動リセットされます。",
            "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M JST")},
        }]
    }
    _send(payload)


def notify_error(message: str):
    """エラー通知"""
    payload = {
        "embeds": [{
            "title": "❌ エラー発生",
            "color": 0xFF4444,
            "description": message[:1000],
            "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M JST")},
        }]
    }
    _send(payload)


def notify_note_review(title: str, body_preview: str, run_id: str = ""):
    """note記事の確認依頼通知"""
    approve_url = (
        f"https://github.com/tkm369/sns-auto-poster/actions/workflows/note_publish.yml"
        if not run_id else
        f"https://github.com/tkm369/sns-auto-poster/actions/runs/{run_id}"
    )
    payload = {
        "embeds": [{
            "title": "📝 note記事の確認をお願いします",
            "color": 0x4A90E2,
            "fields": [
                {"name": "タイトル", "value": title},
                {"name": "本文プレビュー", "value": body_preview[:300] + "…" if len(body_preview) > 300 else body_preview},
                {"name": "承認して投稿する", "value": f"[GitHubで承認 →]({approve_url})"},
            ],
            "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M JST")},
        }]
    }
    _send(payload)
