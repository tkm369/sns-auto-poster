"""
post_job.py - GitHub Actionsから呼ばれる1投稿スクリプト

【フロー】
  1. strategy.jsonを読み込む（PDCA学習結果）
  2. カード投稿 or 音声投稿を確率で選択
  3. コンテンツ生成 → 動画合成 → TikTokに投稿
  4. posts_log.jsonに記録
"""
import sys
import os
import time
import json
import hashlib
import logging
import random
import subprocess
import tempfile
from datetime import datetime
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from content_generator import generate_content, load_strategy
from card_generator import generate_card, CARD_STYLES
from composer import compose_video, compose_voice_video
from uploader import upload_to_tiktok

# ------------------------------------------------------------------ #
#  カテゴリ別ハッシュタグ（⑤ 改善）
# ------------------------------------------------------------------ #
_CATEGORY_HASHTAGS = {
    "片思い":       ["片思い", "好きな人", "恋愛あるある", "共感", "恋愛"],
    "失恋":         ["失恋", "失恋した", "恋愛相談", "共感", "恋愛"],
    "復縁":         ["復縁", "復縁したい", "元彼", "元カノ", "恋愛"],
    "恋愛あるある": ["恋愛あるある", "片思い", "共感", "好きな人", "恋愛"],
    "元カレ元カノ": ["元彼", "元カノ", "失恋", "復縁", "恋愛"],
    "好きな人":     ["好きな人", "片思い", "恋愛あるある", "共感", "恋愛"],
    "寂しい夜":     ["寂しい", "深夜", "失恋", "共感", "恋愛"],
    "恋愛名言":     ["恋愛名言", "名言", "恋愛あるある", "共感", "恋愛"],
}
_ALWAYS_TAGS = ["深夜"]  # 全カテゴリに追加


def _build_caption(text: str, category: str) -> str:
    """カテゴリに合わせたハッシュタグ付きキャプションを生成"""
    tags = list(_CATEGORY_HASHTAGS.get(category, ["恋愛", "共感"]))
    for t in _ALWAYS_TAGS:
        if t not in tags:
            tags.append(t)
    hashtag_str = " ".join(f"#{t}" for t in tags)
    return f"{text}\n\n{hashtag_str}"

def _build_voice_caption(title: str, category: str, voice_format: str) -> str:
    """音声投稿用のハッシュタグ付きキャプションを生成"""
    from voice_content_generator import get_voice_hashtags
    hashtag_str = get_voice_hashtags(voice_format, category)
    return f"{title}\n\n{hashtag_str}"


# ------------------------------------------------------------------ #
#  音声投稿パイプライン
# ------------------------------------------------------------------ #

