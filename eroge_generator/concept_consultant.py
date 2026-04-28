"""
AIプロデュース相談モジュール
Geminiがエロゲの企画を一緒に練り上げ、DLSite販売戦略アドバイスを提供する
"""
import json
import re
import time
import google.generativeai as genai

# ── システムプロンプト ─────────────────────────────────────────────
CONSULTANT_SYSTEM = """あなたはDLSiteでエロゲを販売するトッププロデューサーです。
年間数千万円を売り上げるタイトルを多数手がけた、企画・市場分析・販売戦略のエキスパートです。

## あなたの役割
1. ユーザーが作ろうとしているゲームの企画を一緒に練り上げる
2. DLSiteの市場動向・売れ筋・人気タグを踏まえた具体的なアドバイスをする
3. 「それは売れる/売れにくい、なぜなら〜」と正直かつ具体的に指摘する
4. 差別化ポイント・独自フック・ニッチ市場を積極的に提案する
5. 企画変更・路線変更にも柔軟に対応する

## スタイル
- 歯に衣着せぬ正直なアドバイス（お世辞なし）
- DLSiteの具体的な売上傾向・競合状況を踏まえた分析
- 「〇〇というタイトルが月3000本売れている理由は〜」のように具体的に話す
- 質問は一度に**最大2〜3個**に絞る（多すぎない）
- ユーザーが迷っているときは複数の選択肢を提示して比較する
- 最後に「この方向で行きますか？」と確認を取る

## 禁止事項
- 全年齢向けの提案（このパイプラインはR18専用）
- 曖昧なアドバイス（「面白くすればいい」のような抽象論）
- キャラの年齢を18歳未満にする提案

現在の会話では、ユーザーが作ろうとしているエロゲの企画を一緒に固めていきます。"""

# ── Gemini 呼び出し ────────────────────────────────────────────────
def _chat_response(model, history: list, user_message: str, system: str = "") -> str:
    """チャット履歴を使ってGeminiに返答させる"""
    # 履歴をテキストに変換
    history_text = ""
    for role, msg in history:
        label = "ユーザー" if role == "user" else "プロデューサー"
        history_text += f"\n{label}: {msg}"

    full_prompt = f"{system}\n\n## これまでの会話\n{history_text}\n\nユーザー: {user_message}\n\nプロデューサー:"

    for attempt in range(3):
        try:
            result = []
            for chunk in model.generate_content(full_prompt, stream=True,
                                                  request_options={"timeout": 60}):
                text = chunk.text or ""
                result.append(text)
            return "".join(result).strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(3 + attempt * 2)
            else:
                raise


# ── 初回メッセージ生成 ─────────────────────────────────────────────
def start_consultation(game_type: str, settings_summary: str,
                       api_key: str, log=print) -> str:
    """
    相談セッションを開始する最初のAIメッセージを生成する

    game_type: "ビジュアルノベル" / "RPGツクールMZ" / "Godotアクション"
    settings_summary: 現在の設定内容のテキスト
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""{CONSULTANT_SYSTEM}

## ユーザーが設定した内容
ゲームタイプ: {game_type}
{settings_summary}

これを見て、プロデューサーとして最初のアドバイスと質問をしてください。

以下の観点を含めてください:
1. この設定の市場での強み・弱み（DLSiteの現状を踏まえて）
2. 気になる点・もっと聞きたいこと（2〜3個の質問）
3. もし変えた方がいいと思う部分があれば率直に指摘

フレンドリーかつプロフェッショナルな口調で、200〜300字程度で答えてください。"""

    for attempt in range(3):
        try:
            result = []
            for chunk in model.generate_content(prompt, stream=True,
                                                  request_options={"timeout": 60}):
                result.append(chunk.text or "")
            return "".join(result).strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
            else:
                return f"（初期化エラー: {e}）"


