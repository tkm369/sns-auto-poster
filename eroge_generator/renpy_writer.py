"""
Ren'Py プロジェクトファイルの出力（eroge_generator用）
"""
import json
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"


def write_project(concept: dict, char_defs: str, scenes: list,
                  art_style: dict, assets: dict) -> Path:
    """Ren'Py プロジェクト一式を output/ に書き出す"""
    title = concept["title"]
    game_dir = OUTPUT_DIR / title
    (game_dir / "game" / "images").mkdir(parents=True, exist_ok=True)
    (game_dir / "assets").mkdir(exist_ok=True)

    _write_script(game_dir, title, char_defs, scenes)
    _write_options(game_dir, title)
    _copy_gui_template(game_dir)
    _write_concept(game_dir, concept)
    _write_assets(game_dir, assets, art_style)
    _write_readme(game_dir, concept, art_style, assets)

    print(f"  -> game/script.rpy")
    print(f"  -> game/options.rpy")
    print(f"  -> concept.json")
    print(f"  -> assets/  ({art_style['name']}用素材情報)")
    print(f"  -> README.md")
    return game_dir


# ── script.rpy ──────────────────────────────────────────────────
def _write_script(game_dir: Path, title: str, char_defs: str, scenes: list):
    lines = [
        f"# {title}",
        "# 自動生成: eroge_generator",
        "",
        char_defs,
        "",
        "label start:",
        "    scene bg_title with fade",
        f'    narrator "{title}"',
        "    jump scene_1",
        "",
    ]
    for i, scene in enumerate(scenes, 1):
        # カーリークォート → ストレートクォート（Ren'Py は " のみ認識）
        fixed = scene.replace('\u201c', '"').replace('\u201d', '"')
        fixed = fixed.replace('\u2018', "'").replace('\u2019', "'")
        # Ren'Py構文修正: label なし scene_N: を label scene_N: に
        fixed = re.sub(r'^(?!.*\blabel\b)scene_(\d+):', lambda m: f'label scene_{m.group(1)}:', fixed, flags=re.MULTILINE)
        # AI が次シーンを先走り生成した場合は truncate
        next_label = re.search(rf'^label scene_{i + 1}:', fixed, re.MULTILINE)
        if next_label:
            fixed = fixed[:next_label.start()]
        # at center right / at center left → 単一position
        fixed = re.sub(r'\bat center (right|left)\b', r'at \1', fixed)
        fixed = re.sub(r'\bat (right|left) center\b', r'at \1', fixed)
        fixed = re.sub(r'\bclose to (left|right|center)\b', r'at \1', fixed)
        # fadein/fadeout は with dissolve に
        fixed = re.sub(r'(at (?:left|right|center))\s+fade(?:in|out)', r'\1 with dissolve', fixed)
        # show narrator（無効）を削除
        fixed = re.sub(r'\n\s*show narrator \S+(?: at \S+)?(?: with \S+)?\n', '\n', fixed)
        # show bg_XXX → scene bg_XXX
        fixed = re.sub(r'^(\s*)show (bg_\w+)', r'\1scene \2', fixed, flags=re.MULTILINE)
        lines.append(fixed)
        if i < len(scenes):
            if f"jump scene_{i + 1}" not in fixed:
                lines.append(f"\njump scene_{i + 1}")
        else:
            lines.append("\nreturn")
        lines.append("")
    (game_dir / "game" / "script.rpy").write_text("\n".join(lines), encoding="utf-8")


# ── options.rpy（Ren'Py 8.x形式） ────────────────────────────────
def _write_options(game_dir: Path, title: str):
    # save_directory は英数字のみ
    save_dir = re.sub(r'[^\w]', '_', title)[:40]
    text = f"""define config.name = "{title}"

define gui.show_name = True

define config.version = "1.0"

define gui.about = _("")

define config.save_directory = "{save_dir}"

define config.window_icon = "gui/window_icon.png"

define config.has_sound = True
define config.has_music = True
define config.has_voice = False

define config.screen_width = 1280
define config.screen_height = 720
"""
    (game_dir / "game" / "options.rpy").write_text(text, encoding="utf-8")


# ── Ren'Py GUI テンプレートをコピー ────────────────────────────────
def _copy_gui_template(game_dir: Path):
    """Ren'Py SDK の the_question からGUI基本ファイルをコピー"""
    import shutil
    sdk_paths = [
        Path(__file__).parent.parent / "renpy-8.5.2-sdk",        # ai-project/renpy-8.5.2-sdk
        Path(__file__).parent.parent.parent / "renpy-8.5.2-sdk", # Desktop/renpy-8.5.2-sdk（旧パス）
        Path.home() / "Desktop" / "renpy-8.5.2-sdk",
    ]
    for sdk in sdk_paths:
        template = sdk / "the_question" / "game"
        if template.exists():
            for fname in ("gui.rpy", "screens.rpy"):
                src = template / fname
                dst = game_dir / "game" / fname
                if src.exists() and not dst.exists():
                    shutil.copy2(src, dst)
            gui_src = template / "gui"
            gui_dst = game_dir / "game" / "gui"
            if gui_src.exists() and not gui_dst.exists():
                shutil.copytree(gui_src, gui_dst)
            return True
    return False


