import json
import os
from datetime import datetime
import pytz

LOG_FILE = os.path.join(os.path.dirname(__file__), "posts_log.json")
MAX_ENTRIES = 90  # 約30日分

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_log(log):
    # 古いエントリを削除して最大件数を維持
    log = log[-MAX_ENTRIES:]
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def add_post(post_id, platform, content, time_slot, has_affiliate=False):
    log = load_log()
    jst = pytz.timezone("Asia/Tokyo")
    entry = {
        "id": post_id,
        "platform": platform,
        "timestamp": datetime.now(jst).isoformat(),
        "content": content,
        "time_slot": time_slot,
        "has_affiliate": has_affiliate,
        "metrics": None,
        "metrics_collected": False
    }
    log.append(entry)
    save_log(log)

def count_posts_today():
    """今日すでに投稿した回数（X投稿をラン数として使用）"""
    log = load_log()
    jst = pytz.timezone("Asia/Tokyo")
    today = datetime.now(jst).strftime("%Y-%m-%d")
    return sum(
        1 for p in log
        if p.get("platform") == "x" and p.get("timestamp", "").startswith(today)
    )


def get_time_slot_stats():
    """時間帯別の投稿数と平均エンゲージメント率を返す {slot: {"count": N, "avg_rate": float}}"""
    from collections import defaultdict
    log = load_log()
    slot_data = defaultdict(list)
    for p in log:
        if p.get("metrics_collected") and p.get("metrics") and p.get("platform") == "threads":
            slot = p.get("time_slot")
            rate = p["metrics"].get("engagement_rate", 0)
            if slot:
                slot_data[slot].append(rate)
    return {
        slot: {"count": len(rates), "avg_rate": sum(rates) / len(rates)}
        for slot, rates in slot_data.items() if rates
    }


def get_time_slot_performance():
    """時間帯別の平均エンゲージメント率を返す {slot: avg_rate}（後方互換）"""
    return {slot: s["avg_rate"] for slot, s in get_time_slot_stats().items()}


def get_top_posts(n=3, has_affiliate=False):
    """エンゲージメント率が高い上位N件を返す（Threads投稿のみ・同じモードの投稿から学習）"""
    log = load_log()
    scored = [
        p for p in log
        if p.get("metrics_collected")
        and p.get("metrics")
        and p.get("platform") == "threads"
        and p.get("has_affiliate", False) == has_affiliate  # アフィリあり/なしを分けて学習
    ]
    scored.sort(key=lambda x: x["metrics"].get("engagement_rate", 0), reverse=True)
    return scored[:n]
