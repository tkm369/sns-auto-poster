"""
RPGツクールMZ用 Gemini/ローカルモデル生成ロジック
"""
import json
import re
import time
import queue as _q
import threading as _th


# ── 内部ユーティリティ ─────────────────────────────────────────────

def _parse_retry_after(error_str: str) -> int:
    """429レスポンスから推奨待ち秒数を取得。なければ0を返す"""
    m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', str(error_str), re.DOTALL)
    return int(m.group(1)) + 3 if m else 0


def _stream(model, prompt: str, system: str = "", log=print,
            local_client=None) -> str:
    """Gemini またはローカルモデルを呼び出しテキストを返す。"""
    if local_client is not None:
        from local_model import generate_local
        return generate_local(prompt, system=system,
                              base_url=local_client["base_url"],
                              max_tokens=16000, log=log)
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    max_attempts = 5   # レート制限リトライを多めに
    _WALL_TIMEOUT = 120  # 秒: 接続が生きていても応答なしならタイムアウト
    for attempt in range(max_attempts):
        try:
            chunk_q = _q.Queue()

            def _api_worker(fp=full_prompt, cq=chunk_q):
                try:
                    for chunk in model.generate_content(fp, stream=True,
                                                        request_options={"timeout": _WALL_TIMEOUT}):
                        cq.put(('chunk', chunk.text or ""))
                except Exception as exc:
                    cq.put(('error', exc))
                finally:
                    cq.put(('done', None))

            _th.Thread(target=_api_worker, daemon=True).start()

            result   = []
            chars    = 0
            dot_next = 200
            deadline = time.time() + _WALL_TIMEOUT
            log(f"  Gemini API 呼び出し中{'（リトライ ' + str(attempt) + '回目）' if attempt > 0 else ''}...")

            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError(f"Gemini API が{_WALL_TIMEOUT}秒応答なし")
                try:
                    kind, val = chunk_q.get(timeout=min(remaining, 2.0))
                except _q.Empty:
                    continue
                if kind == 'chunk':
                    result.append(val)
                    chars += len(val)
                    if chars >= dot_next:
                        log(f"  受信中... {chars}字")
                        dot_next += 500
                elif kind == 'error':
                    raise val
                elif kind == 'done':
                    break

            log(f"  受信完了 ({chars}字)")
            return _clean("".join(result))
        except Exception as e:
            err = str(e)
            if attempt < max_attempts - 1:
                # 429レート制限: APIが指定した秒数だけ待つ
                retry_after = _parse_retry_after(err)
                if retry_after:
                    log(f"  ⚠️ レート制限 — {retry_after}秒後にリトライ... ({attempt+1}/{max_attempts})")
                    time.sleep(retry_after)
                else:
                    wait = 5 + attempt * 5
                    log(f"  API エラー: {err[:80]} → {wait}秒後にリトライ ({attempt+1}/{max_attempts})")
                    time.sleep(wait)
            else:
                raise


