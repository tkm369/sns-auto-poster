"""
godot_2d_writer.py
Godot 4プロジェクトファイルを実際に書き出す関数群
"""

from pathlib import Path
import json
import random
import re

GODOT_OUTPUT = Path(__file__).parent.parent / "output_godot"


# ─────────────────────────────────────────────
#  ユーティリティ
# ─────────────────────────────────────────────

def _sanitize(name: str) -> str:
    """ファイル名に使えない文字を除去"""
    return re.sub(r'[^\w\-]', '_', name, flags=re.UNICODE)


def _hex_to_godot_color(hex_color: str) -> str:
    """#rrggbbをGodot Color(r,g,b,1)形式に変換"""
    h = hex_color.lstrip('#')
    if len(h) == 6:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return f"Color({r:.4f}, {g:.4f}, {b:.4f}, 1)"
    return "Color(0.5, 0.5, 0.5, 1)"


# ─────────────────────────────────────────────
#  project.godot
# ─────────────────────────────────────────────

def _write_project_godot(proj_dir: Path, concept: dict) -> None:
    title = concept.get("title", "My Game")
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
#  main.tscn
# ─────────────────────────────────────────────

def _write_main_tscn(scenes_dir: Path) -> None:
    content = """[gd_scene load_steps=3 format=3 uid="uid://main"]

[ext_resource type="Script" path="res://scripts/game_manager.gd" id="1_main"]
[ext_resource type="PackedScene" path="res://scenes/ui/hud.tscn" id="2_hud"]

[node name="Main" type="Node2D"]
script = ExtResource("1_main")

[node name="LevelContainer" type="Node2D" parent="."]

[node name="HUD" parent="." instance=ExtResource("2_hud")]
"""
    (scenes_dir / "main.tscn").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  player.tscn
# ─────────────────────────────────────────────

def _write_player_tscn(scenes_dir: Path) -> None:
    content = """[gd_scene load_steps=3 format=3 uid="uid://player"]

[ext_resource type="Script" path="res://scripts/player.gd" id="1_player"]

[sub_resource type="RectangleShape2D" id="RectangleShape2D_player"]
size = Vector2(30, 30)

[sub_resource type="RectangleShape2D" id="RectangleShape2D_attack"]
size = Vector2(80, 40)

[sub_resource type="RectangleShape2D" id="RectangleShape2D_hurt"]
size = Vector2(28, 28)

[node name="Player" type="CharacterBody2D" groups=["player"]]
script = ExtResource("1_player")

[node name="Sprite" type="ColorRect" parent="."]
offset_left = -15.0
offset_top = -15.0
offset_right = 15.0
offset_bottom = 15.0
color = Color(0.2, 0.6, 1, 1)

[node name="CollisionShape2D" type="CollisionShape2D" parent="."]
shape = SubResource("RectangleShape2D_player")

[node name="AttackArea" type="Area2D" parent="."]
collision_layer = 4
collision_mask = 2

[node name="AttackShape" type="CollisionShape2D" parent="AttackArea"]
position = Vector2(40, 0)
shape = SubResource("RectangleShape2D_attack")
disabled = true

[node name="HurtBox" type="Area2D" parent="."]
collision_layer = 1
collision_mask = 2

[node name="HurtShape" type="CollisionShape2D" parent="HurtBox"]
shape = SubResource("RectangleShape2D_hurt")
"""
    (scenes_dir / "player.tscn").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  enemy_N.tscn
# ─────────────────────────────────────────────

