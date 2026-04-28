"""
godot_strip_writer.py
野球拳スタイル脱衣カードゲームのGodot 4プロジェクトファイルを書き出す
"""

from pathlib import Path
import json
import re

GODOT_OUTPUT = Path(__file__).parent.parent / "output_godot"


# ─────────────────────────────────────────────
#  ユーティリティ
# ─────────────────────────────────────────────

def _sanitize(name: str) -> str:
    """ファイル名に使えない文字を除去"""
    return re.sub(r'[^\w\-]', '_', name, flags=re.UNICODE)


# ─────────────────────────────────────────────
#  project.godot
# ─────────────────────────────────────────────

def _write_project_godot(proj_dir: Path, concept: dict) -> None:
    title = concept.get("title", "Strip Card Game")
    story = concept.get("story", "").replace('"', '\\"')
    content = f"""; Engine configuration file.
; It contains the configuration settings of the game.
; Edit at your own risk.

config_version=5

[application]

config/name="{title}"
config/description="{story}"
run/main_scene="res://scenes/main.tscn"
config/features=PackedStringArray("4.3", "Forward Plus")
config/icon="res://icon.svg"

[autoload]

GameManager="*res://scripts/game_manager.gd"

[display]

window/size/viewport_width=1280
window/size/viewport_height=720
window/stretch/mode="canvas_items"

[rendering]

renderer/rendering_method="forward_plus"
"""
    (proj_dir / "project.godot").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  icon.svg
# ─────────────────────────────────────────────

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">
<rect width="128" height="128" fill="#c0392b"/>
<text x="64" y="50" font-size="28" text-anchor="middle" fill="white">STRIP</text>
<text x="64" y="90" font-size="28" text-anchor="middle" fill="white">CARD</text>
</svg>
"""


# ─────────────────────────────────────────────
#  scenes/main.tscn
# ─────────────────────────────────────────────

def _write_main_tscn(scenes_dir: Path, concept: dict) -> None:
    heroine = concept.get("heroine", {})
    heroine_name = heroine.get("name", "ヒロイン")
    clothing_count = len(heroine.get("clothing_items", ["シャツ", "スカート", "ブラ", "パンティ"]))

    content = f"""[gd_scene load_steps=5 format=3 uid="uid://strip_main"]

[ext_resource type="Script" path="res://scripts/card_battle.gd" id="1_card_battle"]
[ext_resource type="Script" path="res://scripts/character.gd" id="2_character"]
[ext_resource type="Script" path="res://scripts/h_scene_viewer.gd" id="3_h_scene"]

[node name="Main" type="Node2D"]

[node name="Background" type="ColorRect" parent="."]
offset_left = 0.0
offset_top = 0.0
offset_right = 1280.0
offset_bottom = 720.0
color = Color(0.08, 0.05, 0.12, 1)

[node name="CardBattle" type="Control" parent="."]
script = ExtResource("1_card_battle")
offset_left = 0.0
offset_top = 0.0
offset_right = 700.0
offset_bottom = 720.0

[node name="PlayerCardBg" type="ColorRect" parent="CardBattle"]
offset_left = 80.0
offset_top = 200.0
offset_right = 280.0
offset_bottom = 420.0
color = Color(0.15, 0.1, 0.25, 1)

[node name="PlayerCard" type="Label" parent="CardBattle"]
offset_left = 80.0
offset_top = 250.0
offset_right = 280.0
offset_bottom = 370.0
text = "?"
horizontal_alignment = 1
vertical_alignment = 1
theme_override_font_sizes/font_size = 72

[node name="PlayerLabel" type="Label" parent="CardBattle"]
offset_left = 80.0
offset_top = 200.0
offset_right = 280.0
offset_bottom = 240.0
text = "あなた"
horizontal_alignment = 1

[node name="OpponentCardBg" type="ColorRect" parent="CardBattle"]
offset_left = 420.0
offset_top = 200.0
offset_right = 620.0
offset_bottom = 420.0
color = Color(0.25, 0.1, 0.15, 1)

