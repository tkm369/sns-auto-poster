"""
占い・スピリチュアル系フォーチュンカード画像を生成する
Pillowを使用して1080x1080のグラジエント画像を生成
"""
import os
import textwrap
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

SIZE = 1080

COLOR_TOP = (60, 10, 100)       # 深い紫
COLOR_BOTTOM = (180, 40, 110)   # ピンク紫
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (255, 215, 90)   # 金色

FONT_PATHS = [
    # Ubuntu / GitHub Actions
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    # Windows
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    "C:/Windows/Fonts/YuGothM.ttc",
]


def _get_font(size):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _make_gradient():
    img = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(img)
    for y in range(SIZE):
        ratio = y / SIZE
        r = int(COLOR_TOP[0] + (COLOR_BOTTOM[0] - COLOR_TOP[0]) * ratio)
        g = int(COLOR_TOP[1] + (COLOR_BOTTOM[1] - COLOR_TOP[1]) * ratio)
        b = int(COLOR_TOP[2] + (COLOR_BOTTOM[2] - COLOR_TOP[2]) * ratio)
        draw.line([(0, y), (SIZE, y)], fill=(r, g, b))
    return img


def _draw_decorations(draw):
    """星・装飾ラインを描く"""
    import random
    random.seed(42)
    for _ in range(40):
        x = random.randint(0, SIZE)
        y = random.randint(0, SIZE)
        r = random.randint(1, 3)
        alpha = random.randint(80, 200)
        c = (255, 255, 255)
        # RGBモードなのでアルファはブレンドで代用
        blend = tuple(int(cv * alpha / 255 + gc * (1 - alpha / 255))
                      for cv, gc in zip(c, (60, 10, 100)))
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=c)

    # 区切りライン
    lw = 2
    draw.line([(SIZE * 0.1, SIZE * 0.22), (SIZE * 0.9, SIZE * 0.22)],
              fill=ACCENT_COLOR, width=lw)
    draw.line([(SIZE * 0.1, SIZE * 0.78), (SIZE * 0.9, SIZE * 0.78)],
              fill=ACCENT_COLOR, width=lw)


def _extract_hook(post_text):
    """投稿の最初の非ハッシュタグ行を取得"""
    for line in post_text.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            return line
    return post_text.strip().split('\n')[0]


def _draw_text_centered(draw, text, font, y, color, shadow_color=(20, 5, 40)):
    """影付きセンタリングテキスト描画"""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw, _ = draw.textsize(text, font=font)
    x = (SIZE - tw) / 2
    draw.text((x + 3, y + 3), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=color)


def create_fortune_image(post_text, output_path):
    """
    フォーチュンカード画像を生成して保存する
    Args:
        post_text: 投稿テキスト
        output_path: 保存先パス (.png)
    """
    img = _make_gradient()
    draw = ImageDraw.Draw(img)

    _draw_decorations(draw)

    # ヘッダー
    header_font = _get_font(34)
    _draw_text_centered(draw, "✨  今日のスピリチュアルメッセージ  ✨",
                        header_font, SIZE * 0.25, ACCENT_COLOR)

    # メインフック（最初の1行）
    hook = _extract_hook(post_text)
    if len(hook) > 28:
        hook = hook[:26] + "…"

    hook_font = _get_font(64)
    wrapped = textwrap.wrap(hook, width=15)
    line_h = 82
    total_h = len(wrapped) * line_h
    y_start = (SIZE - total_h) / 2 - 10

    for i, line in enumerate(wrapped):
        _draw_text_centered(draw, line, hook_font, y_start + i * line_h, TEXT_COLOR)

    # フッター装飾
    sub_font = _get_font(32)
    _draw_text_centered(draw, "★  あなたへのメッセージ  ★",
                        sub_font, SIZE * 0.80, ACCENT_COLOR)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    return output_path


def cleanup_old_images(images_dir, keep_days=7):
    """指定日数より古い画像を削除"""
    if not os.path.exists(images_dir):
        return
    cutoff = datetime.now() - timedelta(days=keep_days)
    deleted = 0
    for filename in os.listdir(images_dir):
        if not filename.endswith('.png'):
            continue
        try:
            ts = datetime.strptime(filename[:15], "%Y%m%d_%H%M%S")
            if ts < cutoff:
                os.remove(os.path.join(images_dir, filename))
                deleted += 1
        except ValueError:
            pass
    if deleted:
        print(f"  古い画像を{deleted}件削除しました")
