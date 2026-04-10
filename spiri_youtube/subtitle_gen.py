"""
subtitle_gen.py — faster-whisperで音声 → SRT/ASS字幕生成
audio_cutter の srt_generator.py を流用
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional


def _to_srt_time(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _to_ass_time(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def transcribe(
    audio_path: str,
    model_size: str = "medium",
    language: str = "ja",
    word_timestamps: bool = False,
) -> list[dict]:
    """
    faster-whisperで文字起こしし、セグメントリストを返す。

    Returns:
        [{"start": float, "end": float, "text": str}, ...]
    """
    from faster_whisper import WhisperModel

    print(f"[Subtitle] Whisperモデル読み込み中: {model_size}")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments_iter, info = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=word_timestamps,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    segments = []
    for seg in segments_iter:
        segments.append({
            "start": seg.start,
            "end":   seg.end,
            "text":  seg.text.strip(),
        })

    print(f"[Subtitle] {len(segments)} セグメント生成")
    return segments


def segments_to_srt(segments: list[dict]) -> str:
    blocks = []
    for i, seg in enumerate(segments, 1):
        start = _to_srt_time(seg["start"])
        end   = _to_srt_time(seg["end"])
        text  = seg["text"]
        if text:
            blocks.append(f"{i}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + "\n"


def segments_to_ass(
    segments: list[dict],
    fontname:        str   = "Noto Sans CJK JP",
    fontsize:        int   = 52,
    primary_colour:  str   = "&H00FFFFFF",
    outline_colour:  str   = "&H00000000",
    back_colour:     str   = "&H80000000",
    bold:            int   = -1,
    outline:         float = 3.0,
    shadow:          float = 1.0,
    margin_v:        int   = 60,
    alignment:       int   = 2,
    play_res_x:      int   = 1920,
    play_res_y:      int   = 1080,
) -> str:
    """
    FFmpeg字幕フィルタで使えるASSファイル文字列を返す。
    SubtitleStyle の各フィールドをそのまま受け取れる。
    is_shorts の場合は play_res_x=1080, play_res_y=1920 を渡す。
    """
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},{primary_colour},&H000000FF,{outline_colour},{back_colour},{bold},0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for seg in segments:
        start = _to_ass_time(seg["start"])
        end   = _to_ass_time(seg["end"])
        text  = seg["text"].replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    return header + "\n".join(events) + "\n"


def save_srt(segments: list[dict], output_path: str) -> str:
    content = segments_to_srt(segments)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def save_ass(
    segments: list[dict],
    output_path: str,
    subtitle_style=None,
    is_shorts: bool = False,
) -> str:
    """
    subtitle_style に SubtitleStyle インスタンスを渡すと型別スタイルを適用する。
    is_shorts=True の場合は解像度を 1080x1920 に設定する。
    """
    kwargs: dict = {}
    if subtitle_style is not None:
        kwargs = dict(
            fontsize       = subtitle_style.fontsize,
            primary_colour = subtitle_style.primary_colour,
            outline_colour = subtitle_style.outline_colour,
            back_colour    = subtitle_style.back_colour,
            bold           = subtitle_style.bold,
            outline        = subtitle_style.outline,
            shadow         = subtitle_style.shadow,
            margin_v       = subtitle_style.margin_v,
            alignment      = subtitle_style.alignment,
        )
    if is_shorts:
        kwargs["play_res_x"] = 1080
        kwargs["play_res_y"] = 1920
    content = segments_to_ass(segments, **kwargs)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def generate_subtitles(
    audio_path: str,
    output_dir: str,
    model_size: str = "medium",
    subtitle_style=None,
    is_shorts: bool = False,
) -> tuple[str, str]:
    """
    音声ファイルから SRT + ASS を生成。
    subtitle_style に SubtitleStyle インスタンスを渡すと型別スタイルを適用。
    is_shorts=True の場合は PlayResX/Y をショート解像度（1080x1920）に設定する。

    Returns:
        (srt_path, ass_path)
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    stem = Path(audio_path).stem
    srt_path = str(out / f"{stem}.srt")
    ass_path = str(out / f"{stem}.ass")

    segments = transcribe(audio_path, model_size=model_size)
    save_srt(segments, srt_path)
    save_ass(segments, ass_path, subtitle_style=subtitle_style, is_shorts=is_shorts)

    return srt_path, ass_path


if __name__ == "__main__":
    import sys
    audio = sys.argv[1] if len(sys.argv) > 1 else "test.mp3"
    srt, ass = generate_subtitles(audio, "./output/subtitles")
    print(f"SRT: {srt}\nASS: {ass}")
