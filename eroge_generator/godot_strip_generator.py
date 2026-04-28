"""
godot_strip_generator.py
Gemini APIを使ってGodot 4.x 野球拳スタイル脱衣カードゲームのスクリプトを生成する
"""

import json
import re
import time
import queue as _q
import threading as _th


# ─────────────────────────────────────────────
#  低レベルAPI呼び出しユーティリティ（godot_2d_generator.pyと同パターン）
# ─────────────────────────────────────────────

def _parse_retry_after(error_str: str) -> int:
    """429レート制限エラーから待機秒数を取得する"""
    m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', str(error_str), re.DOTALL)
    return int(m.group(1)) + 3 if m else 0


def _stream(model, prompt, system="", log=print, local_client=None) -> str:
    # ローカルモデル優先
    if local_client is not None:
        from local_model import generate_local
        return generate_local(prompt, system=system,
                              base_url=local_client.get("base_url", "http://localhost:1234/v1"),
                              max_tokens=16000, log=log)

    full = f"{system}\n\n{prompt}" if system else prompt
    max_attempts = 5
    _WALL_TIMEOUT = 120
    for attempt in range(max_attempts):
        try:
            chunk_q = _q.Queue()

            def _api_worker(fp=full, cq=chunk_q):
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
                    log(f"  レート制限 — {retry_after}秒後にリトライ... ({attempt+1}/{max_attempts})")
                    time.sleep(retry_after)
                else:
                    wait = 5 + attempt * 5
                    log(f"  API エラー: {err[:80]} → {wait}秒後にリトライ ({attempt+1}/{max_attempts})")
                    time.sleep(wait)
            else:
                raise


def _clean(text):
    text = re.sub(r"```[a-z]*\n?", "", text)
    return re.sub(r"```", "", text).strip()