[node name="OpponentCard" type="Label" parent="CardBattle"]
offset_left = 420.0
offset_top = 250.0
offset_right = 620.0
offset_bottom = 370.0
text = "?"
horizontal_alignment = 1
vertical_alignment = 1
theme_override_font_sizes/font_size = 72

[node name="OpponentLabel" type="Label" parent="CardBattle"]
offset_left = 420.0
offset_top = 200.0
offset_right = 620.0
offset_bottom = 240.0
text = "{heroine_name}"
horizontal_alignment = 1

[node name="VSLabel" type="Label" parent="CardBattle"]
offset_left = 290.0
offset_top = 290.0
offset_right = 410.0
offset_bottom = 330.0
text = "VS"
horizontal_alignment = 1
theme_override_font_sizes/font_size = 24

[node name="ResultLabel" type="Label" parent="CardBattle"]
offset_left = 50.0
offset_top = 450.0
offset_right = 650.0
offset_bottom = 510.0
text = ""
horizontal_alignment = 1
theme_override_font_sizes/font_size = 24

[node name="DrawButton" type="Button" parent="CardBattle"]
offset_left = 250.0
offset_top = 540.0
offset_right = 450.0
offset_bottom = 590.0
text = "カードを引く"

[node name="Character" type="Node2D" parent="."]
script = ExtResource("2_character")
position = Vector2(1000.0, 360.0)

[node name="CharacterSprite" type="Sprite2D" parent="Character"]

[node name="ReactionLabel" type="Label" parent="Character"]
offset_left = -150.0
offset_top = -350.0
offset_right = 150.0
offset_bottom = -300.0
text = ""
horizontal_alignment = 1
modulate = Color(1, 0.8, 0.9, 1)

[node name="StatusPanel" type="CanvasLayer" parent="."]

[node name="PlayerStatusBg" type="ColorRect" parent="StatusPanel"]
offset_left = 10.0
offset_top = 10.0
offset_right = 220.0
offset_bottom = 100.0
color = Color(0, 0, 0, 0.6)

[node name="PlayerStatusLabel" type="Label" parent="StatusPanel"]
offset_left = 20.0
offset_top = 15.0
offset_right = 210.0
offset_bottom = 50.0
text = "あなたの服: 3枚"

[node name="OpponentStatusLabel" type="Label" parent="StatusPanel"]
offset_left = 20.0
offset_top = 55.0
offset_right = 210.0
offset_bottom = 90.0
text = "{heroine_name}の服: {clothing_count}枚"

[node name="HSceneViewer" type="CanvasLayer" parent="."]
script = ExtResource("3_h_scene")
visible = false

[node name="HSceneBg" type="ColorRect" parent="HSceneViewer"]
offset_left = 0.0
offset_top = 0.0
offset_right = 1280.0
offset_bottom = 720.0
color = Color(0, 0, 0, 0.95)

[node name="SceneImage" type="TextureRect" parent="HSceneViewer"]
offset_left = 0.0
offset_top = 0.0
offset_right = 1280.0
offset_bottom = 620.0
stretch_mode = 6

[node name="DialogueLabel" type="Label" parent="HSceneViewer"]
offset_left = 40.0
offset_top = 620.0
offset_right = 1000.0
offset_bottom = 710.0
text = ""
theme_override_font_sizes/font_size = 20

[node name="NextButton" type="Button" parent="HSceneViewer"]
offset_left = 1050.0
offset_top = 640.0
offset_right = 1180.0
offset_bottom = 680.0
text = "次へ ▶"

[node name="PrevButton" type="Button" parent="HSceneViewer"]
offset_left = 900.0
offset_top = 640.0
offset_right = 1030.0
offset_bottom = 680.0
text = "◀ 前へ"

[node name="CloseButton" type="Button" parent="HSceneViewer"]
offset_left = 1190.0
offset_top = 10.0
offset_right = 1270.0
offset_bottom = 50.0
text = "✕"

[node name="AutoButton" type="Button" parent="HSceneViewer"]
offset_left = 1050.0
offset_top = 590.0
offset_right = 1180.0
offset_bottom = 630.0
text = "AUTO"

