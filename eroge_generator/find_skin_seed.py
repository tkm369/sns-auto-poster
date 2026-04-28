"""
肌色が良いシードを探す。
state_0 を3回ランダム生成して候補を並べて保存。
良いものが見つかったらそのシードで全state再生成。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sd_rpg_strip import _noob_positive, _generate_char, CHAR_NEGATIVE

OUT = Path(r"C:\Users\inoue\Desktop\ai-project\eroge_generator\skin_test")
OUT.mkdir(exist_ok=True)

APPEARANCE = (
    "very long straight black hair down to waist, blue-grey eyes, large innocent eyes, "
    "tan skin, warm skin tone, peach skin, light brown skin, healthy skin color, "
    "large breasts, petite slim figure, beautiful face, cute face"
)

NEG = (
    CHAR_NEGATIVE + ", "
    "pale skin, white skin, paper white skin, grey skin, overly pale, "
    "porcelain skin, white body, colorless skin, cold skin"
)

CLOTHING = "white bra, white panties, bare legs, topless adjacent, underwear only, half undressed"
EXPRESSION = "extremely embarrassed, red face, deeply blushing, teary eyes, eyes closed"
BODY = "standing, covering chest with arms, cowering"

positive = (
    f"1girl, solo, {APPEARANCE}, "
    f"{CLOTHING}, "
    f"{EXPRESSION}, {BODY}, "
    f"highly detailed face, detailed eyes, shiny hair, "
    f"soft lighting, white background, simple background, "
    f"cowboy shot, upper body focus, filling frame, anime style"
)

from sd_client import txt2img, is_available, auto_start as sd_auto_start
from sd_rpg_strip import CHAR_W, CHAR_H

def log(msg): print(msg, flush=True)

if not is_available():
    log("SD Forge 起動中...")
    sd_auto_start(log=log)

seeds_used = []
pos = _noob_positive(positive)

for i in range(3):
    log(f"\n候補{i+1} 生成中...")
    png, seed = txt2img(
        pos, NEG,
        width=CHAR_W, height=CHAR_H,
        steps=28, cfg=6.0,
        seed=-1,
        hires=True,
        use_adetailer=True,
        sampler_override="Euler a",
    )
    out = OUT / f"candidate_{i+1}_seed{seed}.png"
    out.write_bytes(png)
    seeds_used.append(seed)
    log(f"  保存: {out.name}")

log(f"\n=== 候補3枚生成完了 ===")
log(f"保存先: {OUT}")
log(f"シード: {seeds_used}")
log(f"\n気に入った候補のシードをメモして教えてください。")
log(f"そのシードで全state+Hシーンを統一生成します。")
