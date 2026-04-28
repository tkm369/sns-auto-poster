# -*- coding: utf-8 -*-
"""
project_editor.py — 生成済みゲームプロジェクトの修正・編集モジュール

サポートするプロジェクトタイプ:
  - RPGツクールMZ  (data/*.json)
  - ビジュアルノベル (game/*.rpy)
  - Godot          (*.gd, *.tscn)
"""
from __future__ import annotations
import json, re, time
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# プロジェクト検出
# ──────────────────────────────────────────────────────────────────

def detect_project(path: str) -> dict:
    """
    フォルダパスからプロジェクトタイプを判定して情報を返す。
    Returns:
      {
        "type":  "rpg" | "vn" | "godot" | "unknown",
        "title": str,
        "path":  Path,
        "files": { カテゴリ名: [(label, rel_path), ...] }
      }
    """
    p = Path(path.strip())
    if not p.exists():
        return {"type": "unknown", "title": "フォルダが見つかりません", "path": p, "files": {}}

    # ── RPGツクールMZ
    data_dir = p / "data"
    if (data_dir / "System.json").exists():
        return _rpg_project(p, data_dir)

    # ── ビジュアルノベル (Ren'Py)
    game_dir = p / "game"
    if game_dir.exists() and list(game_dir.glob("*.rpy")):
        return _vn_project(p, game_dir)

    # ── Godot
    if (p / "project.godot").exists():
        return _godot_project(p)

    return {"type": "unknown", "title": "不明なプロジェクト", "path": p, "files": {}}


def _rpg_project(p: Path, data_dir: Path) -> dict:
    try:
        sys = json.loads((data_dir / "System.json").read_text(encoding="utf-8"))
        title = sys.get("gameTitle", "RPGプロジェクト")
    except Exception:
        title = "RPGプロジェクト"

    files = {
        "🎮 ゲーム設定": [
            ("ゲームタイトル・基本設定",    "data/System.json"),
        ],
        "👥 キャラクター": [
            ("アクター（主人公・仲間）",     "data/Actors.json"),
            ("クラス",                      "data/Classes.json"),
        ],
        "⚔️ バトルデータ": [
            ("敵キャラクター",              "data/Enemies.json"),
            ("スキル",                      "data/Skills.json"),
            ("アイテム",                    "data/Items.json"),
            ("武器",                        "data/Weapons.json"),
            ("防具",                        "data/Armors.json"),
            ("敵グループ（トループ）",       "data/Troops.json"),
        ],
        "🗺️ マップ・イベント": [],
        "📖 その他": [],
    }

    # マップファイル一覧
    map_files = sorted(data_dir.glob("Map[0-9]*.json"))
    for mf in map_files:
        try:
            md = json.loads(mf.read_text(encoding="utf-8"))
            name = md.get("displayName") or mf.stem
        except Exception:
            name = mf.stem
        files["🗺️ マップ・イベント"].append((f"マップ: {name}", f"data/{mf.name}"))

    # MapInfos
    if (data_dir / "MapInfos.json").exists():
        files["📖 その他"].append(("マップ情報一覧", "data/MapInfos.json"))
    # CommonEvents
    if (data_dir / "CommonEvents.json").exists():
        files["📖 その他"].append(("コモンイベント", "data/CommonEvents.json"))

    # 空カテゴリ削除
    files = {k: v for k, v in files.items() if v}

    return {"type": "rpg", "title": title, "path": p, "files": files}


def _vn_project(p: Path, game_dir: Path) -> dict:
    files = {"📝 スクリプト": [], "🖼️ 画像": [], "🎵 その他": []}
    for rpy in sorted(game_dir.glob("*.rpy")):
        files["📝 スクリプト"].append((rpy.name, f"game/{rpy.name}"))
    for img in sorted((game_dir / "images").glob("**/*") if (game_dir / "images").exists() else []):
        if img.suffix.lower() in (".png", ".jpg", ".webp"):
            files["🖼️ 画像"].append((img.name, str(img.relative_to(p))))
    files = {k: v for k, v in files.items() if v}
    title_rpy = game_dir / "script.rpy"
    title = "ビジュアルノベル"
    if title_rpy.exists():
        m = re.search(r'define\s+config\.name\s*=\s*["\'](.+?)["\']',
                      title_rpy.read_text(encoding="utf-8", errors="ignore"))
        if m:
            title = m.group(1)
    return {"type": "vn", "title": title, "path": p, "files": files}


def _godot_project(p: Path) -> dict:
    files = {"📜 スクリプト": [], "🎬 シーン": []}
    for gd in sorted(p.rglob("*.gd")):
        rel = str(gd.relative_to(p))
        files["📜 スクリプト"].append((gd.name, rel))
    for tscn in sorted(p.rglob("*.tscn")):
        rel = str(tscn.relative_to(p))
        files["🎬 シーン"].append((tscn.name, rel))
    files = {k: v for k, v in files.items() if v}
    title = "Godotプロジェクト"
    cfg = p / "project.godot"
    if cfg.exists():
        m = re.search(r'config/name="(.+?)"', cfg.read_text(encoding="utf-8", errors="ignore"))
        if m:
            title = m.group(1)
    return {"type": "godot", "title": title, "path": p, "files": files}


