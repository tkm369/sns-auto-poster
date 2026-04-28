"""
催眠調教セラピー風キャラ生成。
参照: body_export_idle1 のアートスタイル
  - 黒髪ストレート・ぱっつん前髪
  - 紫/青の目
  - 極巨乳（セーターがはだけるスタイル）
  - 白背景（立ち絵）
  - ダーク背景（Hシーン）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sd_rpg_strip import _noob_positive, CHAR_NEGATIVE, H_NEGATIVE, CHAR_W, CHAR_H, SCENE_W, SCENE_H
from sd_client import is_available, auto_start as sd_auto_start, txt2img, img2img

PROJECT  = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")
CHAR_DIR = PROJECT / "assets" / "characters"
H_DIR    = PROJECT / "assets" / "h_scenes"
CHAR_DIR.mkdir(parents=True, exist_ok=True)
H_DIR.mkdir(parents=True, exist_ok=True)

FIXED_SEED = 2847391056

# ── キャラ外見（セラピーゲーム風） ────────────────────────────────────
APPEARANCE = (
    "1girl, solo, "
    "very long straight black hair, blunt bangs, hair past waist, "
    "purple eyes, large innocent eyes, red lips, "
    "huge breasts, hyper breasts, massive breasts, large areolae, "
    "light skin, fair skin, slightly tan skin, "
    "beautiful face, mature face, adult woman, elegant, "
    "slim waist, wide hips, hourglass figure"
)

# ── ネガティブ ──────────────────────────────────────────────────────
NEG_BASE = (
    CHAR_NEGATIVE + ", "
    "small breasts, flat chest, loli, young, teenager, childlike, "
    "multiple girls, 2girls, bad anatomy, extra limbs, "
    "ugly, deformed, malformed"
)

NEG_H = (
    H_NEGATIVE + ", "
    "small breasts, flat chest, loli, young, "
    "2girls, multiple girls, clone, mirror, "
    "bad anatomy, extra limbs, ugly, deformed"
)

# ── 立ち絵ステート定義 ────────────────────────────────────────────────
STATES = [
    # state_0: 完全着衣（白セーター + 黒スカート + パンスト）
    {
        "clothing": (
            "white turtleneck sweater, black tight skirt, black pantyhose, "
            "fully clothed, elegant office lady outfit"
        ),
        "expression": "slight smile, calm, composed, looking at viewer",
        "pose": "standing straight, arms at sides, cowboy shot, white background, simple background",
        "label": "着衣",
    },
    # state_1: セーター肩からずり落ち（胸の上部が見える）
    {
        "clothing": (
            "white sweater falling off shoulders, off-shoulder sweater, "
            "sweater pulled down slightly, top of breasts visible, "
            "black tight skirt, black pantyhose"
        ),
        "expression": "slightly surprised, light blush, looking at viewer",
        "pose": "standing, one hand holding sweater, cowboy shot, white background",
        "label": "セーターずれ",
    },
    # state_2: セーターが下にずり落ち（胸が大きく露出）
    {
        "clothing": (
            "white sweater pulled down below breasts, breasts exposed, bare breasts, "
            "sweater bunched at waist, black tight skirt, black pantyhose, "
            "nipples visible"
        ),
        "expression": "blushing, embarrassed, flushed cheeks, lips parted",
        "pose": "standing, arms slightly raised, cowboy shot, white background",
        "label": "胸露出",
    },
    # state_3: スカートも下に（下着が見える）
    {
        "clothing": (
            "white sweater bunched at waist, bare breasts, nipples, "
            "black skirt pulled down, white panties visible, black pantyhose rolled down"
        ),
        "expression": "deeply blushing, teary eyes, looking down, ashamed",
        "pose": "standing, trying to cover, cowboy shot, white background",
        "label": "スカート落ち",
    },
    # state_4: ブラ＆パンツのみ
    {
        "clothing": (
            "no sweater, no skirt, white bra, white panties, "
            "black pantyhose, semi-undressed, underwear only"
        ),
        "expression": "extremely embarrassed, red face, crying tears",
        "pose": "standing, arms covering chest partially, cowboy shot, white background",
        "label": "下着のみ",
    },
    # state_5: パンツのみ（上は全裸）
    {
        "clothing": (
            "topless, bare chest, bare breasts, nipples, huge exposed breasts, "
            "white panties, black pantyhose, no bra"
        ),
        "expression": "mortified, streams of tears, deeply flushed, trembling",
        "pose": "standing, both arms attempting to cover breasts, cowboy shot, white background",
        "label": "トップレス",
    },
    # state_6: 全裸
    {
        "clothing": (
            "completely nude, naked, no clothes, bare skin everywhere, "
            "huge bare breasts, nipples, exposed pussy, "
            "slight tan line"
        ),
        "expression": "ahegao light, deeply blushing, teary, mouth slightly open, tongue out slightly",
        "pose": "standing, one arm raised, leaning slightly, cowboy shot, white background",
        "label": "全裸",
    },
]

def log(msg): print(msg, flush=True)

def build_pos(state: dict) -> str:
    raw = (
        f"{APPEARANCE}, "
        f"{state['clothing']}, "
        f"{state['expression']}, "
        f"{state['pose']}, "
        "highly detailed, masterpiece, best quality, "
        "anime style, thick outlines, clean lineart, "
        "detailed eyes, shiny hair, smooth skin, soft shading"
    )
    return _noob_positive(raw)

def main():
    if not is_available():
        log("SD Forge 起動確認中...")
        sd_auto_start(log=log)

    log("=== セラピー風キャラ生成 ===")

    # ── state_0: txt2img でベースキャラ確立 ─────────────────────────
    log(f"\n[state_0] txt2img 基準生成 seed={FIXED_SEED}...")
    pos0 = build_pos(STATES[0])
    png0, seed0 = txt2img(
        pos0, NEG_BASE,
        width=CHAR_W, height=CHAR_H,
        steps=30, cfg=6.5, seed=FIXED_SEED,
        hires=True, use_adetailer=True,
        sampler_override="Euler a"
    )
    (CHAR_DIR / "state_0.png").write_bytes(png0)
    log(f"  seed={seed0} -> state_0.png 保存")

    # ── state_1〜6: img2img でキャラ統一 ────────────────────────────
    # denoise: 服が少なくなるほど変化を許容する
    denoise_map = {1: 0.50, 2: 0.55, 3: 0.58, 4: 0.60, 5: 0.63, 6: 0.65}
    base_png = png0

    for i in range(1, 7):
        s = STATES[i]
        strength = denoise_map[i]
        log(f"\n[state_{i}] img2img ({s['label']}) strength={strength}...")
        pos = build_pos(s)
        png, used = img2img(
            pos, NEG_BASE, base_png,
            denoising_strength=strength,
            width=CHAR_W, height=CHAR_H,
            steps=30, cfg=6.5, seed=seed0,
            use_adetailer=True
        )
        (CHAR_DIR / f"state_{i}.png").write_bytes(png)
        log(f"  seed={used} -> state_{i}.png 保存")
        # 次のステートは1つ前の画像を参照（連続した変化）
        if i <= 4:
            base_png = png

    # ── パイズリシーン ────────────────────────────────────────────────
    log("\n[paizuri] Hシーン生成...")
    paizuri_pos = _noob_positive(
        f"{APPEARANCE}, "
        "nsfw, explicit, nude, paizuri, titjob, breasts around penis, penis between breasts, "
        "huge breasts, hyper breasts, breast squeeze, "
        "looking up at viewer, from below angle, pov, "
        "ahegao, tongue out, saliva, half-lidded eyes, blushing, "
        "kneeling, on knees, "
        "dark background, purple background, dramatic lighting, "
        "highly detailed, masterpiece, anime style, thick outlines"
    )
    png_p, used_p = txt2img(
        paizuri_pos, NEG_H,
        width=SCENE_W, height=SCENE_H,
        steps=32, cfg=7.0, seed=-1,
        hires=True, use_adetailer=True,
        sampler_override="Euler a"
    )
    (H_DIR / "fellatio.png").write_bytes(png_p)
    log(f"  seed={used_p} -> fellatio.png 保存")

    # ── セックスシーン ────────────────────────────────────────────────
    log("\n[sex] Hシーン生成...")
    sex_pos = _noob_positive(
        f"{APPEARANCE}, "
        "nsfw, explicit, nude, hetero sex, vaginal intercourse, "
        "missionary position, lying on back, legs spread, legs raised, "
        "pov, from above, looking up at viewer, "
        "penis, penetration, insertion visible, penis inside vagina, "
        "ahegao, ecstasy, moaning, eyes rolling back, mouth open wide, drooling, "
        "huge breasts bouncing, nipples hard, "
        "dark background, clinic room, soft lighting, "
        "highly detailed, masterpiece, anime style, thick outlines"
    )
    png_s, used_s = txt2img(
        sex_pos, NEG_H,
        width=SCENE_W, height=SCENE_H,
        steps=32, cfg=7.0, seed=-1,
        hires=True, use_adetailer=True,
        sampler_override="Euler a"
    )
    (H_DIR / "sex.png").write_bytes(png_s)
    log(f"  seed={used_s} -> sex.png 保存")

    log("\n=== 全完了 ===")
    log(f"キャラ: {CHAR_DIR}")
    log(f"Hシーン: {H_DIR}")
    log("\n次: Godotでゲームを起動してください")

if __name__ == "__main__":
    main()
