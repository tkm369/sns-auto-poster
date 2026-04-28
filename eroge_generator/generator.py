"""
Gemini API を使った生成ロジック
タイトル・キャラクター・あらすじ・全シーンを自動生成する
"""
import json
import re
import time
import queue as _q
import threading as _th
import google.generativeai as genai


def _parse_retry_after(error_str: str) -> int:
    """429レート制限エラーから待機秒数を取得する"""
    m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', str(error_str), re.DOTALL)
    return int(m.group(1)) + 3 if m else 0


def _stream(model, prompt: str, system: str = "", log=print,
            local_client=None) -> str:
    """Gemini または ローカルモデルを呼び出しテキストを返す。"""
    # ローカルモデル優先
    if local_client is not None:
        from local_model import generate_local
        return generate_local(prompt, system=system,
                              base_url=local_client["base_url"],
                              max_tokens=16000, log=log)

    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    max_attempts = 5
    _WALL_TIMEOUT = 120
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

            result = []
            chars = 0
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
                retry_after = _parse_retry_after(err)
                if retry_after:
                    log(f"  ⚠️ レート制限 — {retry_after}秒後にリトライ... ({attempt+1}/{max_attempts})")
                    time.sleep(retry_after)
                else:
                    wait = 5 + attempt * 5
                    log(f"  API呼び出しエラー: {err[:80]} → {wait}秒後にリトライ ({attempt+1}/{max_attempts})")
                    time.sleep(wait)
            else:
                raise