def _run_voice_post(strategy: dict, t_start: float) -> bool:
    """
    音声コンテンツ投稿のパイプライン。
    戻り値: True=成功, False=失敗 (main が sys.exit するかどうかを決定)
    """
    from voice_content_generator import generate_voice_content

    # 参照音声の存在確認（早期チェック）
    ref_audio = getattr(config, "TTS_REF_AUDIO_PATH", "")
    ref_text  = getattr(config, "TTS_REF_TEXT", "")
    if not ref_audio or not os.path.exists(ref_audio):
        logger.error(f"参照音声ファイルが設定/存在しません: {ref_audio}")
        logger.error("config.py の TTS_REF_AUDIO_PATH に WAV ファイルのパスを設定してください")
        return False

    # スクリプト生成
    try:
        content = generate_voice_content(strategy)
    except Exception as e:
        logger.error(f"音声スクリプト生成失敗: {e}")
        return False

    voice_format = content["voice_format"]
    title        = content["title"]
    script       = content["script"]
    category     = content["category"]

    if len(script) < 50:
        logger.warning(f"音声スクリプトが短すぎる: {len(script)}文字")
        return False

    logger.info(f"音声コンテンツ [{voice_format}]: {title}")
    logger.info(f"スクリプト ({len(script)}文字): {script[:80]}...")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    voice_dir = getattr(config, "VOICE_OUTPUT_DIR",
                        os.path.join(config.BASE_DIR, "voice_output"))
    os.makedirs(voice_dir, exist_ok=True)

    # タイトルカード生成
    card_path = os.path.join(config.SCREENSHOTS_DIR, f"voice_card_{ts}.png")
    generate_card(title, card_path, style="voice_title")
    logger.info(f"タイトルカード生成: {card_path}")

    # TTS音声生成（サブプロセス）
    wav_path   = os.path.join(voice_dir, f"voice_{ts}.wav")
    tts_worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_worker.py")

    # args を JSON ファイル経由で渡す（長いテキストや特殊文字対策）
    args_dict = {
        "script":      script,
        "ref_audio":   ref_audio,
        "ref_text":    ref_text,
        "output_path": wav_path,
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(args_dict, tf, ensure_ascii=False)
        args_json_path = tf.name

    try:
        # Qwen3-TTS は専用 venv の Python で実行（qwen_tts パッケージが入っているため）
        tts_python = getattr(config, "TTS_PYTHON", sys.executable)
        if not os.path.exists(tts_python):
            tts_python = sys.executable
            logger.warning(f"TTS_PYTHON が見つからないため sys.executable を使用: {tts_python}")
        logger.info(f"TTS音声生成中（約1〜3分）... [{tts_python}]")
        result = subprocess.run(
            [tts_python, tts_worker, args_json_path],
            capture_output=True, text=True, timeout=360,
            env={**os.environ},
        )
    finally:
        try:
            os.unlink(args_json_path)
        except Exception:
            pass

    for line in result.stdout.splitlines():
        logger.info(f"[tts] {line}")
    if result.stderr:
        for line in result.stderr.splitlines()[:15]:
            logger.warning(f"[tts stderr] {line}")

    if result.returncode != 0 or not os.path.exists(wav_path):
        logger.error("TTS生成失敗")
        return False

    # 実際の音声長を stdout から取得
    voice_duration = 60.0  # デフォルト
    for line in result.stdout.splitlines():
        if line.startswith("DURATION:"):
            try:
                voice_duration = float(line[9:])
            except ValueError:
                pass

    # 動画合成
    video_path = os.path.join(config.OUTPUT_DIR, f"voice_tiktok_{ts}.mp4")
    try:
        compose_voice_video(card_path, wav_path, video_path)
        logger.info(f"音声動画合成完了: {video_path}")
    except Exception as e:
        logger.error(f"動画合成失敗: {e}")
        return False

    # TikTok アップロード
    caption = _build_voice_caption(title, category, voice_format)
    logger.info("TikTokにアップロード中...")
    ok = upload_to_tiktok(video_path, caption)

    if ok:
        _record_voice_post(title, script, category, voice_format, voice_duration)
        logger.info(
            f"=== 音声投稿成功 [{voice_format}/{category}] "
            f"{time.time() - t_start:.0f}秒 ==="
        )
    else:
        logger.error(f"=== 音声投稿失敗 {time.time() - t_start:.0f}秒 ===")

    return ok


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


def _record_post(text: str, category: str, tone: str, fmt: str, card_style: str = "xdark"):
    """カード投稿の記録"""
    log = _load_log()
    now = datetime.now()
    log.append({
        "id":             now.strftime("%Y%m%d_%H%M%S"),
        "posted_at":      now.isoformat(),
        "content_type":   "card",
        "text":           text,
        "text_hash":      hashlib.md5(text.strip().encode("utf-8")).hexdigest(),
        "category":       category,
        "tone":           tone,
        "format":         fmt,
        "card_style":     card_style,
        "posting_hour":   now.hour,
        "text_length":    len(text),
        "video_duration": config.VIDEO_DURATION,
        # メトリクスは analytics_collector.py が後から埋める
        "views":          None,
        "likes":          None,
        "comments":       None,
        "saves":          None,
        "shares":         None,
        "last_checked":   None,
    })
    if len(log) > 500:
        log = log[-500:]
    _save_log(log)


def _record_voice_post(title: str, script: str, category: str, voice_format: str,
                       video_duration: float):
    """音声投稿の記録"""
    log = _load_log()
    now = datetime.now()
    log.append({
        "id":             now.strftime("%Y%m%d_%H%M%S"),
        "posted_at":      now.isoformat(),
        "content_type":   "voice",
        "voice_format":   voice_format,
        "text":           title,           # ログ検索用（タイトル）
        "text_hash":      hashlib.md5(title.strip().encode("utf-8")).hexdigest(),
        "script":         script[:200],    # 先頭200文字だけ記録
        "category":       category,
        "posting_hour":   now.hour,
        "text_length":    len(script),
        "video_duration": video_duration,
        "views":          None,
        "likes":          None,
        "comments":       None,
        "saves":          None,
        "shares":         None,
        "last_checked":   None,
    })
    if len(log) > 500:
        log = log[-500:]
    _save_log(log)


# ------------------------------------------------------------------ #
#  メイン
# ------------------------------------------------------------------ #

def _run_card_post(strategy: dict, t_start: float) -> bool:
    """カード投稿のパイプライン"""
    hashes  = _posted_hashes()
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
        logger.error("コンテンツ生成に3回失敗")
        return False

    text       = content["text"]
    category   = content["category"]
    tone       = content["tone"]
    fmt        = content["format"]
    card_style = content.get("card_style", "xdark")

    logger.info(f"生成完了 [{category} / {tone} / {fmt} / {card_style}]")
    logger.info(f"テキスト: {text}")

    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    card_path = os.path.join(config.SCREENSHOTS_DIR, f"card_{ts}.png")
    generate_card(text, card_path, style=card_style)
    logger.info(f"カード生成: {card_path} [style={card_style}]")

    video_path = os.path.join(config.OUTPUT_DIR, f"tiktok_{ts}.mp4")
    caption    = _build_caption(text, category)
    compose_video(card_path, video_path, caption_text=caption, duration=config.VIDEO_DURATION)
    logger.info(f"動画合成: {video_path}")

    logger.info("TikTokにアップロード中...")
    ok = upload_to_tiktok(video_path, caption)

    if ok:
        _record_post(text, category, tone, fmt, card_style)
        logger.info(f"=== カード投稿成功 [{category}/{card_style}] {time.time()-t_start:.0f}秒 ===")
    else:
        logger.error(f"=== カード投稿失敗 {time.time()-t_start:.0f}秒 ===")

    return ok


def main():
    logger.info("=== 投稿ジョブ開始 ===")
    t_start = time.time()

    # 1. 戦略読み込み
    strategy = load_strategy()
    logger.info(f"戦略: tone={strategy['generation_params'].get('tone')} "
                f"insights={strategy.get('insights', '')[:40]}")

    # 2. 音声投稿 or カード投稿を確率で選択
    voice_ratio  = getattr(config, "TTS_VOICE_RATIO", 0.33)
    ref_audio    = getattr(config, "TTS_REF_AUDIO_PATH", "")
    # 参照音声ファイルがない場合は常にカード投稿
    do_voice = (
        os.path.exists(ref_audio)
        and random.random() < voice_ratio
    )

    logger.info(f"投稿タイプ: {'音声投稿' if do_voice else 'カード投稿'} "
                f"(voice_ratio={voice_ratio:.0%}, ref_audio={'あり' if os.path.exists(ref_audio) else 'なし'})")

    if do_voice:
        ok = _run_voice_post(strategy, t_start)
        if not ok:
            # 音声投稿失敗 → カード投稿にフォールバック
            logger.warning("音声投稿失敗 → カード投稿にフォールバック")
            ok = _run_card_post(strategy, t_start)
    else:
        ok = _run_card_post(strategy, t_start)

    if not ok:
        logger.error("=== 投稿失敗 ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
