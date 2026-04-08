"""
card_generator.py - X(Twitter)風の投稿カード画像を生成
"""
import textwrap
from PIL import Image, ImageDraw, ImageFont
import os

# カードサイズ
CARD_WIDTH = 900
PADDING = 48
FONT_SIZE_TEXT = 36
FONT_SIZE_META = 26
LINE_SPACING = 1.5
MAX_CHARS_PER_LINE = 22

# X ダークモードカラー
BG_COLOR       = (0, 0, 0)           # 黒背景
CARD_COLOR     = (21, 32, 43)        # X dark blue-gray
TEXT_COLOR     = (231, 233, 234)     # ほぼ白
META_COLOR     = (113, 118, 123)     # グレー
BORDER_COLOR   = (47, 51, 54)        # 境界線
X_LOGO_COLOR   = (231, 233, 234)     # ロゴ色


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """日本語対応フォントを取得"""
    candidates = [
        r"C:\Windows\Fonts\YuGothM.ttc",   # 游ゴシック Medium
        r"C:\Windows\Fonts\YuGothB.ttc",   # 游ゴシック Bold
        r"C:\Windows\Fonts\meiryo.ttc",    # メイリオ
        r"C:\Windows\Fonts\msgothic.ttc",  # MSゴシック
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_x_logo(draw: ImageDraw.Draw, x: int, y: int, size: int):
    """X ロゴを手描き（太い × 記号）"""
    lw = max(3, size // 8)
    draw.line([(x, y), (x + size, y + size)], fill=X_LOGO_COLOR, width=lw)
    draw.line([(x + size, y), (x, y + size)], fill=X_LOGO_COLOR, width=lw)


def _wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    """テキストを幅に合わせて折り返す"""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = list(paragraph)  # 日本語は1文字ずつ
        current = ""
        for char in words:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] > max_width:
                if current:
                    lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
    return lines


def generate_card(text: str, save_path: str) -> str:
    """
    X風カード画像を生成して save_path に保存
    戻り値: save_path
    """
    font_text = _get_font(FONT_SIZE_TEXT)
    font_meta = _get_font(FONT_SIZE_META)

    # 一時的なdrawオブジェクトでテキスト折り返し計算
    tmp = Image.new("RGB", (CARD_WIDTH, 100))
    tmp_draw = ImageDraw.Draw(tmp)

    text_max_w = CARD_WIDTH - PADDING * 2
    lines = _wrap_text(text[:300], font_text, text_max_w, tmp_draw)

    # 行の高さを計算
    bbox = tmp_draw.textbbox((0, 0), "あ", font=font_text)
    line_h = int((bbox[3] - bbox[1]) * LINE_SPACING)

    # カードの高さを計算（アイコン・いいねボタンなし）
    card_h = PADDING + line_h * len(lines) + PADDING

    # カード生成
    img = Image.new("RGB", (CARD_WIDTH, card_h), CARD_COLOR)
    draw = ImageDraw.Draw(img)

    # 本文のみ
    text_y = PADDING
    for line in lines:
        draw.text((PADDING, text_y), line, font=font_text, fill=TEXT_COLOR)
        text_y += line_h

    # 角丸マスク
    from PIL import Image as PILImage
    mask = PILImage.new("L", img.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=24, fill=255)
    img_rgba = img.convert("RGBA")
    img_rgba.putalpha(mask)

    img_rgba.save(save_path, "PNG")
    return save_path


if __name__ == "__main__":
    # テスト
    sample = (
        "かなり長く付き合って別れた方たちで振った側の気持ちを知りたいです。\n"
        "色々と理由はあると思いますが、後悔とか復縁したいとか、\n"
        "この人が1番だったなとか思うことありますか？"
    )
    generate_card(sample, "test_card.png")
    print("test_card.png を生成しました")
