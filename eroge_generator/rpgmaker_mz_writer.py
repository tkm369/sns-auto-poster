"""
RPGツクールMZプロジェクトを生成するライター
MZのテンプレートをコピーしてAI生成データで上書きする
"""
import json
import shutil
from pathlib import Path

MZ_TEMPLATE = Path("C:/Program Files (x86)/Steam/steamapps/common/RPG Maker MZ/newdata")
MZ_OUTPUT = Path(__file__).parent.parent / "output_rpg"


def _write_json(path: Path, data, log=print):
    """JSONファイルをUTF-8で書き出す"""
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  書き込み: {path.name}")


def _read_json(path: Path):
    """JSONファイルを読み込む"""
    return json.loads(path.read_text(encoding="utf-8"))


def _make_bgm(name: str, volume: int = 90, pitch: int = 100, pan: int = 0) -> dict:
    """BGMオブジェクトを生成"""
    return {"name": name, "pan": pan, "pitch": pitch, "volume": volume}


def _make_map_json(template_map: dict, display_name: str, bgm_name: str,
                   events: list, troop_ids: list = None,
                   map_type: str = "town") -> dict:
    """
    テンプレートのMap001.jsonをベースに新しいマップJSONを生成する

    template_map: テンプレートのMap001.jsonの内容
    display_name: マップの表示名
    bgm_name: BGMファイル名（.ogg拡張子なし）
    events: AI生成のイベントリスト
    troop_ids: エンカウントする敵グループIDリスト（ダンジョン用）
    map_type: "town" / "dungeon" / "world"
    """
    new_map = dict(template_map)

    new_map["displayName"] = display_name
    new_map["autoplayBgm"] = bool(bgm_name)
    new_map["bgm"] = _make_bgm(bgm_name) if bgm_name else _make_bgm("")
    new_map["events"] = events if events else []

    if map_type == "dungeon":
        encounter_list = []
        if troop_ids:
            for tid in troop_ids:
                encounter_list.append({
                    "troopId": tid,
                    "weight": 10,
                    "regionSet": []
                })
        new_map["encounterList"] = encounter_list
        new_map["encounterStep"] = 20
        new_map["battleback1Name"] = "Dungeon1"
        new_map["battleback2Name"] = "Dungeon1"
        new_map["specifyBattleback"] = True
    elif map_type == "town":
        new_map["encounterList"] = []
        new_map["encounterStep"] = 30
        new_map["disableDashing"] = False
    else:  # world
        new_map["encounterList"] = []
        new_map["encounterStep"] = 30

    return new_map


def _update_system_json(system: dict, concept: dict, actors: list) -> dict:
    """System.jsonの必要なフィールドのみ更新する"""
    updated = dict(system)

    # ゲームタイトル
    updated["gameTitle"] = concept.get("title", "RPG")

    # ロケール
    updated["locale"] = "ja_JP"

    # 開始マップID（1固定）
    updated["startMapId"] = 1

    # パーティメンバー（actorのIDリスト）
    actor_ids = [a["id"] for a in actors[1:] if a is not None]
    updated["partyMembers"] = actor_ids[:4]

    # 通貨単位
    updated["currencyUnit"] = "G"

    return updated


def _make_map_infos(maps: dict) -> list:
    """MapInfos.jsonを生成する

    maps: {"Map001": {...}, "Map002": {...}, ...}
    """
    infos = [None]
    map_keys = sorted(maps.keys())
    for i, key in enumerate(map_keys):
        map_data = maps[key]
        infos.append({
            "id": i + 1,
            "expanded": False,
            "name": map_data.get("displayName", key),
            "order": i + 1,
            "parentId": 0,
            "scrollX": 0.0,
            "scrollY": 0.0
        })
    return infos


