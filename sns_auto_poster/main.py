import sys
import json
import os
import random
from datetime import datetime
import pytz

from generator import get_best_post, get_time_theme
from poster import post_to_x, post_to_threads
from logger import add_post, count_posts_today, get_time_slot_stats, get_image_vs_text_stats
from config import AFFILIATE_LINK

MAX_POSTS_PER_DAY = 6
MIN_DATA_POINTS = 5
SCORE_THRESHOLD = 50   # これ未満のスコアは投稿スキップ
AB_MIN_SAMPLES = 5     # 画像/テキスト各タイプのA/B判定に必要な最低サンプル数

PENDING_POST_FILE = os.path.join(os.path.dirname(__file__), "pending_post.json")
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "generated_images")


def should_post_now(time_slot):
    """今この時間帯に投稿すべきか判断する（PDCAベース）"""
    posts_today = count_posts_today()
    if posts_today >= MAX_POSTS_PER_DAY:
        return False, f"本日 {posts_today}/{MAX_POSTS_PER_DAY} 回投稿済み（上限到達）"

    stats = get_time_slot_stats()
    slot_stat = stats.get(time_slot)

    # データ不足 → 探索フェーズ（必ず投稿してデータを集める）
    if not slot_stat or slot_stat["count"] < MIN_DATA_POINTS:
        count = slot_stat["count"] if slot_stat else 0
        return True, f"スロット {time_slot}: データ {count}件（探索フェーズ・投稿）"

    # 十分なデータがあるスロットのみ比較対象にする
    mature_rates = [s["avg_rate"] for s in stats.values() if s["count"] >= MIN_DATA_POINTS]
    overall_avg = sum(mature_rates) / len(mature_rates)
    threshold = overall_avg * 0.8  # 平均の80%以上なら投稿

    if slot_stat["avg_rate"] >= threshold:
        return True, (f"スロット {time_slot}: エンゲージ {slot_stat['avg_rate']:.2%} "
                      f"≥ 閾値 {threshold:.2%}（投稿）")
    else:
        return False, (f"スロット {time_slot}: エンゲージ {slot_stat['avg_rate']:.2%} "
                       f"< 閾値 {threshold:.2%}（低パフォーマンス・スキップ）")


def decide_use_image():
    """画像を使うかどうかをエンゲージデータで判断する
    - データ不足: 50/50でランダム（A/B探索）
    - データあり: 勝者を70%、敗者を30%の確率で選ぶ
    """
    stats = get_image_vs_text_stats()
    img = stats["image"]
    txt = stats["text"]

    img_ok = img["count"] >= AB_MIN_SAMPLES
    txt_ok = txt["count"] >= AB_MIN_SAMPLES

    if not img_ok or not txt_ok:
        # どちらかデータ不足 → 交互にA/Bテスト（50/50）
        use_image = random.random() < 0.5
        reason = (f"A/B探索中 (画像:{img['count']}件, テキスト:{txt['count']}件) "
                  f"→ {'画像' if use_image else 'テキスト'}")
    else:
        image_rate = img["avg_rate"]
        text_rate = txt["avg_rate"]
        if image_rate > text_rate * 1.1:
            # 画像が10%以上上回る → 画像70%
            use_image = random.random() < 0.70
            reason = (f"画像優勢 ({image_rate:.2%} vs {text_rate:.2%}) "
                      f"→ 画像70%ルール → {'画像' if use_image else 'テキスト'}")
        elif text_rate > image_rate * 1.1:
            # テキストが10%以上上回る → テキスト70%
            use_image = random.random() < 0.30
            reason = (f"テキスト優勢 ({text_rate:.2%} vs {image_rate:.2%}) "
                      f"→ テキスト70%ルール → {'画像' if use_image else 'テキスト'}")
        else:
            # 差が小さい → 50/50継続
            use_image = random.random() < 0.5
            reason = (f"差なし (画像:{image_rate:.2%} vs テキスト:{text_rate:.2%}) "
                      f"→ 50/50 → {'画像' if use_image else 'テキスト'}")

    print(f"  [A/B] {reason}")
    return use_image


