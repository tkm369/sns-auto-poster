#!/usr/bin/env python3
"""
YouTube Shorts 自動DL & 編集ツール
- チャンネルのショート本数をチェック
- 指定範囲でDL
- 冒頭ズームイン + 冒頭SE（薄め）
- 上下にランダムカラー帯 + 上帯にランダムテロップを追加
"""

import sys
import json
import random
import subprocess
import tempfile
import shutil
import time
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("yt-dlp が見つかりません。pip install yt-dlp を実行してください。")
    sys.exit(1)


# ============================================================
# テロップ候補リスト
# ============================================================
CAPTION_POOL = [
    "知らなきゃ損！",
    "これは必見🔥",
    "バズり確定✨",
    "ちょっと待って…",
    "え、マジで？",
    "思わず二度見した",
    "みんな知ってる？",
    "衝撃の事実",
    "保存必須👇",
    "見逃し厳禁！",
    "トレンド最前線",
    "今話題の…",
    "信じられない…",
    "思わず笑った😂",
    "これは天才すぎ",
    "シェアして！",
    "フォローよろしく",
    "最後まで見てね",
    "コメントどうぞ",
    "いいね押して！",
]

# ============================================================
# 設定
# ============================================================
TOP_BAND_HEIGHT_RATIO    = 0.18   # 上帯：動画高さの18%
BOTTOM_BAND_HEIGHT_RATIO = 0.12   # 下帯：動画高さの12%

ZOOM_DURATION = 1.5    # 冒頭ズームインの秒数
ZOOM_START    = 1.25   # ズーム開始倍率（1.0 = 等倍）

SE_VOLUME = 0.25       # SEの音量（0.0〜1.0）

OUTPUT_DIR   = Path("出力動画")
DOWNLOAD_DIR = OUTPUT_DIR / "ダウンロード"
EDITED_DIR   = OUTPUT_DIR / "編集済み"
SE_DIR       = Path("SE音源")      # ここにSEファイルを置く
COOKIE_FILE  = Path(__file__).parent / "cookies.txt"


# ============================================================
# ユーティリティ
# ============================================================

def random_color_hex():
    return random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)


def random_vivid_color():
    vivid = [
        (255, 50,  50),   # 赤
        (255, 200,  0),   # 黄
        (0,  220,  80),   # 緑
        (0,  180, 255),   # 水色
        (220, 50, 255),   # 紫
        (255, 120,  0),   # オレンジ
        (255, 255, 255),  # 白
        (50,  255, 220),  # シアン
    ]
    return random.choice(vivid)


def get_video_info(video_path: Path):
    """幅・高さ・fps・長さを取得"""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate:format=duration",
        "-of", "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    w = stream["width"]
    h = stream["height"]
    num, den = stream.get("r_frame_rate", "30/1").split("/")
    fps = round(float(num) / float(den), 3)
    duration = float(data.get("format", {}).get("duration", 60))
    return w, h, fps, duration


def find_or_create_se() -> Path | None:
    """SEフォルダからファイルを探す。なければデフォルトSEを生成"""
    SE_DIR.mkdir(exist_ok=True)
    for ext in ["*.wav", "*.mp3", "*.m4a", "*.ogg"]:
        files = list(SE_DIR.glob(ext))
        if files:
            return files[0]

    # デフォルトSE（周波数が上昇するサイン波チャイム）を生成
    default_se = SE_DIR / "default_se.wav"
    if not default_se.exists():
        print("  SE ファイルが見つからないため、デフォルトSEを自動生成します...")
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "aevalsrc=0.5*sin(2*PI*t*(400+400*t)):s=44100:d=0.8",
            "-af", "afade=t=in:st=0:d=0.05,afade=t=out:st=0.6:d=0.2",
            str(default_se),
        ]
        subprocess.run(cmd, capture_output=True)

    return default_se if default_se.exists() else None


# ============================================================
# チャンネル情報取得
# ============================================================


