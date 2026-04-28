"""
sd_rpg_strip.py
野球拳スタイル脱衣カードゲーム向けのSD Forge画像生成モジュール
NoobAI XL epsilon pred に最適化済み
"""
import json
import urllib.request
from pathlib import Path
from sd_client import (
    txt2img, is_available, auto_start as sd_auto_start,
    COMMON_NEGATIVE, SPRITE_W, SPRITE_H,
)

# ── 画像サイズ ────────────────────────────────────────────────────
CHAR_W,  CHAR_H  = SPRITE_W, SPRITE_H  # 832×1216
SCENE_W, SCENE_H = 1216, 832           # Hシーン横長

# ── NoobAI XL 専用品質タグ ────────────────────────────────────────
# NoobAI は "very aesthetic / newest / amazing quality" が効く
NOOB_QUALITY = (
    "very aesthetic, amazing quality, newest, absurdres, highres, "
    "ultra-detailed, intricate details, sharp focus, "
    "beautiful detailed face, perfect anatomy, beautiful lighting"
)
NOOB_SCORE   = "score_9, score_8_up, score_7_up"

# キャラクター共通ネガティブ（NoobAI XL強化版）
CHAR_NEGATIVE = (
    "score_1, score_2, score_3, "
    "worst quality, low quality, normal quality, lowres, "
    "bad anatomy, bad hands, bad fingers, extra fingers, missing fingers, "
    "extra limbs, missing limbs, deformed hands, "
    "bad face, ugly face, asymmetrical eyes, cross-eyed, "
    "mutation, disfigured, malformed, "
    "text, watermark, signature, username, "
    "blurry, jpeg artifacts, "
    "multiple people, male, boy, man, "
    "3d, cgi, render, photo, realistic, "
    "multiple panels, comic, manga page, grid, 4koma, doujinshi page, "
    "split screen, multiple views, collage"
)

# Hシーン用ネガティブ
H_NEGATIVE = (
    CHAR_NEGATIVE + ", "
    "censored, mosaic censoring, bar censor, "
    "poorly drawn, rough sketch"
)


def _noob_positive(base: str) -> str:
    """NoobAI XL 用に品質タグを先頭付加"""
    return f"{NOOB_SCORE}, {NOOB_QUALITY}, {base}"


def _generate_char(positive: str, log=print, seed: int = -1) -> tuple[bytes, int]:
    """キャラクター画像：NoobAI XL最適設定（CFG=6, Euler a, Hires+ADetailer）"""
    pos = _noob_positive(positive)
    png, used_seed = txt2img(
        pos, CHAR_NEGATIVE,
        width=CHAR_W, height=CHAR_H,
        steps=28, cfg=6.0,           # NoobAI XL は CFG低め(5-6)が◎
        seed=seed,
        hires=True,
        use_adetailer=True,
        sampler_override="Euler a",  # Euler a = NAIデフォルト、柔らかく鮮明
    )
    log(f"    seed={used_seed}")
    return png, used_seed


def _generate_scene(positive: str, log=print, seed: int = -1) -> bytes:
    """Hシーン画像：NoobAI XL最適設定"""
    pos = _noob_positive(positive)
    png, used_seed = txt2img(
        pos, H_NEGATIVE,
        width=SCENE_W, height=SCENE_H,
        steps=30, cfg=6.0,
        seed=seed,
        hires=True,
        use_adetailer=True,
        sampler_override="Euler a",
    )
    log(f"    seed={used_seed}")
    return png


