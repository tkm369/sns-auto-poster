"""
AK-47 | 桜嵐 - テクスチャ生成スクリプト
Pillow を使ってベースのカラーマップ PNG を生成します。

使い方:
    pip install Pillow
    python generate_texture.py

出力: textures/ak47_col.png (2048x2048)
"""

import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


OUTPUT_DIR = Path("textures")
OUTPUT_DIR.mkdir(exist_ok=True)

WIDTH, HEIGHT = 2048, 2048

# カラーパレット
COLOR_BASE_DARK  = (26, 31, 60)      # 深紺 #1A1F3C
COLOR_BASE_MID   = (46, 53, 96)      # 中紺 #2E3560
COLOR_SAKURA     = (244, 184, 200)   # 淡ピンク #F4B8C8
COLOR_SAKURA_SHD = (212, 116, 138)   # 濃いピンク #D4748A
COLOR_BRANCH     = (92, 51, 23)      # 焦げ茶 #5C3317
COLOR_GOLD       = (184, 150, 12)    # 金 #B8960C
COLOR_WHITE      = (240, 237, 232)   # 白 #F0EDE8


def lerp_color(c1, c2, t):
    """2色の線形補間"""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_base_gradient(img: Image.Image):
    """ベースグラデーション（左=深紺、右=中紺）"""
    draw = ImageDraw.Draw(img)
    for x in range(WIDTH):
        t = x / WIDTH
        color = lerp_color(COLOR_BASE_DARK, COLOR_BASE_MID, t)
        draw.line([(x, 0), (x, HEIGHT)], fill=color)


