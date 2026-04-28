"""state_0.png のみ固定シードで再生成"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sd_rpg_strip import _noob_positive, _generate_char, CHAR_NEGATIVE

PROJECT_DIR = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")
FIXED_SEED  = 2112473829

appearance = "very long straight black hair down to waist, blue-grey eyes, large innocent eyes, fair white skin, large breasts, petite slim figure, beautiful face, cute face"

positive = (
    f"1girl, solo, {appearance}, "
    f"fully clothed, school uniform, blazer, white shirt, pleated skirt, white knee socks, "
    f"slight smile, looking at viewer, calm, composed, "
    f"standing, upper body, arms at sides, "
    f"highly detailed face, detailed eyes, shiny hair, "
    f"smooth skin, soft lighting, "
    f"white background, simple background, "
    f"cowboy shot, from waist up, upper body focus, "
    f"close-up portrait, large character, filling frame, "
    f"anime style"
)

def log(msg): print(msg, flush=True)

log(f"state_0.png 再生成 (seed={FIXED_SEED})...")
png, used_seed = _generate_char(positive, log=log, seed=FIXED_SEED)
out = PROJECT_DIR / "assets" / "characters" / "state_0.png"
out.write_bytes(png)
log(f"完了 -> {out}  seed={used_seed}")
