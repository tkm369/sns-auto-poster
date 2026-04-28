"""
split_layers.py
キャラクター画像を hair / body / skirt の3レイヤーに分割する。
各レイヤーは境界をフェードさせて透明にしてある。
ベース画像（full）と重ねることで隙間が出ない。
"""
from pathlib import Path
from PIL import Image
import numpy as np

PROJECT = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")
CHAR_DIR = PROJECT / "assets" / "characters"

# ── 境界の定義（UV比率）────────────────────────────────────────────
HAIR_END   = 0.34   # 上34%が髪メインゾーン
BODY_START = 0.22   # 体レイヤーの開始
BODY_END   = 0.72   # 体レイヤーの終了
SKIRT_START= 0.60   # スカートレイヤーの開始
FADE_PX    = 50     # フェード幅（ピクセル）

def remove_white_bg(arr: np.ndarray) -> np.ndarray:
    """白背景を透明化"""
    out = arr.copy()
    white = (out[:,:,0] > 235) & (out[:,:,1] > 235) & (out[:,:,2] > 235)
    out[white, 3] = 0
    return out

def make_layer(arr: np.ndarray, start_ratio: float, end_ratio: float) -> np.ndarray:
    """
    指定した縦範囲を切り出し、境界をフェードさせたレイヤーを返す。
    arr: RGBA numpy配列（白背景除去済み）
    """
    h = arr.shape[0]
    layer = arr.copy()

    start_px = int(h * start_ratio)
    end_px   = int(h * end_ratio)

    # 上部フェード（start_ratio より上は消す）
    if start_px > 0:
        # start_px - FADE_PX → start_px でフェードイン
        fade_top_start = max(0, start_px - FADE_PX)
        for y in range(0, fade_top_start):
            layer[y, :, 3] = 0
        for y in range(fade_top_start, start_px):
            alpha = (y - fade_top_start) / max(1, start_px - fade_top_start)
            layer[y, :, 3] = (layer[y, :, 3].astype(float) * alpha).astype(np.uint8)

    # 下部フェード（end_ratio より下は消す）
    if end_px < h:
        # end_px → end_px + FADE_PX でフェードアウト
        fade_bot_end = min(h, end_px + FADE_PX)
        for y in range(fade_bot_end, h):
            layer[y, :, 3] = 0
        for y in range(end_px, fade_bot_end):
            alpha = 1.0 - (y - end_px) / max(1, fade_bot_end - end_px)
            layer[y, :, 3] = (layer[y, :, 3].astype(float) * alpha).astype(np.uint8)

    return layer

def split_state(state: int) -> None:
    src = CHAR_DIR / f"state_{state}.png"
    if not src.exists():
        print(f"  skip: state_{state}.png not found")
        return

    img = Image.open(src).convert("RGBA")
    arr = np.array(img)
    arr = remove_white_bg(arr)

    # hair レイヤー（上部～HAIR_END、上端フェードなし）
    hair = make_layer(arr, 0.0, HAIR_END)
    Image.fromarray(hair).save(CHAR_DIR / f"state_{state}_hair.png")

    # body レイヤー（BODY_START～BODY_END）
    body = make_layer(arr, BODY_START, BODY_END)
    Image.fromarray(body).save(CHAR_DIR / f"state_{state}_body.png")

    # skirt レイヤー（SKIRT_START～下端、下端フェードなし）
    skirt = make_layer(arr, SKIRT_START, 1.0)
    Image.fromarray(skirt).save(CHAR_DIR / f"state_{state}_skirt.png")

    print(f"  state_{state}: hair / body / skirt 出力完了")

def main():
    print("=== キャラクターレイヤー分割 ===")
    for s in range(7):
        split_state(s)
    print("完了！")

if __name__ == "__main__":
    main()
