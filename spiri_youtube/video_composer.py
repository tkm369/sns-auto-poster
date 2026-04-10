"""
video_composer.py — FFmpegで背景動画 + ナレーション音声 + 字幕を合成

フロー:
  1. Pexelsから背景動画をダウンロード（複数クリップをシーン別に使用）
  2. 音声尺に合わせて背景動画をループ/トリム
  3. BGM を低音量でミックス
  4. ASS字幕をハードサブとして焼き込み
  5. タイトルテロップ（冒頭5秒）を追加
  6. 最終MP4を出力
"""
from __future__ import annotations
import random
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests

from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    BGM_VOLUME, BGM_DIR, OUTPUT_DIR, PEXELS_API_KEY,
)

# broll_inserterのPexelsクライアントを流用
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "broll_inserter"))
from stock_fetcher import PexelsClient


# ────────────────────────────────────────────────────────
# Pexels背景動画ダウンロード
# ────────────────────────────────────────────────────────

def fetch_background_video(keyword: str, out_dir: Path) -> Optional[Path]:
    """
    Pexelsからキーワードで背景動画を検索・ダウンロード。
    失敗時はNoneを返す。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    keys = [PEXELS_API_KEY] if PEXELS_API_KEY else None
    client = PexelsClient(keys=keys)

    try:
        video = client.search(keyword, per_page=10)
        if not video:
            print(f"[Video] Pexelsで '{keyword}' が見つかりません")
            return None

        url = client.get_download_url(video, prefer_hd=True)
        if not url:
            return None

        filename = out_dir / f"bg_{keyword.replace(' ', '_')[:30]}.mp4"
        if filename.exists():
            print(f"[Video] キャッシュ使用: {filename}")
            return filename

        print(f"[Video] ダウンロード中: {keyword}")
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return filename

    except Exception as e:
        print(f"[Video] Pexelsエラー: {e}")
        return None


# ────────────────────────────────────────────────────────
# FFmpegヘルパー
# ────────────────────────────────────────────────────────

def get_audio_duration(audio_path: str) -> float:
    """音声ファイルの再生時間を秒で取得"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def _get_bgm_path() -> Optional[Path]:
    """BGMフォルダからランダムにMP3を1つ選ぶ"""
    bgm_dir = Path(BGM_DIR)
    if not bgm_dir.exists():
        return None
    files = list(bgm_dir.glob("*.mp3")) + list(bgm_dir.glob("*.wav"))
    return random.choice(files) if files else None


def _build_title_drawtext(title: str, title_style=None) -> str:
    """
    冒頭N秒にタイトルテロップを表示するdrawtext フィルタ文字列を返す。
    title_style に TitleStyle インスタンスを渡すと型別スタイルを適用する。
    """
    from video_types import TitleStyle
    s = title_style if title_style is not None else TitleStyle()

    escaped = (
        title
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
    )

    parts = [
        f"text='{escaped}'",
        "fontfile=/Windows/Fonts/meiryo.ttc",
        f"fontsize={s.fontsize}",
        f"fontcolor={s.fontcolor}",
        f"borderw={s.borderw}",
        f"bordercolor={s.bordercolor}",
        "x=(w-text_w)/2",
        f"y=h*{s.y_ratio}",
        f"enable='between(t,0,{s.duration_sec})'",
    ]
    if s.box:
        parts += [
            "box=1",
            f"boxcolor={s.boxcolor}",
            "boxborderw=12",
        ]

    return "drawtext=" + ":".join(parts)


# ────────────────────────────────────────────────────────
# メイン合成関数
# ────────────────────────────────────────────────────────