def _clean(text: str) -> str:
    text = re.sub(r"```[a-z]*\n?", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()


def _parse_json_with_retry(model, prompt: str, system: str = "",
                           max_retry: int = 3, log=print,
                           local_client=None) -> dict:
    for attempt in range(max_retry):
        raw = _stream(model, prompt, system, log=log, local_client=local_client)
        m = re.search(r'(\[[\s\S]+\]|\{[\s\S]+\})', raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError as e:
                log(f"  JSON解析エラー (試行 {attempt+1}/{max_retry}): {e}")
        else:
            log(f"  JSONが見つかりませんでした (試行 {attempt+1}/{max_retry})")
        if attempt < max_retry - 1:
            time.sleep(2)
    raise ValueError(f"JSON生成に{max_retry}回失敗しました")


def _parse_list_with_retry(model, prompt: str, system: str = "",
                           max_retry: int = 3, log=print,
                           local_client=None) -> list:
    for attempt in range(max_retry):
        raw = _stream(model, prompt, system, log=log, local_client=local_client)
        m = re.search(r'\[[\s\S]+\]', raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError as e:
                log(f"  JSON解析エラー (試行 {attempt+1}/{max_retry}): {e}")
        else:
            log(f"  JSONリストが見つかりませんでした (試行 {attempt+1}/{max_retry})")
        if attempt < max_retry - 1:
            time.sleep(2)
    raise ValueError(f"JSONリスト生成に{max_retry}回失敗しました")


# ── MZデフォルト素材リスト ─────────────────────────────────────────

MZ_CHARACTER_NAMES = ["Actor1", "Actor2", "Actor3", "People1", "People2", "People3", "People4"]
MZ_BATTLER_NAMES = [
    "Bat", "Bear", "BigMono", "Blob", "Dragon", "Eagle",
    "Goblin", "Golem", "GreenDragon", "Harpy", "Minotaurus",
    "Mushroom", "Orc", "RedDragon", "Skeleton", "Slime",
    "Spider", "Troll", "Vampire", "Wolf"
]
MZ_BGM_TOWNS = ["Town1", "Town2", "Town3", "Town4", "Town5", "Town6", "Town7", "Town8"]
MZ_BGM_DUNGEONS = ["Dungeon1", "Dungeon2", "Dungeon3", "Dungeon4", "Dungeon5", "Dungeon6", "Dungeon7"]
MZ_BGM_BATTLE = ["Battle1", "Battle2", "Battle3", "Battle4", "Battle5", "Battle6", "Battle7", "Battle8"]
MZ_BGM_FIELD = ["Field1", "Field2", "Field3", "Field4"]

# MZデフォルトのパラム成長曲線（100レベル分）
def _make_param_curve(base: int, growth: float) -> list:
    """レベル1〜99の成長曲線を生成する（100要素）"""
    curve = [base]
    for lv in range(1, 99):
        val = int(base + growth * lv * (lv + 1) / 2)
        curve.append(val)
    return curve


# ── Step 1: ゲームコンセプト生成 ──────────────────────────────────

def generate_rpg_concept(model, genre: str, settings: dict = None, log=print, local_client=None) -> dict:
    """ゲームコンセプト（タイトル・世界観・主人公・敵・ストーリー）を生成

    settings keys (optional):
      party_size: int (1-4)
      town_count: int (1-5)
      dungeon_count: int (1-5)
      protagonist_gender: "male"/"female"/"any"
      atmosphere: "王道"/"ダーク"/"コメディ"/"ロマンス"
      focus: "バトル重視"/"ストーリー重視"/"探索重視"
      adult: bool

    戻り値のJSON形式:
    {
      "title": "ゲームタイトル",
      "subtitle": "サブタイトル",
      "story": "あらすじ（200字）",
      "world": "世界観説明（100字）",
      "protagonist": {
        "name": "主人公名",
        "class": "職業名",
        "gender": "male/female",
        "description": "キャラ説明"
      },
      "party": [  // 主人公含む最大4人
        {"name": "名前", "class": "職業", "description": "説明"}
      ],
      "villain": {"name": "ラスボス名", "description": "説明"},
      "towns": [  // 3つ
        {"name": "町名", "description": "説明", "bgm": "Town1"}
      ],
      "dungeons": [  // 3つ
        {"name": "ダンジョン名", "description": "説明", "bgm": "Dungeon1"}
      ]
    }
    """
    s = settings or {}
    party_size    = max(1, min(4,  int(s.get("party_size",    4))))
    town_count    = max(1, min(10, int(s.get("town_count",    3))))
    dungeon_count = max(1, min(10, int(s.get("dungeon_count", 3))))
    chapter_count = max(1, min(6,  int(s.get("chapter_count", 1))))
    gender        = s.get("protagonist_gender", "any")
    atmosphere    = s.get("atmosphere", "王道")
    focus         = s.get("focus", "バトル重視")
    adult         = s.get("adult", False)

    gender_note = {
        "male":   "主人公は男性",
        "female": "主人公は女性",
        "any":    "主人公の性別は自由に設定",
    }.get(gender, "主人公の性別は自由に設定")

    eroge_scenario = s.get("eroge_scenario", "戦闘敗北H — 敵に負けるとHシーンが発生")
    h_intensity    = s.get("h_intensity", "普通")

    adult_note = f"""このゲームはR18成人向けエロRPGです。
Hシーンの発生タイミング: {eroge_scenario}
エロの濃さ: {h_intensity}
DLSiteのエロRPGとして売れるような、プレイヤーの欲求に刺さるコンテンツにしてください。
全キャラの年齢は18歳以上にすること。"""

    log(f"\n[コンセプト] ゲームコンセプト生成中... (ジャンル: {genre})\n")

    # 町・ダンジョンのBGMリストを事前に組む
    town_bgm_entries  = "\n".join(
        f'    {{"name": "町名", "description": "説明（1文）", "bgm": "Town{i*2+1}"}}'
        for i in range(town_count)
    )
    dungeon_bgm_entries = "\n".join(
        f'    {{"name": "ダンジョン名", "description": "説明（1文）", "bgm": "Dungeon{i*2+1}"}}'
        for i in range(dungeon_count)
    )
    party_entries = "\n".join(
        '    {"name": "名前", "class": "職業", "description": "説明（1文）"}'
        for _ in range(party_size)
    )

    prompt = f"""以下の条件でRPGゲームのコンセプトを考えてください。
ジャンル: {genre}
雰囲気: {atmosphere}
ゲームの重点: {focus}
{gender_note}
{adult_note}
RPGツクールMZで制作する日本語RPGです。

以下のJSON形式のみで出力してください（他のテキスト不要）:
{{
  "title": "ゲームタイトル（日本語、10字以内）",
  "subtitle": "サブタイトル（日本語、20字以内）",
  "story": "あらすじ（日本語、200字以内）",
  "world": "世界観説明（日本語、100字以内）",
  "protagonist": {{
    "name": "主人公名（日本語）",
    "class": "職業名（日本語）",
    "gender": "{gender if gender != 'any' else 'male'}",
    "description": "キャラ説明（1文）"
  }},
  "party": [
{party_entries}
  ],
  "villain": {{"name": "ラスボス名", "description": "説明（1文）"}},
  "towns": [
{town_bgm_entries}
  ],
  "dungeons": [
{dungeon_bgm_entries}
  ]
}}

注意:
- partyの最初の要素は必ずprotagonistと同じキャラにする
- partyはちょうど{party_size}人にする
- townのbgmはTown1〜Town8のいずれか
- dungeonのbgmはDungeon1〜Dungeon7のいずれか
- 全て日本語で生成する"""

    result = _parse_json_with_retry(model, prompt, log=log, local_client=local_client)
    # party の先頭を protagonist に統一
    if result.get("party") and result.get("protagonist"):
        result["party"][0]["name"] = result["protagonist"]["name"]
        result["party"][0]["class"] = result["protagonist"]["class"]
    return result


# ── Step 2: アクター生成 ───────────────────────────────────────────

def generate_actors(model, concept: dict, log=print, local_client=None) -> list:
    """Actors.json形式のデータを生成（最大4人）

    戻り値: MZ Actors.json形式のリスト [null, {...}, {...}, ...]
    """
    log("\n[アクター] アクターデータ生成中...\n")
    party = concept.get("party", [])[:4]
    num = len(party)

    party_desc = "\n".join(
        f"{i+1}. 名前:{m['name']} 職業:{m['class']} 説明:{m['description']}"
        for i, m in enumerate(party)
    )

    # characterName/faceNameのインデックスを割り当て
    # Actor1: index 0-7, Actor2: index 0-7, Actor3: index 0-7
    char_assignments = []
    for i in range(num):
        char_file = f"Actor{(i // 8) + 1}"
        char_idx = i % 8
        face_file = f"Actor{(i // 8) + 1}"
        face_idx = i % 8
        battler = f"Actor1_{i+1}"
        char_assignments.append({
            "characterName": char_file,
            "characterIndex": char_idx,
            "faceName": face_file,
            "faceIndex": face_idx,
            "battlerName": battler,
        })

    prompt = f"""以下のRPGパーティメンバーのActors.jsonデータを生成してください。
ゲームタイトル: {concept.get('title', 'RPG')}

パーティメンバー（{num}人）:
{party_desc}

以下のJSON配列形式のみで出力してください（他のテキスト不要）:
[
  {{
    "id": 1,
    "name": "キャラ名（日本語）",
    "nickname": "あだ名（日本語、5字以内、空でも可）",
    "classId": 1,
    "initialLevel": 1,
    "maxLevel": 99,
    "characterName": "Actor1",
    "characterIndex": 0,
    "faceName": "Actor1",
    "faceIndex": 0,
    "battlerName": "Actor1_1",
    "equips": [1, 0, 0, 1, 0],
    "profile": "キャラの一言紹介（日本語、30字以内）",
    "traits": [],
    "note": ""
  }},
  ... （{num}人分）
]

各メンバーのID（1〜{num}）、name（上記名前をそのまま使用）を正確に設定してください。
equipsの配列は[武器ID, 盾ID, 頭防具ID, 体防具ID, 装飾品ID]です（0は装備なし）。
初期装備として1〜5程度の武器・防具IDを割り当ててください。"""

    raw_list = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)

    # 素材名と基本フィールドを確実に設定
    actors = [None]
    for i, member in enumerate(party):
        if i < len(raw_list):
            actor = raw_list[i]
        else:
            actor = {}

        # 必須フィールドを強制上書き
        actor["id"] = i + 1
        actor["name"] = member["name"]
        actor["classId"] = i + 1
        actor["initialLevel"] = actor.get("initialLevel", 1)
        actor["maxLevel"] = actor.get("maxLevel", 99)
        actor["characterName"] = char_assignments[i]["characterName"]
        actor["characterIndex"] = char_assignments[i]["characterIndex"]
        actor["faceName"] = char_assignments[i]["faceName"]
        actor["faceIndex"] = char_assignments[i]["faceIndex"]
        actor["battlerName"] = char_assignments[i]["battlerName"]
        actor.setdefault("nickname", "")
        actor.setdefault("equips", [1, 0, 0, 1, 0])
        actor.setdefault("profile", member["description"][:30])
        actor.setdefault("traits", [])
        actor.setdefault("note", "")

        actors.append(actor)

    return actors


# ── Step 3: クラス生成 ────────────────────────────────────────────

def generate_classes(model, concept: dict, log=print, local_client=None) -> list:
    """Classes.json形式のデータを生成（パーティの職業数分）"""
    log("\n[クラス] クラスデータ生成中...\n")
    party = concept.get("party", [])[:4]

    party_desc = "\n".join(
        f"{i+1}. 職業名:{m['class']} 説明:{m['description']}"
        for i, m in enumerate(party)
    )

    prompt = f"""以下のRPGクラスのClasses.jsonデータを生成してください。
ゲームタイトル: {concept.get('title', 'RPG')}

クラス（{len(party)}種）:
{party_desc}

以下のJSON配列形式のみで出力してください（他のテキスト不要）:
[
  {{
    "id": 1,
    "name": "職業名（日本語）",
    "expParams": [30, 20, 30, 30],
    "traits": [
      {{"code": 23, "dataId": 0, "value": 1}},
      {{"code": 51, "dataId": 2, "value": 0}},
      {{"code": 51, "dataId": 1, "value": 1}}
    ],
    "learnings": [
      {{"level": 1, "note": "", "skillId": 1}},
      {{"level": 5, "note": "", "skillId": 2}},
      {{"level": 10, "note": "", "skillId": 3}}
    ],
    "note": ""
  }},
  ... （クラス数分）
]

traitsのcodeは: 23=装備タイプ, 51=スキルタイプ追加, 52=スキルタイプ封印
learningsは各クラスの特徴に合った3〜5個のスキル習得（skillIdは2〜25の範囲）を設定してください。"""

    raw_list = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)

    # paramsを各クラスに追加（固定の成長曲線テンプレート使用）
    PARAM_TEMPLATES = [
        # [HP, MP, ATK, DEF, MAT, MDF, AGI, LUK] の初期値と成長率
        {"base": [500, 50, 15, 12, 10, 10, 10, 10], "growth": [12, 1, 0.3, 0.25, 0.2, 0.2, 0.2, 0.2]},  # 戦士系
        {"base": [350, 100, 8, 8, 18, 15, 12, 10], "growth": [8, 2, 0.15, 0.15, 0.4, 0.35, 0.25, 0.2]},  # 魔法使い系
        {"base": [400, 80, 10, 10, 14, 14, 14, 12], "growth": [10, 1.5, 0.2, 0.2, 0.3, 0.3, 0.28, 0.25]},  # 万能系
        {"base": [420, 60, 14, 8, 12, 8, 18, 14], "growth": [10, 1.2, 0.28, 0.15, 0.25, 0.15, 0.35, 0.28]},  # 盗賊系
    ]

    classes = [None]
    for i, member in enumerate(party):
        if i < len(raw_list):
            cls = raw_list[i]
        else:
            cls = {}

        tpl = PARAM_TEMPLATES[i % len(PARAM_TEMPLATES)]
        params = []
        for stat_idx in range(8):
            base = tpl["base"][stat_idx]
            growth = tpl["growth"][stat_idx]
            curve = _make_param_curve(base, growth)
            params.append(curve)

        cls["id"] = i + 1
        cls["name"] = member["class"]
        cls.setdefault("expParams", [30, 20, 30, 30])
        cls.setdefault("traits", [
            {"code": 23, "dataId": 0, "value": 1},
            {"code": 51, "dataId": 1, "value": 1},
        ])
        cls.setdefault("learnings", [
            {"level": 1, "note": "", "skillId": 1},
            {"level": 5, "note": "", "skillId": i + 2},
        ])
        cls.setdefault("note", "")
        cls["params"] = params

        classes.append(cls)

    return classes


# ── Step 4: 敵キャラ生成 ──────────────────────────────────────────

def generate_enemies(model, concept: dict, settings: dict = None, log=print, local_client=None) -> list:
    """Enemies.json形式のデータを生成"""
    s = settings or {}
    enemy_count = int(s.get("enemy_count", 10))
    difficulty  = s.get("difficulty", "普通")

    diff_note = {
        "簡単": "敵のHPや攻撃力は低め。初心者でも倒せる強さ。",
        "普通": "敵のHPや攻撃力は標準的なRPGバランス。",
        "難しい": "敵のHPや攻撃力は高め。歯ごたえのある難易度。",
    }.get(difficulty, "敵のHPや攻撃力は標準的なRPGバランス。")

    log(f"\n[エネミー] 敵キャラクターデータ生成中... ({enemy_count}体 / 難易度:{difficulty})\n")

    battler_list = ", ".join(MZ_BATTLER_NAMES)
    prompt = f"""以下のRPGの敵キャラクターのEnemies.jsonデータを{enemy_count}体生成してください。
ゲームタイトル: {concept.get('title', 'RPG')}
世界観: {concept.get('world', '')}
ラスボス: {concept.get('villain', {}).get('name', '')} — {concept.get('villain', {}).get('description', '')}
難易度設定: {diff_note}

使用可能なbattlerName（MZデフォルト素材のみ）:
{battler_list}

以下のJSON配列形式のみで出力してください（他のテキスト不要）:
[
  {{
    "id": 1,
    "name": "敵名（日本語）",
    "battlerName": "Goblin",
    "battlerHue": 0,
    "params": [200, 0, 25, 20, 20, 20, 20, 20],
    "exp": 10,
    "gold": 5,
    "dropItems": [
      {{"dataId": 1, "denominator": 5, "kind": 1}},
      {{"dataId": 0, "denominator": 1, "kind": 0}},
      {{"dataId": 0, "denominator": 1, "kind": 0}}
    ],
    "actions": [
      {{"conditionParam1": 0, "conditionParam2": 0, "conditionType": 0, "rating": 5, "skillId": 1}}
    ],
    "traits": [],
    "note": ""
  }},
  ... （10体分）
]

注意:
- params配列は [最大HP, 最大MP, 攻撃力, 防御力, 魔法力, 魔法防御, 敏捷性, 運] の順
- 弱い敵から強い敵へ順番に並べる（id=1が最弱、id=10が最強/ラスボス付近）
- ラスボス（id={enemy_count}）は名前を '{concept.get('villain', {}).get('name', 'ラスボス')}' にする
- battlerHueは0〜360
- dropItems の kind: 0=なし, 1=アイテム, 2=武器, 3=防具
- dropItemsのdenominatorは落とす確率（1=100%, 5=20%, 10=10%）
- battlerNameは上記リストから選ぶこと"""

    raw_list = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)

    enemies = [None]
    for i, enemy in enumerate(raw_list):
        enemy["id"] = i + 1
        # battlerNameの検証
        if enemy.get("battlerName") not in MZ_BATTLER_NAMES:
            enemy["battlerName"] = MZ_BATTLER_NAMES[i % len(MZ_BATTLER_NAMES)]
        enemy.setdefault("battlerHue", 0)
        enemy.setdefault("params", [200, 0, 25, 20, 20, 20, 20, 20])
        enemy.setdefault("exp", 10 * (i + 1))
        enemy.setdefault("gold", 5 * (i + 1))
        enemy.setdefault("dropItems", [
            {"dataId": 1, "denominator": 5, "kind": 1},
            {"dataId": 0, "denominator": 1, "kind": 0},
            {"dataId": 0, "denominator": 1, "kind": 0},
        ])
        # dropItemsを必ず3要素にする
        while len(enemy["dropItems"]) < 3:
            enemy["dropItems"].append({"dataId": 0, "denominator": 1, "kind": 0})
        enemy["dropItems"] = enemy["dropItems"][:3]
        enemy.setdefault("actions", [
            {"conditionParam1": 0, "conditionParam2": 0, "conditionType": 0, "rating": 5, "skillId": 1}
        ])
        enemy.setdefault("traits", [])
        enemy.setdefault("note", "")
        enemies.append(enemy)

    return enemies


