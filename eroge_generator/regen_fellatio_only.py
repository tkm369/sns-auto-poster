"""fellatio.png のみ再生成"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sd_rpg_strip import _noob_positive, _generate_scene, H_NEGATIVE

PROJECT_DIR = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")

appearance = "very long straight black hair down to waist, blue-grey eyes, large innocent eyes, fair skin, natural skin tone, large breasts, petite slim figure, beautiful face, cute face"

h_neg_strict = (
    H_NEGATIVE + ", "
    "2girls, multiple girls, two girls, multiple characters, "
    "multiple people, group, mirror, reflection, clone, duplicate"
)

positive = (
    f"1girl, solo, {appearance}, "
    f"nsfw, explicit, rating:explicit, nude, "
    f"fellatio, blowjob, oral, penis, penis in mouth, sucking penis, "
    f"close-up, upper body, face and penis both visible, "
    f"from the side, side view, "
    f"kneeling, on knees, sitting on floor, "
    f"ahegao, tongue out, saliva dripping, half-lidded eyes, blushing, "
    f"beautiful detailed face, "
    f"anime style, perfect anatomy, "
    f"warm lighting, indoor, classroom"
)

from sd_rpg_strip import SCENE_W, SCENE_H
from sd_client import txt2img

def log(msg): print(msg, flush=True)

pos = _noob_positive(positive)
log("fellatio.png 再生成中...")
png, seed = txt2img(
    pos, h_neg_strict,
    width=SCENE_W, height=SCENE_H,
    steps=30, cfg=6.0,
    seed=-1,
    hires=True,
    use_adetailer=True,
    sampler_override="Euler a",
)
log(f"    seed={seed}")
out = PROJECT_DIR / "assets" / "h_scenes" / "fellatio.png"
out.write_bytes(png)
log(f"完了 -> {out}")
