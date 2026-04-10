"""
srt_generator.py
Whisperセグメント → SRTファイル生成
"""
from typing import List, Dict


def _to_srt_time(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: List[Dict]) -> str:
    """セグメントリスト → SRT文字列"""
    blocks = []
    for i, seg in enumerate(segments, 1):
        start = _to_srt_time(seg["start"])
        end   = _to_srt_time(seg["end"])
        text  = seg["text"].strip()
        if text:
            blocks.append(f"{i}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + "\n"


def save_srt(segments: List[Dict], output_path: str) -> str:
    content = segments_to_srt(segments)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path