# ── Step 5: スキル生成 ────────────────────────────────────────────

def generate_skills(model, concept: dict, log=print, local_client=None) -> list:
    """Skills.json形式のデータを生成（20〜30個）

    スキル1は必ず "Attack"（攻撃）として保持。
    """
    log("\n[スキル] スキルデータ生成中...\n")

    # スキル1（攻撃）は固定
    attack_skill = {
        "id": 1,
        "animationId": -1,
        "damage": {
            "critical": True,
            "elementId": -1,
            "formula": "a.atk * 4 - b.def * 2",
            "type": 1,
            "variance": 20
        },
        "description": "",
        "effects": [{"code": 21, "dataId": 0, "value1": 1, "value2": 0}],
        "hitType": 1,
        "iconIndex": 76,
        "message1": "%1は攻撃した！",
        "message2": "",
        "mpCost": 0,
        "name": "攻撃",
        "note": "Skill #1 corresponds to the Attack command.",
        "occasion": 1,
        "repeats": 1,
        "requiredWtypeId1": 0,
        "requiredWtypeId2": 0,
        "scope": 1,
        "speed": 0,
        "stypeId": 0,
        "successRate": 100,
        "tpCost": 0,
        "tpGain": 5,
        "messageType": 1
    }

    prompt = f"""以下のRPGのスキルのSkills.jsonデータを24個生成してください（IDは2〜25）。
ゲームタイトル: {concept.get('title', 'RPG')}
世界観: {concept.get('world', '')}

スキルの種類（バランスよく含める）:
- 物理攻撃スキル（単体・全体）
- 魔法攻撃スキル（単体・全体・属性あり）
- 回復スキル（HP回復・状態異常回復）
- バフ/デバフスキル
- 必殺技

以下のJSON配列形式のみで出力してください（IDは2から始め25まで）:
[
  {{
    "id": 2,
    "name": "スキル名（日本語）",
    "description": "説明（日本語、20字以内）",
    "animationId": -1,
    "damage": {{
      "critical": false,
      "elementId": 0,
      "formula": "a.atk * 3 - b.def * 2",
      "type": 1,
      "variance": 15
    }},
    "effects": [],
    "hitType": 1,
    "iconIndex": 64,
    "message1": "%1は%2を使った！",
    "message2": "",
    "mpCost": 10,
    "note": "",
    "occasion": 1,
    "repeats": 1,
    "requiredWtypeId1": 0,
    "requiredWtypeId2": 0,
    "scope": 1,
    "speed": 0,
    "stypeId": 1,
    "successRate": 100,
    "tpCost": 0,
    "tpGain": 0,
    "messageType": 1
  }},
  ... （24個）
]

注意:
- damage.type: 0=なし, 1=HP減少, 2=MP減少, 3=HP回復, 4=MP回復, 5=HP減少（吸収）, 6=MP減少（吸収）
- damage.elementId: 0=なし, 1=物理, 2=炎, 3=氷, 4=雷, 5=水, 6=土, 7=風, 8=光, 9=闇
- scope: 1=敵単体, 2=敵全体, 7=味方単体, 8=味方全体, 11=使用者
- hitType: 0=必中, 1=物理攻撃, 2=魔法攻撃
- stypeId: 1=魔法, 2=必殺技（0はスキルタイプなし）
- 回復スキルのdamage.typeは3（HP回復）でformulaは"a.mat * 4"等
- iconIndexは64〜120の適切な値"""

    raw_list = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)

    skills = [None, attack_skill]
    for i, skill in enumerate(raw_list):
        skill["id"] = i + 2
        skill.setdefault("animationId", -1)
        skill.setdefault("damage", {
            "critical": False,
            "elementId": 0,
            "formula": "a.atk * 2 - b.def",
            "type": 1,
            "variance": 15
        })
        skill.setdefault("effects", [])
        skill.setdefault("hitType", 1)
        skill.setdefault("iconIndex", 64 + (i % 50))
        skill.setdefault("message1", f"%1は{skill.get('name', 'スキル')}を使った！")
        skill.setdefault("message2", "")
        skill.setdefault("mpCost", 10)
        skill.setdefault("note", "")
        skill.setdefault("occasion", 1)
        skill.setdefault("repeats", 1)
        skill.setdefault("requiredWtypeId1", 0)
        skill.setdefault("requiredWtypeId2", 0)
        skill.setdefault("scope", 1)
        skill.setdefault("speed", 0)
        skill.setdefault("stypeId", 1)
        skill.setdefault("successRate", 100)
        skill.setdefault("tpCost", 0)
        skill.setdefault("tpGain", 0)
        skill.setdefault("messageType", 1)
        skills.append(skill)

    return skills