def _write_enemy_tscn(enemies_dir: Path, enemy: dict, idx: int) -> None:
    name_safe = _sanitize(enemy.get("name", f"enemy_{idx}"))
    color = _hex_to_godot_color(enemy.get("color", "#ff4444"))
    script_path = f"res://scripts/enemies/enemy_{idx}.gd"

    content = f"""[gd_scene load_steps=3 format=3 uid="uid://enemy{idx}"]

[ext_resource type="Script" path="{script_path}" id="1_enemy{idx}"]

[sub_resource type="RectangleShape2D" id="RectangleShape2D_body{idx}"]
size = Vector2(28, 28)

[sub_resource type="CircleShape2D" id="CircleShape2D_detect{idx}"]
radius = {enemy.get('detect_range', 200)}.0

[sub_resource type="CircleShape2D" id="CircleShape2D_attack{idx}"]
radius = {enemy.get('attack_range', 50)}.0

[node name="Enemy" type="CharacterBody2D" groups=["enemy"]]
script = ExtResource("1_enemy{idx}")

[node name="Sprite" type="ColorRect" parent="."]
offset_left = -14.0
offset_top = -14.0
offset_right = 14.0
offset_bottom = 14.0
color = {color}

[node name="CollisionShape2D" type="CollisionShape2D" parent="."]
shape = SubResource("RectangleShape2D_body{idx}")

[node name="DetectArea" type="Area2D" parent="."]
collision_layer = 0
collision_mask = 1

[node name="DetectShape" type="CollisionShape2D" parent="DetectArea"]
shape = SubResource("CircleShape2D_detect{idx}")

[node name="AttackArea" type="Area2D" parent="."]
collision_layer = 2
collision_mask = 1

[node name="AttackShape" type="CollisionShape2D" parent="AttackArea"]
shape = SubResource("CircleShape2D_attack{idx}")

[node name="HurtBox" type="Area2D" parent="."]
collision_layer = 2
collision_mask = 4
"""
    fname = f"enemy_{idx}.tscn"
    (enemies_dir / fname).write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  hud.tscn
# ─────────────────────────────────────────────

def _write_hud_tscn(ui_dir: Path, concept: dict) -> None:
    max_hp = concept.get("player", {}).get("max_hp", 100)
    content = f"""[gd_scene load_steps=2 format=3 uid="uid://hud"]

[ext_resource type="Script" path="res://scripts/hud.gd" id="1_hud"]

[node name="HUD" type="CanvasLayer"]
script = ExtResource("1_hud")

[node name="HPBar" type="ProgressBar" parent="."]
offset_left = 20.0
offset_top = 20.0
offset_right = 220.0
offset_bottom = 45.0
max_value = {max_hp}.0
value = {max_hp}.0

[node name="ScoreLabel" type="Label" parent="."]
offset_left = 20.0
offset_top = 55.0
offset_right = 220.0
offset_bottom = 80.0
text = "Score: 0"

[node name="LevelLabel" type="Label" parent="."]
offset_left = 20.0
offset_top = 90.0
offset_right = 220.0
offset_bottom = 115.0
text = "Level: 1"

[node name="GameOverPanel" type="Panel" parent="."]
visible = false
offset_left = 390.0
offset_top = 260.0
offset_right = 890.0
offset_bottom = 460.0

[node name="GameOverLabel" type="Label" parent="GameOverPanel"]
offset_left = 100.0
offset_top = 30.0
offset_right = 400.0
offset_bottom = 80.0
text = "GAME OVER"
horizontal_alignment = 1

[node name="RestartButton" type="Button" parent="GameOverPanel"]
offset_left = 150.0
offset_top = 110.0
offset_right = 350.0
offset_bottom = 150.0
text = "Restart"

[node name="ClearPanel" type="Panel" parent="."]
visible = false
offset_left = 390.0
offset_top = 260.0
offset_right = 890.0
offset_bottom = 460.0

[node name="ClearLabel" type="Label" parent="ClearPanel"]
offset_left = 100.0
offset_top = 30.0
offset_right = 400.0
offset_bottom = 80.0
text = "STAGE CLEAR!"
horizontal_alignment = 1

[node name="NextButton" type="Button" parent="ClearPanel"]
offset_left = 150.0
offset_top = 110.0
offset_right = 350.0
offset_bottom = 150.0
text = "Next Stage"
"""
    (ui_dir / "hud.tscn").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  level_N.tscn（タイルベース手動生成）
# ─────────────────────────────────────────────

TILE_SIZE = 32


