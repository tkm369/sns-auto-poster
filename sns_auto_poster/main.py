from generator import get_best_post
from poster import post_to_x, post_to_threads


def main():
    print("=" * 40)
    print("  SNS 自動投稿システム 起動")
    print("=" * 40)

    # X用投稿を生成・改善
    print("\n【X 投稿生成】")
    x_post = get_best_post(platform="x")
    print(f"\n--- X 投稿内容 ---\n{x_post}\n")

    # Threads用投稿を生成・改善（少し長めに）
    print("\n【Threads 投稿生成】")
    threads_post = get_best_post(platform="threads")
    print(f"\n--- Threads 投稿内容 ---\n{threads_post}\n")

    # 投稿実行
    print("\n【投稿実行】")
    x_ok = post_to_x(x_post)
    threads_ok = post_to_threads(threads_post)

    # 結果サマリー
    print("\n" + "=" * 40)
    print(f"  X       : {'✅ 成功' if x_ok else '❌ 失敗/スキップ'}")
    print(f"  Threads : {'✅ 成功' if threads_ok else '❌ 失敗/スキップ'}")
    print("=" * 40)


if __name__ == "__main__":
    main()
