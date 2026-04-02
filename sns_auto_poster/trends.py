import json
import os
import time
from datetime import datetime
import pytz

TRENDS_CACHE_FILE = os.path.join(os.path.dirname(__file__), "trends_cache.json")
GENRE_KEYWORDS = ["占い", "恋愛運"]


def fetch_and_save_trends():
    """Google Trendsからトレンドキーワードを取得してキャッシュに保存"""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='ja-JP', tz=540, timeout=(10, 30), retries=2, backoff_factor=0.5)

        # 日本のトレンド急上昇ワード
        trending_now = []
        try:
            df = pytrends.trending_searches(pn='japan')
            trending_now = df[0].head(10).tolist()
        except Exception as e:
            print(f"  急上昇ワード取得失敗: {e}")

        time.sleep(3)  # Rate limit対策

        # 占い・恋愛ジャンルの関連クエリ
        genre_trends = []
        try:
            pytrends.build_payload(GENRE_KEYWORDS, timeframe='now 7-d', geo='JP')
            related = pytrends.related_queries()
            for kw in GENRE_KEYWORDS:
                top = related.get(kw, {}).get('top')
                if top is not None and not top.empty:
                    genre_trends.extend(top['query'].head(5).tolist())
            genre_trends = list(dict.fromkeys(genre_trends))[:10]
        except Exception as e:
            print(f"  ジャンル関連クエリ取得失敗: {e}")

        jst = pytz.timezone("Asia/Tokyo")
        data = {
            "fetched_at": datetime.now(jst).isoformat(),
            "trending_now": trending_now,
            "genre_trends": genre_trends,
        }

        with open(TRENDS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ トレンド取得完了: 急上昇{len(trending_now)}件 / ジャンル関連{len(genre_trends)}件")
        return data

    except Exception as e:
        print(f"⚠️ トレンド取得失敗（スキップ）: {e}")
        return None


def load_trends():
    """キャッシュされたトレンドを読み込む（古すぎる場合はNone）"""
    if not os.path.exists(TRENDS_CACHE_FILE):
        return None
    try:
        with open(TRENDS_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # 48時間以上古いキャッシュは使わない
        jst = pytz.timezone("Asia/Tokyo")
        fetched = datetime.fromisoformat(data["fetched_at"])
        age_hours = (datetime.now(jst) - fetched).total_seconds() / 3600
        if age_hours > 48:
            return None
        return data
    except Exception:
        return None