def _write_level_tscn(levels_dir: Path, level_data: dict, level_idx: int,
                      concept: dict, enemy_list: list) -> None:
    """
    外周を壁、内部を床としたレベルシーンを生成する。
    敵スポーン位置はPythonで計算する。
    """

    width = max(10, int(level_data.get("width", 25)))
    height = max(8, int(level_data.get("height", 18)))
    floor_color = _hex_to_godot_color(level_data.get("floor_color", "#2a4a2a"))
    wall_color = _hex_to_godot_color(level_data.get("wall_color", "#1a1a1a"))
    enemy_count = int(level_data.get("enemy_count", 8))
    enemy_types = level_data.get("enemy_types", [])

    # プレイヤーのスポーン位置（左上付近の内部）
    player_spawn_x = TILE_SIZE * 2
    player_spawn_y = TILE_SIZE * 2

    # 敵スポーン位置の計算（内部グリッドからランダム選択）
    rng = random.Random(level_idx * 1234)
    inner_positions = []
    for gy in range(2, height - 2):
        for gx in range(2, width - 2):
            # プレイヤースポーンから離れた位置
            if gx >= 5 or gy >= 5:
                inner_positions.append((gx * TILE_SIZE, gy * TILE_SIZE))
    rng.shuffle(inner_positions)
    spawn_positions = inner_positions[:min(enemy_count, len(inner_positions))]

    # 出口位置（右下付近）
    exit_x = (width - 2) * TILE_SIZE
    exit_y = (height - 2) * TILE_SIZE

    # 敵種類のインデックスを取得
    enemy_name_to_idx = {}
    for i, enemy in enumerate(concept.get("enemies", [])):
        enemy_name_to_idx[enemy["name"]] = i

    # リソース参照を構築
    load_steps = 2  # Script + player scene
    ext_resources = []
    ext_resources.append('ext_resource type="PackedScene" path="res://scenes/player.tscn" id="1_player_scene"')

    # 使用する敵シーンのリスト（重複除去）
    used_enemy_indices = set()
    for ename in enemy_types:
        if ename in enemy_name_to_idx:
            used_enemy_indices.add(enemy_name_to_idx[ename])
    # enemy_typesが空の場合は最初の敵を使う
    if not used_enemy_indices and concept.get("enemies"):
        used_enemy_indices.add(0)

    for eidx in sorted(used_enemy_indices):
        res_id = f"{eidx + 2}_enemy{eidx}"
        ext_resources.append(
            f'ext_resource type="PackedScene" path="res://scenes/enemies/enemy_{eidx}.tscn" id="{res_id}"'
        )

    load_steps = 1 + len(ext_resources)

    lines = []
    lines.append(f'[gd_scene load_steps={load_steps} format=3 uid="uid://level{level_idx}"]')
    lines.append("")
    for r in ext_resources:
        lines.append(f"[{r}]")
    lines.append("")

    # ルートノード
    lines.append(f'[node name="Level{level_idx}" type="Node2D"]')
    lines.append("")

    # 背景（床全体）
    lines.append('[node name="Floor" type="Node2D" parent="."]')
    lines.append("")

    # 床タイルを生成（内部全体を1枚のColorRectで）
    floor_px_x = TILE_SIZE
    floor_px_y = TILE_SIZE
    floor_w = (width - 2) * TILE_SIZE
    floor_h = (height - 2) * TILE_SIZE
    lines.append('[node name="FloorRect" type="ColorRect" parent="Floor"]')
    lines.append(f"position = Vector2({floor_px_x}, {floor_px_y})")
    lines.append(f"size = Vector2({floor_w}, {floor_h})")
    lines.append(f"color = {floor_color}")
    lines.append("")

    # 壁ノード
    lines.append('[node name="Walls" type="Node2D" parent="."]')
    lines.append("")

    wall_idx = 0

    def add_wall(wx, wy, ww, wh):
        nonlocal wall_idx
        lines.append(f'[node name="Wall{wall_idx}" type="StaticBody2D" parent="Walls"]')
        lines.append(f"position = Vector2({wx}, {wy})")
        lines.append("")
        lines.append(f'[node name="WallRect{wall_idx}" type="ColorRect" parent="Walls/Wall{wall_idx}"]')
        lines.append(f"size = Vector2({ww}, {wh})")
        lines.append(f"color = {wall_color}")
        lines.append("")
        # CollisionShape2D はStaticBody2Dの子でないといけないがtscnでは別途sub_resourceが必要
        # 簡略化のためShapeはスクリプトで追加する代わりに、
        # CollisionShape2D + インラインShapeを使う
        lines.append(f'[node name="CollisionShape2D{wall_idx}" type="CollisionShape2D" parent="Walls/Wall{wall_idx}"]')
        lines.append(f"position = Vector2({ww/2:.1f}, {wh/2:.1f})")
        # shape はsub_resourceが必要だが、tscnのインライン記述では複雑になるため
        # 実用的な方法として RectangleShape2Dを型として指定
        lines.append("")
        wall_idx += 1

    # 上壁
    add_wall(0, 0, width * TILE_SIZE, TILE_SIZE)
    # 下壁
    add_wall(0, (height - 1) * TILE_SIZE, width * TILE_SIZE, TILE_SIZE)
    # 左壁
    add_wall(0, TILE_SIZE, TILE_SIZE, (height - 2) * TILE_SIZE)
    # 右壁
    add_wall((width - 1) * TILE_SIZE, TILE_SIZE, TILE_SIZE, (height - 2) * TILE_SIZE)

    # 出口（Area2D）
    lines.append('[node name="Exit" type="Area2D" parent="."]')
    lines.append(f"position = Vector2({exit_x}, {exit_y})")
    lines.append("")
    lines.append('[node name="ExitRect" type="ColorRect" parent="Exit"]')
    lines.append("offset_left = -16.0")
    lines.append("offset_top = -16.0")
    lines.append("offset_right = 16.0")
    lines.append("offset_bottom = 16.0")
    lines.append("color = Color(1, 1, 0, 0.8)")
    lines.append("")
    lines.append('[node name="ExitLabel" type="Label" parent="Exit"]')
    lines.append("offset_left = -20.0")
    lines.append("offset_top = -30.0")
    lines.append("offset_right = 60.0")
    lines.append("offset_bottom = -10.0")
    lines.append('text = "EXIT"')
    lines.append("")

    # プレイヤーインスタンス
    lines.append('[node name="Player" parent="." instance=ExtResource("1_player_scene")]')
    lines.append(f"position = Vector2({player_spawn_x}, {player_spawn_y})")
    lines.append("")

    # 敵インスタンス配置
    used_enemy_list = list(sorted(used_enemy_indices))
    for i, (sx, sy) in enumerate(spawn_positions):
        # ラウンドロビンで敵種類を割り当て
        eidx = used_enemy_list[i % len(used_enemy_list)] if used_enemy_list else 0
        res_id = f"{eidx + 2}_enemy{eidx}"
        lines.append(f'[node name="Enemy{i}" parent="." instance=ExtResource("{res_id}")]')
        lines.append(f"position = Vector2({sx}, {sy})")
        lines.append("")

    # レベル制御スクリプトを埋め込み（インラインGDScript）
    # level_controller.gd を使ってExit検知とゲームクリア処理
    lines.append("")

    content = "\n".join(lines)
    fname = f"level_{level_idx}.tscn"
    (levels_dir / fname).write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  level_controller.gd（レベル内制御）