[node name="AutoTimer" type="Timer" parent="HSceneViewer"]
wait_time = 3.0
autostart = false
"""
    (scenes_dir / "main.tscn").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  scenes/card_battle.tscn
# ─────────────────────────────────────────────

def _write_card_battle_tscn(scenes_dir: Path, concept: dict) -> None:
    card_theme = concept.get("card_theme", "トランプ")
    content = f"""[gd_scene load_steps=2 format=3 uid="uid://strip_card_battle"]

[ext_resource type="Script" path="res://scripts/card_battle.gd" id="1_card_battle"]

[node name="CardBattle" type="Control"]
script = ExtResource("1_card_battle")

[node name="Title" type="Label" parent="."]
offset_left = 0.0
offset_top = 20.0
offset_right = 700.0
offset_bottom = 60.0
text = "{card_theme} 野球拳"
horizontal_alignment = 1
theme_override_font_sizes/font_size = 28

[node name="PlayerCardBg" type="ColorRect" parent="."]
offset_left = 80.0
offset_top = 100.0
offset_right = 280.0
offset_bottom = 320.0
color = Color(0.15, 0.1, 0.25, 1)

[node name="PlayerCard" type="Label" parent="."]
offset_left = 80.0
offset_top = 150.0
offset_right = 280.0
offset_bottom = 270.0
text = "?"
horizontal_alignment = 1
vertical_alignment = 1
theme_override_font_sizes/font_size = 72

[node name="PlayerLabel" type="Label" parent="."]
offset_left = 80.0
offset_top = 100.0
offset_right = 280.0
offset_bottom = 140.0
text = "あなた"
horizontal_alignment = 1

[node name="OpponentCardBg" type="ColorRect" parent="."]
offset_left = 420.0
offset_top = 100.0
offset_right = 620.0
offset_bottom = 320.0
color = Color(0.25, 0.1, 0.15, 1)

[node name="OpponentCard" type="Label" parent="."]
offset_left = 420.0
offset_top = 150.0
offset_right = 620.0
offset_bottom = 270.0
text = "?"
horizontal_alignment = 1
vertical_alignment = 1
theme_override_font_sizes/font_size = 72

[node name="OpponentLabel" type="Label" parent="."]
offset_left = 420.0
offset_top = 100.0
offset_right = 620.0
offset_bottom = 140.0
text = "相手"
horizontal_alignment = 1

[node name="VSLabel" type="Label" parent="."]
offset_left = 290.0
offset_top = 190.0
offset_right = 410.0
offset_bottom = 230.0
text = "VS"
horizontal_alignment = 1
theme_override_font_sizes/font_size = 24

[node name="ResultLabel" type="Label" parent="."]
offset_left = 50.0
offset_top = 350.0
offset_right = 650.0
offset_bottom = 410.0
text = ""
horizontal_alignment = 1
theme_override_font_sizes/font_size = 24

[node name="DrawButton" type="Button" parent="."]
offset_left = 250.0
offset_top = 440.0
offset_right = 450.0
offset_bottom = 490.0
text = "カードを引く"

[node name="AnimationPlayer" type="AnimationPlayer" parent="."]
"""
    (scenes_dir / "card_battle.tscn").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  scenes/h_scene.tscn
# ─────────────────────────────────────────────

def _write_h_scene_tscn(scenes_dir: Path, concept: dict) -> None:
    content = """[gd_scene load_steps=2 format=3 uid="uid://strip_h_scene"]

[ext_resource type="Script" path="res://scripts/h_scene_viewer.gd" id="1_h_scene"]

[node name="HSceneViewer" type="CanvasLayer"]
script = ExtResource("1_h_scene")

[node name="Background" type="ColorRect" parent="."]
offset_left = 0.0
offset_top = 0.0
offset_right = 1280.0
offset_bottom = 720.0
color = Color(0, 0, 0, 0.95)

[node name="SceneImage" type="TextureRect" parent="."]
offset_left = 0.0
offset_top = 0.0
offset_right = 1280.0
offset_bottom = 620.0
stretch_mode = 6

