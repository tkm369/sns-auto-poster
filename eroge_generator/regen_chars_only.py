"""キャラ立ち絵のみ再生成（Hシーンはスキップ）"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sd_rpg_strip import generate_strip_images

PROJECT_PATH = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")
concept = json.loads((PROJECT_PATH / "concept.json").read_text(encoding="utf-8"))

def log(msg): print(msg, flush=True)

print("=== キャラ立ち絵再生成（肌色修正版） ===")
print(f"外見: {concept['heroine']['appearance']}")
saved, seed = generate_strip_images(concept, PROJECT_PATH, log=log)
print(f"完了: {len(saved)}枚  seed={seed}")