def generate_strip_images(concept: dict, project_path: Path, log=print) -> tuple[dict, int]:
    """
    ヒロインの衣装状態別立ち絵を生成する。
    state_0.png（完全着衣）〜 state_N.png（全裸）まで生成。
    assets/characters/ に保存。
    最初のseedを固定して全stateでキャラクターの一貫性を保つ。
    戻り値: (saved_dict, fixed_seed)  ← seedをHシーン生成にも渡せる
    """
    char_dir = project_path / "assets" / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)

    heroine       = concept.get("heroine", {})
    heroine_name  = heroine.get("name", "ヒロイン")
    appearance    = heroine.get("appearance", "beautiful young woman, long black hair, fair skin")
    clothing_items = heroine.get("clothing_items", ["シャツ", "スカート", "ブラ", "パンティ"])
    setting       = concept.get("setting", "classroom, indoor")
    total_states  = len(clothing_items) + 1

    log(f"  [SD] キャラクター衣装画像生成: {heroine_name} ({total_states}状態) 高解像度モード")

    saved      = {}
    fixed_seed = -1  # state_0で生成したseedを全stateで固定

    for state in range(total_states):
        if state == 0:
            # 完全着衣
            clothing_desc = "fully clothed, school uniform, blazer, white shirt, pleated skirt, white knee socks"
            expression    = "slight smile, looking at viewer, calm, composed"
            body_desc     = "standing, upper body, arms at sides"
        elif state == 1:
            clothing_desc = "removed blazer, white shirt, pleated skirt, white knee socks, no blazer"
            expression    = "surprised expression, light blush, looking away"
            body_desc     = "standing, upper body, arms crossed over chest"
        elif state == 2:
            clothing_desc = "white dress shirt, pleated skirt, white knee socks, shirt partially unbuttoned"
            expression    = "blushing, embarrassed, flushed cheeks, looking down"
            body_desc     = "standing, upper body, hands nervously on shirt"
        elif state == 3:
            clothing_desc = "white bra visible, pleated skirt, white knee socks, unbuttoned shirt hanging open"
            expression    = "deeply blushing, teary eyes, covering face with hands"
            body_desc     = "standing, upper body, leaning slightly forward"
        elif state == 4:
            clothing_desc = "white bra, white panties, white knee socks, no skirt, half undressed"
            expression    = "extremely embarrassed, red face, crying tears, eyes closed"
            body_desc     = "standing, covering chest with arms, cowering slightly"
        elif state == 5:
            clothing_desc = "white panties only, topless, bare chest, white knee socks"
            expression    = "mortified expression, streams of tears, deeply flushed"
            body_desc     = "standing, both arms covering breasts, hunching over"
        else:
            # 全裸
            clothing_desc = "completely nude, naked, no clothes"
            expression    = "ahegao light, deeply blushing, teary eyes, mouth slightly open"
            body_desc     = "standing, one arm covering breasts, other hand covering groin, trembling"

        positive = (
            f"1girl, solo, {appearance}, "
            f"{clothing_desc}, "
            f"{expression}, {body_desc}, "
            f"highly detailed face, detailed eyes, shiny hair, "
            f"smooth skin, soft lighting, "
            f"white background, simple background, "
            f"cowboy shot, from waist up, upper body focus, "
            f"close-up portrait, large character, filling frame, "
            f"anime style"
        )

        log(f"  [SD] state_{state}.png 生成中 ({'着衣' if state == 0 else '全裸' if state == total_states-1 else f'脱衣{state}'})...")
        try:
            png, used_seed = _generate_char(positive, log=log, seed=fixed_seed)
            # state_0のシードを固定して以降全stateで同じキャラを維持
            if fixed_seed == -1:
                fixed_seed = used_seed
                log(f"    シード固定: {fixed_seed}（以降このシードで統一）")
            out_path = char_dir / f"state_{state}.png"
            out_path.write_bytes(png)
            log(f"    -> assets/characters/state_{state}.png")
            saved[f"state_{state}"] = str(out_path)
        except Exception as e:
            log(f"    !! state_{state}.png 生成失敗: {e}")

    return saved, fixed_seed


def generate_h_scene_images(concept: dict, project_path: Path, log=print, char_seed: int = -1) -> dict:
    """
    Hシーン画像を生成する。
    assets/h_scenes/fellatio.png と sex.png を生成。
    char_seed: キャラ立ち絵と同じシードを渡すとキャラの一貫性が上がる。
    """
    h_dir = project_path / "assets" / "h_scenes"
    h_dir.mkdir(parents=True, exist_ok=True)

    heroine      = concept.get("heroine", {})
    heroine_name = heroine.get("name", "ヒロイン")
    appearance   = heroine.get("appearance", "beautiful young woman, long black hair, fair skin")
    setting      = concept.get("setting", "classroom, indoor")

    log(f"  [SD] Hシーン画像生成: {heroine_name} 高解像度モード")
    if char_seed != -1:
        log(f"  [SD] キャラ統一シード使用: {char_seed}")

    saved = {}

    # Hシーン用ネガティブ（2girl対策強化）
    h_neg_strict = (
        H_NEGATIVE + ", "
        "2girls, multiple girls, two girls, three girls, multiple characters, "
        "multiple people, group, harem, two people, other girl, second girl, "
        "mirror, reflection, clone, duplicate character"
    )

    # フェラチオシーン
    log("  [SD] フェラチオシーン生成中...")
    fellatio_positive = (
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
    try:
        png = _generate_scene(fellatio_positive, log=log, seed=-1)
        out_path = h_dir / "fellatio.png"
        out_path.write_bytes(png)
        log("    -> assets/h_scenes/fellatio.png")
        saved["fellatio"] = str(out_path)
    except Exception as e:
        log(f"    !! fellatio.png 生成失敗: {e}")

    # セックスシーン
    log("  [SD] セックスシーン生成中...")
    sex_positive = (
        f"1girl, solo focus, only one girl, {appearance}, "
        f"nude, completely naked, nsfw, explicit, rating:explicit, "
        f"hetero sex, vaginal intercourse, penis, penetration, "
        f"missionary position, lying on back, legs raised, "
        f"pov, male pov, from above, looking up at viewer, "
        f"insertion visible, penis inside vagina, "
        f"ahegao, ecstasy, moaning, eyes rolling back, mouth open, "
        f"upper body focus, face and chest visible, "
        f"beautiful detailed face, "
        f"perfect anatomy, anime style, "
        f"classroom desk, indoor, warm lighting"
    )
    try:
        png = _generate_scene(sex_positive, log=log, seed=-1)
        out_path = h_dir / "sex.png"
        out_path.write_bytes(png)
        log("    -> assets/h_scenes/sex.png")
        saved["sex"] = str(out_path)
    except Exception as e:
        log(f"    !! sex.png 生成失敗: {e}")

    return saved