def compose_video(
    narration_audio: str,
    ass_subtitle: str,
    output_path: str,
    title: str = "",
    bg_keyword: str = "cosmos meditation",
    bg_video: Optional[str] = None,
    work_dir: Optional[Path] = None,
    title_style=None,
    is_shorts: bool = False,
) -> str:
    """
    ナレーション音声 + 字幕 + 背景動画を合成して最終MP4を出力。

    Args:
        narration_audio: ナレーションMP3/WAVパス
        ass_subtitle:    ASSファイルパス
        output_path:     出力MP4パス
        title:           冒頭に表示するタイトルテロップ（空の場合は表示なし）
        bg_keyword:      Pexels検索キーワード（bg_videoが指定されていない場合に使用）
        bg_video:        背景動画パス（指定時はPexels検索をスキップ）
        work_dir:        一時ファイルディレクトリ
        title_style:     TitleStyle インスタンス（型別スタイル）
        is_shorts:       True の場合は 1080x1920 縦型で出力

    Returns:
        出力ファイルパス
    """
    # 解像度を決定
    if is_shorts:
        out_w, out_h = 1080, 1920
        print(f"[Compose] ショートモード: {out_w}x{out_h}")
    else:
        out_w, out_h = VIDEO_WIDTH, VIDEO_HEIGHT

    if work_dir is None:
        work_dir = Path(output_path).parent / "_work"
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. 音声尺を取得
    duration = get_audio_duration(narration_audio)
    print(f"[Compose] ナレーション尺: {duration:.1f}秒")

    # 2. 背景動画を準備
    if bg_video:
        bg_path = Path(bg_video)
    else:
        bg_path = fetch_background_video(bg_keyword, work_dir / "bg")
        if not bg_path:
            print("[Compose] 背景動画なし → 黒背景で合成")
            bg_path = None

    # 3. 背景動画をループ/リサイズしてトリム
    #    ショートの場合: 横動画を縦にクロップ（中央寄り）
    if bg_path:
        looped_bg = work_dir / "bg_looped.mp4"
        if is_shorts:
            # 横動画→縦クロップ: まず高さに合わせてスケール、幅をクロップ
            vf_scale = (
                f"scale=-2:{out_h},"                    # 高さ1920に合わせ幅を自動
                f"crop={out_w}:{out_h}"                 # 中央から1080幅でクロップ
            )
        else:
            vf_scale = (
                f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
                f"crop={out_w}:{out_h}"
            )
        subprocess.run([
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(bg_path),
            "-t", str(duration + 1),
            "-vf", vf_scale,
            "-r", str(VIDEO_FPS),
            "-c:v", "libx264",
            "-preset", "fast",
            "-an",
            str(looped_bg),
        ], check=True, capture_output=True)
        video_input = ["-i", str(looped_bg)]
    else:
        black_bg = work_dir / "black_bg.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:size={out_w}x{out_h}:r={VIDEO_FPS}",
            "-t", str(duration + 1),
            "-c:v", "libx264",
            str(black_bg),
        ], check=True, capture_output=True)
        video_input = ["-i", str(black_bg)]

    # 4. BGMを準備（任意）
    bgm_path = _get_bgm_path()
    bgm_inputs = []
    bgm_filter = ""
    if bgm_path:
        print(f"[Compose] BGM: {bgm_path.name}")
        bgm_inputs = ["-stream_loop", "-1", "-i", str(bgm_path)]
        bgm_filter = (
            f"[2:a]volume={BGM_VOLUME},atrim=0:{duration}[bgm];"
            "[1:a][bgm]amix=inputs=2:duration=first[aout]"
        )
    else:
        bgm_filter = "[1:a]acopy[aout]"

    # 5. フィルタグラフ構築
    ass_escaped = str(Path(ass_subtitle).as_posix()).replace(":", "\\:")
    vf_parts = [f"ass={ass_escaped}"]
    if title:
        vf_parts.append(_build_title_drawtext(title, title_style=title_style))
    vf_str = ",".join(vf_parts)

    filter_complex = f"[0:v]{vf_str}[vout];{bgm_filter}"

    # 6. FFmpeg合成
    cmd = [
        "ffmpeg", "-y",
        *video_input,
        "-i", narration_audio,
        *bgm_inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]

    print(f"[Compose] FFmpeg合成中...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpegエラー:\n{result.stderr[-2000:]}")

    print(f"[Compose] 完成: {output_path}")
    return output_path


if __name__ == "__main__":
    # 動作確認（既存の音声・字幕がある場合）
    import sys
    audio = sys.argv[1] if len(sys.argv) > 1 else "test.mp3"
    ass   = sys.argv[2] if len(sys.argv) > 2 else "test.ass"
    out   = sys.argv[3] if len(sys.argv) > 3 else "output_test.mp4"
    compose_video(audio, ass, out, title="テスト動画", bg_keyword="nature peaceful")
