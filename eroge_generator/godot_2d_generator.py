"""
godot_2d_generator.py
Gemini APIを使ってGodot 4.x 2Dアクションゲームのデザインとスクリプトを生成する
"""

import json
import re
import time
import queue as _q
import threading as _th


# ─────────────────────────────────────────────
#  低レベルAPI呼び出しユーティリティ
# ─────────────────────────────────────────────

def _parse_retry_after(error_str: str) -> int:
    """429レート制限エラーから待機秒数を取得する"""
    m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', str(error_str), re.DOTALL)
    return int(m.group(1)) + 3 if m else 0


def _stream(model, prompt, system="", log=print) -> str:
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
                    log(f"  ⚠️ レート制限 — {retry_after}秒後にリトライ... ({attempt+1}/{max_attempts})")
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


def _parse_json_with_retry(model, prompt, system="", max_retry=3, log=print) -> dict:
    for attempt in range(max_retry):
        raw = _stream(model, prompt, system, log)
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
#  ゲームデザイン生成
# ─────────────────────────────────────────────

def generate_game_concept(model, genre: str, log=print) -> dict:
    """ゲームコンセプトを生成"""

    system = (
        "あなたはゲームデザイナーです。指定されたジャンルの2Dアクションゲームのコンセプトを"
        "JSON形式で生成してください。必ず有効なJSONのみを返してください。"
    )

    prompt = f"""
{genre}ジャンルの2Dアクションゲームのコンセプトを以下のJSON形式で生成してください。
必ず有効なJSONのみを返し、説明文は不要です。

{{
  "title": "ゲームタイトル（日本語）",
  "genre_desc": "ジャンル説明（30字以内）",
  "story": "あらすじ（100字以内）",
  "player": {{
    "name": "主人公名（日本語）",
    "description": "説明（50字以内）",
    "move_speed": 200,
    "max_hp": 100,
    "attack_power": 20,
    "attack_range": 80
  }},
  "enemies": [
    {{
      "name": "敵名（日本語）",
      "description": "説明（30字以内）",
      "color": "#ff4444",
      "hp": 30,
      "speed": 100,
      "attack_power": 10,
      "detect_range": 200,
      "attack_range": 50,
      "exp": 10,
      "drop_chance": 0.3
    }}
  ],
  "items": [
    {{
      "name": "アイテム名（日本語）",
      "color": "#ffff00",
      "effect": "heal",
      "value": 30
    }}
  ],
  "levels": [
    {{
      "name": "ステージ名（日本語）",
      "description": "説明（40字以内）",
      "floor_color": "#2a4a2a",
      "wall_color": "#1a1a1a",
      "bgm": "なし",
      "enemy_types": ["敵名1", "敵名2"],
      "enemy_count": 8,
      "width": 25,
      "height": 18
    }}
  ],
  "bgm_style": "8bitピクセルサウンド風"
}}

条件:
- enemiesは3〜5種類
- itemsは3〜5種類（effect は heal / speed_up / attack_up のいずれか）
- levelsは必ず3ステージ（難易度順）
- colorは有効な16進数カラーコード
- widthは20〜30、heightは15〜22の整数
- enemy_countは5〜15の整数
- JSONのキーはすべて英語のまま（値の日本語はOK）
"""

    return _parse_json_with_retry(model, prompt, system, log=log)


# ─────────────────────────────────────────────
#  GDScriptコード生成
# ─────────────────────────────────────────────

def generate_player_script(model, concept: dict, log=print) -> str:
    """プレイヤーのGDScript（player.gd）を生成"""

    player = concept.get("player", {})
    system = (
        "あなたはGodot 4.x専門のゲームプログラマーです。"
        "有効なGDScript 2.0コードのみを返してください。コードブロック(```)は不要です。"
    )

    prompt = f"""
以下のパラメータを持つGodot 4.xの2Dアクションゲームプレイヤースクリプトを生成してください。

プレイヤー情報:
- 名前: {player.get('name', '主人公')}
- 移動速度: {player.get('move_speed', 200)}
- 最大HP: {player.get('max_hp', 100)}
- 攻撃力: {player.get('attack_power', 20)}
- 攻撃範囲: {player.get('attack_range', 80)}

要件:
- extends CharacterBody2D
- WASDまたは矢印キーで移動
- Spaceキーで近接攻撃（AttackAreaでArea2D判定）
- HP管理（take_damage(amount)関数）
- 死亡時にgame_over シグナル発火
- HUD更新用シグナル: hp_changed(current, maximum)
- 攻撃クールダウン: 0.5秒
- move_and_slide()はGodot 4形式（引数なし）
- $ノード名形式でノード参照
- Godot 4のSignal記法を使う
- GameManagerシングルトンを参照（GameManager.add_score()など）

コードのみ返してください。説明不要。
"""

    return _stream(model, prompt, system, log)