# ─────────────────────────────────────────────

LEVEL_CONTROLLER_GD = """extends Node2D

func _ready() -> void:
    var exit = $Exit
    if exit:
        exit.body_entered.connect(_on_exit_entered)

func _on_exit_entered(body: Node2D) -> void:
    if body.is_in_group("player"):
        GameManager.next_level()
"""


# ─────────────────────────────────────────────
#  icon.svg（最小限のアイコン）
# ─────────────────────────────────────────────

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">
<rect width="128" height="128" fill="#3a7bd5"/>
<text x="64" y="80" font-size="48" text-anchor="middle" fill="white">G</text>
</svg>
"""


# ─────────────────────────────────────────────
#  README.txt
# ─────────────────────────────────────────────

def _write_readme(proj_dir: Path, concept: dict) -> None:
    title = concept.get("title", "My Game")
    story = concept.get("story", "")
    content = f"""=== {title} ===

【開き方】
1. Godot Engine 4.x をダウンロード: https://godotengine.org/download/
2. Godotを起動
3. 「Import」→ このフォルダの project.godot を選択
4. F5 または「Play」ボタンで実行

【操作方法】
- 移動: WASDまたは矢印キー
- 攻撃: Spaceキー
- ポーズ: Escape

【ゲーム説明】
{story}