# ──────────────────────────────────────────────────────────────────
# ファイル読み込み
# ──────────────────────────────────────────────────────────────────

def load_file(project_path: str, rel_path: str) -> str:
    """ファイルを読み込んで表示用テキストを返す"""
    p = Path(project_path) / rel_path
    if not p.exists():
        return f"# ファイルが見つかりません: {p}"

    text = p.read_text(encoding="utf-8", errors="replace")

    # JSONの場合は整形して返す（ただし大きすぎる場合は要約）
    if p.suffix == ".json":
        try:
            data = json.loads(text)
            return _json_to_readable(data, p.name)
        except Exception:
            pass

    return text


def _json_to_readable(data, filename: str) -> str:
    """JSON データを人間が読みやすい形式に変換"""
    lines = [f"# {filename}"]

    if filename == "System.json" and isinstance(data, dict):
        lines += [
            f"gameTitle: {data.get('gameTitle', '')}",
            f"currency: {data.get('currency', 'G')}",
        ]
        return "\n".join(lines)

    if isinstance(data, list):
        for item in data:
            if item is None:
                continue
            if isinstance(item, dict):
                parts = []
                for k in ("id", "name", "note", "description", "profile",
                          "message1", "message2", "message3", "message4"):
                    v = item.get(k)
                    if v:
                        parts.append(f"  {k}: {v}")
                if parts:
                    lines.append("")
                    lines += parts
        return "\n".join(lines)

    # フォールバック: 生JSON（最大8000文字）
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    return raw[:8000] + ("\n... (省略)" if len(raw) > 8000 else "")


# ──────────────────────────────────────────────────────────────────
# ファイル保存
# ──────────────────────────────────────────────────────────────────

def save_file(project_path: str, rel_path: str, content: str) -> str:
    """編集済みコンテンツをファイルに保存する"""
    p = Path(project_path) / rel_path
    if not p.exists():
        return f"❌ ファイルが見つかりません: {p}"

    # JSONファイルの場合は valid JSON か確認
    if p.suffix == ".json":
        # 人間が読みやすい形式で書いた場合はそのまま保存（元のJSONを一部置換）
        # → readable形式を逆変換せず、JSONとしてパースできるか試みる
        try:
            json.loads(content)
            # valid JSON → そのまま保存
            p.write_text(content, encoding="utf-8")
            return f"✅ 保存しました: {p.name}"
        except Exception:
            # readable形式 → 元JSONに部分適用
            result = _apply_readable_edits(p, content)
            return result

    # テキストファイル
    p.write_text(content, encoding="utf-8")
    return f"✅ 保存しました: {p.name}"


def _apply_readable_edits(json_path: Path, readable: str) -> str:
    """
    readable形式（_json_to_readable の出力）で編集されたテキストを
    元のJSONに差分適用する。
    対応: name, note, description, profile, gameTitle 等の文字列フィールド。
    """
    try:
        original = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"❌ 元JSONの読み込み失敗: {e}"

    # System.json
    if json_path.name == "System.json" and isinstance(original, dict):
        for line in readable.splitlines():
            for key in ("gameTitle", "currency"):
                if line.startswith(f"{key}:"):
                    val = line[len(key)+1:].strip()
                    original[key] = val
        json_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"✅ 保存しました: {json_path.name}"

    # リスト系 (Actors, Skills 等) — name/note/description 等を更新
    if isinstance(original, list):
        # readable テキストからブロックを解析
        current_id = None
        edits: dict[int, dict] = {}
        for line in readable.splitlines():
            line = line.rstrip()
            m = re.match(r'\s+id:\s*(\d+)', line)
            if m:
                current_id = int(m.group(1))
                edits[current_id] = {}
                continue
            if current_id is not None:
                for key in ("name", "note", "description", "profile",
                            "message1", "message2", "message3", "message4"):
                    if re.match(rf'\s+{key}:', line):
                        val = line.split(":", 1)[1].strip()
                        edits[current_id][key] = val

        changed = 0
        for item in original:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if item_id in edits:
                for k, v in edits[item_id].items():
                    if k in item:
                        item[k] = v
                        changed += 1

        json_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"✅ 保存しました: {json_path.name}（{changed}箇所更新）"

    return f"❌ このファイル形式の保存には完全なJSONを貼り付けてください"


# ──────────────────────────────────────────────────────────────────
# AI による再生成・修正
# ──────────────────────────────────────────────────────────────────

