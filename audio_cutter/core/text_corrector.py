"""
text_corrector.py
Gemini API（無料枠）でSRTテキストを校正する。

無料枠: 15 RPM / 1日100万トークン（2025年時点）
モデル: gemini-2.0-flash（高速・高精度・無料）
"""
import json
import re
import base64
from typing import List, Dict

from google import genai


def _get_api_key() -> str:
    """難読化されたAPIキーを復元する"""
    _o = "GxImPA0mIQAcKi4dbAceAQwzJmwoFSIwMwESJzMuLw8xMBESODU+"
    _s = 0x5A
    raw = base64.b64decode(_o)
    return "".join(chr(b ^ (_s + i % 7)) for i, b in enumerate(raw))


_PROMPT_TEMPLATE = """\
以下は動画の音声をAIで文字起こしした日本語テキストです。
次のルールで校正してください。

{custom_rules}

【必須制約（変更不可）】
- セグメントの数・順番は絶対に変えないこと
- "text" フィールドのみ変更すること（id, start, end は変えない）

【出力形式】
JSONのみ返してください。説明文・コードブロック記号は不要です。

【入力】
{segments_json}
"""

DEFAULT_RULES = """\
【条件】
1. 誤字・脱字・明らかな文法ミスのみを修正する
　※意味・言い回し・語順は一切変更しない

2. 読みやすさを重視し、適切な位置で改行する
　※助詞の直前・直後、文節の切れ目で改行すること
　※不自然な単語分断はしない

3. 不足している「てにをは」のみ補完する
　※新しい表現や言い換えは行わない

4. 1行あたり30〜35文字程度にする
　※文字数を優先しすぎて視認性を損なわないこと

5. 要約・省略は一切行わず、一語一句すべて書き出す

6. テロップ用途のため句点は使用しない

【固有名詞の統一ルール】
「義満先生」「吉光先生」「義光先生」「佳光先生」など
読みが「よしみつせんせい」の表記はすべて「よしみつ先生」に統一する
※完全一致を最優先とする

【数字表記の統一ルール】
・数字はすべて算用数字（半角）で表記する
　（例：一→1、十→10、二十→20）
・回数、人数、年数、割合、金額など数量を表す表現はすべて算用数字（半角）に統一する
・漢数字と算用数字が混在している場合は意味を変えず算用数字（半角）に統一する
・慣用表現、熟語、固有名詞として漢数字が使われている場合のみ原文表記を維持する
　（例：一般的、一切、唯一、第一印象 など）\
"""


def correct_segments(
    segments: List[Dict],
    api_key: str,
    model_name: str = "gemini-2.0-flash",
    custom_rules: str = "",
) -> List[Dict]:
    """
    Gemini APIでセグメントのテキストを校正する。

    Args:
        segments:   [{"id": int, "start": float, "end": float, "text": str}]
        api_key:    Gemini APIキー
        model_name: 使用するGeminiモデル

    Returns:
        校正済みセグメントリスト（start/endは変更なし）
    """
    # api_keyが未指定の場合は埋め込みキーを使用
    client = genai.Client(api_key=api_key or _get_api_key())

    # idを付与してAPIに送る
    payload = [
        {"id": i, "start": seg["start"], "end": seg["end"], "text": seg["text"]}
        for i, seg in enumerate(segments)
    ]

    # 一度に送れるトークン量の上限を考慮し、100セグメントずつ分割
    CHUNK = 100
    corrected_map: Dict[int, str] = {}

    for chunk_start in range(0, len(payload), CHUNK):
        chunk = payload[chunk_start:chunk_start + CHUNK]
        rules = custom_rules.strip() if custom_rules.strip() else DEFAULT_RULES
        prompt = _PROMPT_TEMPLATE.format(
            custom_rules=rules,
            segments_json=json.dumps(chunk, ensure_ascii=False, indent=2)
        )

        # モデルのフォールバック順（クォータ超過時に次を試す）
        fallback_models = [model_name, "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
        response = None
        last_error = None
        for model_candidate in fallback_models:
            try:
                import time
                response = client.models.generate_content(
                    model=model_candidate, contents=prompt)
                if model_candidate != model_name:
                    print(f"  ※ {model_candidate} にフォールバックしました")
                break
            except Exception as e:
                last_error = e
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    # レート制限: 少し待ってから次のモデルを試す
                    import re as _re
                    delay_match = _re.search(r"retryDelay.*?(\d+)s", err_str)
                    wait = int(delay_match.group(1)) if delay_match else 5
                    wait = min(wait, 10)  # 最大10秒待機
                    print(f"  クォータ超過 ({model_candidate})、{wait}秒後に次のモデルを試します...")
                    time.sleep(wait)
                    continue
                raise  # クォータ以外のエラーはそのまま再送出
        if response is None:
            raise RuntimeError(
                f"すべてのモデルでクォータ超過しました。\n"
                f"aistudio.google.com で新しいAPIキーを発行してください。\n"
                f"詳細: {last_error}"
            )
        raw = response.text.strip()

        # コードブロック記号を除去
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        corrected_chunk = json.loads(raw)
        for item in corrected_chunk:
            corrected_map[item["id"]] = item["text"]

    # 元のセグメントに反映
    result = []
    for i, seg in enumerate(segments):
        new_seg = seg.copy()
        if i in corrected_map:
            new_seg["text"] = corrected_map[i]
        result.append(new_seg)

    return result