def write_mz_project(concept: dict, actors: list, classes: list,
                     enemies: list, skills: list, items: list,
                     weapons: list, armors: list, troops: list,
                     maps: dict, log=print) -> Path:
    """
    RPGツクールMZプロジェクトを出力する

    maps: {
      "Map001": {"displayName": "...", "bgm": "...", "events": [...], "map_type": "town"},
      "Map002": {...},
      ...
    }

    処理:
    1. MZ_OUTPUT / concept["title"] にフォルダを作成
    2. MZテンプレートフォルダを丸ごとコピー
    3. data/*.json をAI生成データで上書き
    4. System.jsonのgameTitleを更新
    5. MapInfos.jsonを更新
    6. 各マップのMap00x.jsonを生成（タイル配列はテンプレートを使用）
    7. README.txtを生成（開き方の説明）

    戻り値: プロジェクトフォルダのPath
    """
    title = concept.get("title", "RPG")
    # ファイル名に使えない文字を除去
    safe_title = "".join(c for c in title if c not in r'\/:*?"<>|')
    if not safe_title:
        safe_title = "MyRPG"

    project_dir = MZ_OUTPUT / safe_title
    data_dir = project_dir / "data"

    # ── 1. テンプレートをコピー ────────────────────────────────────
    if not MZ_TEMPLATE.exists():
        raise FileNotFoundError(
            f"RPGツクールMZのテンプレートが見つかりません: {MZ_TEMPLATE}\n"
            "Steam版RPGツクールMZがインストールされているか確認してください。"
        )

    log(f"\n[プロジェクト] テンプレートをコピー中: {project_dir}")
    if project_dir.exists():
        shutil.rmtree(project_dir)
    shutil.copytree(MZ_TEMPLATE, project_dir)
    log("  テンプレートコピー完了")

    # ── 2. 各データファイルを上書き ──────────────────────────────────
    log("\n[プロジェクト] ゲームデータを書き込み中...")

    # Actors.json
    _write_json(data_dir / "Actors.json", actors, log=log)

    # Classes.json
    _write_json(data_dir / "Classes.json", classes, log=log)

    # Enemies.json
    _write_json(data_dir / "Enemies.json", enemies, log=log)

    # Skills.json
    _write_json(data_dir / "Skills.json", skills, log=log)

    # Items.json
    _write_json(data_dir / "Items.json", items, log=log)

    # Weapons.json
    _write_json(data_dir / "Weapons.json", weapons, log=log)

    # Armors.json
    _write_json(data_dir / "Armors.json", armors, log=log)

    # Troops.json
    _write_json(data_dir / "Troops.json", troops, log=log)

    # ── 3. System.jsonを更新 ──────────────────────────────────────
    log("\n[プロジェクト] System.jsonを更新中...")
    system_path = data_dir / "System.json"
    system = _read_json(system_path)
    system = _update_system_json(system, concept, actors)
    _write_json(system_path, system, log=log)

    # ── 4. MapInfos.jsonを更新 ────────────────────────────────────
    log("\n[プロジェクト] MapInfos.jsonを更新中...")
    map_infos = _make_map_infos(maps)
    _write_json(data_dir / "MapInfos.json", map_infos, log=log)

    # ── 5. テンプレートのMap001.jsonを読み込み（タイルデータ取得用） ──
    log("\n[プロジェクト] マップファイルを生成中...")
    template_map = _read_json(data_dir / "Map001.json")

    # ── 6. 各マップのMap00x.jsonを生成 ───────────────────────────
    # トループIDを割り当て（ダンジョンごとに3〜4グループ）
    troop_ids = [t["id"] for t in troops[1:] if t is not None]

    dungeon_keys = [k for k in sorted(maps.keys()) if maps[k].get("map_type") == "dungeon"]

    map_keys = sorted(maps.keys())
    for i, key in enumerate(map_keys):
        map_data = maps[key]
        display_name  = map_data.get("displayName", f"マップ{i+1}")
        bgm_name      = map_data.get("bgm", "Town1")
        events        = map_data.get("events", [None])
        map_type      = map_data.get("map_type", "town")
        floor         = map_data.get("floor", 1)
        total_floors  = map_data.get("total_floors", 1)

        # ダンジョンには敵グループを割り当て（深層ほど強いグループ）
        assigned_troops = []
        if map_type == "dungeon" and troop_ids:
            dungeon_idx = dungeon_keys.index(key) if key in dungeon_keys else 0
            # フロアが深いほど後半（強い）のトループを使う
            total_dungeon_maps = len(dungeon_keys)
            progress = dungeon_idx / max(total_dungeon_maps - 1, 1)  # 0.0〜1.0
            start = int(progress * max(len(troop_ids) - 3, 0))
            assigned_troops = [troop_ids[(start + j) % len(troop_ids)] for j in range(3)]

        map_json = _make_map_json(
            template_map=template_map,
            display_name=display_name,
            bgm_name=bgm_name,
            events=events,
            troop_ids=assigned_troops,
            map_type=map_type
        )

        map_filename = f"Map{str(i+1).zfill(3)}.json"
        _write_json(data_dir / map_filename, map_json, log=log)

    # ── 7. README.txtを生成 ────────────────────────────────────────
    readme_path = project_dir / "README.txt"
    readme_content = f"""■ {title} — RPGツクールMZプロジェクト
{'=' * 50}

このプロジェクトはAIによって自動生成されました。

【開き方】
1. RPGツクールMZ を起動します
2. 「プロジェクトを開く」を選択します
3. このフォルダ（{safe_title}）を選択します
4. プロジェクトが開きます

【プロジェクト情報】
タイトル  : {title}
サブタイトル: {concept.get('subtitle', '')}
あらすじ  : {concept.get('story', '')}

【パーティメンバー】
{chr(10).join(f"  {i+1}. {m.get('name','')}（{m.get('class','')}）— {m.get('description','')}" for i, m in enumerate(concept.get('party', [])))}

【ラスボス】
  {concept.get('villain', {}).get('name', '')} — {concept.get('villain', {}).get('description', '')}

【マップ構成】
{chr(10).join(f"  {k}: {maps[k].get('displayName', k)} [{maps[k].get('map_type','town')}]" for k in sorted(maps.keys()))}

【注意事項】
- 本プロジェクトはMZデフォルト素材のみを使用しています
- 追加のプラグイン・素材のインストールは不要です
- イベント・マップはAI生成のため、調整が必要な場合があります

生成日時: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    readme_path.write_text(readme_content, encoding="utf-8")
    log(f"  書き込み: README.txt")

    log(f"\n[完了] プロジェクトを生成しました: {project_dir}")
    return project_dir


def build_maps_from_concept(concept: dict, map_events_dict: dict,
                            floors_per_dungeon: int = 1) -> dict:
    """
    コンセプトデータとイベントデータからmaps辞書を構築するヘルパー関数。
    floors_per_dungeon >= 2 の場合、各ダンジョンを複数フロアに展開する。

    map_events_dict のキー形式:
      町:         "Map001", "Map002", ...
      ダンジョン: "Map003_F1", "Map003_F2", ... (複数フロア時)
               or "Map003" (1フロア時・後方互換)
    """
    maps = {}
    map_index = 1
    fpd = max(1, int(floors_per_dungeon))

    towns    = concept.get("towns",    [])
    dungeons = concept.get("dungeons", [])

    # 町マップ
    for town in towns:
        key = f"Map{str(map_index).zfill(3)}"
        maps[key] = {
            "displayName": town["name"],
            "bgm":         town.get("bgm", "Town1"),
            "events":      map_events_dict.get(key, [None]),
            "map_type":    "town",
        }
        map_index += 1

    # ダンジョンマップ（複数フロア対応）
    bgm_dungeons = ["Dungeon1","Dungeon2","Dungeon3","Dungeon4","Dungeon5","Dungeon6","Dungeon7"]
    for d_idx, dungeon in enumerate(dungeons):
        base_bgm = dungeon.get("bgm", bgm_dungeons[d_idx % len(bgm_dungeons)])
        base_name = dungeon["name"]

        if fpd == 1:
            key = f"Map{str(map_index).zfill(3)}"
            maps[key] = {
                "displayName": base_name,
                "bgm":         base_bgm,
                "events":      map_events_dict.get(key, map_events_dict.get(f"{key}_F1", [None])),
                "map_type":    "dungeon",
                "dungeon_idx": d_idx,
                "floor":       1,
                "total_floors": 1,
            }
            map_index += 1
        else:
            for fl in range(1, fpd + 1):
                key = f"Map{str(map_index).zfill(3)}"
                floor_label = f"B{fl}F" if fl > 1 else "1F"
                floor_name  = f"{base_name} {floor_label}"
                # 深層ほど暗い BGM に変える
                bgm_shift = min(fl - 1, len(bgm_dungeons) - 1)
                floor_bgm = bgm_dungeons[(d_idx + bgm_shift) % len(bgm_dungeons)]
                events_key = f"Map{str(map_index - (fl - 1)).zfill(3)}_F{fl}"  # 旧キー互換
                maps[key] = {
                    "displayName":  floor_name,
                    "bgm":          floor_bgm,
                    "events":       map_events_dict.get(key, map_events_dict.get(events_key, [None])),
                    "map_type":     "dungeon",
                    "dungeon_idx":  d_idx,
                    "floor":        fl,
                    "total_floors": fpd,
                }
                map_index += 1

    return maps


def run_full_pipeline(genre: str = "ファンタジー", api_key: str = "",
                      log=print, cancel_event=None, pause_event=None,
                      model=None, settings: dict = None,
                      use_sd: bool = False) -> Path:
    """
    コンセプト生成からプロジェクト出力までの一括実行パイプライン

    settings keys:
      party_size:         int (1-4)
      town_count:         int (1-10)
      dungeon_count:      int (1-10)
      floors_per_dungeon: int (1-5)   ★NEW: ダンジョン1つ当たりのフロア数
      chapter_count:      int (1-6)   ★NEW: 章数
      side_quest_count:   int (5-20)  ★NEW: サブクエスト数
      enemy_count:        int (5-50)
      difficulty:         "簡単"/"普通"/"難しい"
      protagonist_gender: "male"/"female"/"any"
      atmosphere:         "王道"/"ダーク"/"コメディ"/"ロマンス"
      focus:              "バトル重視"/"ストーリー重視"/"探索重視"
      adult:              bool
    """
    import google.generativeai as genai
    from rpgmaker_mz_generator import (
        generate_rpg_concept,
        generate_actors, generate_classes,
        generate_enemies,
        generate_skills,
        generate_items, generate_weapons, generate_armors,
        generate_troops,
        generate_map_events,
        generate_chapters,
        generate_side_quests,
        generate_dungeon_floor_events,
        generate_actors_and_classes,
        generate_items_weapons_armors,
    )

    def _check_cancel():
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("キャンセルされました")
        import time as _t
        while pause_event and pause_event.is_set():
            _t.sleep(0.3)
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("キャンセルされました")

    # Gemini 初期化
    if model is None:
        import os
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.0-flash")

    s = settings or {}
    fpd    = max(1, min(5, int(s.get("floors_per_dungeon", 1))))
    chaps  = max(1, min(6, int(s.get("chapter_count",     1))))
    quests = max(0, min(20, int(s.get("side_quest_count", 0))))

    # 推定プレイ時間を計算
    towns_n    = int(s.get("town_count",    3))
    dungeons_n = int(s.get("dungeon_count", 3))
    total_maps = towns_n + dungeons_n * fpd
    est_hours  = round((towns_n * 0.2 + dungeons_n * fpd * 0.4 + quests * 0.2), 1)

    log("=" * 60)
    log("  RPGツクールMZ 自動ゲーム生成パイプライン")
    log(f"  ジャンル: {genre}")
    log(f"  雰囲気: {s.get('atmosphere','王道')} / 重点: {s.get('focus','バトル重視')}")
    log(f"  パーティ: {s.get('party_size',4)}人 / 町: {towns_n} / ダンジョン: {dungeons_n}×{fpd}F")
    log(f"  章数: {chaps} / サブクエスト: {quests}個")
    log(f"  敵: {s.get('enemy_count',10)}種 / 難易度: {s.get('difficulty','普通')}")
    log(f"  推定マップ数: {total_maps} / 推定プレイ時間: 約{est_hours}時間")
    log("=" * 60)

    # 並列化で10→5ステップに削減: コンセプト/データ並列/トループ/オプション/マップ/出力
    total_steps = 5 + (1 if chaps > 1 or quests > 0 else 0)
    step = [0]
    def _step(name):
        step[0] += 1
        _check_cancel()
        log(f"\n■ Step {step[0]}/{total_steps}: {name}")

    import concurrent.futures as _cf

    _step("コンセプト生成")
    concept = generate_rpg_concept(model, genre, settings=s, log=log)
    log(f"  タイトル: {concept.get('title','不明')}")

    # ── バッチ化＋並列生成 ──────────────────────────────────────────
    # 章/クエストもコンセプト依存のみ → メインデータと同時に走らせる
    _step("ゲームデータ並列生成（全データ同時）")
    n_workers = 4 + (1 if chaps > 1 else 0) + (1 if quests > 0 else 0)
    log(f"  {n_workers}並列でデータ生成中（APIコール数を大幅削減）...")

    chapters    = []
    side_quests = []

    with _cf.ThreadPoolExecutor(max_workers=n_workers) as ex:
        f_ac    = ex.submit(generate_actors_and_classes,   model, concept, log=log)
        f_en    = ex.submit(generate_enemies,              model, concept, settings=s, log=log)
        f_sk    = ex.submit(generate_skills,               model, concept, log=log)
        f_iwa   = ex.submit(generate_items_weapons_armors, model, concept, log=log)
        f_chaps = ex.submit(generate_chapters,    model, concept, settings=s, log=log) if chaps > 1 else None
        f_quest = ex.submit(generate_side_quests, model, concept, settings=s, log=log) if quests > 0 else None

        actors, classes        = f_ac.result();  log("  ✓ アクター＋クラス完了")
        enemies                = f_en.result();  log("  ✓ 敵キャラ完了")
        skills                 = f_sk.result();  log("  ✓ スキル完了")
        items, weapons, armors = f_iwa.result(); log("  ✓ アイテム＋武器＋防具完了")
        if f_chaps:
            chapters = f_chaps.result()
            concept["chapters"] = chapters
            log(f"  ✓ 章構成完了 ({len(chapters)}章)")
        if f_quest:
            side_quests = f_quest.result()
            concept["side_quests"] = side_quests
            log(f"  ✓ サブクエスト完了 ({len(side_quests)}個)")

    _step("トループ生成")
    troops = generate_troops(model, concept, enemies, log=log)

    # ── マップイベント 並列生成 ────────────────────────────────────
    _step(f"マップイベント並列生成（町{towns_n} + ダンジョン{dungeons_n}×{fpd}F）")
    log("  4並列でマップイベント生成中...")

    # (map_index, key, future) のリストを作る
    map_tasks = []
    map_index = 1

    with _cf.ThreadPoolExecutor(max_workers=4) as ex:
        for town in concept.get("towns", []):
            key = f"Map{str(map_index).zfill(3)}"
            f = ex.submit(generate_map_events, model, concept, "town",
                          {"displayName": town["name"]}, log)
            map_tasks.append((key, f))
            map_index += 1

        for dungeon in concept.get("dungeons", []):
            for fl in range(1, fpd + 1):
                key = f"Map{str(map_index).zfill(3)}"
                if fpd == 1:
                    f = ex.submit(generate_map_events, model, concept, "dungeon",
                                  {"displayName": dungeon["name"]}, log)
                else:
                    f = ex.submit(generate_dungeon_floor_events, model, concept,
                                  {"displayName": dungeon["name"]}, fl, fpd, log)
                map_tasks.append((key, f))
                map_index += 1

        map_events_dict = {}
        for key, f in map_tasks:
            map_events_dict[key] = f.result()
            log(f"  ✓ {key} イベント完了")

    maps = build_maps_from_concept(concept, map_events_dict, floors_per_dungeon=fpd)

    # プロジェクト出力
    log("\n■ プロジェクト出力")
    project_path = write_mz_project(
        concept=concept,
        actors=actors,
        classes=classes,
        enemies=enemies,
        skills=skills,
        items=items,
        weapons=weapons,
        armors=armors,
        troops=troops,
        maps=maps,
        log=log,
    )

    # サブクエスト・章情報を README に追記
    if side_quests or chapters:
        readme = project_path / "README.txt"
        extra = ""
        if chapters:
            extra += f"\n【章構成】\n" + "\n".join(
                f"  第{c.get('chapter',i+1)}章「{c.get('title','')}」— {c.get('summary','')[:60]}"
                for i, c in enumerate(chapters)
            )
        if side_quests:
            extra += f"\n\n【サブクエスト一覧（{len(side_quests)}個）】\n" + "\n".join(
                f"  [{q.get('id',i+1)}] {q.get('title','')} — 依頼: {q.get('giver','')} / 報酬: {q.get('reward','')}"
                for i, q in enumerate(side_quests)
            )
        existing = readme.read_text(encoding="utf-8")
        readme.write_text(existing.rstrip() + "\n" + extra + "\n", encoding="utf-8")

    # ── SD画像生成 ────────────────────────────────────────────────
    if use_sd:
        try:
            from sd_rpg import generate_rpg_images
            generate_rpg_images(concept, project_path, log=log)
        except Exception as e:
            log(f"  !! SD画像生成エラー（スキップ）: {e}")

    # DLSite販売戦略レポート
    log("\n■ DLSite販売戦略レポート生成")
    try:
        from dlsite_advisor import generate_full_report
        report_md = generate_full_report(
            model, concept,
            game_type="RPGツクールMZ",
            genre=genre,
            adult=s.get("adult", False),
            log=log,
        )
        report_path = project_path / "DLSITE_STRATEGY.md"
        report_path.write_text(report_md, encoding="utf-8")
        log(f"  販売戦略レポート: {report_path}")
    except Exception as e:
        log(f"  !! 販売戦略レポート生成エラー（スキップ）: {e}")

    log("\n" + "=" * 60)
    log(f"  生成完了！プロジェクト: {project_path}")
    log("=" * 60)
    return project_path


# ── スタンドアロン実行 ────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import os

    # Gemini APIの設定
    try:
        import google.generativeai as genai
    except ImportError:
        print("google-generativeai がインストールされていません。")
        print("pip install google-generativeai を実行してください。")
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("環境変数 GEMINI_API_KEY が設定されていません。")
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    genre = sys.argv[1] if len(sys.argv) > 1 else "ダークファンタジー"
    print(f"ジャンル: {genre}")

    project_path = run_full_pipeline(model, genre=genre)
    print(f"\nRPGツクールMZで開いてください: {project_path}")