# ── Step 6: アイテム生成 ──────────────────────────────────────────

def generate_items(model, concept: dict, log=print, local_client=None) -> list:
    """Items.json形式のデータを生成（回復薬・フィールドアイテム等 15〜20個）"""
    log("\n[アイテム] アイテムデータ生成中...\n")

    prompt = f"""以下のRPGのアイテムのItems.jsonデータを18個生成してください（IDは1〜18）。
ゲームタイトル: {concept.get('title', 'RPG')}
世界観: {concept.get('world', '')}

アイテムの種類（バランスよく含める）:
- HP回復アイテム（小・中・大・完全回復）
- MP回復アイテム（小・中・大）
- 状態異常回復アイテム（毒・睡眠・混乱等）
- 戦闘補助アイテム（攻撃力UP等）
- フィールドアイテム（エーテル類）
- 特殊アイテム（蘇生薬等）

以下のJSON配列形式のみで出力してください:
[
  {{
    "id": 1,
    "name": "アイテム名（日本語）",
    "description": "説明（日本語、30字以内）",
    "animationId": 0,
    "consumable": true,
    "damage": {{
      "critical": false,
      "elementId": 0,
      "formula": "0",
      "type": 0,
      "variance": 20
    }},
    "effects": [
      {{"code": 11, "dataId": 0, "value1": 0.5, "value2": 0}}
    ],
    "hitType": 0,
    "iconIndex": 176,
    "itypeId": 1,
    "note": "",
    "occasion": 0,
    "price": 100,
    "repeats": 1,
    "scope": 7,
    "speed": 0,
    "successRate": 100,
    "tpGain": 0
  }},
  ... （18個）
]

注意:
- effects codeは: 11=HP回復(value1は回復率0.0〜1.0, value2は固定値), 12=MP回復, 22=ステート付与, 21=ステート解除
- scope: 7=味方単体, 8=味方全体, 9=味方単体（戦闘不能）, 14=使用者
- itypeId: 1=通常アイテム, 2=重要アイテム
- occasion: 0=常時, 1=バトルのみ, 2=メニューのみ
- price は 50〜5000の範囲で適切に設定"""

    raw_list = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)

    items = [None]
    for i, item in enumerate(raw_list):
        item["id"] = i + 1
        item.setdefault("animationId", 0)
        item.setdefault("consumable", True)
        item.setdefault("damage", {
            "critical": False, "elementId": 0, "formula": "0", "type": 0, "variance": 20
        })
        item.setdefault("effects", [{"code": 11, "dataId": 0, "value1": 0.3, "value2": 0}])
        item.setdefault("hitType", 0)
        item.setdefault("iconIndex", 176 + (i % 20))
        item.setdefault("itypeId", 1)
        item.setdefault("note", "")
        item.setdefault("occasion", 0)
        item.setdefault("price", 100 * (i + 1))
        item.setdefault("repeats", 1)
        item.setdefault("scope", 7)
        item.setdefault("speed", 0)
        item.setdefault("successRate", 100)
        item.setdefault("tpGain", 0)
        items.append(item)

    return items