def _clean(text: str) -> str:
    """コードブロック記号・余分なマークダウンを除去"""
    text = re.sub(r"```[a-z]*\n?", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()


def _parse_json_with_retry(model, prompt: str, system: str = "",
                           max_retry: int = 3, log=print,
                           local_client=None) -> dict:
    """JSONが壊れていたら最大 max_retry 回リトライして返す"""
    for attempt in range(max_retry):
        raw = _stream(model, prompt, system, log=log, local_client=local_client)
        m = re.search(r'\{[\s\S]+\}', raw)
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


# ── Step 1: タイトル・キャラクター・設定を自動生成 ─────────────────
def generate_concept(model, genre: dict, fmt: dict, adult: bool,
                     archetype: dict = None, h_tags: list = None,
                     extra_context: dict = None, log=print,
                     local_client=None) -> dict:
    """ジャンル+シナリオ形式からエロゲコンセプト（タイトル・キャラ・設定）を生成"""
    log("\n[1/4] コンセプト生成中...\n")
    archetype_note = f"ヒロインの属性: {archetype['name']}（{archetype['description']}）" if archetype else ""
    h_tag_note = f"Hシーンのタグ・要素: {', '.join(h_tags)}" if h_tags else "バニラ・甘めのHシーン"
    h_intensity = fmt.get("h_intensity", "中程度")

    # AIプロデューサーとの相談内容を反映
    extra_note = ""
    if extra_context:
        parts = []
        if extra_context.get("title_direction"):
            parts.append(f"タイトルの方向性: {extra_context['title_direction']}")
        if extra_context.get("unique_hook"):
            parts.append(f"独自の売り・フック: {extra_context['unique_hook']}")
        if extra_context.get("heroine_details"):
            parts.append(f"ヒロインの詳細: {extra_context['heroine_details']}")
        if extra_context.get("special_requests"):
            parts.append(f"特別な要望: {extra_context['special_requests']}")
        if parts:
            extra_note = "\n【AIプロデューサーとの相談で決まった追加要件】\n" + "\n".join(parts)

    prompt = f"""以下の条件で成人向けビジュアルノベル（エロゲ）のコンセプトを考えてください。
このゲームはR18専用のアダルト作品です。

ジャンル: {genre['name']}（舞台: {genre['setting']}、雰囲気: {genre['atmosphere']}）
シナリオ形式: {fmt['name']} — {fmt['description']}
ヒロイン人数: {fmt['heroine_count']}人
{archetype_note}
{h_tag_note}
エロシーンの強度: {h_intensity}

エロゲとして魅力的なタイトル・キャラクター・設定を考えてください。
DLSiteで売れるような、プレイヤーの欲求に刺さるコンセプトにしてください。
{extra_note}

以下のJSON形式のみで出力してください（他のテキスト不要）:
{{
  "title": "ゲームタイトル（エロゲらしい煽情的なタイトル）",
  "tagline": "キャッチコピー（20字以内、購買意欲を刺激する一言）",
  "setting": "具体的な舞台設定（2〜3文）",
  "protagonist": {{
    "name": "主人公の名前",
    "gender": "male",
    "description": "主人公の性格・特徴（1文）"
  }},
  "heroines": [
    {{
      "name": "ヒロイン名（日本語の名前）",
      "age": 18,
      "role": "主人公との関係・役割",
      "personality": "性格（1文）",
      "appearance": "外見の特徴（1文、エロゲらしいスタイルの描写含む）",
      "h_appeal": "このキャラのエロ的な魅力・見どころ（1文）",
      "var_name": "renpy用英字変数名（例: sakura）"
    }}
  ]
}}

注意: ヒロインの年齢は必ず18歳以上にすること"""

    return _parse_json_with_retry(model, prompt, log=log, local_client=local_client)


# ── Step 2: あらすじ・シーン構成を生成 ────────────────────────────
def generate_outline(model, concept: dict, genre: dict, fmt: dict,
                     num_scenes: int, adult: bool,
                     h_scenes: int = 0, h_tags: list = None,
                     log=print, local_client=None) -> str:
    log("\n[2/4] あらすじ・シーン構成生成中...\n")
    heroine_desc = "\n".join(
        f"- {h['name']}（{h['role']}）: {h['personality']} / エロ的魅力: {h.get('h_appeal', '')}"
        for h in concept["heroines"]
    )
    h_tag_note = f"含めるHシーン要素: {', '.join(h_tags)}" if h_tags else ""
    normal_scenes = num_scenes - h_scenes

    prompt = f"""以下のエロゲコンセプトで{num_scenes}シーン構成のビジュアルノベルのあらすじを作ってください。
このゲームはR18成人向けです。

タイトル: {concept['title']}
ジャンル: {genre['name']} / シナリオ: {fmt['name']}
舞台: {concept['setting']}
主人公: {concept['protagonist']['description']}
ヒロイン:
{heroine_desc}
{h_tag_note}

シーン構成の指針:
- 通常シーン（ストーリー・会話・雰囲気作り）: {normal_scenes}シーン
- Hシーン（濃厚な性描写を含む）: {h_scenes}シーン
- Hシーンはシナリオの流れ上自然な位置に配置し、[Hシーン]と明記すること
- 最初の1〜2シーンは導入・キャラ紹介、終盤にクライマックスのHシーンを配置

出力形式:
【全体あらすじ】（150〜200字）
（あらすじ本文）

【シーン構成】
シーン1: タイトル — 概要（1文）[Hシーンは末尾に [Hシーン] と付ける]
...シーン{num_scenes}まで"""

    return _stream(model, prompt, log=log, local_client=local_client)


# ── Step 3: キャラクター define 文を生成 ─────────────────────────
def _make_var_name(name: str) -> str:
    """日本語名からRen'Py用英字変数名を生成（フォールバック用）"""
    import unicodedata
    # ローマ字化は難しいので、名前の文字コードからシンプルな英字列を生成
    ascii_name = name.encode("ascii", errors="ignore").decode()
    if ascii_name:
        return re.sub(r"[^a-zA-Z]", "", ascii_name).lower() or "heroine"
    # 日本語のみの場合はインデックスで命名
    return "heroine"


def generate_char_defs(model, concept: dict, log=print, local_client=None) -> str:
    log("\n[3a] キャラクター定義生成中...\n")
    heroines = concept.get("heroines", [])
    # var_name が欠けている場合はインデックスから補完
    for i, h in enumerate(heroines):
        if not h.get("var_name"):
            h["var_name"] = _make_var_name(h.get("name", f"heroine{i+1}")) or f"heroine{i+1}"
    heroine_list = "\n".join(
        f"  - 変数名: {h['var_name']}, 表示名: {h['name']}, 役割: {h['role']}"
        for h in heroines
    )
    prompt = f"""以下のキャラクターに対して Ren'Py の define 文を生成してください。

主人公名: {concept['protagonist']['name']}
ヒロイン:
{heroine_list}

ルール:
- narrator は必ず含める
- コードブロック記号（```）は使わない
- 1行1define の形式のみで出力する

形式例:
define narrator = Character(None, kind=nvl)
define sakura = Character("桜井 愛", color="#ff69b4")"""

    return _stream(model, prompt, log=log, local_client=local_client)


# ── Step 4: 各シーンのスクリプトを生成 ──────────────────────────
SCENE_SYSTEM = """あなたはエロゲ専門の熟練シナリオライターです。
R18成人向けビジュアルノベルのシナリオをRen'Pyスクリプト形式で書いてください。

厳守ルール:
- ナレーション: narrator "テキスト"
- キャラ台詞: [変数名] "台詞"
- 背景切り替え: scene bg_xxx with dissolve
- キャラ表示: show [変数名] [表情] at [left/center/right]
- label は scene_[番号]: 形式（コロンあり）
- コードブロック記号（``` など）は絶対に使わない
- 各シーン最低20行以上の台詞・ナレーションを書く
- Hシーンは官能的・扇情的な日本語で詳細に描写する
- 通常シーンは感情豊かで自然な日本語で書く"""

def _scene_note(scene_num: int, outline: str, h_tags: list) -> tuple[str, bool]:
    """シーン番号からHシーン判定とプロンプト注釈を返す"""
    scene_lines = [l for l in outline.split("\n")
                   if f"シーン{scene_num}:" in l or f"シーン {scene_num}:" in l]
    is_h = any("[Hシーン]" in l for l in scene_lines)
    if is_h:
        h_tag_note = f"このHシーンに含める要素: {', '.join(h_tags)}" if h_tags else ""
        note = (f"【Hシーン】官能的で詳細な描写を30行以上。"
                f"ヒロインの感情・身体の反応・喘ぎ声・台詞を豊かに。{h_tag_note}")
    else:
        note = "【通常シーン】感情豊かな台詞・ナレーションを20行以上。"
    return note, is_h


def generate_scene(model, scene_num: int, total: int, concept: dict,
                   outline: str, char_defs: str, adult: bool,
                   h_tags: list = None, log=print,
                   local_client=None) -> str:
    """シーン1本を生成して返す"""
    note, is_h = _scene_note(scene_num, outline, h_tags or [])
    if is_h and local_client:
        log(f"  ※ローカルモデルでHシーン {scene_num} 生成中...")

    system = f"{SCENE_SYSTEM}\n\nキャラクター定義:\n{char_defs}"
    prompt = f"""以下のエロゲのシーン {scene_num} を書いてください。
タイトル: {concept['title']}
あらすじ:
{outline}

{note}
label scene_{scene_num}: から始めてください。"""
    return _stream(model, prompt, system=system, log=log, local_client=local_client)


def _generate_scene_batch(model, scene_nums: list, total: int, concept: dict,
                          outline: str, char_defs: str, h_tags: list,
                          log=print) -> dict:
    """複数シーンを1回のAPIコールでまとめて生成し {scene_num: text} を返す"""
    notes = []
    for n in scene_nums:
        note, _ = _scene_note(n, outline, h_tags or [])
        notes.append(f"=== シーン {n} ===\n{note}\nlabel scene_{n}: から始める")

    system = f"{SCENE_SYSTEM}\n\nキャラクター定義:\n{char_defs}"
    prompt = f"""以下のエロゲの複数シーンを続けて書いてください。各シーンは label scene_N: で始めてください。
タイトル: {concept['title']}
あらすじ:
{outline}

{'---'.join(notes)}"""

    raw = _stream(model, prompt, system=system, log=log)

    # label scene_N: で分割
    result = {}
    for i, n in enumerate(scene_nums):
        next_n = scene_nums[i + 1] if i + 1 < len(scene_nums) else None
        pattern = rf'(label scene_{n}:.*?)'
        end_pat = rf'label scene_{next_n}:' if next_n else r'$'
        m = re.search(rf'label scene_{n}:(.*?)(?=label scene_{next_n}:|$)',
                      raw, re.DOTALL)
        if m:
            result[n] = f"label scene_{n}:" + m.group(1).rstrip()
        else:
            result[n] = f"# シーン {n} 分割失敗\n"
    return result


def generate_all_scenes(model, concept: dict, outline: str, char_defs: str,
                        num_scenes: int, adult: bool, log=print,
                        cancel_event=None, h_tags: list = None,
                        local_client=None) -> list:
    import concurrent.futures

    # ローカルモデルは逐次（LM Studioが並列非対応）
    if local_client:
        scenes_dict = {}
        for i in range(1, num_scenes + 1):
            if cancel_event and cancel_event.is_set():
                break
            for attempt in range(3):
                try:
                    s = generate_scene(model, i, num_scenes, concept, outline,
                                       char_defs, adult, h_tags=h_tags, log=log,
                                       local_client=local_client)
                    scenes_dict[i] = s
                    break
                except Exception as e:
                    log(f"  シーン {i} エラー (試行 {attempt+1}/3): {e}")
                    if attempt < 2:
                        time.sleep(3)
            else:
                scenes_dict[i] = f"# シーン {i} 生成失敗\n"
        return [scenes_dict.get(i, "") for i in range(1, num_scenes + 1)]

    # ── Gemini: 2シーンずつバッチ化 → 5並列 ─────────────────────
    # バッチサイズ=2: 1コールで2シーン → コール数が半減
    BATCH = 2
    MAX_WORKERS = 5
    batches = [list(range(1, num_scenes + 1))[i:i+BATCH]
               for i in range(0, num_scenes, BATCH)]
    log(f"  {num_scenes}シーンを{len(batches)}バッチ（各{BATCH}シーン）× {MAX_WORKERS}並列で生成...")

    def _gen_batch(scene_nums):
        if cancel_event and cancel_event.is_set():
            return {n: f"# シーン {n} キャンセル\n" for n in scene_nums}
        for attempt in range(3):
            if cancel_event and cancel_event.is_set():
                break
            try:
                if len(scene_nums) == 1:
                    n = scene_nums[0]
                    s = generate_scene(model, n, num_scenes, concept, outline,
                                       char_defs, adult, h_tags=h_tags, log=log)
                    log(f"  ✓ シーン {n} 完了")
                    return {n: s}
                else:
                    result = _generate_scene_batch(model, scene_nums, num_scenes,
                                                   concept, outline, char_defs,
                                                   h_tags or [], log=log)
                    log(f"  ✓ シーン {scene_nums} 完了")
                    return result
            except Exception as e:
                log(f"  バッチ {scene_nums} エラー (試行 {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(3)
        return {n: f"# シーン {n} 生成失敗\n" for n in scene_nums}

    scenes_dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(_gen_batch, b) for b in batches]
        for future in concurrent.futures.as_completed(futures):
            scenes_dict.update(future.result())

    return [scenes_dict.get(i, f"# シーン {i} 生成失敗\n") for i in range(1, num_scenes + 1)]


# ── アート素材生成（2D / 3D 共通エントリ） ────────────────────────
def generate_assets(model, concept: dict, outline: str,
                    art_style: dict, adult: bool, log=print,
                    local_client=None) -> dict:
    """
    2D → Stable Diffusion / NovelAI 用プロンプト集を生成
    3D → Koikatsu / VRM / DAZ3D 向けキャラ設定JSONを生成
    戻り値: {"mode": "2d"|"3d", "characters": [...], "backgrounds": [...]}
    """
    if art_style["mode"] == "2d":
        return _generate_sd_prompts(model, concept, art_style, adult, log=log,
                                    local_client=local_client)
    else:
        return _generate_3d_settings(model, concept, art_style, adult, log=log,
                                     local_client=local_client)


# ── 2D: Stable Diffusion プロンプト生成 ──────────────────────────
def _generate_sd_prompts(model, concept: dict, art_style: dict, adult: bool,
                         log=print, local_client=None) -> dict:
    log("\n[画像] 2D: Stable Diffusion プロンプト生成中...\n")
    adult_note = "nsfw, explicit content allowed" if adult else "sfw only, tasteful"
    expressions = art_style["expression_list"]

    import concurrent.futures

    def _gen_char_prompt(h):
        log(f"  キャラ: {h['name']}")
        prompt = f"""以下のキャラクターの Stable Diffusion / NovelAI 用プロンプトを生成してください。

キャラ名: {h['name']}
外見: {h['appearance']}
役割: {h['role']}
ベースポジティブ: {art_style['sd_base_positive']}
ベースネガティブ: {art_style['sd_base_negative']}
{adult_note}

以下のJSON形式のみで出力してください（他テキスト不要）:
{{
  "name": "{h['name']}",
  "var_name": "{h['var_name']}",
  "expressions": {{
    {', '.join(f'"{e}": {{"positive": "...", "negative": "..."}}' for e in expressions)}
  }}
}}"""
        try:
            return _parse_json_with_retry(model, prompt, log=log, local_client=local_client)
        except ValueError as e:
            log(f"  キャラ {h['name']} のプロンプト生成に失敗しました: {e}")
            return None

    heroines = concept["heroines"]
    max_workers = 1 if local_client else min(3, len(heroines))
    heroine_prompts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(_gen_char_prompt, heroines))
    heroine_prompts = [r for r in results if r is not None]

    # 背景プロンプト生成
    log("\n  背景プロンプト生成中...\n")
    bg_prompt = f"""以下のビジュアルノベルで登場する背景シーンの Stable Diffusion プロンプトを生成してください。

ゲームタイトル: {concept['title']}
舞台設定: {concept['setting']}
背景スタイル: {art_style['bg_style']}
あらすじ概要: （ゲームの舞台に合わせた背景を5種類）

以下のJSON形式のみで出力してください:
{{
  "backgrounds": [
    {{"name": "bg_xxx", "label": "場所名（日本語）", "positive": "...", "negative": "..."}},
    ...5件
  ]
}}"""
    try:
        bg_data = _parse_json_with_retry(model, bg_prompt, log=log, local_client=local_client)
        backgrounds = bg_data.get("backgrounds", [])
    except ValueError as e:
        log(f"  背景プロンプト生成に失敗しました: {e}")
        backgrounds = []

    return {
        "mode": "2d",
        "tool": "Stable Diffusion / NovelAI",
        "characters": heroine_prompts,
        "backgrounds": backgrounds,
    }


