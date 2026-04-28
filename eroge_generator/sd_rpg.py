"""
sd_rpg.py
RPGツクールMZ / Godot 向けのSD Forge画像生成モジュール
"""
from pathlib import Path
from sd_client import (
    txt2img, is_available, auto_start as sd_auto_start,
    _get_model_type, _quality_positive, COMMON_NEGATIVE,
)

# ── RPGツクールMZ 画像サイズ ─────────────────────────────────────
TITLE_W,     TITLE_H     = 816, 624   # タイトル画面
BATTLEBACK_W, BATTLEBACK_H = 816, 624 # 戦闘背景
PICTURE_W,   PICTURE_H   = 816, 624   # イベント絵/CG

# ── Godot 画像サイズ ──────────────────────────────────────────────
GODOT_BG_W,  GODOT_BG_H  = 1280, 720  # 横長背景


def _safe(s: str) -> str:
    """ファイル名に使えない文字を除去"""
    return "".join(c for c in s if c not in r'\/:*?"<>| ').strip() or "image"


def _generate(positive: str, negative: str, width: int, height: int,
              steps: int = 28, log=print) -> bytes:
    """txt2imgを呼んでPNGバイト列を返す"""
    model_type = _get_model_type()
    pos = _quality_positive(positive, model_type)
    neg = negative or COMMON_NEGATIVE
    png, seed = txt2img(
        pos, neg,
        width=width, height=height,
        steps=steps, cfg=7.0,
        hires=False,
        use_adetailer=False,
    )
    log(f"    seed={seed}")
    return png


# ── タイトル画面 ──────────────────────────────────────────────────
def generate_title_screen(concept: dict, out_dir: Path, log=print) -> Path | None:
    """
    タイトル画面画像を生成して img/titles1/Game_Title.png に保存
    RPGツクールMZは titles1 フォルダの画像をタイトルBGとして使用する
    """
    titles_dir = out_dir / "img" / "titles1"
    titles_dir.mkdir(parents=True, exist_ok=True)

    title   = concept.get("title", "RPG")
    setting = concept.get("setting", "fantasy world")
    atm     = concept.get("atmosphere", "dark fantasy")

    log(f"  [SD] タイトル画面生成: 「{title}」")

    positive = (
        f"epic fantasy landscape, {setting}, {atm}, "
        f"dramatic lighting, cinematic, wide angle, "
        f"no humans, beautiful scenery, title screen art, "
        f"detailed environment, atmospheric, masterpiece"
    )
    negative = (
        "worst quality, low quality, text, watermark, "
        "people, character, portrait, anime, cartoon, "
        "ugly, deformed"
    )

    try:
        png = _generate(positive, negative, TITLE_W, TITLE_H, steps=30, log=log)
        out_path = titles_dir / "Game_Title.png"
        out_path.write_bytes(png)
        log(f"    -> {out_path.name}")
        return out_path
    except Exception as e:
        log(f"    !! タイトル画面生成失敗: {e}")
        return None


# ── 戦闘背景 ──────────────────────────────────────────────────────
def generate_battle_backgrounds(concept: dict, out_dir: Path, log=print) -> dict:
    """
    ダンジョン毎の戦闘背景を生成
    battlebacks1 = 床/地面レイヤー
    battlebacks2 = 壁/空レイヤー

    RPGツクールMZはこれら2枚を重ねて戦闘画面の背景にする
    """
    bb1_dir = out_dir / "img" / "battlebacks1"
    bb2_dir = out_dir / "img" / "battlebacks2"
    bb1_dir.mkdir(parents=True, exist_ok=True)
    bb2_dir.mkdir(parents=True, exist_ok=True)

    dungeons = concept.get("dungeons", [])
    if not dungeons:
        dungeons = [{"name": "Dungeon", "theme": "dark cave"}]

    saved = {}

    for dungeon in dungeons:
        dname = dungeon.get("name", "dungeon")
        theme = dungeon.get("theme", dungeon.get("description", "dark cave"))
        safe  = _safe(dname)

        log(f"  [SD] 戦闘背景生成: {dname}")

        # battlebacks1 = 床
        pos1 = (
            f"dungeon floor, {theme}, stone floor, cobblestone, "
            f"atmospheric lighting, rpg battle background, "
            f"top-down view of floor, dark dungeon, "
            f"detailed texture, no characters"
        )
        # battlebacks2 = 壁・遠景
        pos2 = (
            f"dungeon wall background, {theme}, cave wall, "
            f"atmospheric, rpg battle background, "
            f"dark atmospheric wall, torches, "
            f"detailed stone texture, no characters"
        )
        neg = (
            "worst quality, low quality, character, person, "
            "anime face, portrait, ui, hud, text"
        )

        try:
            png1 = _generate(pos1, neg, BATTLEBACK_W, BATTLEBACK_H, log=log)
            path1 = bb1_dir / f"{safe}_floor.png"
            path1.write_bytes(png1)
            log(f"    -> battlebacks1/{path1.name}")

            png2 = _generate(pos2, neg, BATTLEBACK_W, BATTLEBACK_H, log=log)
            path2 = bb2_dir / f"{safe}_wall.png"
            path2.write_bytes(png2)
            log(f"    -> battlebacks2/{path2.name}")

            saved[dname] = {"floor": str(path1), "wall": str(path2)}
        except Exception as e:
            log(f"    !! {dname} 戦闘背景生成失敗: {e}")

    return saved


