"""
make_demo.py - サンプル投稿画像 + 背景動画を生成してデモ動画を作る
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip, ImageClip, CompositeVideoClip
from moviepy.video.fx import Crop, Resize, CrossFadeIn

import config

# ------------------------------------------------------------------ #
#  フォント取得 (Windowsのフォントを使う)
# ------------------------------------------------------------------ #
def get_font(size):
    candidates = [
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ------------------------------------------------------------------ #
#  サンプルXポスト画像を生成
# ------------------------------------------------------------------ #
def make_sample_x_post(save_path: str):
    # 本文だけ表示 (アカウント情報・エンゲージメントなし)
    body_lines = [
        "【今日の恋愛運🌙】",
        "",
        "あなたに近づいてくる人は",
        "偶然ではありません。",
        "",
        "宇宙があなたのために",
        "用意した出会いです✨",
        "",
        "その縁を大切に。",
        "",
        "信じる心が",
        "奇跡を引き寄せます🔮",
    ]

    font_body = get_font(34)
    pad = 48
    line_h = 52

    H = pad * 2 + len(body_lines) * line_h
    W = 1100

    img  = Image.new("RGBA", (W, H), (15, 20, 25, 255))
    draw = ImageDraw.Draw(img)

    y = pad
    for line in body_lines:
        draw.text((pad, y), line, font=font_body, fill=(231, 233, 234))
        y += line_h

    img.save(save_path)
    print(f"サンプル投稿画像を生成: {save_path}")
    return save_path


# ------------------------------------------------------------------ #
#  グラデーション背景動画をメモリ上で生成
# ------------------------------------------------------------------ #
def make_gradient_frame(t):
    """時間 t に応じてゆっくり色が変わるグラデーションフレームを返す"""
    W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    frame = np.zeros((H, W, 3), dtype=np.uint8)

    # 紫→濃紺のグラデーション (時間で少しずつ動く)
    shift = int(t * 8) % H
    for y in range(H):
        ratio = ((y + shift) % H) / H
        r = int(20  + ratio * 30)
        g = int(10  + ratio * 15)
        b = int(60  + ratio * 80)
        frame[y, :] = [r, g, b]

    # 星っぽいノイズを少し散らす
    rng = np.random.default_rng(seed=int(t * 5))
    stars = rng.integers(0, H * W, size=120)
    for s in stars:
        py, px = divmod(s, W)
        brightness = rng.integers(150, 255)
        frame[py, px] = [brightness, brightness, brightness]

    return frame


# ------------------------------------------------------------------ #
#  デモ動画生成
# ------------------------------------------------------------------ #
def make_demo():
    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR,      exist_ok=True)

    # 1) サンプル投稿画像
    ss_path  = os.path.join(config.SCREENSHOTS_DIR, "demo_post.png")
    make_sample_x_post(ss_path)

    # 2) スクショ加工 (角丸+影)
    from composer import prepare_screenshot
    ss_target_w = int(config.VIDEO_WIDTH * config.SCREENSHOT_WIDTH_RATIO)
    ss_img      = prepare_screenshot(ss_path, ss_target_w)
    ss_array    = np.array(ss_img)

    # 3) 背景動画クリップ (プログラム生成)
    duration = 15.0
    bg_clip  = VideoClip(make_gradient_frame, duration=duration)
    bg_clip  = bg_clip.with_effects([Resize((config.VIDEO_WIDTH, config.VIDEO_HEIGHT))])

    # 4) スクショクリップ
    ss_clip = ImageClip(ss_array)
    ss_clip = ss_clip.with_start(0.3).with_duration(duration - 0.3)
    ss_clip = ss_clip.with_effects([CrossFadeIn(0.5)])

    x_pos = (config.VIDEO_WIDTH  - ss_img.width)  // 2
    y_pos = int(config.VIDEO_HEIGHT * config.SCREENSHOT_Y_RATIO)
    ss_clip = ss_clip.with_position((x_pos, y_pos))

    # 5) 合成・書き出し
    final = CompositeVideoClip([bg_clip, ss_clip],
                                size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))
    final = final.with_duration(duration)

    output_path = os.path.join(config.OUTPUT_DIR, "DEMO_tiktok.mp4")
    print(f"動画を生成中... (15秒, 1080x1920)")
    final.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio=False,
        preset="fast",
        ffmpeg_params=["-crf", "28"],
        logger="bar",
    )
    print(f"\n完成! → {output_path}")
    return output_path


if __name__ == "__main__":
    make_demo()