# ── Step 7: 武器生成 ──────────────────────────────────────────────

def generate_weapons(model, concept: dict, log=print, local_client=None) -> list:
    """Weapons.json形式のデータを生成（10〜15個）"""
    log("\n[武器] 武器データ生成中...\n")

    prompt = f"""以下のRPGの武器のWeapons.jsonデータを12個生成してください（IDは1〜12）。
ゲームタイトル: {concept.get('title', 'RPG')}
世界観: {concept.get('world', '')}

武器の種類（バランスよく含める）:
- 剣（片手剣・両手剣）
- 槍
- 斧
- 杖（魔法使い向け）
- 弓
- 短剣

以下のJSON配列形式のみで出力してください:
[
  {{
    "id": 1,
    "name": "武器名（日本語）",
    "description": "説明（日本語、30字以内）",
    "animationId": 6,
    "etypeId": 1,
    "traits": [
      {{"code": 31, "dataId": 1, "value": 0}}
    ],
    "iconIndex": 97,
    "note": "",
    "params": [0, 0, 10, 0, 0, 0, 0, 0],
    "price": 500,
    "wtypeId": 1
  }},
  ... （12個）
]

注意:
- params配列は [HP補正, MP補正, 攻撃力補正, 防御力補正, 魔法力補正, 魔法防御補正, 敏捷補正, 運補正]
- etypeId: 1=武器（固定）
- wtypeId: 1=短剣, 2=剣, 3=フレイル, 4=斧, 5=鞭, 6=杖, 7=弓, 8=クロスボウ, 9=弾, 10=長剣, 11=槍, 12=武具
- price は 300〜10000の範囲で強さに応じて設定
- iconIndex は 96〜112の範囲で設定"""

    raw_list = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)

    weapons = [None]
    for i, weapon in enumerate(raw_list):
        weapon["id"] = i + 1
        weapon.setdefault("animationId", 6)
        weapon.setdefault("etypeId", 1)
        weapon.setdefault("traits", [{"code": 31, "dataId": 1, "value": 0}])
        weapon.setdefault("iconIndex", 97 + (i % 15))
        weapon.setdefault("note", "")
        weapon.setdefault("params", [0, 0, 10 + i * 3, 0, 0, 0, 0, 0])
        weapon.setdefault("price", 500 * (i + 1))
        weapon.setdefault("wtypeId", 2)
        weapons.append(weapon)

    return weapons


# ── Step 8: 防具生成 ──────────────────────────────────────────────

def generate_armors(model, concept: dict, log=print, local_client=None) -> list:
    """Armors.json形式のデータを生成（10〜15個）"""
    log("\n[防具] 防具データ生成中...\n")

    prompt = f"""以下のRPGの防具のArmors.jsonデータを12個生成してください（IDは1〜12）。
ゲームタイトル: {concept.get('title', 'RPG')}
世界観: {concept.get('world', '')}

防具の種類（バランスよく含める）:
- 鎧（重・軽）
- ローブ（魔法使い向け）
- 盾
- 兜・帽子
- 装飾品（リング・アクセサリー）

以下のJSON配列形式のみで出力してください:
[
  {{
    "id": 1,
    "name": "防具名（日本語）",
    "description": "説明（日本語、30字以内）",
    "atypeId": 1,
    "etypeId": 4,
    "traits": [
      {{"code": 22, "dataId": 1, "value": 0.1}}
    ],
    "iconIndex": 135,
    "note": "",
    "params": [0, 0, 0, 10, 0, 5, 0, 0],
    "price": 400
  }},
  ... （12個）
]

注意:
- params配列は [HP補正, MP補正, 攻撃力補正, 防御力補正, 魔法力補正, 魔法防御補正, 敏捷補正, 運補正]
- etypeId: 2=盾, 3=頭防具, 4=体防具, 5=装飾品
- atypeId: 1=一般防具, 2=魔法防具, 3=軽装備, 4=重装備, 5=小型盾, 6=大型盾
- price は 300〜8000の範囲で強さに応じて設定
- iconIndex は 128〜160の範囲で設定"""

    raw_list = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)

    armors = [None]
    for i, armor in enumerate(raw_list):
        armor["id"] = i + 1
        armor.setdefault("atypeId", 1)
        armor.setdefault("etypeId", 4)
        armor.setdefault("traits", [])
        armor.setdefault("iconIndex", 135 + (i % 20))
        armor.setdefault("note", "")
        armor.setdefault("params", [0, 0, 0, 8 + i * 2, 0, 5 + i, 0, 0])
        armor.setdefault("price", 400 * (i + 1))
        armors.append(armor)

    return armors


# ── Step 9: トループ生成 ──────────────────────────────────────────

def generate_troops(model, concept: dict, enemies: list, log=print, local_client=None) -> list:
    """Troops.json形式のデータを生成（8〜12グループ）"""
    log("\n[トループ] 敵グループデータ生成中...\n")

    # enemies[0]はnullなのでskip
    enemy_list = enemies[1:]
    enemy_desc = "\n".join(
        f"  id={e['id']}: {e['name']}"
        for e in enemy_list if e
    )

    prompt = f"""以下のRPGの敵グループ（トループ）のTroops.jsonデータを10グループ生成してください。
ゲームタイトル: {concept.get('title', 'RPG')}

登場する敵キャラクター:
{enemy_desc}

以下のJSON配列形式のみで出力してください:
[
  {{
    "id": 1,
    "name": "グループ名（日本語）",
    "members": [
      {{"enemyId": 1, "x": 336, "y": 436, "hidden": false}},
      {{"enemyId": 1, "x": 480, "y": 436, "hidden": false}}
    ],
    "pages": [
      {{
        "conditions": {{
          "actorHp": 50, "actorId": 1, "actorValid": false,
          "enemyHp": 50, "enemyIndex": 0, "enemyValid": false,
          "switchId": 1, "switchValid": false,
          "turnA": 0, "turnB": 0, "turnEnding": false, "turnValid": false
        }},
        "list": [{{"code": 0, "indent": 0, "parameters": []}}],
        "span": 0
      }}
    ]
  }},
  ... （10グループ）
]

注意:
- membersのx座標は192〜624の範囲、y座標は344〜480の範囲
- 同じ敵を複数体配置する場合はx座標をずらす（144ずつ）
- 弱いグループ（id=1〜3）は弱い敵（enemyId=1〜3）のみ
- 中程度のグループ（id=4〜7）は中程度の敵
- 強いグループ（id=8〜10）は強い敵や混成
- pagesは最低1つ必要（バトルイベントなしでOK）"""

    raw_list = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)

    troops = [None]
    for i, troop in enumerate(raw_list):
        troop["id"] = i + 1
        troop.setdefault("members", [
            {"enemyId": min(i + 1, len(enemy_list)), "x": 336, "y": 436, "hidden": False}
        ])
        troop.setdefault("pages", [{
            "conditions": {
                "actorHp": 50, "actorId": 1, "actorValid": False,
                "enemyHp": 50, "enemyIndex": 0, "enemyValid": False,
                "switchId": 1, "switchValid": False,
                "turnA": 0, "turnB": 0, "turnEnding": False, "turnValid": False
            },
            "list": [{"code": 0, "indent": 0, "parameters": []}],
            "span": 0
        }])
        troops.append(troop)

    return troops