def get_channel_shorts_info(channel_url: str):
    print(f"\nチャンネル情報を取得中: {channel_url}")
    print("（数十秒かかる場合があります）\n")

    if "/shorts" not in channel_url:
        shorts_url = channel_url.rstrip("/") + "/shorts"
    else:
        shorts_url = channel_url

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlist_items": "1-500",
        "js_runtimes": {"node": {}},
        **({"cookiefile": str(COOKIE_FILE)} if COOKIE_FILE.exists() else {}),
    }
    entries = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(shorts_url, download=False)
        if info and "entries" in info:
            entries = [e for e in info["entries"] if e]
    return entries


# ============================================================
# ダウンロード
# ============================================================

def download_shorts(entries, start_idx: int, count: int):
    target = entries[start_idx - 1 : start_idx - 1 + count]
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n{len(target)} 本のショートをダウンロードします...\n")

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": str(DOWNLOAD_DIR / "%(autonumber)s_%(id)s.%(ext)s"),
        "quiet": False,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "autonumber_start": 1,
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        "sleep_interval_requests": 1,
        "js_runtimes": {"node": {}},
        **({"cookiefile": str(COOKIE_FILE)} if COOKIE_FILE.exists() else {}),
    }
    BATCH_SIZE  = 50   # 何本ごとに休憩するか
    BATCH_REST  = 60   # 50本ごとの休憩（秒）
    LONG_BATCH  = 200  # 何本ごとに長めの休憩
    LONG_REST   = 300  # 200本ごとの休憩（秒）

    downloaded = []
    urls = [f"https://www.youtube.com/watch?v={e['id']}" for e in target if e.get("id")]
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for i, url in enumerate(urls, 1):
            try:
                info = ydl.extract_info(url, download=True)
                p = Path(ydl.prepare_filename(info))
                if not p.exists():
                    p = p.with_suffix(".mp4")
                if p.exists():
                    downloaded.append(p)
                    print(f"  ✓ {p.name}")
            except Exception as e:
                print(f"  ✗ エラー: {e}")

            # 休憩（長い休憩を優先チェック）
            if i % LONG_BATCH == 0 and i < len(urls):
                print(f"\n  [{i}/{len(urls)}] {LONG_REST//60}分休憩中（長期DL対策）...")
                time.sleep(LONG_REST)
                print("  再開します\n")
            elif i % BATCH_SIZE == 0 and i < len(urls):
                print(f"\n  [{i}/{len(urls)}] {BATCH_REST}秒 休憩中...")
                time.sleep(BATCH_REST)
                print("  再開します\n")
    return downloaded


# ============================================================
# 編集（ズームイン + SE + 帯 + テロップ）
# ============================================================