def ai_edit(project_path: str, rel_path: str, current_content: str,
            instruction: str, api_key: str, log=print) -> str:
    """
    現在のコンテンツと指示文を Gemini に渡して書き直した内容を返す。
    Returns: 新しいコンテンツ文字列（エラー時はエラーメッセージ）
    """
    import google.generativeai as genai

    p = Path(project_path) / rel_path
    file_type = _infer_file_type(p)

    system = f"""あなたはゲーム開発のエキスパートです。
ゲームファイルの内容を、ユーザーの指示に従って修正してください。

ファイル: {p.name}
ファイルタイプ: {file_type}

ルール:
- 指示された箇所だけを変更し、それ以外は元の内容を保持する
- フォーマット（インデント、構造）は元と同じにする
- 日本語で出力する
- 修正後の内容だけを出力する（説明文・コメントは不要）
- R18コンテンツOK（エロゲプロジェクトです）
- キャラクターの年齢は18歳以上にする"""

    prompt = f"""{system}

## 現在の内容
{current_content[:6000]}

## 修正指示
{instruction}

## 修正後の内容（修正後のテキストのみ出力）"""

    log(f"  [AI編集] {p.name} を修正中...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    for attempt in range(3):
        try:
            result = []
            for chunk in model.generate_content(prompt, stream=True,
                                                request_options={"timeout": 60}):
                result.append(chunk.text or "")
            text = "".join(result).strip()
            log(f"  [AI編集] 完了")
            return text
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
            else:
                return f"❌ AI生成エラー: {e}"


def _infer_file_type(p: Path) -> str:
    name = p.name.lower()
    if name == "actors.json":   return "RPGツクールMZ アクターデータ (JSON)"
    if name == "enemies.json":  return "RPGツクールMZ 敵データ (JSON)"
    if name == "skills.json":   return "RPGツクールMZ スキルデータ (JSON)"
    if name == "items.json":    return "RPGツクールMZ アイテムデータ (JSON)"
    if name == "weapons.json":  return "RPGツクールMZ 武器データ (JSON)"
    if name == "armors.json":   return "RPGツクールMZ 防具データ (JSON)"
    if name == "troops.json":   return "RPGツクールMZ 敵グループデータ (JSON)"
    if name == "system.json":   return "RPGツクールMZ システム設定 (JSON)"
    if name.startswith("map") and name.endswith(".json"):
        return "RPGツクールMZ マップデータ (JSON) — イベント・台詞を含む"
    if name == "commonevents.json": return "RPGツクールMZ コモンイベント (JSON)"
    if p.suffix == ".rpy":      return "Ren'Py スクリプト (Python風DSL)"
    if p.suffix == ".gd":       return "GDScript (Godot)"
    if p.suffix == ".tscn":     return "Godot シーンファイル"
    return p.suffix


# ──────────────────────────────────────────────────────────────────
# 画像再生成（SD Forge）
# ──────────────────────────────────────────────────────────────────

def regenerate_image(image_path: str, new_prompt: str,
                     apply_mosaic: bool = True, mosaic_block: int = 15,
                     log=print) -> str:
    """
    指定した画像を新しいプロンプトで再生成してファイルを上書きする。
    Returns: 結果メッセージ
    """
    from sd_client import txt2img, is_available, COMMON_NEGATIVE, QUALITY_PREFIX, SCORE_TAGS

    if not is_available():
        return "❌ SD Forge が起動していません (http://localhost:7860)"

    p = Path(image_path)
    if not p.exists():
        return f"❌ ファイルが見つかりません: {p}"

    # 画像サイズを元画像から取得
    try:
        from PIL import Image as _PIL
        with _PIL.open(p) as img:
            w, h = img.size
    except Exception:
        w, h = 832, 1216  # デフォルト

    positive = f"score_9, score_8_up, {QUALITY_PREFIX}, {new_prompt}"
    log(f"  [再生成] {p.name} ({w}x{h}) ...")

    try:
        png, seed = txt2img(
            positive, COMMON_NEGATIVE,
            width=w, height=h,
            steps=30, cfg=7.0,
            hires=False,
            apply_mosaic=apply_mosaic,
            mosaic_block=mosaic_block,
        )
        p.write_bytes(png)
        log(f"  [再生成] 完了 → {p.name} (seed={seed})")
        return f"✅ 再生成完了: {p.name}"
    except Exception as e:
        return f"❌ SD生成エラー: {e}"


# ──────────────────────────────────────────────────────────────────
# ファイルツリーをフラットなドロップダウン用リストに変換
# ──────────────────────────────────────────────────────────────────

def files_to_choices(project_files: dict) -> list[str]:
    """{ カテゴリ: [(label, rel_path), ...] } → ["カテゴリ / label", ...] のリスト"""
    choices = []
    for cat, items in project_files.items():
        for label, rel in items:
            choices.append(f"{cat} / {label}")
    return choices


def choice_to_rel_path(choice: str, project_files: dict) -> str | None:
    """choices の文字列から rel_path を逆引き"""
    for cat, items in project_files.items():
        for label, rel in items:
            if f"{cat} / {label}" == choice:
                return rel
    return None