# ── Step 10: マップイベント生成 ───────────────────────────────────

def generate_map_events(model, concept: dict, map_type: str, map_info: dict, log=print, local_client=None) -> list:
    """マップ上のイベント（NPC・宝箱・ダンジョン入口等）を生成

    map_type: "town" / "dungeon" / "world"
    戻り値: MZ events配列（index 0はnull）
    """
    log(f"\n[マップイベント] {map_info.get('displayName', map_type)}のイベント生成中...\n")

    if map_type == "town":
        event_guide = """
町マップのイベント（5〜8個）:
- NPC（村人・商人・情報提供者）: 3〜4人
- 宝箱: 1〜2個
- 看板: 1個
- 道具屋/武器屋の入口: 1個（別マップへの移動）

キャラクタースプライト例:
- NPC: People1, People2, People3, People4 (characterIndex 0-7)
- 宝箱: !Chest (characterIndex 0)
"""
    elif map_type == "dungeon":
        event_guide = """
ダンジョンマップのイベント（4〜6個）:
- 宝箱: 2〜3個（アイテム・武器・防具が手に入る）
- 落とし穴/罠: 1個
- ボス戦トリガー: 1個（最深部）
- ヒント石碑/看板: 1個

キャラクタースプライト例:
- 宝箱: !Chest (characterIndex 0)
- 石碑: !Other1 (characterIndex 0)
"""
    else:  # world
        event_guide = """
ワールドマップのイベント（3〜5個）:
- 町への入口: 2〜3個
- ダンジョンへの入口: 1〜2個
- 情報看板: 1個
"""

    npc_names = "\n".join(
        f"  - {t['name']}の住人" for t in concept.get("towns", [])
    )

    prompt = f"""以下のRPGの{map_type}マップのイベントデータを生成してください。
ゲームタイトル: {concept.get('title', 'RPG')}
マップ名: {map_info.get('displayName', map_type)}
{event_guide}

登場する町:
{npc_names}

以下のJSON配列形式のみで出力してください（最初の要素はnull）:
[
  null,
  {{
    "id": 1,
    "name": "イベント名",
    "x": 5,
    "y": 5,
    "pages": [
      {{
        "conditions": {{
          "actorId": 1, "actorValid": false,
          "itemId": 1, "itemValid": false,
          "selfSwitchCh": "A", "selfSwitchValid": false,
          "switch1Id": 1, "switch1Valid": false,
          "switch2Id": 1, "switch2Valid": false,
          "variableId": 1, "variableValid": false, "variableValue": 0
        }},
        "directionFix": false,
        "image": {{
          "characterIndex": 0,
          "characterName": "People1",
          "direction": 2,
          "pattern": 0,
          "tileId": 0
        }},
        "list": [
          {{"code": 101, "indent": 0, "parameters": ["", 0, 0, 2, ""]}},
          {{"code": 401, "indent": 0, "parameters": ["こんにちは！（日本語のセリフ）"]}},
          {{"code": 0, "indent": 0, "parameters": []}}
        ],
        "moveFrequency": 3,
        "moveRoute": {{"list": [{{"code": 0, "parameters": []}}], "repeat": true, "skippable": false, "wait": false}},
        "moveSpeed": 3,
        "moveType": 0,
        "priorityType": 1,
        "stepAnime": false,
        "through": false,
        "trigger": 0,
        "walkAnime": true
      }}
    ],
    "note": ""
  }},
  ... （イベント数分）
]

注意:
- x, y座標はマップサイズ（17x13）内に収める（x: 1〜15, y: 1〜11）
- 宝箱の場合: characterName="!Chest", trigger=0（決定キー）
  宝箱listの例: [{{"code": 605, "indent": 0, "parameters": [1, 1, 0, 0]}}]（アイテム取得）の後に終了
- NPC: trigger=0（決定キー）, moveType=1（ランダム移動）や0（固定）
- code 101: メッセージウィンドウ開始, parameters=["顔グラ名", 顔インデックス, 背景, ウィンドウ位置, 話者名]
- code 401: メッセージテキスト（日本語で実際のセリフを書く）
- code 0: コマンド終了（必須）
- priorityType: 0=通常キャラの下, 1=通常キャラと同じ, 2=通常キャラの上
- 全てのlistは必ずcode:0で終わること"""

    for attempt in range(3):
        try:
            raw = _stream(model, prompt, log=log, local_client=local_client)
            m = re.search(r'\[[\s\S]+\]', raw)
            if m:
                events = json.loads(m.group())
                # 先頭がnullでない場合は挿入
                if events and events[0] is not None:
                    events.insert(0, None)
                # 各イベントのIDを正規化
                for i, ev in enumerate(events):
                    if ev is not None:
                        ev["id"] = i
                        ev.setdefault("note", "")
                return events
        except (json.JSONDecodeError, Exception) as e:
            log(f"  マップイベント生成エラー (試行 {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(2)

    # 失敗時はデフォルトの簡単なイベントを返す
    log("  マップイベント生成失敗。デフォルトイベントを使用します。")
    return _default_events(map_type)


def _default_events(map_type: str) -> list:
    """生成失敗時のデフォルトイベント"""
    events = [None]
    if map_type == "town":
        events.append({
            "id": 1, "name": "村人", "x": 5, "y": 5, "note": "",
            "pages": [{
                "conditions": {
                    "actorId": 1, "actorValid": False, "itemId": 1, "itemValid": False,
                    "selfSwitchCh": "A", "selfSwitchValid": False,
                    "switch1Id": 1, "switch1Valid": False, "switch2Id": 1, "switch2Valid": False,
                    "variableId": 1, "variableValid": False, "variableValue": 0
                },
                "directionFix": False,
                "image": {"characterIndex": 0, "characterName": "People1",
                          "direction": 2, "pattern": 0, "tileId": 0},
                "list": [
                    {"code": 101, "indent": 0, "parameters": ["", 0, 0, 2, "村人"]},
                    {"code": 401, "indent": 0, "parameters": ["この町へようこそ！"]},
                    {"code": 0, "indent": 0, "parameters": []}
                ],
                "moveFrequency": 3,
                "moveRoute": {"list": [{"code": 0, "parameters": []}], "repeat": True, "skippable": False, "wait": False},
                "moveSpeed": 3, "moveType": 0, "priorityType": 1,
                "stepAnime": False, "through": False, "trigger": 0, "walkAnime": True
            }]
        })
    elif map_type == "dungeon":
        events.append({
            "id": 1, "name": "宝箱", "x": 8, "y": 6, "note": "",
            "pages": [{
                "conditions": {
                    "actorId": 1, "actorValid": False, "itemId": 1, "itemValid": False,
                    "selfSwitchCh": "A", "selfSwitchValid": False,
                    "switch1Id": 1, "switch1Valid": False, "switch2Id": 1, "switch2Valid": False,
                    "variableId": 1, "variableValid": False, "variableValue": 0
                },
                "directionFix": True,
                "image": {"characterIndex": 0, "characterName": "!Chest",
                          "direction": 2, "pattern": 0, "tileId": 0},
                "list": [
                    {"code": 605, "indent": 0, "parameters": [1, 1, 0, 0]},
                    {"code": 0, "indent": 0, "parameters": []}
                ],
                "moveFrequency": 3,
                "moveRoute": {"list": [{"code": 0, "parameters": []}], "repeat": True, "skippable": False, "wait": False},
                "moveSpeed": 3, "moveType": 0, "priorityType": 1,
                "stepAnime": False, "through": False, "trigger": 0, "walkAnime": False
            }]
        })
    return events


# ── Step 11: 章構成生成（6時間RPG用） ────────────────────────────────

def generate_chapters(model, concept: dict, settings: dict = None,
                      log=print, local_client=None) -> list:
    """ゲーム全体を複数章に分割したストーリー構成を生成。
    戻り値: [{"chapter": 1, "title": "...", "summary": "...",
              "key_events": [...], "dungeon": "...", "boss": "..."}, ...]
    """
    s = settings or {}
    chapter_count = max(2, min(6, int(s.get("chapter_count", 4))))
    log(f"\n[章構成] {chapter_count}章のストーリー構成を生成中...\n")

    towns     = [t["name"] for t in concept.get("towns", [])]
    dungeons  = [d["name"] for d in concept.get("dungeons", [])]
    villain   = concept.get("villain", {}).get("name", "ラスボス")

    prompt = f"""以下のRPGを{chapter_count}章構成にしてください。

タイトル: {concept.get('title', 'RPG')}
あらすじ: {concept.get('story', '')}
町: {', '.join(towns)}
ダンジョン: {', '.join(dungeons)}
ラスボス: {villain}

各章に意味のある分岐・盛り上がりを設け、プレイヤーが飽きないよう展開してください。

以下のJSON配列形式のみで出力してください:
[
  {{
    "chapter": 1,
    "title": "第1章タイトル",
    "summary": "この章のあらすじ（100字程度）",
    "key_events": ["重要イベント1（NPC名・場所・内容）", "重要イベント2", "重要イベント3"],
    "location": "この章の主な舞台（町またはダンジョン名）",
    "boss": "この章のボス名（またはnull）",
    "estimated_minutes": 90
  }}
]"""

    try:
        result = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)
        return result if isinstance(result, list) else []
    except Exception as e:
        log(f"  章構成生成エラー（スキップ）: {e}")
        return []


