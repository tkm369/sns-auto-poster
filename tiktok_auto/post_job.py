"""
post_job.py - GitHub Actionsから呼ばれる1投稿スクリプト

【フロー】
  1. strategy.jsonを読み込む（PDCA学習結果）
  2. Geminiでオリジナルコンテンツを生成
  3. 動画を合成
  4. TikTokに投稿
  5. posts_log.jsonに記録
"""
import sys
import os
import time
import json
import hashlib
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from content_generator import generate_content, load_strategy
from card_generator import generate_card
from composer import compose_video
from uploader import upload_to_tiktok

# ------------------------------------------------------------------ #
#  ログ設定
# ------------------------------------------------------------------ #
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiktok_auto.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  posts_log 管理
# ------------------------------------------------------------------ #
POSTS_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts_log.json")


def _load_log() -> list:
    if os.path.exists(POSTS_LOG):
        with open(POSTS_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_log(log: list):
    with open(POSTS_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def _posted_hashes() -> set:
    return {p.get("text_hash") for p in _load_log() if p.get("text_hash")}

def _is_duplicate(text: str) -> bool:
    """同じテキストが過去に投稿済みか確認"""
    h = hashlib.md5(text.strip().encode("utf-8")).hexdigest()
    return h in _posted_hashes()


def _record_post(text: str, category: str, tone: str, fmt: str):
    log = _load_log()
    now = datetime.now()
    log.append({
        "id":           now.strftime("%Y%m%d_%H%M%S"),
        "posted_at":    now.isoformat(),
        "text":         text,
        "text_hash":    hashlib.md5(text.strip().encode("utf-8")).hexdigest(),
        "category":     category,
        "tone":         tone,
        "format":       fmt,
        "posting_hour": now.hour,
        "video_duration": config.VIDEO_DURATION,
        # メトリクスは analytics_collector.py が後から埋める
        "views":        None,
        "likes":        None,
        "comments":     None,
        "last_checked": None,
    })
    # 最新500件に絞る
    if len(log) > 500:
        log = log[-500:]
    _save_log(log)


# ------------------------------------------------------------------ #
#  メイン
# ------------------------------------------------------------------ #

def main():
    logger.info("=== 投稿ジョブ開始 ===")
    t_start = time.time()

    # 1. 戦略読み込み
    strategy = load_strategy()
    logger.info(f"戦略: tone={strategy['generation_params'].get('tone')} "
                f"format={strategy['generation_params'].get('format')} "
                f"insights={strategy.get('insights', '')[:40]}")

    # 2. コンテンツ生成（リトライ最大3回）
    hashes = _posted_hashes()
    content = None
    for attempt in range(3):
        try:
            candidate = generate_content(strategy, posted_hashes=hashes)
            text = candidate["text"]

            if not text or len(text) < 20:
                logger.warning(f"生成テキストが短すぎる ({attempt+1}/3): {repr(text)}")
                continue

            if _is_duplicate(text):
                logger.warning(f"重複テキストのため再生成 ({attempt+1}/3)")
                continue

            content = candidate
            break
        except Exception as e:
            logger.warning(f"コンテンツ生成エラー ({attempt+1}/3): {e}")
            time.sleep(2)

    if content is None:
        logger.error("コンテンツ生成に3回失敗。中断します。")
        sys.exit(1)

    text     = content["text"]
    category = content["category"]
    tone     = content["tone"]
    fmt      = content["format"]

    logger.info(f"生成完了 [{category} / {tone} / {fmt}]")
    logger.info(f"テキスト: {text}")

    # 3. カード画像生成
    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    card_path = os.path.join(config.SCREENSHOTS_DIR, f"card_{ts}.png")
    generate_card(text, card_path)
    logger.info(f"カード生成: {card_path}")

    # 4. 動画合成
    video_path = os.path.join(config.OUTPUT_DIR, f"tiktok_{ts}.mp4")
    caption    = config.TIKTOK_CAPTION_TEMPLATE.format(text=text)
    compose_video(card_path, video_path, caption_text=caption, duration=config.VIDEO_DURATION)
    logger.info(f"動画合成: {video_path}")

    # 5. TikTokアップロード
    logger.info("TikTokにアップロード中...")
    ok = upload_to_tiktok(video_path, caption)

    if ok:
        _record_post(text, category, tone, fmt)
        logger.info(f"=== 投稿成功 [{category}] {time.time()-t_start:.0f}秒 ===")
    else:
        logger.error(f"=== 投稿失敗 {time.time()-t_start:.0f}秒 ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
