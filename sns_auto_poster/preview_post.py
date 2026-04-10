"""投稿プレビュー用スクリプト（SNSには投稿しない）"""
import os, sys
if not os.getenv("GEMINI_API_KEY"):
    print("使い方: $env:GEMINI_API_KEY='YOUR_KEY'; python preview_post.py")
    sys.exit(1)

from generator import get_best_post, get_time_theme

slot, theme = get_time_theme()
print(f"\n現在のスロット: {slot}（テーマ: {theme}）\n")
print("生成中...")
post = get_best_post(platform="x")
print("\n" + "="*50)
print(post)
print("="*50)