[node name="DialoguePanel" type="ColorRect" parent="."]
offset_left = 0.0
offset_top = 615.0
offset_right = 1280.0
offset_bottom = 720.0
color = Color(0, 0, 0, 0.7)

[node name="DialogueLabel" type="Label" parent="."]
offset_left = 40.0
offset_top = 625.0
offset_right = 1000.0
offset_bottom = 715.0
text = ""
theme_override_font_sizes/font_size = 20

[node name="NextButton" type="Button" parent="."]
offset_left = 1050.0
offset_top = 645.0
offset_right = 1180.0
offset_bottom = 685.0
text = "次へ ▶"

[node name="PrevButton" type="Button" parent="."]
offset_left = 900.0
offset_top = 645.0
offset_right = 1030.0
offset_bottom = 685.0
text = "◀ 前へ"

[node name="CloseButton" type="Button" parent="."]
offset_left = 1190.0
offset_top = 10.0
offset_right = 1270.0
offset_bottom = 50.0
text = "✕"

[node name="AutoButton" type="Button" parent="."]
offset_left = 1050.0
offset_top = 600.0
offset_right = 1180.0
offset_bottom = 640.0
text = "AUTO"

[node name="AutoTimer" type="Timer" parent="."]
wait_time = 3.0
autostart = false
"""
    (scenes_dir / "h_scene.tscn").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  scenes/ui/result_popup.tscn
# ─────────────────────────────────────────────

def _write_result_popup_tscn(ui_dir: Path) -> None:
    content = """[gd_scene load_steps=1 format=3 uid="uid://strip_result_popup"]

[node name="ResultPopup" type="CanvasLayer"]

[node name="Background" type="ColorRect" parent="."]
offset_left = 390.0
offset_top = 260.0
offset_right = 890.0
offset_bottom = 460.0
color = Color(0.05, 0.05, 0.1, 0.95)

[node name="ResultTitle" type="Label" parent="."]
offset_left = 400.0
offset_top = 280.0
offset_right = 880.0
offset_bottom = 340.0
text = "結果"
horizontal_alignment = 1
theme_override_font_sizes/font_size = 36

[node name="ResultMessage" type="Label" parent="."]
offset_left = 400.0
offset_top = 350.0
offset_right = 880.0
offset_bottom = 410.0
text = ""
horizontal_alignment = 1
theme_override_font_sizes/font_size = 20

[node name="ContinueButton" type="Button" parent="."]
offset_left = 530.0
offset_top = 420.0
offset_right = 750.0
offset_bottom = 455.0
text = "続ける"
"""
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "result_popup.tscn").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  README.txt
# ─────────────────────────────────────────────

def _write_readme(proj_dir: Path, concept: dict) -> None:
    title = concept.get("title", "Strip Card Game")
    subtitle = concept.get("subtitle", "")
    story = concept.get("story", "")
    heroine = concept.get("heroine", {})
    card_theme = concept.get("card_theme", "トランプ")
    setting = concept.get("setting", "")

    clothing_items = heroine.get("clothing_items", [])
    clothing_list = "\n".join(f"  {i+1}. {item}" for i, item in enumerate(clothing_items))

    content = f"""=== {title} ===
{subtitle}

【開き方】
1. Godot Engine 4.x をダウンロード: https://godotengine.org/download/
2. Godotを起動
3. 「Import」→ このフォルダの project.godot を選択
4. F5 または「Play」ボタンで実行

【ゲーム説明】
{story}

【舞台】
{setting}

【操作方法】
- 「カードを引く」ボタンをクリックでカードバトル開始
- 数字が高い方が勝ち
- 引き分けの場合は両者1枚脱ぐ
- ヒロインを全裸にするとHシーンが開放される

【ヒロイン】
名前: {heroine.get('name', 'ヒロイン')}
年齢: {heroine.get('age', 20)}歳
性格: {heroine.get('personality', '')}

【衣装（脱衣順）】
{clothing_list}

【カードテーマ】
{card_theme}

