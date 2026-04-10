"""
audio_analyzer.py
無音・ノイズ区間の検出
"""
import static_ffmpeg
static_ffmpeg.add_paths()  # ffmpeg.exeをPATHに追加（同梱バイナリを使用）

from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from typing import List, Dict


def detect_silence_cuts(
    audio_path: str,
    silence_thresh: float = -40,
    min_silence_sec: float = 0.3,
    keep_gap: float = 0.15,
) -> List[Dict]:
    """
    無音/ノイズ区間を検出してカットリストを返す。

    Args:
        audio_path:      動画/音声ファイルパス
        silence_thresh:  無音と判断するdBFS（例: -40）
        min_silence_sec: カット対象とする最小無音時間（秒）
        keep_gap:        発話前後に残す余白（秒）

    Returns:
        [{"start": float, "end": float, "reason": str}]  ※秒単位
    """
    audio = AudioSegment.from_file(audio_path)
    total_ms = len(audio)
    min_silence_ms = int(min_silence_sec * 1000)

    nonsilent = detect_nonsilent(
        audio,
        min_silence_len=min_silence_ms,
        silence_thresh=silence_thresh,
        seek_step=10,
    )

    if not nonsilent:
        return [{"start": 0.0, "end": round(total_ms / 1000, 4), "reason": "silence(全区間)"}]

    # 余白を付加してオーバーラップをマージ
    gap_ms = int(keep_gap * 1000)
    kept: List[List[int]] = []
    for s, e in nonsilent:
        padded_s = max(0, s - gap_ms)
        padded_e = min(total_ms, e + gap_ms)
        if kept and padded_s <= kept[-1][1]:
            kept[-1][1] = max(kept[-1][1], padded_e)
        else:
            kept.append([padded_s, padded_e])

    # 「保持」の逆 → カット区間
    cuts: List[Dict] = []
    prev_end = 0
    for s, e in kept:
        if s > prev_end + 50:  # 50ms以上の隙間のみカット
            cuts.append({
                "start": round(prev_end / 1000, 4),
                "end": round(s / 1000, 4),
                "reason": "silence",
            })
        prev_end = e

    if prev_end < total_ms - 50:
        cuts.append({
            "start": round(prev_end / 1000, 4),
            "end": round(total_ms / 1000, 4),
            "reason": "silence",
        })

    return cuts
