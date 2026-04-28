"""
脱衣状態（肌が多く見えるstate）のみ再生成。
肌色を強制指定して白すぎる問題を修正。
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sd_rpg_strip import _noob_positive, _generate_char, CHAR_NEGATIVE
from sd_client import is_available, auto_start as sd_auto_start

PROJECT = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")
CHAR_DIR = PROJECT / "assets" / "characters"

# 肌色タグを強化した外見
APPEARANCE = (
    "very long straight black hair down to waist, blue-grey eyes, large innocent eyes, "
    "warm skin tone, peach skin, light tan skin, natural skin color, not pale, "
    "large breasts, petite slim figure, beautiful face, cute face"
)

# 肌色強化ネガティブ
SKIN_NEG = (
    CHAR_NEGATIVE + ", "
    "pale skin, white skin, paper white skin, grey skin, overly pale, "
    "porcelain skin, albino, white body, colorless skin"
)

FIXED_SEED = 2112473829

# 各状態の服装・表情・ポーズ定義
STATES = {
    4: {
        "clothing": "white bra, white panties, white knee socks, no skirt, half undressed",
        "expression": "extremely embarrassed, red face, crying tears, eyes closed",
        "body": "standing, covering chest with arms, cowering slightly",
        "label": "ブラ＆パンツ",
    },
    5: {
        "clothing": "white panties only, topless, bare chest, bare breasts, white knee socks",
        "expression": "mortified expression, streams of tears, deeply flushed cheeks",
        "body": "standing, both arms covering breasts, hunching over",
        "label": "パンツのみ",
    },
    6: {
        "clothing": "completely nude, naked, no clothes, no underwear, bare skin",
        "expression": "ahegao light, deeply blushing, teary eyes, mouth slightly open",
        "body": "standing, one arm covering breasts, other hand covering groin, trembling",
        "label": "全裸",
    },
}

def log(msg): print(msg, flush=True)

def main():
    if not is_available():
        log("SD Forge 起動中...")
        sd_auto_start(log=log)

    for state, info in STATES.items():
        positive = (
            f"1girl, solo, {APPEARANCE}, "
            f"{info['clothing']}, "
            f"{info['expression']}, {info['body']}, "
            f"highly detailed face, detailed eyes, shiny hair, "
            f"smooth skin, soft lighting, "
            f"white background, simple background, "
            f"cowboy shot, from waist up, upper body focus, "
            f"close-up portrait, large character, filling frame, "
            f"anime style"
        )
        log(f"\nstate_{state}.png 再生成中（{info['label']}）seed={FIXED_SEED}...")
        try:
            png, used_seed = _generate_char(positive, log=log, seed=FIXED_SEED)
            out = CHAR_DIR / f"state_{state}.png"
            out.write_bytes(png)
            log(f"  -> 保存完了: state_{state}.png  seed={used_seed}")
        except Exception as e:
            log(f"  !! 失敗: {e}")

    log("\n=== 完了 ===")
    log("次: split_layers.py を実行してレイヤーを更新してください")

if __name__ == "__main__":
    main()