def _save_pending(data):
    with open(PENDING_POST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_mode():
    """コンテンツ・画像を生成して pending_post.json に保存"""
    print("=" * 40)
    print("  [生成モード] SNS 自動投稿システム")
    print("=" * 40)

    time_slot, _ = get_time_theme()
    should_post, reason = should_post_now(time_slot)
    print(f"\n【投稿判断】{reason}")

    if not should_post:
        print("  → スキップします。")
        _save_pending({"skip": True, "reason": reason})
        return

    print("\n【投稿生成】")
    try:
        post_content, score = get_best_post(platform="threads")
    except Exception as e:
        err_str = str(e)
        if "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower() or "429" in err_str:
            print(f"⚠️  Gemini APIの日次クォータを超過しました")
            _save_pending({"skip": True, "reason": "Gemini quota exceeded"})
            return
        raise

    if score < SCORE_THRESHOLD:
        print(f"  スコア {score} < 閾値 {SCORE_THRESHOLD}、品質不足につきスキップ")
        _save_pending({"skip": True, "reason": f"score {score} < threshold {SCORE_THRESHOLD}"})
        return

    print(f"\n--- 投稿内容 (スコア: {score}/100) ---\n{post_content}\n")

    # 画像を使うか判断（A/Bテスト）
    use_image = decide_use_image()

    image_filename = None
    if use_image:
        try:
            from image_gen import create_fortune_image
            os.makedirs(IMAGES_DIR, exist_ok=True)
            jst = pytz.timezone("Asia/Tokyo")
            ts = datetime.now(jst).strftime("%Y%m%d_%H%M%S")
            image_filename = f"{ts}.png"
            image_path = os.path.join(IMAGES_DIR, image_filename)
            create_fortune_image(post_content, image_path)
            print(f"  画像生成: {image_filename}")
        except Exception as e:
            print(f"  ⚠️ 画像生成失敗 (テキスト投稿に変更): {e}")
            image_filename = None
    else:
        print(f"  テキストのみで投稿")

    _save_pending({
        "skip": False,
        "content": post_content,
        "score": score,
        "time_slot": time_slot,
        "image_filename": image_filename,
    })
    print(f"  pending_post.json を保存しました")


def post_mode():
    """pending_post.json を読んで投稿実行"""
    print("=" * 40)
    print("  [投稿モード] SNS 自動投稿システム")
    print("=" * 40)

    if not os.path.exists(PENDING_POST_FILE):
        print("  pending_post.json が見つかりません。スキップ。")
        return

    with open(PENDING_POST_FILE, encoding="utf-8") as f:
        pending = json.load(f)

    if pending.get("skip"):
        print(f"  スキップ: {pending.get('reason', '')}")
        return

    post_content = pending["content"]
    time_slot = pending["time_slot"]
    image_filename = pending.get("image_filename")

    # 画像URL構築（GitHub Actions環境変数から）
    image_url = None
    if image_filename:
        github_repo = os.getenv("GITHUB_REPOSITORY", "")
        github_branch = os.getenv("GITHUB_REF_NAME", "master")
        if github_repo:
            image_url = (f"https://raw.githubusercontent.com/"
                         f"{github_repo}/{github_branch}/"
                         f"sns_auto_poster/generated_images/{image_filename}")
            print(f"  画像URL: {image_url}")

    print(f"\n--- 投稿内容 ---\n{post_content}\n")

    # 投稿実行
    print("\n【投稿実行】")
    x_id = post_to_x(post_content)
    threads_id = post_to_threads(post_content, image_url=image_url)

    # ログ記録
    has_affiliate = bool(AFFILIATE_LINK)
    has_image = bool(image_filename)
    if x_id:
        add_post(x_id, "x", post_content, time_slot, has_affiliate=has_affiliate, has_image=has_image)
    if threads_id:
        add_post(threads_id, "threads", post_content, time_slot, has_affiliate=has_affiliate, has_image=has_image)

    # 古い画像を削除
    try:
        from image_gen import cleanup_old_images
        cleanup_old_images(IMAGES_DIR)
    except Exception:
        pass

    print("\n" + "=" * 40)
    print(f"  X       : {'✅ 成功' if x_id else '❌ 失敗/スキップ'}")
    print(f"  Threads : {'✅ 成功' if threads_id else '❌ 失敗/スキップ'}")
    print("=" * 40)


def main():
    mode = "post"
    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]

    if mode == "generate":
        generate_mode()
    elif mode == "post":
        post_mode()
    else:
        print(f"未知のモード: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
