"""
regen_all_unified.py
全キャラ画像（state_0〜N）＋Hシーンを同一シードで再生成してキャラを統一する。
state_0 で決まったシードをHシーン生成にも渡し、同じ顔・髪・体型を維持する。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sd_client import is_available, auto_start as sd_auto_start
from sd_rpg_strip import generate_strip_images, generate_h_scene_images

# ── パス設定 ─────────────────────────────────────────────────────
PROJECT_DIR  = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")
CONCEPT_PATH = PROJECT_DIR / "concept.json"

def log(msg: str) -> None:
    print(msg, flush=True)

def main() -> None:
    # concept.json 読み込み
    concept = json.loads(CONCEPT_PATH.read_text(encoding="utf-8"))
    heroine_name = concept.get("heroine", {}).get("name", "ヒロイン")
    log(f"対象: {concept['title']}")
    log(f"ヒロイン: {heroine_name}")
    log(f"外見: {concept['heroine']['appearance']}")
    log("")

    # SD Forge 起動確認
    if not is_available():
        log("SD Forge 起動中...")
        sd_auto_start(log=log)

    # ── キャラ立ち絵（state_0〜N）生成 ────────────────────────────
    log("=== キャラ立ち絵生成 ===")
    saved_chars, char_seed = generate_strip_images(concept, PROJECT_DIR, log=log)
    log(f"  立ち絵完了: {len(saved_chars)}枚  固定seed={char_seed}")
    log("")

    # ── Hシーン生成（同一シードでキャラ統一）──────────────────────
    log("=== Hシーン生成（キャラ統一シード使用）===")
    saved_h = generate_h_scene_images(concept, PROJECT_DIR, log=log, char_seed=char_seed)
    log(f"  Hシーン完了: {len(saved_h)}枚")
    log("")

    log("=== 全完了 ===")
    log(f"立ち絵 {len(saved_chars)}枚 + Hシーン {len(saved_h)}枚")
    log("")
    log("次: Godot のインポートキャッシュをクリアしてゲームを再起動してください。")

if __name__ == "__main__":
    main()