def _parse_json_with_retry(model, prompt, system="", max_retry=3, log=print,
                           local_client=None) -> dict:
    for attempt in range(max_retry):
        raw = _stream(model, prompt, system, log, local_client=local_client)
        m = re.search(r'\{[\s\S]+\}', raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError as e:
                log(f"  JSON error (try {attempt+1}/{max_retry}): {e}")
        else:
            log(f"  JSON not found (try {attempt+1}/{max_retry})")
        if attempt < max_retry - 1:
            time.sleep(2)
    raise ValueError(f"JSON生成に{max_retry}回失敗")


# ─────────────────────────────────────────────
#  ゲームコンセプト生成
# ─────────────────────────────────────────────

def generate_strip_concept(model, genre: str, log=print, local_client=None) -> dict:
    """野球拳カードゲームのコンセプトをJSON形式で生成"""

    system = (
        "あなたはR18エロゲのゲームデザイナーです。野球拳スタイルの脱衣カードゲームのコンセプトを"
        "JSON形式で生成してください。登場するヒロインは必ず18歳以上に設定してください。"
        "必ず有効なJSONのみを返してください。"
    )

    prompt = f"""
{genre}の野球拳スタイル脱衣カードゲームのコンセプトを以下のJSON形式で生成してください。
ヒロインは必ず18歳以上にしてください。大人向けR18コンテンツです。
必ず有効なJSONのみを返し、説明文は不要です。

{{
  "title": "ゲームタイトル（日本語、魅力的なR18タイトル）",
  "subtitle": "サブタイトル（30字以内）",
  "story": "あらすじ（100字以内、R18要素を含む）",
  "heroine": {{
    "name": "ヒロイン名（日本語）",
    "age": 20,
    "personality": "性格（40字以内）",
    "appearance": "外見描写（60字以内、SD生成用英語プロンプトに使える詳細）",
    "clothing_items": ["ジャケット", "シャツ", "スカート", "ブラ", "パンティ"]
  }},
  "card_theme": "カードのテーマ（例: 花札、トランプ、タロット）",
  "setting": "ゲームの舞台（例: 放課後の教室、温泉旅館、事務所）"
}}

条件:
- heroineのageは必ず18以上の整数
- clothing_itemsは5〜7個のリスト（服を順番に脱いでいく順序で）
- clothing_itemsの最後の項目は必ず「全裸」に近い状態の下着や肌着
- card_themeはゲームの雰囲気に合った独自のテーマ
- settingはR18エロゲに相応しい雰囲気の場所
- JSONのキーはすべて英語のまま（値の日本語はOK）
"""

    return _parse_json_with_retry(model, prompt, system, log=log, local_client=local_client)


# ─────────────────────────────────────────────
#  GDScript生成
# ─────────────────────────────────────────────

def generate_game_manager_script(model, concept: dict, log=print, local_client=None) -> str:
    """game_manager.gdを生成（Autoloadシングルトン）"""

    system = (
        "あなたはGodot 4.x専門のゲームプログラマーです。"
        "有効なGDScript 2.0コードのみを返してください。コードブロック(```)は不要です。"
    )

    heroine = concept.get("heroine", {})
    clothing_items = heroine.get("clothing_items", ["シャツ", "スカート", "ブラ", "パンティ", "全裸"])
    clothing_count = len(clothing_items)

    prompt = f"""
以下の仕様でGodot 4.xの野球拳脱衣カードゲーム用ゲームマネージャースクリプトを生成してください。

ゲーム情報:
- タイトル: {concept.get('title', '野球拳ゲーム')}
- ヒロイン名: {heroine.get('name', 'ヒロイン')}
- 衣装アイテム数: {clothing_count}個
- 衣装リスト: {clothing_items}

要件:
- extends Node（Autoloadシングルトン「GameManager」として使用）
- ゲーム状態のenum: TITLE, CARD_BATTLE, STRIP_ANIM, H_SCENE_FELLATIO, H_SCENE_SEX, GAME_OVER, PLAYER_WIN
- 変数:
  - var current_state: int = GameState.TITLE
  - var opponent_clothing_count: int = {clothing_count}（ヒロインの服の数）
  - var player_clothing_count: int = 3（プレイヤー: シャツ、ズボン、下着）
  - var current_h_scene: int = -1
  - var round_count: int = 0
- シグナル:
  - signal game_state_changed(new_state: int)
  - signal clothing_removed(who: String)
  - signal h_scene_unlocked(scene_id: int)
- 関数:
  - func start_game(): ゲーム開始、CARD_BATTLEへ遷移
  - func on_player_wins_round(): プレイヤー勝利時の処理
  - func on_opponent_wins_round(): 相手勝利時の処理
  - func on_tie_round(): 引き分け時の処理（両者1枚ずつ脱ぐ）
  - func change_state(new_state: int): 状態遷移、シグナル発火
  - func check_h_scene_unlock(): Hシーンアンロック判定
  - func restart(): ゲームリセット
- Hシーンアンロック条件:
  - opponent_clothing_count <= {max(1, clothing_count - 2)}: フェラチオシーン（scene_id=0）
  - opponent_clothing_count <= 0: セックスシーン（scene_id=1）
- ゲームオーバー: player_clothing_count <= 0
- プレイヤー勝利: opponent_clothing_count <= 0
- Godot 4のSignal記法を使う

コードのみ返してください。説明不要。
"""

    return _stream(model, prompt, system, log, local_client=local_client)


def generate_card_battle_script(model, concept: dict, log=print, local_client=None) -> str:
    """card_battle.gdを生成（カード対戦ロジック）"""

    system = (
        "あなたはGodot 4.x専門のゲームプログラマーです。"
        "有効なGDScript 2.0コードのみを返してください。コードブロック(```)は不要です。"
    )

    prompt = f"""
以下の仕様でGodot 4.xの野球拳カード対戦スクリプトを生成してください。

ゲーム情報:
- タイトル: {concept.get('title', '野球拳ゲーム')}
- カードテーマ: {concept.get('card_theme', 'トランプ')}

要件:
- extends Control（またはNode）
- ノード参照:
  - @onready var player_card_label: Label = $PlayerCard
  - @onready var opponent_card_label: Label = $OpponentCard
  - @onready var result_label: Label = $ResultLabel
  - @onready var draw_button: Button = $DrawButton
  - @onready var animation_player: AnimationPlayer = $AnimationPlayer
- 変数:
  - var player_card_value: int = 0
  - var opponent_card_value: int = 0
  - var is_animating: bool = false
- 関数:
  - func draw_card() -> void: ボタン押下時、両者のカードを抽選
    - player_card = randi() % 10 + 1（1〜10）
    - opponent_card = randi() % 10 + 1（1〜10）
    - カード値をラベルに表示（Tweenでフェードイン）
    - resolve_round()を呼ぶ
  - func resolve_round() -> void: 勝敗判定
    - player > opponent → GameManager.on_player_wins_round()
    - player < opponent → GameManager.on_opponent_wins_round()
    - player == opponent → GameManager.on_tie_round()
    - show_result()を呼ぶ
  - func show_result(result_text: String) -> void: 結果テキスト表示（Tweenでアニメ）
  - func _on_draw_button_pressed() -> void: draw_card()を呼ぶ
  - func reset_cards() -> void: 次のラウンドのためにカード表示をリセット
- GameManagerのシグナルを受け取ってUIを更新する
- is_animatingがtrueの間はdraw_cardを無効化
- Godot 4のTween（create_tween）を使う
- Godot 4のSignal記法を使う

コードのみ返してください。説明不要。
"""

    return _stream(model, prompt, system, log, local_client=local_client)


def generate_character_script(model, concept: dict, log=print, local_client=None) -> str:
    """character.gdを生成（衣装状態管理）"""

    system = (
        "あなたはGodot 4.x専門のゲームプログラマーです。"
        "有効なGDScript 2.0コードのみを返してください。コードブロック(```)は不要です。"
    )

    heroine = concept.get("heroine", {})
    clothing_items = heroine.get("clothing_items", ["シャツ", "スカート", "ブラ", "パンティ"])
    clothing_count = len(clothing_items)

    prompt = f"""
以下の仕様でGodot 4.xのキャラクター衣装管理スクリプトを生成してください。

ヒロイン情報:
- 名前: {heroine.get('name', 'ヒロイン')}
- 衣装アイテム数: {clothing_count}個
- 衣装リスト（脱ぐ順）: {clothing_items}

要件:
- extends Node2D
- 変数:
  - var current_state: int = 0（0=完全着衣、{clothing_count}=全裸）
  - var max_states: int = {clothing_count}
  - var textures: Array[Texture2D] = []（state_0.png〜state_{clothing_count}.png）
- @onready var sprite: Sprite2D = $CharacterSprite
- @onready var reaction_label: Label = $ReactionLabel
- func _ready() -> void:
  - テクスチャを読み込む（res://assets/characters/state_0.png〜）
  - GameManagerのclothing_removedシグナルに接続
- func set_clothing_state(state: int) -> void:
  - current_stateをstateにセット（clamp使用）
  - spriteのtextureを更新
- func strip_animation(removed_item: String) -> void:
  - Tweenでspriteをscale up→scaleダウン（スクリーン揺れ効果）
  - その後set_clothing_state(current_state + 1)を呼ぶ
- func show_embarrassed_reaction() -> void:
  - reaction_labelに恥ずかしそうな表情テキスト（>///<など）を表示してフェードアウト
- func show_seductive_reaction() -> void:
  - reaction_labelに誘惑的なテキストを表示してフェードアウト
- func _on_clothing_removed(who: String) -> void:
  - whoが"opponent"の場合strip_animation()を呼ぶ
- Godot 4のTween（create_tween）を使う
- Godot 4のSignal記法を使う

コードのみ返してください。説明不要。
"""

    return _stream(model, prompt, system, log, local_client=local_client)


def generate_h_scene_script(model, concept: dict, log=print, local_client=None) -> str:
    """h_scene_viewer.gdを生成（Hシーンビューア）"""

    system = (
        "あなたはGodot 4.x専門のゲームプログラマーです。"
        "有効なGDScript 2.0コードのみを返してください。コードブロック(```)は不要です。"
    )

    heroine = concept.get("heroine", {})

    prompt = f"""
以下の仕様でGodot 4.xのR18 Hシーンビューアスクリプトを生成してください。

ヒロイン情報:
- 名前: {heroine.get('name', 'ヒロイン')}

要件:
- extends CanvasLayer
- @onready var scene_image: TextureRect = $SceneImage
- @onready var dialogue_label: Label = $DialogueLabel
- @onready var next_button: Button = $NextButton
- @onready var prev_button: Button = $PrevButton
- @onready var auto_timer: Timer = $AutoTimer
- @onready var close_button: Button = $CloseButton
- @onready var auto_button: Button = $AutoButton
- 変数:
  - var current_scene_id: int = -1（0=フェラチオ, 1=セックス）
  - var current_page: int = 0
  - var auto_advance: bool = false
  - var scene_data: Dictionary = {{}}（scene_id → {{image_path, lines}}）
- func _ready() -> void:
  - GameManagerのh_scene_unlockedシグナルに接続
  - visible = false
- func show_h_scene(scene_id: int) -> void:
  - current_scene_idとcurrent_pageをセット
  - scene_idに応じた画像を読み込み（res://assets/h_scenes/fellatio.pngまたはsex.png）
  - 最初のセリフを表示
  - visible = true
- func show_page(page: int) -> void:
  - scene_data[current_scene_id].linesからセリフを表示
  - scene_imageのテクスチャ更新
- func next_page() -> void: 次のページ、最後ならclose
- func prev_page() -> void: 前のページ
- func close_scene() -> void: visible = false, auto_advance = false
- func toggle_auto() -> void: auto_advanceをトグル
- func _on_h_scene_unlocked(scene_id: int) -> void: show_h_scene(scene_id)を呼ぶ
- func _on_auto_timer_timeout() -> void: auto_advanceがtrueならnext_page()
- Godot 4のSignal記法を使う

コードのみ返してください。説明不要。
"""

    return _stream(model, prompt, system, log, local_client=local_client)


def generate_dialogue(model, concept: dict, log=print, local_client=None) -> dict:
    """ゲーム内セリフをJSON形式で生成（R18日本語）"""

    system = (
        "あなたはR18エロゲのシナリオライターです。"
        "指定されたキャラクターのセリフをJSON形式で生成してください。"
        "セリフは日本語で、大人向けの官能的な内容にしてください。"
        "必ず有効なJSONのみを返してください。"
    )

    heroine = concept.get("heroine", {})
    heroine_name = heroine.get("name", "ヒロイン")
    clothing_items = heroine.get("clothing_items", ["シャツ", "スカート", "ブラ", "パンティ"])
    personality = heroine.get("personality", "恥ずかしがり屋")

    # clothing_itemsに合わせたstrip_linesのプレースホルダーを作成
    clothing_list_str = "\n".join(
        f"  {i+1}. {item}を脱ぐ時のセリフ" for i, item in enumerate(clothing_items)
    )

    prompt = f"""
以下のキャラクター設定に合わせて、野球拳カードゲームのR18セリフをJSON形式で生成してください。

キャラクター:
- 名前: {heroine_name}
- 年齢: {heroine.get('age', 20)}歳（成人）
- 性格: {personality}

以下のJSON形式で返してください:
{{
  "strip_lines": [
    "{clothing_items[0] if clothing_items else 'シャツ'}を脱ぐ時の恥ずかしそうなセリフ（30字以内）",
    "{clothing_items[1] if len(clothing_items) > 1 else 'スカート'}を脱ぐ時のセリフ（30字以内）",
    "{clothing_items[2] if len(clothing_items) > 2 else 'ブラ'}を脱ぐ時の照れたセリフ（30字以内）",
    "{clothing_items[3] if len(clothing_items) > 3 else 'パンティ'}を脱ぐ時の恥辱的なセリフ（30字以内）",
    "最後の一枚を脱ぐ時の絶望と興奮が混じったセリフ（30字以内）"
  ],
  "h_scene_fellatio_lines": [
    "フェラチオシーンのセリフ1（官能的、40字以内）",
    "フェラチオシーンのセリフ2（もっと露骨、40字以内）",
    "フェラチオシーンのセリフ3（絶頂寸前、40字以内）"
  ],
  "h_scene_sex_lines": [
    "セックスシーンのセリフ1（官能的、40字以内）",
    "セックスシーンのセリフ2（快楽の表現、40字以内）",
    "セックスシーンのセリフ3（絶頂、40字以内）",
    "セックスシーンのセリフ4（余韻、40字以内）"
  ],
  "win_lines": [
    "プレイヤーがラウンド勝利した時の得意気なセリフ（20字以内）",
    "さらに追い込む時のセリフ（20字以内）"
  ],
  "lose_lines": [
    "プレイヤーが負けた時の{heroine_name}の勝ち誇ったセリフ（20字以内）",
    "プレイヤーを挑発するセリフ（20字以内）"
  ]
}}

条件:
- strip_linesは衣装アイテムの数（{len(clothing_items)}個）に合わせて生成
- セリフはすべて{heroine_name}の口調に合わせる
- 官能的で成人向けのR18コンテンツとして適切なセリフ
- JSONのキーはすべて英語のまま（値の日本語はOK）
- 必ず有効なJSONのみ返すこと
"""

    return _parse_json_with_retry(model, prompt, system, log=log, local_client=local_client)