def draw_seigaiha(img: Image.Image, alpha: int = 40):
    """青海波パターン（半透明オーバーレイ）"""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    scale = 60  # 波のサイズ
    for row in range(-1, HEIGHT // (scale // 2) + 2):
        for col in range(-1, WIDTH // scale + 2):
            x = col * scale + (scale // 2 if row % 2 else 0)
            y = row * (scale // 2)
            # 外側の弧
            draw.ellipse(
                [x - scale // 2, y - scale // 2, x + scale // 2, y + scale // 2],
                outline=(*COLOR_GOLD, alpha),
                width=1,
            )

    img.paste(overlay, mask=overlay.split()[3])


def draw_branch(img: Image.Image):
    """桜の木の枝シルエット（右側面）"""
    draw = ImageDraw.Draw(img)

    # メインの幹
    trunk_points = [
        (1600, HEIGHT), (1580, 1600), (1540, 1200),
        (1500, 900), (1480, 600), (1460, 300),
    ]
    draw.line(trunk_points, fill=COLOR_BRANCH, width=18)

    # 枝1（右上方向）
    branch1 = [(1500, 900), (1600, 750), (1720, 680), (1820, 700)]
    draw.line(branch1, fill=COLOR_BRANCH, width=10)

    # 枝2（左方向）
    branch2 = [(1480, 600), (1380, 480), (1260, 440), (1160, 460)]
    draw.line(branch2, fill=COLOR_BRANCH, width=8)

    # 小枝
    small_branches = [
        [(1720, 680), (1760, 580), (1800, 520)],
        [(1600, 750), (1650, 640)],
        [(1380, 480), (1340, 380), (1300, 300)],
        [(1260, 440), (1220, 340)],
    ]
    for branch in small_branches:
        draw.line(branch, fill=COLOR_BRANCH, width=5)


def draw_sakura_petal(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                      size: int, rotation: float, color: tuple, alpha: int = 200):
    """桜の花びら1枚を描く（楕円で近似）"""
    # 5枚の楕円で桜を表現
    petal_color = (*color, alpha)
    for i in range(5):
        angle = rotation + i * (2 * math.pi / 5)
        px = cx + int(math.cos(angle) * size * 0.6)
        py = cy + int(math.sin(angle) * size * 0.6)
        draw.ellipse(
            [px - size // 2, py - size // 3,
             px + size // 2, py + size // 3],
            fill=petal_color,
        )


def draw_scattered_petals(img: Image.Image):
    """花びらを散らす"""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    rng = random.Random(42)  # 再現性のある乱数

    # 大きめの花びら（30〜50枚）
    for _ in range(40):
        x = rng.randint(0, WIDTH)
        y = rng.randint(0, HEIGHT)
        size = rng.randint(30, 70)
        rot = rng.uniform(0, 2 * math.pi)
        alpha = rng.randint(150, 230)
        color = COLOR_SAKURA if rng.random() > 0.3 else COLOR_SAKURA_SHD
        draw_sakura_petal(draw, x, y, size, rot, color, alpha)

    # 小さな花びら（100〜150枚）
    for _ in range(120):
        x = rng.randint(0, WIDTH)
        y = rng.randint(0, HEIGHT)
        size = rng.randint(10, 28)
        rot = rng.uniform(0, 2 * math.pi)
        alpha = rng.randint(100, 180)
        color = COLOR_SAKURA if rng.random() > 0.4 else COLOR_SAKURA_SHD
        draw_sakura_petal(draw, x, y, size, rot, color, alpha)

    img.paste(overlay, mask=overlay.split()[3])


def draw_kamon(img: Image.Image, cx: int, cy: int, radius: int):
    """家紋風の桜円紋を描く"""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 外円
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        outline=(*COLOR_GOLD, 220),
        width=4,
    )

    # 内円
    inner_r = int(radius * 0.7)
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        outline=(*COLOR_GOLD, 180),
        width=2,
    )

    # 桜の花（5枚の花びら）
    petal_size = int(radius * 0.35)
    for i in range(5):
        angle = i * (2 * math.pi / 5) - math.pi / 2
        px = cx + int(math.cos(angle) * inner_r * 0.6)
        py = cy + int(math.sin(angle) * inner_r * 0.6)
        draw.ellipse(
            [px - petal_size // 2, py - petal_size // 2,
             px + petal_size // 2, py + petal_size // 2],
            fill=(*COLOR_SAKURA, 200),
            outline=(*COLOR_GOLD, 160),
            width=2,
        )

    # 中心の丸
    center_r = int(radius * 0.12)
    draw.ellipse(
        [cx - center_r, cy - center_r, cx + center_r, cy + center_r],
        fill=(*COLOR_GOLD, 220),
    )

    img.paste(overlay, mask=overlay.split()[3])


def draw_kasumi(img: Image.Image):
    """霞（かすみ）模様を描く"""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 横に流れる霞帯
    kasumi_positions = [300, 700, 1200, 1700]
    for y_center in kasumi_positions:
        for dy in range(-40, 41):
            alpha = int(30 * (1 - abs(dy) / 40))
            x_start = random.randint(-100, 200)
            x_end = WIDTH + random.randint(-200, 100)
            draw.line(
                [(x_start, y_center + dy), (x_end, y_center + dy)],
                fill=(*COLOR_WHITE, alpha),
                width=1,
            )

    # ガウスぼかし
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=8))
    img.paste(overlay, mask=overlay.split()[3])


def main():
    print("テクスチャ生成開始: AK-47 | 桜嵐")

    # ベース画像（RGBA）
    img = Image.new("RGBA", (WIDTH, HEIGHT), (*COLOR_BASE_DARK, 255))

    print("  [1/6] ベースグラデーション...")
    draw_base_gradient(img)

    print("  [2/6] 青海波パターン...")
    draw_seigaiha(img, alpha=35)

    print("  [3/6] 霞模様...")
    draw_kasumi(img)

    print("  [4/6] 桜の枝...")
    draw_branch(img)

    print("  [5/6] 花びら散らし...")
    draw_scattered_petals(img)

    print("  [6/6] 家紋（ストック中央）...")
    # ストック部分に配置（UV上の位置はモデルに依存するため概算）
    draw_kamon(img, cx=256, cy=1800, radius=120)

    # RGB に変換して保存
    out_path = OUTPUT_DIR / "ak47_col.png"
    img.convert("RGB").save(out_path)
    print(f"\n完了! 出力先: {out_path}")
    print(f"解像度: {WIDTH}x{HEIGHT}px")


if __name__ == "__main__":
    main()
