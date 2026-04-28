"""
NoobAI XL v1.1 で野球拳ゲーム画像を再生成するスクリプト
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sd_rpg_strip import generate_strip_images, generate_h_scene_images

PROJECT_PATH = Path(r"C:\Users\inoue\Desktop\ai-project\output_godot\秘密の野球拳_課外授業の誘惑_")

concept = {
    "title": "秘密の野球拳～課外授業の誘惑～",
    "heroine": {
        "name": "星野 恋花",
        "appearance": "long black hair, fair skin, large breasts, petite figure, school uniform with blouse and pleated skirt, white socks",
        "clothing_items": [
            "制服ブレザー",
            "ワイシャツ",
            "セーター",
            "スカート",
            "ストッキング",
            "ブラジャー",
        ],
    },
    "setting": "after school classroom, indoor, warm lighting",
}

def log(msg):
    print(msg, flush=True)

print("=== キャラ立ち絵再生成 (NoobAI XL v1.1) ===")
saved_chars, char_seed = generate_strip_images(concept, PROJECT_PATH, log=log)
print(f"完了: {len(saved_chars)}枚  seed={char_seed}\n")

print("=== Hシーン画像再生成 (NoobAI XL v1.1) ===")
saved_h = generate_h_scene_images(concept, PROJECT_PATH, log=log, char_seed=char_seed)
print(f"完了: {len(saved_h)}枚\n")

print("全完了！")