【ファイル構成】
project.godot          - Godotプロジェクト設定
scenes/main.tscn       - メインシーン（統合型）
scenes/card_battle.tscn - カードバトルシーン
scenes/h_scene.tscn    - Hシーンビューア
scenes/ui/             - UIシーン群
scripts/game_manager.gd - ゲームマネージャー（Autoload）
scripts/card_battle.gd  - カードバトルロジック
scripts/character.gd    - キャラクター衣装管理
scripts/h_scene_viewer.gd - Hシーンビューア
assets/characters/     - キャラクター画像（state_0〜N.png）
assets/h_scenes/       - Hシーン画像（fellatio.png, sex.png）
concept.json           - ゲームコンセプト（デバッグ用）
dialogue.json          - セリフデータ

【注意】
このゲームはR18コンテンツを含みます。18歳以上の方のみプレイしてください。
"""
    (proj_dir / "README.txt").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  プレースホルダー画像（PNG）
# ─────────────────────────────────────────────

def _write_placeholder_png(path: Path, width: int, height: int,
                            label: str, bg_color=(50, 30, 60)) -> None:
    """最小限のPNGプレースホルダーを書き出す（Pillow不要、純Pythonで生成）"""
    # 1x1ピクセルの最小PNGを書くシンプルな実装
    # Pillowが利用可能な場合はより良い画像を生成する
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        # テキストを中央に描画
        text = label
        draw.text((width // 2, height // 2), text, fill=(200, 180, 220),
                  anchor="mm" if hasattr(draw, "textlength") else None)
        img.save(str(path), "PNG")
    except Exception:
        # Pillowがない場合は最小PNGバイナリ（1×1ピクセル）を書く
        import struct
        import zlib

        def _pack_chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        png_sig = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr = _pack_chunk(b'IHDR', ihdr_data)
        raw = b'\x00' + bytes(bg_color[:3])
        idat = _pack_chunk(b'IDAT', zlib.compress(raw))
        iend = _pack_chunk(b'IEND', b'')
        path.write_bytes(png_sig + ihdr + idat + iend)


def _write_placeholder_assets(proj_dir: Path, concept: dict, log=print) -> None:
    """SDが利用できない場合のプレースホルダー画像を生成"""
    heroine = concept.get("heroine", {})
    clothing_items = heroine.get("clothing_items", ["シャツ", "スカート", "ブラ", "パンティ"])
    total_states = len(clothing_items) + 1

    char_dir = proj_dir / "assets" / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)

    h_dir = proj_dir / "assets" / "h_scenes"
    h_dir.mkdir(parents=True, exist_ok=True)

    log("  プレースホルダー画像を生成中...")

    for state in range(total_states):
        path = char_dir / f"state_{state}.png"
        label = f"State {state}"
        _write_placeholder_png(path, 512, 768, label, (50, 30, 60))

    _write_placeholder_png(h_dir / "fellatio.png", 1280, 720,
                           "Fellatio Scene", (40, 20, 30))
    _write_placeholder_png(h_dir / "sex.png", 1280, 720,
                           "Sex Scene", (50, 20, 30))

    log(f"  プレースホルダー画像: {total_states}キャラ + 2Hシーン")


# ─────────────────────────────────────────────
#  メイン書き出し関数
# ─────────────────────────────────────────────

def write_strip_project(concept: dict, scripts: dict, dialogue: dict,
                        log=print) -> Path:
    """
    野球拳脱衣カードゲームのGodot 4プロジェクトを生成する

    scripts: {
        "game_manager": "GDScriptコード",
        "card_battle": "GDScriptコード",
        "character": "GDScriptコード",
        "h_scene_viewer": "GDScriptコード",
    }
    dialogue: {
        "strip_lines": [...],
        "h_scene_fellatio_lines": [...],
        "h_scene_sex_lines": [...],
        "win_lines": [...],
        "lose_lines": [...],
    }

    戻り値: プロジェクトフォルダのPath
    """

    title = concept.get("title", "strip_card_game")
    folder_name = _sanitize(title)
    proj_dir = GODOT_OUTPUT / folder_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    log(f"  出力先: {proj_dir}")

    # ディレクトリ構造作成
    scenes_dir = proj_dir / "scenes"
    ui_dir = scenes_dir / "ui"
    scripts_dir = proj_dir / "scripts"
    assets_dir = proj_dir / "assets"
    char_dir = assets_dir / "characters"
    h_dir = assets_dir / "h_scenes"

    for d in [scenes_dir, ui_dir, scripts_dir, assets_dir, char_dir, h_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ── project.godot ──────────────────────
    log("  project.godot を書き出し中...")
    _write_project_godot(proj_dir, concept)

    # ── icon.svg ───────────────────────────
    (proj_dir / "icon.svg").write_text(ICON_SVG, encoding="utf-8")

    # ── scenes/main.tscn ──────────────────
    log("  main.tscn を書き出し中...")
    _write_main_tscn(scenes_dir, concept)

    # ── scenes/card_battle.tscn ───────────
    log("  card_battle.tscn を書き出し中...")
    _write_card_battle_tscn(scenes_dir, concept)

    # ── scenes/h_scene.tscn ───────────────
    log("  h_scene.tscn を書き出し中...")
    _write_h_scene_tscn(scenes_dir, concept)

    # ── scenes/ui/result_popup.tscn ───────
    log("  result_popup.tscn を書き出し中...")
    _write_result_popup_tscn(ui_dir)

    # ── scripts/game_manager.gd ───────────
    log("  game_manager.gd を書き出し中...")
    gm_gd = scripts.get("game_manager", "extends Node\n# game_manager.gd\n")
    (scripts_dir / "game_manager.gd").write_text(gm_gd, encoding="utf-8")

    # ── scripts/card_battle.gd ────────────
    log("  card_battle.gd を書き出し中...")
    cb_gd = scripts.get("card_battle", "extends Control\n# card_battle.gd\n")
    (scripts_dir / "card_battle.gd").write_text(cb_gd, encoding="utf-8")

    # ── scripts/character.gd ──────────────
    log("  character.gd を書き出し中...")
    char_gd = scripts.get("character", "extends Node2D\n# character.gd\n")
    (scripts_dir / "character.gd").write_text(char_gd, encoding="utf-8")

    # ── scripts/h_scene_viewer.gd ─────────
    log("  h_scene_viewer.gd を書き出し中...")
    hs_gd = scripts.get("h_scene_viewer", "extends CanvasLayer\n# h_scene_viewer.gd\n")
    (scripts_dir / "h_scene_viewer.gd").write_text(hs_gd, encoding="utf-8")

    # ── concept.json ──────────────────────
    (proj_dir / "concept.json").write_text(
        json.dumps(concept, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── dialogue.json ─────────────────────
    (proj_dir / "dialogue.json").write_text(
        json.dumps(dialogue, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── README.txt ────────────────────────
    log("  README.txt を書き出し中...")
    _write_readme(proj_dir, concept)

    log(f"  完了: {len(list(proj_dir.rglob('*')))} ファイル生成")
    return proj_dir


# ─────────────────────────────────────────────
#  run_full_pipeline（エントリポイント）
# ─────────────────────────────────────────────

def run_full_pipeline(genre: str = "野球拳スタイル", api_key: str = "",
                      log=print, cancel_event=None, pause_event=None,
                      use_sd: bool = False) -> Path:
    """app.pyから呼ばれるエントリポイント（野球拳脱衣ゲーム専用）"""
    import os
    import time as _t
    from godot_strip_generator import (
        generate_strip_concept,
        generate_game_manager_script,
        generate_card_battle_script,
        generate_character_script,
        generate_h_scene_script,
        generate_dialogue,
    )

    def _check():
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("キャンセル")
        while pause_event and pause_event.is_set():
            _t.sleep(0.3)
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("キャンセル")

    # ── モデル選択（LM Studio優先、なければGemini）─────────────────
    local_client = None
    model = None

    try:
        from local_model import is_available as _local_ok
        if _local_ok():
            local_client = {"base_url": "http://localhost:1234/v1"}
            log("  LM Studio 検出 → ローカルモデル使用 (localhost:1234)")
    except Exception:
        pass

    if local_client is None:
        # Gemini にフォールバック
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("LM Studio が起動していないため Gemini を使おうとしましたが、"
                             "GEMINI_API_KEY も設定されていません。"
                             "LM Studio を起動するか、Gemini APIキーを入力してください。")
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            log("  Gemini API 使用")
        except Exception as e:
            raise RuntimeError(f"Gemini 初期化失敗: {e}")

    log("━━━ 野球拳スタイル脱衣カードゲーム生成開始 ━━━")

    _check()
    log("▶ [1/6] ゲームコンセプト生成")
    concept = generate_strip_concept(model, genre, log=log, local_client=local_client)
    log(f"  タイトル: {concept.get('title', '?')}")
    log(f"  ヒロイン: {concept.get('heroine', {}).get('name', '?')} "
        f"({concept.get('heroine', {}).get('age', '?')}歳)")

    _check()
    log("▶ [2/6] ゲームマネージャースクリプト生成")
    gm_script = generate_game_manager_script(model, concept, log=log, local_client=local_client)

    _check()
    log("▶ [3/6] カードバトル＆キャラクタースクリプト生成")
    cb_script = generate_card_battle_script(model, concept, log=log, local_client=local_client)
    _check()
    char_script = generate_character_script(model, concept, log=log, local_client=local_client)

    _check()
    log("▶ [4/6] Hシーンスクリプト生成")
    hs_script = generate_h_scene_script(model, concept, log=log, local_client=local_client)

    _check()
    log("▶ [5/6] セリフ生成")
    dialogue = generate_dialogue(model, concept, log=log, local_client=local_client)
    log(f"  脱衣セリフ: {len(dialogue.get('strip_lines', []))}行")

    _check()
    log("▶ [6/6] プロジェクト出力")
    scripts = {
        "game_manager": gm_script,
        "card_battle": cb_script,
        "character": char_script,
        "h_scene_viewer": hs_script,
    }
    proj_path = write_strip_project(concept, scripts, dialogue, log=log)

    # ── SD画像生成 ────────────────────────────────────────────────
    if use_sd:
        log("▶ [+] SD画像生成")
        try:
            from sd_rpg_strip import generate_strip_images, generate_h_scene_images
            from sd_client import auto_start as sd_auto_start
            if sd_auto_start(log=log, wait_sec=180):
                log("  SD Forge 接続OK → キャラクター画像生成")
                _, char_seed = generate_strip_images(concept, proj_path, log=log)
                log("  Hシーン画像生成")
                generate_h_scene_images(concept, proj_path, log=log, char_seed=char_seed)
            else:
                log("  SD Forge が起動できませんでした → プレースホルダー画像を使用")
                _write_placeholder_assets(proj_path, concept, log=log)
        except Exception as e:
            log(f"  !! SD画像生成エラー（プレースホルダー使用）: {e}")
            _write_placeholder_assets(proj_path, concept, log=log)
    else:
        log("▶ [+] プレースホルダー画像生成（SD無効）")
        _write_placeholder_assets(proj_path, concept, log=log)

    # ── DLSite販売戦略レポート ────────────────────────────────────
    log("▶ [+] DLSite販売戦略レポート生成")
    try:
        from dlsite_advisor import generate_full_report
        report_md = generate_full_report(
            model, concept,
            game_type="Godot 野球拳脱衣カードゲーム",
            genre=genre,
            adult=True,
            log=log,
            local_client=local_client,
        )
        report_path = proj_path / "DLSITE_STRATEGY.md"
        report_path.write_text(report_md, encoding="utf-8")
        log(f"  販売戦略レポート: {report_path}")
    except Exception as e:
        log(f"  !! 販売戦略レポート生成エラー（スキップ）: {e}")

    log(f"\n完成: {proj_path}")
    return proj_path


# ─────────────────────────────────────────────
#  単体実行用
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    genre = sys.argv[1] if len(sys.argv) > 1 else "野球拳スタイル・カードバトル脱衣ゲーム"
    result = run_full_pipeline(genre=genre)
    print(f"\n出力先: {result}")