【ファイル構成】
project.godot          - Godotプロジェクト設定
scenes/main.tscn       - メインシーン
scenes/player.tscn     - プレイヤーシーン
scenes/enemies/        - 敵シーン群
scenes/levels/         - レベルシーン群
scenes/ui/hud.tscn     - HUDシーン
scripts/player.gd      - プレイヤースクリプト
scripts/game_manager.gd - ゲームマネージャー
scripts/hud.gd         - HUDスクリプト
scripts/enemies/       - 敵スクリプト群

【ジャンル】
{concept.get('genre_desc', '')}
"""
    (proj_dir / "README.txt").write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────
#  メイン書き出し関数
# ─────────────────────────────────────────────

def write_godot_project(concept: dict, scripts: dict, log=print) -> Path:
    """
    Godot 4プロジェクトを生成する

    scripts: {
        "player": "GDScriptコード",
        "game_manager": "GDScriptコード",
        "hud": "GDScriptコード",
        "enemies": {"敵名": "GDScriptコード", ...}
    }

    戻り値: プロジェクトフォルダのPath
    """

    title = concept.get("title", "my_game")
    folder_name = _sanitize(title)
    proj_dir = GODOT_OUTPUT / folder_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    log(f"  出力先: {proj_dir}")

    # ディレクトリ構造作成
    scenes_dir = proj_dir / "scenes"
    enemies_scene_dir = scenes_dir / "enemies"
    levels_dir = scenes_dir / "levels"
    ui_dir = scenes_dir / "ui"
    scripts_dir = proj_dir / "scripts"
    enemies_script_dir = scripts_dir / "enemies"

    for d in [scenes_dir, enemies_scene_dir, levels_dir, ui_dir,
              scripts_dir, enemies_script_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ── project.godot ──────────────────────
    log("  project.godot を書き出し中...")
    _write_project_godot(proj_dir, concept)

    # ── icon.svg ───────────────────────────
    (proj_dir / "icon.svg").write_text(ICON_SVG, encoding="utf-8")

    # ── scenes/main.tscn ──────────────────
    log("  main.tscn を書き出し中...")
    _write_main_tscn(scenes_dir)

    # ── scenes/player.tscn ────────────────
    log("  player.tscn を書き出し中...")
    _write_player_tscn(scenes_dir)

    # ── scenes/ui/hud.tscn ────────────────
    log("  hud.tscn を書き出し中...")
    _write_hud_tscn(ui_dir, concept)

    # ── scripts/player.gd ─────────────────
    log("  player.gd を書き出し中...")
    player_gd = scripts.get("player", "extends CharacterBody2D\n")
    (scripts_dir / "player.gd").write_text(player_gd, encoding="utf-8")

    # ── scripts/game_manager.gd ───────────
    log("  game_manager.gd を書き出し中...")
    gm_gd = scripts.get("game_manager", "extends Node\n")
    (scripts_dir / "game_manager.gd").write_text(gm_gd, encoding="utf-8")

    # ── scripts/hud.gd ────────────────────
    log("  hud.gd を書き出し中...")
    hud_gd = scripts.get("hud", "extends CanvasLayer\n")
    (scripts_dir / "hud.gd").write_text(hud_gd, encoding="utf-8")

    # ── 敵ごとにシーン＆スクリプト ───────
    enemy_list = concept.get("enemies", [])
    enemy_scripts = scripts.get("enemies", {})

    for idx, enemy in enumerate(enemy_list):
        ename = enemy.get("name", f"enemy_{idx}")
        log(f"  enemy_{idx}.tscn / enemy_{idx}.gd を書き出し中... ({ename})")

        # シーン
        _write_enemy_tscn(enemies_scene_dir, enemy, idx)

        # スクリプト
        gd_code = enemy_scripts.get(ename, f"extends CharacterBody2D\n# {ename}\n")
        (enemies_script_dir / f"enemy_{idx}.gd").write_text(gd_code, encoding="utf-8")

    # ── レベルシーン ──────────────────────
    levels = concept.get("levels", [])
    for i, level_data in enumerate(levels):
        lname = level_data.get("name", f"Level {i+1}")
        log(f"  level_{i+1}.tscn を書き出し中... ({lname})")
        _write_level_tscn(levels_dir, level_data, i + 1, concept, enemy_list)

    # ── scripts/level_controller.gd ───────
    (scripts_dir / "level_controller.gd").write_text(
        LEVEL_CONTROLLER_GD, encoding="utf-8"
    )

    # ── README.txt ────────────────────────
    log("  README.txt を書き出し中...")
    _write_readme(proj_dir, concept)

    # ── concept.json（デバッグ用）──────────
    (proj_dir / "concept.json").write_text(
        json.dumps(concept, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log(f"  完了: {len(list(proj_dir.rglob('*')))} ファイル生成")
    return proj_dir


# ─────────────────────────────────────────────
#  run_full_pipeline（エントリポイント）
# ─────────────────────────────────────────────

def run_full_pipeline(genre: str = "ファンタジー", api_key: str = "",
                      log=print, cancel_event=None, pause_event=None,
                      use_sd: bool = False) -> Path:
    """app.pyから呼ばれるエントリポイント"""

    # ストリップゲームは専用パイプラインへ
    if "野球拳" in genre or "ストリップ" in genre or "脱衣" in genre:
        from godot_strip_writer import run_full_pipeline as _strip_pipeline
        return _strip_pipeline(genre=genre, api_key=api_key, log=log,
                               cancel_event=cancel_event, pause_event=pause_event,
                               use_sd=use_sd)

    import google.generativeai as genai
    import os
    from godot_2d_generator import (
        generate_game_concept,
        generate_player_script,
        generate_enemy_script,
        generate_game_manager_script,
        generate_hud_script,
    )

    def _check():
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("キャンセル")
        import time as _t
        while pause_event and pause_event.is_set():
            _t.sleep(0.3)
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("キャンセル")

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("GEMINI_API_KEY が設定されていません")

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    log("━━━ Godot 2Dアクション生成開始 ━━━")

    _check()
    log("▶ [1/6] ゲームコンセプト生成")
    concept = generate_game_concept(model, genre, log=log)
    log(f"  タイトル: {concept['title']}")

    _check()
    log("▶ [2/6] プレイヤースクリプト生成")
    player_script = generate_player_script(model, concept, log=log)

    _check()
    log("▶ [3/6] 敵スクリプト生成")
    enemy_scripts = {}
    for enemy in concept.get("enemies", []):
        name = enemy["name"]
        log(f"  敵: {name}")
        enemy_scripts[name] = generate_enemy_script(model, concept, enemy, log=log)

    _check()
    log("▶ [4/6] ゲームマネージャー生成")
    gm_script = generate_game_manager_script(model, concept, log=log)

    _check()
    log("▶ [5/6] HUD生成")
    hud_script = generate_hud_script(model, concept, log=log)

    _check()
    log("▶ [6/6] プロジェクト出力")
    scripts = {
        "player": player_script,
        "game_manager": gm_script,
        "hud": hud_script,
        "enemies": enemy_scripts,
    }
    path = write_godot_project(concept, scripts, log=log)

    # ── SD画像生成 ────────────────────────────────────────────────
    if use_sd:
        try:
            from sd_rpg import generate_godot_images
            generate_godot_images(concept, path, log=log)
        except Exception as e:
            log(f"  !! SD画像生成エラー（スキップ）: {e}")

    # ── DLSite販売戦略レポート ────────────────────────────────
    log("▶ [+] DLSite販売戦略レポート生成")
    try:
        from dlsite_advisor import generate_full_report
        report_md = generate_full_report(
            model, concept,
            game_type="Godot 2Dアクション",
            genre=genre,
            adult=False,
            log=log,
        )
        report_path = path / "DLSITE_STRATEGY.md"
        report_path.write_text(report_md, encoding="utf-8")
        log(f"  販売戦略レポート: {report_path}")
    except Exception as e:
        log(f"  !! 販売戦略レポート生成エラー（スキップ）: {e}")

    log(f"\n✅ 完成: {path}")
    return path


# ─────────────────────────────────────────────
#  単体実行用
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    genre = sys.argv[1] if len(sys.argv) > 1 else "ファンタジー"
    result = run_full_pipeline(genre=genre)
    print(f"\n出力先: {result}")