# ── 会話継続 ───────────────────────────────────────────────────────
def continue_consultation(user_message: str, history: list,
                          game_type: str, settings_summary: str,
                          api_key: str) -> str:
    """
    ユーザーのメッセージに対してAIが返答する

    history: [(role, message), ...] role は "user" or "assistant"
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    context = f"""{CONSULTANT_SYSTEM}

## ユーザーが作ろうとしているゲームの基本設定
ゲームタイプ: {game_type}
{settings_summary}

上記の設定をベースに会話しています。
ユーザーが「変えたい」「こうしたい」と言ったら、新しい方向性を積極的に支持してください。
企画が固まってきたら「この方向で行きますか？確定したら生成ボタンを押してください」と伝えてください。"""

    return _chat_response(model, history, user_message, system=context)


# ── 最終コンセプト抽出 ─────────────────────────────────────────────
def extract_final_concept(history: list, game_type: str,
                          settings_summary: str, api_key: str) -> dict:
    """
    会話履歴から最終的なゲームコンセプトをJSON形式で抽出する
    生成パイプラインへの追加コンテキストとして使用する
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    history_text = "\n".join(
        f"{'ユーザー' if r == 'user' else 'プロデューサー'}: {m}"
        for r, m in history
    )

    prompt = f"""以下の会話から、エロゲ生成のための最終コンセプトを抽出してください。

## 基本設定
ゲームタイプ: {game_type}
{settings_summary}

## 相談の会話
{history_text}

上記の会話で決まった内容・変更点・追加要素を踏まえて、
生成AIへの指示として使える詳細なゲームコンセプトをJSON形式で出力してください:
{{
  "title_direction": "タイトルの方向性・キーワード",
  "unique_hook": "このゲームの独自の売り・フック",
  "heroine_details": "ヒロインの具体的な設定・魅力",
  "story_direction": "ストーリーの方向性・重点ポイント",
  "h_scene_details": "Hシーンの具体的な内容・こだわりポイント",
  "dlsite_strategy": "DLSite販売上の強調ポイント・タグ方針",
  "special_requests": "その他の特別な要望・こだわり",
  "changes_from_settings": "基本設定から変更になった点のリスト"
}}"""

    for attempt in range(3):
        try:
            result = []
            for chunk in model.generate_content(prompt, stream=True,
                                                  request_options={"timeout": 60}):
                result.append(chunk.text or "")
            raw = "".join(result)
            m = re.search(r'\{[\s\S]+\}', raw)
            if m:
                return json.loads(m.group())
        except Exception:
            if attempt < 2:
                time.sleep(2)

    return {"special_requests": "会話での相談内容を踏まえて生成してください。"}


# ── 設定サマリー生成 ───────────────────────────────────────────────
def build_settings_summary(game_type: str, settings: dict) -> str:
    """設定dictから読みやすいサマリーテキストを生成"""
    lines = []
    if game_type == "ビジュアルノベル":
        lines = [
            f"ジャンル: {settings.get('genre', '未設定')}",
            f"シナリオ形式: {settings.get('scenario', '未設定')}",
            f"ヒロインの属性: {settings.get('archetype', '未設定')}",
            f"Hシーンタグ: {', '.join(settings.get('h_tags', [])) or 'バニラ'}",
            f"長さ: {settings.get('length', '未設定')}",
            f"アートスタイル: {settings.get('art_style', '未設定')}",
        ]
    elif game_type == "RPGツクールMZ":
        lines = [
            f"ジャンル: {settings.get('genre', '未設定')}",
            f"Hシーン発生タイミング: {settings.get('eroge_scenario', '未設定')}",
            f"エロの濃さ: {settings.get('h_intensity', '未設定')}",
            f"パーティ人数: {settings.get('party_size', 4)}人",
            f"難易度: {settings.get('difficulty', '普通')}",
        ]
    elif game_type == "Godotアクション":
        lines = [
            f"ジャンル: {settings.get('genre', '未設定')}",
        ]
    return "\n".join(lines)
