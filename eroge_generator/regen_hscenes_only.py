"""
Hシーン画像のみ再生成（キャラ立ち絵はスキップ）
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sd_rpg_strip import generate_h_scene_images

PROJECT_PATH = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")

concept = {
    "title": "秘密の野球拳～課外授業の誘惑～",
    "heroine": {
        "name": "星野 恋花",
        "appearance": "very long straight black hair down to waist, blue-grey eyes, large innocent eyes, fair skin, natural skin tone, large breasts, petite slim figure, beautiful face, cute face",
        "clothing_items": [
            "制服ブレザー", "ワイシャツ", "セーター",
            "スカート", "ストッキング", "ブラジャー",
        ],
    },
    "setting": "after school classroom, indoor, warm lighting",
}

def log(msg):
    print(msg, flush=True)

print("=== Hシーン画像再生成 (NoobAI XL v1.1) ===")
saved = generate_h_scene_images(concept, PROJECT_PATH, log=log)
print(f"完了: {len(saved)}枚")
for k, v in saved.items():
    print(f"  {k}: {v}")
print("終了！")
