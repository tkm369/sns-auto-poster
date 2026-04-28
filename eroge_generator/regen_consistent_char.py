"""
img2imgでキャラを統一する。
1. state_0 を txt2img で生成（基準キャラ確立）
2. state_1〜6 は state_0 を元画像にして img2img → 顔・体型を維持しつつ服だけ変える
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sd_rpg_strip import _noob_positive, CHAR_NEGATIVE, CHAR_W, CHAR_H
from sd_client import is_available, auto_start as sd_auto_start, txt2img, img2img

PROJECT  = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")
CHAR_DIR = PROJECT / "assets" / "characters"

FIXED_SEED = 4069829107

APPEARANCE = (
    "very long straight black hair down to waist, blue-grey eyes, large innocent eyes, "
    "tan skin, warm skin tone, peach skin, light brown skin, healthy skin color, "
    "large breasts, petite slim figure, beautiful face, cute face"
)

SKIN_NEG = (
    CHAR_NEGATIVE + ", "
    "pale skin, white skin, paper white skin, grey skin, overly pale, "
    "porcelain skin, white body, colorless skin, cold skin"
)

# 全stateで共通の構図（これを固定することでキャラが揃う）
COMMON_COMPOSITION = (
    "standing straight, facing viewer, arms slightly at sides, "
    "cowboy shot, from waist up, centered, white background, simple background, "
    "highly detailed face, detailed eyes, shiny hair, smooth skin, soft lighting, "
    "anime style, filling frame"
)

STATES = [
    {"clothing": "fully clothed, school uniform, navy blazer, white shirt, red ribbon, grey pleated skirt, white knee socks",
     "expression": "slight smile, looking at viewer, calm, composed", "label": "着衣"},
    {"clothing": "no blazer, white shirt, red ribbon, grey pleated skirt, white knee socks",
     "expression": "surprised expression, light blush, looking at viewer slightly away", "label": "ブレザーなし"},
    {"clothing": "white dress shirt partially unbuttoned, grey pleated skirt, white knee socks, shirt open at collar",
     "expression": "blushing, embarrassed, flushed cheeks, looking down", "label": "シャツ緩め"},
    {"clothing": "white bra visible, grey pleated skirt, white knee socks, unbuttoned shirt hanging open",
     "expression": "deeply blushing, teary eyes, trying to cover chest", "label": "ブラ見え"},
    {"clothing": "white bra, white panties, white knee socks, no skirt, no shirt",
     "expression": "extremely embarrassed, red face, crying tears, eyes closed tight",
     "label": "ブラ＆パンツ"},
    {"clothing": "white panties only, topless, bare chest, bare breasts exposed, white knee socks",
     "expression": "mortified, streams of tears, deeply flushed, looking down in shame",
     "label": "パンツのみ"},
    {"clothing": "completely nude, naked, no clothes, bare skin everywhere",
     "expression": "ahegao light, deeply blushing, teary eyes, mouth slightly open",
     "label": "全裸"},
]

def log(msg): print(msg, flush=True)

def build_positive(state: dict) -> str:
    return _noob_positive(
        f"1girl, solo, {APPEARANCE}, "
        f"{state['clothing']}, {state['expression']}, "
        f"{COMMON_COMPOSITION}"
    )

def main():
    if not is_available():
        log("SD Forge 起動確認中...")
        sd_auto_start(log=log)

    log("=== img2img によるキャラ統一生成 ===")

    # ── state_0: txt2img で基準キャラを確立 ─────────────────────────
    log(f"\n[state_0] txt2img 生成中（基準キャラ）seed={FIXED_SEED}...")
    pos0 = build_positive(STATES[0])
    png0, seed0 = txt2img(pos0, SKIN_NEG, width=CHAR_W, height=CHAR_H,
                          steps=28, cfg=6.0, seed=FIXED_SEED,
                          hires=True, use_adetailer=True, sampler_override="Euler a")
    log(f"  seed={seed0}")
    out0 = CHAR_DIR / "state_0.png"
    out0.write_bytes(png0)
    log(f"  -> state_0.png 保存")

    # ── state_1〜6: state_0 を元に img2img ───────────────────────────
    base_image = png0  # 基準画像（state_0）

    for i in range(1, 7):
        s = STATES[i]
        log(f"\n[state_{i}] img2img 生成中（{s['label']}）...")
        pos = build_positive(s)

        # denoising_strength: 0.5=服変え最小限, 0.65=表情も変える
        strength = 0.50 if i <= 2 else 0.58 if i <= 4 else 0.63

        png, used = img2img(pos, SKIN_NEG, base_image,
                            denoising_strength=strength,
                            width=CHAR_W, height=CHAR_H,
                            steps=28, cfg=6.0, seed=seed0,
                            use_adetailer=True)
        log(f"  seed={used}  strength={strength}")
        out = CHAR_DIR / f"state_{i}.png"
        out.write_bytes(png)
        log(f"  -> state_{i}.png 保存")

    log("\n=== 完了 ===")
    log("次: split_layers.py を実行してレイヤーを更新してください")

if __name__ == "__main__":
    main()
