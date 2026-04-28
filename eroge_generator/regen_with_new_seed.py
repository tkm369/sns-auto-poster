"""
選んだシード(4069829107)で全画像を統一生成。
立ち絵7枚 + Hシーン2枚。
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sd_rpg_strip import _noob_positive, _generate_char, _generate_scene, CHAR_NEGATIVE, H_NEGATIVE, CHAR_W, CHAR_H, SCENE_W, SCENE_H
from sd_client import is_available, auto_start as sd_auto_start, txt2img

PROJECT = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")
CHAR_DIR = PROJECT / "assets" / "characters"
H_DIR    = PROJECT / "assets" / "h_scenes"

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

H_NEG_STRICT = (
    H_NEGATIVE + ", "
    "pale skin, white skin, paper white skin, "
    "2girls, multiple girls, two girls, multiple characters, mirror, clone"
)

STATES = [
    {"clothing": "fully clothed, school uniform, blazer, white shirt, pleated skirt, white knee socks",
     "expression": "slight smile, looking at viewer, calm, composed",
     "body": "standing, upper body, arms at sides", "label": "着衣"},
    {"clothing": "removed blazer, white shirt, pleated skirt, white knee socks, no blazer",
     "expression": "surprised expression, light blush, looking away",
     "body": "standing, upper body, arms crossed over chest", "label": "ブレザーなし"},
    {"clothing": "white dress shirt, pleated skirt, white knee socks, shirt partially unbuttoned",
     "expression": "blushing, embarrassed, flushed cheeks, looking down",
     "body": "standing, upper body, hands nervously on shirt", "label": "シャツ緩め"},
    {"clothing": "white bra visible, pleated skirt, white knee socks, unbuttoned shirt hanging open",
     "expression": "deeply blushing, teary eyes, covering face with hands",
     "body": "standing, upper body, leaning slightly forward", "label": "ブラ見え"},
    {"clothing": "white bra, white panties, white knee socks, no skirt, half undressed",
     "expression": "extremely embarrassed, red face, crying tears, eyes closed",
     "body": "standing, covering chest with arms, cowering slightly", "label": "ブラ＆パンツ"},
    {"clothing": "white panties only, topless, bare chest, bare breasts, white knee socks",
     "expression": "mortified expression, streams of tears, deeply flushed cheeks",
     "body": "standing, both arms covering breasts, hunching over", "label": "パンツのみ"},
    {"clothing": "completely nude, naked, no clothes, no underwear, bare skin",
     "expression": "ahegao light, deeply blushing, teary eyes, mouth slightly open",
     "body": "standing, one arm covering breasts, other hand covering groin, trembling", "label": "全裸"},
]

def log(msg): print(msg, flush=True)

def main():
    if not is_available():
        log("SD Forge 起動確認中...")
        auto_start(log=log)

    log(f"=== 全画像再生成 seed={FIXED_SEED} ===")

    # ── 立ち絵 state_0〜6 ─────────────────────────────────────────
    for i, s in enumerate(STATES):
        positive = (
            f"1girl, solo, {APPEARANCE}, "
            f"{s['clothing']}, {s['expression']}, {s['body']}, "
            f"highly detailed face, detailed eyes, shiny hair, "
            f"smooth skin, soft lighting, "
            f"white background, simple background, "
            f"cowboy shot, upper body focus, filling frame, anime style"
        )
        log(f"\nstate_{i}.png 生成中 ({s['label']})...")
        pos = _noob_positive(positive)
        png, used = txt2img(pos, SKIN_NEG, width=CHAR_W, height=CHAR_H,
                            steps=28, cfg=6.0, seed=FIXED_SEED,
                            hires=True, use_adetailer=True, sampler_override="Euler a")
        log(f"  seed={used}")
        (CHAR_DIR / f"state_{i}.png").write_bytes(png)
        log(f"  -> state_{i}.png 保存")

    # ── フェラチオシーン ──────────────────────────────────────────
    log("\nfellatio.png 生成中...")
    fell_pos = _noob_positive(
        f"1girl, solo, {APPEARANCE}, "
        f"nsfw, explicit, nude, fellatio, blowjob, oral, penis, penis in mouth, sucking penis, "
        f"close-up, upper body, face and penis both visible, from the side, side view, "
        f"kneeling, on knees, ahegao, tongue out, saliva dripping, half-lidded eyes, blushing, "
        f"beautiful detailed face, anime style, perfect anatomy, warm lighting, indoor, classroom"
    )
    png, used = txt2img(fell_pos, H_NEG_STRICT, width=SCENE_W, height=SCENE_H,
                        steps=30, cfg=6.0, seed=-1,
                        hires=True, use_adetailer=True, sampler_override="Euler a")
    log(f"  seed={used}")
    (H_DIR / "fellatio.png").write_bytes(png)
    log("  -> fellatio.png 保存")

    # ── セックスシーン ────────────────────────────────────────────
    log("\nsex.png 生成中...")
    sex_pos = _noob_positive(
        f"1girl, solo focus, {APPEARANCE}, "
        f"nsfw, explicit, nude, hetero sex, vaginal intercourse, penis, penetration, "
        f"missionary position, lying on back, legs raised, pov, from above, looking up at viewer, "
        f"insertion visible, penis inside vagina, "
        f"ahegao, ecstasy, moaning, eyes rolling back, mouth open, "
        f"upper body focus, face and chest visible, beautiful detailed face, "
        f"perfect anatomy, anime style, classroom desk, indoor, warm lighting"
    )
    png, used = txt2img(sex_pos, H_NEG_STRICT, width=SCENE_W, height=SCENE_H,
                        steps=30, cfg=6.0, seed=-1,
                        hires=True, use_adetailer=True, sampler_override="Euler a")
    log(f"  seed={used}")
    (H_DIR / "sex.png").write_bytes(png)
    log("  -> sex.png 保存")

    log("\n=== 全完了 ===")

if __name__ == "__main__":
    main()