# ── 3D: Koikatsu / VRM キャラ設定生成 ───────────────────────────
def _generate_3d_settings(model, concept: dict, art_style: dict, adult: bool,
                           log=print, local_client=None) -> dict:
    log("\n[画像] 3D: キャラクター設定ファイル生成中...\n")
    adult_note = "成人向けの衣装設定も含めてよい。" if adult else "全年齢向けの衣装。"

    char_settings = []
    for h in concept["heroines"]:
        log(f"  キャラ: {h['name']}\n")
        prompt = f"""以下のキャラクターの3Dキャラクター作成用設定を生成してください。
Koikatsu Party / VRM / DAZ3D などの3Dツール向けです。

キャラ名: {h['name']}
外見: {h['appearance']}
性格: {h['personality']}
役割: {h['role']}
{adult_note}

以下のJSON形式のみで出力してください:
{{
  "name": "{h['name']}",
  "var_name": "{h['var_name']}",
  "body": {{
    "height": "身長（cm）",
    "build": "体型（slim/average/curvy）",
    "skin_tone": "肌色",
    "hair_color": "髪色",
    "hair_style": "髪型",
    "eye_color": "瞳色",
    "eye_shape": "目の形"
  }},
  "outfit_default": {{
    "description": "デフォルト衣装の説明",
    "items": ["アイテム1", "アイテム2", "..."]
  }},
  "outfit_casual": {{
    "description": "私服の説明",
    "items": ["アイテム1", "アイテム2", "..."]
  }},
  "koikatsu_tips": "Koikatsu でのスライダー調整ヒント",
  "sd_prompt_3d": "このキャラをStable Diffusionで3Dレンダリング風に生成する際のプロンプト"
}}"""
        try:
            data = _parse_json_with_retry(model, prompt, log=log, local_client=local_client)
            char_settings.append(data)
        except ValueError as e:
            log(f"  キャラ {h['name']} の設定生成に失敗しました: {e}")

    # 背景・シーン設定
    log("\n  背景シーン設定生成中...\n")
    bg_prompt = f"""以下のビジュアルノベルの3D背景シーン設定を生成してください。
Unity / UE / Stable Diffusion 3D レンダリング向けです。

舞台設定: {concept['setting']}
背景スタイル: {art_style['bg_style']}

以下のJSON形式のみで出力してください:
{{
  "backgrounds": [
    {{
      "name": "bg_xxx",
      "label": "場所名（日本語）",
      "lighting": "照明設定（昼/夜/夕方など）",
      "atmosphere": "雰囲気",
      "sd_prompt": "Stable Diffusion 3Dレンダリング用プロンプト",
      "unity_notes": "Unity でシーン再現するためのヒント"
    }},
    ...5件
  ]
}}"""
    try:
        bg_data = _parse_json_with_retry(model, bg_prompt, log=log, local_client=local_client)
        backgrounds = bg_data.get("backgrounds", [])
    except ValueError as e:
        log(f"  背景シーン設定生成に失敗しました: {e}")
        backgrounds = []

    return {
        "mode": "3d",
        "tool": "Koikatsu Party / VRM / DAZ3D",
        "characters": char_settings,
        "backgrounds": backgrounds,
    }
