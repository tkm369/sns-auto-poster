import sys
from generator import get_best_post
from poster import post_to_x, post_to_threads
from logger import add_post, count_posts_today, get_time_slot_stats
from generator import get_time_theme
from config import AFFILIATE_LINK

MAX_POSTS_PER_DAY = 6
MIN_DATA_POINTS = 5  # 探索フェーズ終了に必要なデータ数


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


def main():
    print("=" * 40)
    print("  SNS 自動投稿システム 起動")
    print("=" * 40)

    time_slot, _ = get_time_theme()

    # 投稿判断（PDCAベース）
    should_post, reason = should_post_now(time_slot)
    print(f"\n【投稿判断】{reason}")
    if not should_post:
        print("  → 今回はスキップします。")
        sys.exit(0)

    # 投稿生成（APIコール節約のためX・Threads共通コンテンツを1回で生成）
    print("\n【投稿生成】")
    try:
        post_content = get_best_post(platform="x")
    except Exception as e:
        err_str = str(e)
        if "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower() or "429" in err_str:
            print(f"⚠️  Gemini APIの日次クォータを超過しました（本日の残枠なし）")
            print(f"   詳細: {err_str[:200]}")
            print("   次回の実行時間まで待機します。")
            sys.exit(0)
        raise

    print(f"\n--- 投稿内容 ---\n{post_content}\n")

    x_post = post_content
    threads_post = post_content

    # 投稿実行
    print("\n【投稿実行】")
    x_id = post_to_x(x_post)
    threads_id = post_to_threads(threads_post)

    # ログ記録
    has_affiliate = bool(AFFILIATE_LINK)
    if x_id:
        add_post(x_id, "x", x_post, time_slot, has_affiliate=has_affiliate)
    if threads_id:
        add_post(threads_id, "threads", threads_post, time_slot, has_affiliate=has_affiliate)

    # 結果サマリー
    print("\n" + "=" * 40)
    print(f"  X       : {'✅ 成功' if x_id else '❌ 失敗/スキップ'}")
    print(f"  Threads : {'✅ 成功' if threads_id else '❌ 失敗/スキップ'}")
    print("=" * 40)


if __name__ == "__main__":
    main()