# ── Step 12: サブクエスト生成（6時間RPG用） ──────────────────────────

def generate_side_quests(model, concept: dict, settings: dict = None,
                         log=print, local_client=None) -> list:
    """サブクエスト一覧を生成。
    戻り値: [{"id": 1, "title": "...", "giver": "...", "location": "...",
              "objective": "...", "reward": "...", "description": "..."}, ...]
    """
    s = settings or {}
    quest_count = max(5, min(20, int(s.get("side_quest_count", 12))))
    log(f"\n[サブクエスト] {quest_count}個のサブクエストを生成中...\n")

    towns = [t["name"] for t in concept.get("towns", [])]

    prompt = f"""以下のRPGの脇道サブクエストを{quest_count}個考えてください。

タイトル: {concept.get('title', 'RPG')}
世界観: {concept.get('world', '')}
町: {', '.join(towns)}

メインストーリーと並行してプレイヤーが楽しめる、やりがいのある依頼・探索・収集クエストを
バランスよく作ってください（メイン進行に必要ないもの）。

以下のJSON配列形式のみで出力してください:
[
  {{
    "id": 1,
    "title": "クエスト名",
    "giver": "依頼人NPCの名前と職業",
    "location": "依頼を受ける町名",
    "objective": "目標（例: ○○を3個集める、○○を倒す）",
    "reward": "報酬（例: ゴールド500、レアアイテム○○）",
    "description": "依頼内容の詳細説明（NPC台詞風に、80字程度）",
    "estimated_minutes": 15
  }}
]"""

    try:
        result = _parse_list_with_retry(model, prompt, log=log, local_client=local_client)
        return result if isinstance(result, list) else []
    except Exception as e:
        log(f"  サブクエスト生成エラー（スキップ）: {e}")
        return []


# ── ダンジョンフロアイベント生成 ──────────────────────────────────────