def generate_enemy_script(model, concept: dict, enemy: dict, log=print) -> str:
    """敵のGDScript（enemy_xxx.gd）を生成"""

    system = (
        "あなたはGodot 4.x専門のゲームプログラマーです。"
        "有効なGDScript 2.0コードのみを返してください。コードブロック(```)は不要です。"
    )

    prompt = f"""
以下のパラメータを持つGodot 4.xの2Dアクションゲーム敵キャラクタースクリプトを生成してください。

敵情報:
- 名前: {enemy.get('name', '敵')}
- HP: {enemy.get('hp', 30)}
- 速度: {enemy.get('speed', 100)}
- 攻撃力: {enemy.get('attack_power', 10)}
- 探知範囲: {enemy.get('detect_range', 200)}
- 攻撃範囲: {enemy.get('attack_range', 50)}
- 経験値: {enemy.get('exp', 10)}
- ドロップ確率: {enemy.get('drop_chance', 0.3)}

ゲーム情報:
- タイトル: {concept.get('title', 'ゲーム')}

要件:
- extends CharacterBody2D
- 待機状態: ランダム移動（2秒ごとに方向変更）
- 追跡状態: 探知範囲内にプレイヤーが入ったらプレイヤーに向かって移動
- 攻撃状態: 攻撃範囲内でプレイヤーを攻撃（1秒クールダウン）
- take_damage(amount)関数でダメージ受け
- HP0で死亡（GameManager.add_score()、アイテムドロップ）
- プレイヤーはget_tree().get_nodes_in_group("player")で取得
- move_and_slide()はGodot 4形式（引数なし）
- $ノード名形式でノード参照
- Godot 4のSignal記法を使う

コードのみ返してください。説明不要。
"""

    return _stream(model, prompt, system, log)


def generate_game_manager_script(model, concept: dict, log=print) -> str:
    """ゲームマネージャー（game_manager.gd）を生成"""

    system = (
        "あなたはGodot 4.x専門のゲームプログラマーです。"
        "有効なGDScript 2.0コードのみを返してください。コードブロック(```)は不要です。"
    )

    levels = concept.get("levels", [])
    level_names = [lv.get("name", f"Level{i+1}") for i, lv in enumerate(levels)]

    prompt = f"""
以下の仕様でGodot 4.xのゲームマネージャースクリプトを生成してください。

ゲーム情報:
- タイトル: {concept.get('title', 'ゲーム')}
- ステージ数: {len(levels)}
- ステージ名: {level_names}

要件:
- extends Node（Autoloadシングルトンとして使用）
- 変数: current_score, current_level, is_game_over, is_game_clear
- func add_score(amount: int): スコア加算、シグナル発火
- func next_level(): 次のレベルへ遷移（scenes/levels/level_X.tscnをロード）
- func game_over(): ゲームオーバー処理
- func game_clear(): ゲームクリア処理
- func restart(): ゲーム再スタート（level 1から）
- シグナル: score_changed(score), level_changed(level), game_over_signal, game_clear_signal
- レベルシーンはget_tree().change_scene_to_file()で遷移
- Godot 4のSignal記法を使う
- ステージ数は{len(levels)}（最大{len(levels)}ステージ）

コードのみ返してください。説明不要。
"""

    return _stream(model, prompt, system, log)


def generate_hud_script(model, concept: dict, log=print) -> str:
    """HUD（hud.gd）を生成"""

    system = (
        "あなたはGodot 4.x専門のゲームプログラマーです。"
        "有効なGDScript 2.0コードのみを返してください。コードブロック(```)は不要です。"
    )

    player = concept.get("player", {})

    prompt = f"""
以下の仕様でGodot 4.xのHUD（ヘッドアップディスプレイ）スクリプトを生成してください。

ゲーム情報:
- タイトル: {concept.get('title', 'ゲーム')}
- プレイヤー最大HP: {player.get('max_hp', 100)}

HUDノード構成（親: CanvasLayer）:
- HPBar (ProgressBar): HPバー表示
- ScoreLabel (Label): スコア表示
- LevelLabel (Label): 現在レベル表示
- GameOverPanel (Panel): ゲームオーバー画面（初期非表示）
  - GameOverLabel (Label): "GAME OVER"
  - RestartButton (Button): リスタートボタン
- ClearPanel (Panel): クリア画面（初期非表示）
  - ClearLabel (Label): "STAGE CLEAR!"
  - NextButton (Button): 次のステージボタン

要件:
- extends CanvasLayer
- _ready()でGameManagerのシグナルに接続
- update_hp(current, maximum): HPバー更新
- update_score(score): スコアラベル更新
- show_game_over(): ゲームオーバー画面表示
- show_clear(): クリア画面表示
- RestartButtonのpressed()でGameManager.restart()
- NextButtonのpressed()でGameManager.next_level()
- Godot 4のシグナル接続はconnect()またはCallableを使う

コードのみ返してください。説明不要。
"""

    return _stream(model, prompt, system, log)