# ── concept.json ─────────────────────────────────────────────────
def _write_concept(game_dir: Path, concept: dict):
    (game_dir / "concept.json").write_text(
        json.dumps(concept, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── アート素材ファイル（2D / 3D で内容を切り替え） ──────────────────
def _write_assets(game_dir: Path, assets: dict, art_style: dict):
    assets_dir = game_dir / "assets"

    if assets["mode"] == "2d":
        _write_2d_assets(assets_dir, assets)
    else:
        _write_3d_assets(assets_dir, assets)


def _write_2d_assets(assets_dir: Path, assets: dict):
    """2D: キャラ別SDプロンプト + 背景プロンプトを markdown で出力"""
    lines = ["# Stable Diffusion / NovelAI 画像生成プロンプト集", ""]

    # キャラクタースプライト
    lines.append("## キャラクタースプライト\n")
    for char in assets.get("characters", []):
        lines.append(f"### {char['name']}（変数名: `{char['var_name']}`）\n")
        for expr, data in char.get("expressions", {}).items():
            lines.append(f"#### 表情: {expr}")
            lines.append(f"- **Positive**: `{data.get('positive', '')}`")
            lines.append(f"- **Negative**: `{data.get('negative', '')}`")
            lines.append(f"- **ファイル名**: `{char['var_name']}_{expr}.png`\n")

    # 背景
    lines.append("## 背景\n")
    for bg in assets.get("backgrounds", []):
        lines.append(f"### {bg.get('label', bg.get('name', ''))} (`{bg.get('name', '')}.png`)")
        lines.append(f"- **Positive**: `{bg.get('positive', '')}`")
        lines.append(f"- **Negative**: `{bg.get('negative', '')}`\n")

    lines.append("---\n> 上記プロンプトを Stable Diffusion WebUI / NovelAI に貼り付けて画像を生成し、")
    lines.append("> `game/images/` フォルダに配置してください。")

    (assets_dir / "sd_prompts.md").write_text("\n".join(lines), encoding="utf-8")
    # JSONも保存
    (assets_dir / "sd_prompts.json").write_text(
        json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_3d_assets(assets_dir: Path, assets: dict):
    """3D: Koikatsu/VRM向けキャラ設定JSON + 使い方ガイドを出力"""
    # キャラ設定JSON
    (assets_dir / "characters_3d.json").write_text(
        json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 使い方ガイド（Markdown）
    lines = ["# 3Dキャラクター設定ガイド", ""]
    for char in assets.get("characters", []):
        lines.append(f"## {char['name']}（`{char['var_name']}`）\n")
        body = char.get("body", {})
        lines.append(f"| 項目 | 設定値 |")
        lines.append(f"|------|--------|")
        for k, v in body.items():
            lines.append(f"| {k} | {v} |")
        lines.append("")
        lines.append(f"**デフォルト衣装**: {char.get('outfit_default', {}).get('description', '')}")
        for item in char.get('outfit_default', {}).get('items', []):
            lines.append(f"  - {item}")
        lines.append("")
        lines.append(f"**Koikatsu ヒント**: {char.get('koikatsu_tips', '')}\n")
        lines.append(f"**SD 3Dプロンプト**: `{char.get('sd_prompt_3d', '')}`\n")
        lines.append("---\n")

    lines.append("## 背景シーン\n")
    for bg in assets.get("backgrounds", []):
        lines.append(f"### {bg.get('label', '')} (`{bg.get('name', '')}`)")
        lines.append(f"- 照明: {bg.get('lighting', '')}")
        lines.append(f"- 雰囲気: {bg.get('atmosphere', '')}")
        lines.append(f"- SDプロンプト: `{bg.get('sd_prompt', '')}`")
        lines.append(f"- Unityヒント: {bg.get('unity_notes', '')}\n")

    lines.append("---")
    lines.append("> **Koikatsu Party**: 各キャラの設定値を参考にキャラメイク画面でスライダーを調整してください。")
    lines.append("> **VRM / DAZ3D**: `characters_3d.json` のパラメータを参照してください。")

    (assets_dir / "3d_guide.md").write_text("\n".join(lines), encoding="utf-8")


# ── README.md ────────────────────────────────────────────────────
def _write_readme(game_dir: Path, concept: dict, art_style: dict, assets: dict):
    title = concept["title"]
    heroine_info = "\n".join(
        f"- **{h['name']}**（{h['role']}）: {h['personality']}"
        for h in concept["heroines"]
    )

    if assets["mode"] == "2d":
        asset_section = """## 画像素材について（2D）
`assets/sd_prompts.md` に各キャラ・背景の Stable Diffusion プロンプトが入っています。
1. [Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) または [NovelAI](https://novelai.net/) を使用
2. プロンプトをコピーして画像を生成
3. `game/images/` に配置（ファイル名は sd_prompts.md を参照）"""
    else:
        asset_section = """## 画像素材について（3D）
`assets/3d_guide.md` にキャラクター設定・背景シーンの詳細があります。
1. **Koikatsu Party** / **VRM** / **DAZ3D** でキャラを作成
2. `assets/characters_3d.json` のパラメータを参照
3. レンダリングした画像を `game/images/` に配置"""

    readme = f"""# {title}

> {concept.get('tagline', '')}

自動生成された Ren'Py ビジュアルノベルです。
アートスタイル: **{art_style['name']}**

## キャラクター
- **{concept['protagonist']['name']}**（主人公）: {concept['protagonist']['description']}
{heroine_info}

## 実行方法
1. [Ren'Py SDK](https://www.renpy.org/) をダウンロード（無料）
2. このフォルダを Ren'Py ランチャーで開く
3. **Launch Project** をクリック

{asset_section}

画像なしでも台詞テキストは動作します。
"""
    (game_dir / "README.md").write_text(readme, encoding="utf-8")