# ── イベントCG/ピクチャー ─────────────────────────────────────────
def generate_event_pictures(concept: dict, out_dir: Path, log=print) -> dict:
    """
    ストーリーイベントCGを生成して img/pictures/ に保存
    RPGツクールMZの「ピクチャーの表示」コマンドで使用できる
    """
    pics_dir = out_dir / "img" / "pictures"
    pics_dir.mkdir(parents=True, exist_ok=True)

    party   = concept.get("party", [])
    setting = concept.get("setting", "fantasy world")
    saved   = {}

    # ヒロインのCGを生成（存在する場合）
    heroines = [m for m in party if m.get("gender") in ("female", "woman", "女")]
    if not heroines:
        # genderフィールドがない場合はパーティの最初の非主人公メンバー
        heroines = party[1:3] if len(party) > 1 else []

    for i, heroine in enumerate(heroines[:3]):  # 最大3人
        name = heroine.get("name", f"heroine_{i}")
        safe = _safe(name)
        appearance = heroine.get("appearance",
                     heroine.get("description", "beautiful young woman"))
        log(f"  [SD] イベントCG生成: {name}")

        # 一般シーン（立ち絵風CG）
        pos = (
            f"1girl, {appearance}, {setting}, "
            f"detailed face, beautiful detailed eyes, "
            f"indoor lighting, half body portrait, "
            f"visual novel cg, soft lighting, romantic"
        )
        neg = (
            "worst quality, low quality, bad anatomy, "
            "bad hands, extra fingers, deformed face, ugly"
        )

        try:
            png = _generate(pos, neg, PICTURE_W, PICTURE_H, steps=28, log=log)
            path = pics_dir / f"cg_{safe}_normal.png"
            path.write_bytes(png)
            log(f"    -> pictures/{path.name}")
            saved[name] = str(path)
        except Exception as e:
            log(f"    !! {name} CG生成失敗: {e}")

    # タイトルロゴなしの背景絵（オープニング用）
    log("  [SD] オープニング背景CG生成")
    pos_bg = (
        f"beautiful {setting}, wide establishing shot, "
        f"cinematic, detailed environment, atmospheric, "
        f"golden hour lighting, epic landscape, no people"
    )
    try:
        png = _generate(pos_bg, "", PICTURE_W, PICTURE_H, steps=28, log=log)
        path = pics_dir / "cg_opening_bg.png"
        path.write_bytes(png)
        log(f"    -> pictures/{path.name}")
        saved["opening_bg"] = str(path)
    except Exception as e:
        log(f"    !! オープニングBG生成失敗: {e}")

    return saved


# ── Godot背景 ─────────────────────────────────────────────────────
def generate_godot_backgrounds(concept: dict, out_dir: Path, log=print) -> dict:
    """
    Godotプロジェクトのレベル背景を生成
    assets/backgrounds/ に保存
    """
    bg_dir = out_dir / "assets" / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)

    levels  = concept.get("levels", [])
    setting = concept.get("setting", "fantasy world")
    genre   = concept.get("genre", "action")
    saved   = {}

    if not levels:
        levels = [{"name": "Stage 1", "description": setting}]

    for i, level in enumerate(levels[:5]):  # 最大5ステージ
        lname = level.get("name", f"level_{i+1}")
        ldesc = level.get("description", level.get("theme", setting))
        safe  = _safe(lname)

        log(f"  [SD] Godot背景生成: {lname}")

        pos = (
            f"2D game background, side scrolling, {ldesc}, "
            f"{genre} game, detailed background, "
            f"parallax background layer, no characters, "
            f"game art, vibrant colors, wide angle"
        )
        neg = (
            "worst quality, low quality, character, person, "
            "portrait, ui elements, text, logo"
        )

        try:
            png = _generate(pos, neg, GODOT_BG_W, GODOT_BG_H, steps=25, log=log)
            path = bg_dir / f"bg_{safe}.png"
            path.write_bytes(png)
            log(f"    -> assets/backgrounds/{path.name}")
            saved[lname] = str(path)
        except Exception as e:
            log(f"    !! {lname} 背景生成失敗: {e}")

    return saved


# ── メインエントリ（RPGツクール用） ───────────────────────────────
def generate_rpg_images(concept: dict, project_path: Path,
                        log=print, wait_sec: int = 180) -> bool:
    """
    RPGツクールMZプロジェクトにSD画像を生成・配置する

    戻り値: SDが使えた場合True、スキップした場合False
    """
    log("\n■ SD画像生成")

    if not sd_auto_start(log=log, wait_sec=wait_sec):
        log("  SD Forge が起動できませんでした → 画像生成をスキップ")
        return False

    log("  SD Forge 接続OK → 画像生成開始")

    # タイトル画面
    generate_title_screen(concept, project_path, log=log)

    # 戦闘背景
    generate_battle_backgrounds(concept, project_path, log=log)

    # イベントCG
    generate_event_pictures(concept, project_path, log=log)

    log("  SD画像生成 完了")
    return True


# ── メインエントリ（Godot用） ─────────────────────────────────────
def generate_godot_images(concept: dict, project_path: Path,
                          log=print, wait_sec: int = 180) -> bool:
    """
    GodotプロジェクトにSD画像を生成・配置する
    """
    log("\n▶ SD画像生成")

    if not sd_auto_start(log=log, wait_sec=wait_sec):
        log("  SD Forge が起動できませんでした → 画像生成をスキップ")
        return False

    log("  SD Forge 接続OK → 画像生成開始")

    generate_godot_backgrounds(concept, project_path, log=log)

    log("  SD画像生成 完了")
    return True