def edit_video(input_path: Path, output_path: Path):
    w, h, fps, duration = get_video_info(input_path)
    top_band_h = max(70, int(h * TOP_BAND_HEIGHT_RATIO))
    bot_band_h = max(60, int(h * BOTTOM_BAND_HEIGHT_RATIO))

    # 帯の色
    tr, tg, tb = random_color_hex()
    br, bg, bb = random_color_hex()

    # テロップ
    fr, fg, fb = random_vivid_color()
    font_color = f"#{fr:02x}{fg:02x}{fb:02x}"
    caption    = random.choice(CAPTION_POOL)

    size_by_height = int(top_band_h * 0.55)
    size_by_width  = int(w * 0.90 / max(len(caption), 1))
    font_size = max(20, min(size_by_height, size_by_width))
    border_w  = max(2, font_size // 10)

    # フォント（太字優先）
    font_candidates = [
        "C\\:/Windows/Fonts/meiryob.ttc",
        "C\\:/Windows/Fonts/YuGothB.ttc",
        "C\\:/Windows/Fonts/meiryo.ttc",
        "C\\:/Windows/Fonts/YuGothM.ttc",
        "C\\:/Windows/Fonts/msgothic.ttc",
        "C\\:/Windows/Fonts/arialbd.ttf",
        "C\\:/Windows/Fonts/arial.ttf",
    ]
    font_path = next(
        (fc for fc in font_candidates if Path(fc.replace("C\\:/", "C:/")).exists()),
        "C\\:/Windows/Fonts/arial.ttf"
    )

    # テロップはTEMPフォルダ経由（日本語パスのエスケープ問題を回避）
    text_file = Path(tempfile.gettempdir()) / "ffmpeg_caption.txt"
    text_file.write_text(caption, encoding="utf-8")
    # ドライブ文字のコロン（C:）を C\: にエスケープ（ffmpegフィルター内でコロンは区切り文字のため）
    text_file_fwd = str(text_file).replace("\\", "/").replace(":/", "\\:/")

    # 帯 + テロップ フィルター文字列
    bands_text = (
        f"drawbox=x=0:y=0:w={w}:h={top_band_h}:color=#{tr:02x}{tg:02x}{tb:02x}:t=fill,"
        f"drawbox=x=0:y={h - bot_band_h}:w={w}:h={bot_band_h}:color=#{br:02x}{bg:02x}{bb:02x}:t=fill,"
        f"drawtext=textfile='{text_file_fwd}':"
        f"fontfile='{font_path}':"
        f"fontcolor={font_color}:"
        f"fontsize={font_size}:"
        f"borderw={border_w}:"
        f"bordercolor=black:"
        f"x=(w-text_w)/2:"
        f"y=({top_band_h}-text_h)/2"
    )

    # ズームイン：冒頭 ZOOM_DURATION 秒のみ scale+crop → 残りは通常
    zoom_dur = min(ZOOM_DURATION, duration - 0.1)
    zoom_pct = int(ZOOM_START * 100)
    zoom_filter = (
        f"scale=iw*{zoom_pct}/100:ih*{zoom_pct}/100,"
        f"crop=w={w}:h={h}:x=(in_w-{w})/2:y=(in_h-{h})/2"
    )

    if duration > zoom_dur + 0.1:
        video_fc = (
            f"[0:v]split=2[v_head][v_tail];"
            f"[v_head]trim=0:{zoom_dur},setpts=PTS-STARTPTS,{zoom_filter}[v_zoom];"
            f"[v_tail]trim={zoom_dur},setpts=PTS-STARTPTS[v_rest];"
            f"[v_zoom][v_rest]concat=n=2:v=1:a=0[v_concat];"
            f"[v_concat]{bands_text}[v_out]"
        )
    else:
        video_fc = f"[0:v]{zoom_filter},{bands_text}[v_out]"

    # SE
    se_path = find_or_create_se()
    use_se  = se_path and se_path.exists()

    if use_se:
        audio_fc = (
            f"[1:a]volume={SE_VOLUME},apad[se_a];"
            f"[0:a][se_a]amix=inputs=2:duration=first[a_out]"
        )
        filter_complex = video_fc + ";" + audio_fc
        audio_map = "[a_out]"
    else:
        filter_complex = video_fc
        audio_map = "0:a"

    # 日本語パスに ffmpeg が書けない場合があるため、一旦 TEMP に出力して移動する
    tmp_out = Path(tempfile.gettempdir()) / ("tmp_" + input_path.stem + ".mp4")

    # -hwaccel cuda でGPUデコード、-threads 0 でCPUフィルターを全コア使用
    base_cmd = ["ffmpeg", "-y", "-hwaccel", "cuda", "-i", str(input_path)]
    if use_se:
        base_cmd += ["-i", str(se_path)]
    base_cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-map", audio_map,
        "-c:a", "aac", "-b:a", "128k",
        "-threads", "0",
    ]

    # GPU p1（最速）→ CPU ultrafast フォールバック
    encode_modes = [
        ("GPU(NVENC)", ["-c:v", "h264_nvenc", "-rc", "vbr", "-cq", "23", "-preset", "p1"]),
        ("CPU(libx264)", ["-c:v", "libx264", "-crf", "23", "-preset", "ultrafast"]),
    ]

    print(
        f"  編集中: {input_path.name}\n"
        f"    帯(上)#{tr:02x}{tg:02x}{tb:02x} (下)#{br:02x}{bg:02x}{bb:02x} "
        f"文字色:{font_color} テロップ:「{caption}」 SE:{'あり' if use_se else 'なし'}"
    )

    result = None
    for label, enc_args in encode_modes:
        print(f"    エンコード: {label}")
        cmd = base_cmd + enc_args + [str(tmp_out)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode == 0:
            break
        print(f"    {label} 失敗、次の方法を試します...")

    if result.returncode != 0:
        print(f"  ffmpeg エラー（終了コード {result.returncode}）:")
        print(result.stderr[-1500:])
        return False

    # TEMP → 最終出力先に移動
    shutil.move(str(tmp_out), str(output_path))
    return True


# ============================================================
# メイン
# ============================================================

def main():
    print("=" * 55)
    print("  YouTube Shorts 自動DL & 編集ツール")
    print("=" * 55)
    print(f"\n  SE ファイルの置き場所: {SE_DIR.resolve()}")
    print("  （.wav / .mp3 / .m4a を置くと冒頭に流れます）\n")

    channel_url = input("チャンネルURL を入力してください: ").strip()
    if not channel_url:
        print("URLが入力されていません。終了します。")
        sys.exit(1)

    entries = get_channel_shorts_info(channel_url)
    total   = len(entries)
    if total == 0:
        print("ショートが見つかりませんでした。URLを確認してください。")
        sys.exit(1)

    print(f"ショート総数: {total} 本")

    while True:
        try:
            start = int(input(f"何本目からDLしますか？ (1〜{total}): ").strip())
            if 1 <= start <= total:
                break
        except ValueError:
            pass
        print(f"  1〜{total} の範囲で数字を入力してください。")

    max_count = total - start + 1
    while True:
        try:
            count = int(input(f"何本DLしますか？ (1〜{max_count}): ").strip())
            if 1 <= count <= max_count:
                break
        except ValueError:
            pass
        print(f"  1〜{max_count} の範囲で数字を入力してください。")

    total_start = time.time()

    dl_start   = time.time()
    downloaded = download_shorts(entries, start, count)
    dl_elapsed = time.time() - dl_start

    if not downloaded:
        print("\nダウンロードに失敗しました。")
        sys.exit(1)

    print(f"\n✓ {len(downloaded)} 本のダウンロード完了  ({dl_elapsed:.1f}秒)")

    EDITED_DIR.mkdir(parents=True, exist_ok=True)
    print("\nズームイン + SE + 帯 & テロップ追加中...\n")

    edit_start = time.time()
    success    = 0
    edit_times = []
    for vid in downloaded:
        t0  = time.time()
        out = EDITED_DIR / ("edited_" + vid.name)
        if edit_video(vid, out):
            success += 1
            vid.unlink()
        edit_times.append(time.time() - t0)
    edit_elapsed = time.time() - edit_start
    total_elapsed = time.time() - total_start

    avg_edit = sum(edit_times) / len(edit_times) if edit_times else 0

    print(f"\n{'='*50}")
    print(f"  完了サマリー")
    print(f"{'='*50}")
    print(f"  ダウンロード : {dl_elapsed:>7.1f} 秒  ({len(downloaded)}本 / 1本あたり {dl_elapsed/max(len(downloaded),1):.1f}秒)")
    print(f"  編集        : {edit_elapsed:>7.1f} 秒  ({success}本成功 / 1本あたり {avg_edit:.1f}秒)")
    print(f"  合計        : {total_elapsed:>7.1f} 秒  ({total_elapsed/60:.1f}分)")
    print(f"{'='*50}")
    print(f"  出力先: {EDITED_DIR.resolve()}")


if __name__ == "__main__":
    main()