def generate_dungeon_floor_events(model, concept: dict, dungeon_info: dict,
                                   floor: int, total_floors: int,
                                   log=print, local_client=None) -> list:
    """ダンジョンの特定フロアのイベントを生成（階段付き）。
    floor=1が最上階、floor=total_floorsが最深階（ボス）。
    """
    is_boss_floor = (floor == total_floors)
    floor_label = f"B{floor}F" if floor > 1 else "1F"
    log(f"\n[マップイベント] {dungeon_info.get('displayName', 'ダンジョン')} {floor_label} イベント生成中...\n")

    boss_note = f"このフロアには{concept.get('villain', {}).get('name', 'ボス')}との決戦トリガーがある。" if is_boss_floor else ""
    stair_note = "上の階への階段（戻る用）と下の階への階段（進む用）の2つの階段イベントを含める。" if 1 < floor < total_floors else \
                 ("ダンジョン入口への戻り口と下の階への階段を含める。" if floor == 1 else "上の階への階段（戻る用）とボス戦トリガーを含める。")

    prompt = f"""以下のRPGダンジョン「{dungeon_info.get('displayName', 'ダンジョン')}」の{floor_label}（全{total_floors}階）のイベントを生成してください。

ゲームタイトル: {concept.get('title', 'RPG')}
{boss_note}
{stair_note}

イベント構成（計5〜7個）:
- 宝箱: 2〜3個（{floor}階相当の強さのアイテム）
- 石碑/ヒント: 1個（ストーリーの断片や謎のヒント）
- 階段イベント: 1〜2個（別マップへの移動）
{"- ボス戦トリガー: 1個" if is_boss_floor else ""}

以下のJSON配列形式のみで出力してください（最初の要素はnull）:
[
  null,
  {{
    "id": 1,
    "name": "イベント名",
    "x": 8, "y": 6,
    "pages": [{{
      "conditions": {{"actorId":1,"actorValid":false,"itemId":1,"itemValid":false,
        "selfSwitchCh":"A","selfSwitchValid":false,"switch1Id":1,"switch1Valid":false,
        "switch2Id":1,"switch2Valid":false,"variableId":1,"variableValid":false,"variableValue":0}},
      "directionFix": false,
      "image": {{"characterIndex":0,"characterName":"!Chest","direction":2,"pattern":0,"tileId":0}},
      "list": [
        {{"code":605,"indent":0,"parameters":[1,1,0,0]}},
        {{"code":0,"indent":0,"parameters":[]}}
      ],
      "moveFrequency":3,
      "moveRoute":{{"list":[{{"code":0,"parameters":[]}}],"repeat":true,"skippable":false,"wait":false}},
      "moveSpeed":3,"moveType":0,"priorityType":1,
      "stepAnime":false,"through":false,"trigger":0,"walkAnime":false
    }}]
  }}
]"""

    for attempt in range(3):
        raw = _stream(model, prompt, log=log, local_client=local_client)
        m = re.search(r'\[[\s\S]+\]', raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        if attempt < 2:
            time.sleep(2)

    # フォールバック: デフォルト階段イベント
    return _default_floor_events(floor, total_floors)


# ── バッチ生成（複数データを1APIコールで生成） ──────────────────────

def generate_actors_and_classes(model, concept: dict, log=print, local_client=None) -> tuple:
    """actors + classes を1回のAPIコールで同時生成。(actors_list, classes_list) を返す"""
    log("\n[バッチ] アクター＋クラス同時生成中...\n")
    party = concept.get("party", [])[:4]
    num = len(party)
    party_desc = "\n".join(
        f"{i+1}. 名前:{m['name']} 職業:{m['class']} 説明:{m['description']}"
        for i, m in enumerate(party)
    )
    prompt = f"""以下のRPGのActors.jsonとClasses.jsonデータを同時に生成してください。
ゲームタイトル: {concept.get('title','RPG')}
パーティ({num}人): {party_desc}

以下のJSON形式のみで出力してください（他テキスト不要）:
{{
  "actors": [
    null,
    {{"id":1,"name":"名前","nickname":"","classId":1,"initialLevel":1,"maxLevel":99,
      "characterName":"Actor1","characterIndex":0,"faceName":"Actor1","faceIndex":0,
      "battlerName":"Actor1_1","equips":[1,1,2,3,0],"traits":[],"note":"","profile":""}}
  ],
  "classes": [
    null,
    {{"id":1,"name":"クラス名","expParams":[30,20,30,30],"params":[[15,400],[4,80],[4,80],[4,80],[4,80],[4,80],[4,80],[4,80]],
      "skills":[{{"level":1,"skillId":1}}],"learnings":[],"traits":[],"note":""}}
  ]
}}
actorsは{num}個、classesは{num}個生成してください。"""

    for attempt in range(3):
        raw = _stream(model, prompt, log=log, local_client=local_client)
        m = re.search(r'\{[\s\S]+\}', raw)
        if m:
            try:
                data = json.loads(m.group())
                actors = data.get("actors", [])
                classes = data.get("classes", [])
                if actors and classes:
                    if actors[0] is not None:
                        actors.insert(0, None)
                    if classes[0] is not None:
                        classes.insert(0, None)
                    log(f"  ✓ アクター{len(actors)-1}人 / クラス{len(classes)-1}個")
                    return actors, classes
            except json.JSONDecodeError:
                pass
        if attempt < 2:
            time.sleep(2)

    log("  バッチ生成失敗 → 個別生成にフォールバック")
    return generate_actors(model, concept, log=log, local_client=local_client), \
           generate_classes(model, concept, log=log, local_client=local_client)


def generate_items_weapons_armors(model, concept: dict, log=print, local_client=None) -> tuple:
    """items + weapons + armors を1回のAPIコールで同時生成。(items, weapons, armors) を返す"""
    log("\n[バッチ] アイテム＋武器＋防具同時生成中...\n")
    prompt = f"""以下のRPGのItems.json・Weapons.json・Armors.jsonデータを同時に生成してください。
ゲームタイトル: {concept.get('title','RPG')}
世界観: {concept.get('world','')}

以下のJSON形式のみで出力してください:
{{
  "items": [
    null,
    {{"id":1,"name":"ポーション","description":"HPを50回復","iconIndex":176,"itypeId":1,
      "price":50,"consumable":true,"scope":7,"occasion":0,"speed":0,"successRate":100,
      "repeats":1,"tpGain":0,"hitType":0,"animationId":0,"effects":[{{"code":11,"dataId":0,"value1":50,"value2":0}}],
      "traits":[],"note":""}}
  ],
  "weapons": [
    null,
    {{"id":1,"name":"銅の剣","description":"","iconIndex":97,"wtypeId":1,"etypeId":1,
      "price":100,"params":[0,0,10,0,0,0,0,0],"traits":[],"note":""}}
  ],
  "armors": [
    null,
    {{"id":1,"name":"布の服","description":"","iconIndex":129,"atypeId":1,"etypeId":2,
      "price":50,"params":[0,0,0,5,0,0,0,0],"traits":[],"note":""}}
  ]
}}
items: 薬草・解毒薬・テレポート等8個、weapons: 剣・杖・弓・ナイフ等8個、armors: 鎧・ローブ・盾等8個。
IDは1から連番で付けてください。"""

    for attempt in range(3):
        raw = _stream(model, prompt, log=log, local_client=local_client)
        m = re.search(r'\{[\s\S]+\}', raw)
        if m:
            try:
                data = json.loads(m.group())
                items   = data.get("items",   [])
                weapons = data.get("weapons", [])
                armors  = data.get("armors",  [])
                if items and weapons and armors:
                    for lst in (items, weapons, armors):
                        if lst[0] is not None:
                            lst.insert(0, None)
                    log(f"  ✓ アイテム{len(items)-1} / 武器{len(weapons)-1} / 防具{len(armors)-1}")
                    return items, weapons, armors
            except json.JSONDecodeError:
                pass
        if attempt < 2:
            time.sleep(2)

    log("  バッチ生成失敗 → 個別生成にフォールバック")
    return (generate_items(model, concept, log=log, local_client=local_client),
            generate_weapons(model, concept, log=log, local_client=local_client),
            generate_armors(model, concept, log=log, local_client=local_client))


def _default_floor_events(floor: int, total_floors: int) -> list:
    """生成失敗時のデフォルトフロアイベント"""
    events = [None]
    # 宝箱
    events.append({
        "id": 1, "name": "宝箱", "x": 8, "y": 6, "note": "",
        "pages": [{"conditions": {"actorId":1,"actorValid":False,"itemId":1,"itemValid":False,
            "selfSwitchCh":"A","selfSwitchValid":False,"switch1Id":1,"switch1Valid":False,
            "switch2Id":1,"switch2Valid":False,"variableId":1,"variableValid":False,"variableValue":0},
            "directionFix": True,
            "image": {"characterIndex":0,"characterName":"!Chest","direction":2,"pattern":0,"tileId":0},
            "list": [{"code":605,"indent":0,"parameters":[1,1,0,0]},{"code":0,"indent":0,"parameters":[]}],
            "moveFrequency":3,"moveRoute":{"list":[{"code":0,"parameters":[]}],"repeat":True,"skippable":False,"wait":False},
            "moveSpeed":3,"moveType":0,"priorityType":1,"stepAnime":False,"through":False,"trigger":0,"walkAnime":False}]
    })
    # 階段
    stair_text = "下の階へ進む" if floor < total_floors else "ボスが待っている..."
    events.append({
        "id": 2, "name": "階段", "x": 14, "y": 10, "note": "",
        "pages": [{"conditions": {"actorId":1,"actorValid":False,"itemId":1,"itemValid":False,
            "selfSwitchCh":"A","selfSwitchValid":False,"switch1Id":1,"switch1Valid":False,
            "switch2Id":1,"switch2Valid":False,"variableId":1,"variableValid":False,"variableValue":0},
            "directionFix": False,
            "image": {"characterIndex":0,"characterName":"!Other1","direction":2,"pattern":0,"tileId":0},
            "list": [
                {"code":101,"indent":0,"parameters":["",0,0,2,""]},
                {"code":401,"indent":0,"parameters":[stair_text]},
                {"code":0,"indent":0,"parameters":[]}
            ],
            "moveFrequency":3,"moveRoute":{"list":[{"code":0,"parameters":[]}],"repeat":True,"skippable":False,"wait":False},
            "moveSpeed":3,"moveType":0,"priorityType":1,"stepAnime":False,"through":False,"trigger":0,"walkAnime":False}]
    })
    return events
