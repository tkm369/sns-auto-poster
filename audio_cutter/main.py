"""
main.py
Premiere Pro 音声カット自動化ツール

使い方:
  python main.py video.mp4
  python main.py video.mp4 --gap 0.2 --silence-thresh -38 --min-silence 0.4
  python main.py video.mp4 --preview          # カットしない、マーカーのみ追加
  python main.py video.mp4 --dry-run          # JSX生成せず、カット箇所を表示
  python main.py video.mp4 --no-fillers       # フィラー検出を無効化
  python main.py video.mp4 --no-stammers      # 噛み検出を無効化
  python main.py video.mp4 --model medium     # 軽量モデルを使用（速い）
"""

import argparse
import os
import sys
from typing import List, Dict

from core import detect_silence_cuts, analyze_speech_cuts, generate_jsx


def merge_cuts(cuts: List[Dict]) -> List[Dict]:
    """カット区間をソートしてオーバーラップをマージ"""
    if not cuts:
        return []
    sorted_cuts = sorted(cuts, key=lambda x: x["start"])
    merged = [sorted_cuts[0].copy()]
    for cut in sorted_cuts[1:]:
        last = merged[-1]
        if cut["start"] <= last["end"] + 0.05:  # 50ms以内は結合
            last["end"] = max(last["end"], cut["end"])
            if cut["reason"] not in last["reason"]:
                last["reason"] += " + " + cut["reason"]
        else:
            merged.append(cut.copy())
    return merged


def print_cuts(cuts: List[Dict]) -> None:
    print(f"\n{'─'*65}")
    print(f"{'#':>4}  {'開始':>8}  {'終了':>8}  {'時間':>6}  理由")
    print(f"{'─'*65}")
    for i, cut in enumerate(cuts):
        dur = cut["end"] - cut["start"]
        print(f"{i+1:>4}  {cut['start']:>8.3f}s  {cut['end']:>8.3f}s  {dur:>5.2f}s  {cut['reason']}")
    total = sum(c["end"] - c["start"] for c in cuts)
    print(f"{'─'*65}")
    print(f"  合計 {len(cuts)} 箇所 / {total:.1f} 秒カット")
    print(f"{'─'*65}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Premiere Pro 音声カット自動化ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", help="動画/音声ファイルパス")

    # 無音設定
    parser.add_argument(
        "--gap", type=float, default=0.15,
        help="発話前後に残す余白（秒）デフォルト: 0.15",
    )
    parser.add_argument(
        "--silence-thresh", type=float, default=-40,
        help="無音と判断するdBFS デフォルト: -40（静かな環境は-45〜-50）",
    )
    parser.add_argument(
        "--min-silence", type=float, default=0.3,
        help="カット対象とする最小無音時間（秒）デフォルト: 0.3",
    )

    # フィラー設定
    parser.add_argument(
        "--filler-min", type=float, default=0.4,
        help="カット対象フィラーの最小時間（秒）デフォルト: 0.4",
    )
    parser.add_argument("--no-fillers", action="store_true", help="フィラー検出を無効化")
    parser.add_argument("--no-stammers", action="store_true", help="噛み検出を無効化")

    # Whisperモデル
    parser.add_argument(
        "--model", default="large-v3",
        choices=["tiny", "base", "small", "medium", "large", "large-v3"],
        help="Whisperモデル デフォルト: large-v3（精度重視）、medium（速度重視）",
    )

    # 出力設定
    parser.add_argument("--output", default=None, help="出力JSXファイルパス")
    parser.add_argument(
        "--preview", action="store_true",
        help="プレビューモード: JSXはマーカー追加のみ（リップル削除しない）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="JSXを生成せず、カット箇所の一覧だけ表示",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"エラー: ファイルが見つかりません: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  Audio Auto Cutter")
    print(f"{'='*50}")
    print(f"  入力: {args.input}")
    print(f"  余白: {args.gap}s | 無音閾値: {args.silence_thresh}dBFS | 最小無音: {args.min_silence}s")
    if not args.no_fillers:
        print(f"  フィラー検出: ON (最小 {args.filler_min}s)")
    if not args.no_stammers:
        print(f"  噛み検出: ON")
    print(f"{'='*50}\n")

    # ① 無音・ノイズ検出
    print("[1/3] 無音区間を検出中...")
    silence_cuts = detect_silence_cuts(
        args.input,
        silence_thresh=args.silence_thresh,
        min_silence_sec=args.min_silence,
        keep_gap=args.gap,
    )
    print(f"  無音/ノイズ: {len(silence_cuts)} 箇所")

    # ② Whisper解析（フィラー・噛み）
    speech_cuts = []
    use_speech = not args.no_fillers or not args.no_stammers
    if use_speech:
        print(f"[2/3] 音声認識中 (Whisper {args.model})...")
        speech_cuts = analyze_speech_cuts(
            args.input,
            model_name=args.model,
            filler_min_sec=args.filler_min,
            detect_fillers=not args.no_fillers,
            detect_stammers=not args.no_stammers,
        )
    else:
        print("[2/3] 音声認識: スキップ")

    # ③ マージ
    print("[3/3] カット区間を統合中...")
    all_cuts = silence_cuts + speech_cuts
    merged = merge_cuts(all_cuts)
    print(f"  合計 {len(merged)} 箇所")

    # 結果表示
    print_cuts(merged)

    if args.dry_run:
        print("dry-run モード: JSXは生成しません")
        return

    # JSX生成
    base = os.path.splitext(args.input)[0]
    output = args.output or f"{base}_cuts.jsx"
    generate_jsx(merged, output, preview_only=args.preview)

    mode_str = "プレビュー（マーカー）モード" if args.preview else "リップル削除モード"
    print(f"JSX生成完了！（{mode_str}）")
    print(f"  → {output}")
    print()
    print("Premiere Proでの実行方法:")
    print("  ファイル > スクリプト > スクリプトを実行... > 上記ファイルを選択")
    print()
    if not args.preview:
        print("※ まず --preview で確認することをおすすめします")


if __name__ == "__main__":
    main()
