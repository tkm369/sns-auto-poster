"""
LM Studio (OpenAI-compatible API) を使ったローカルモデル呼び出し
デフォルト URL: http://localhost:1234/v1
"""
import time
import re
import json
from openai import OpenAI


def get_client(base_url: str = "http://localhost:1234/v1") -> OpenAI:
    return OpenAI(base_url=base_url, api_key="lm-studio")


def is_available(base_url: str = "http://localhost:1234/v1") -> bool:
    """LM Studio が起動していてモデルがロードされているか確認"""
    try:
        client = get_client(base_url)
        models = client.models.list()
        return len(list(models)) > 0
    except Exception:
        return False


def generate_local(
    prompt: str,
    system: str = "",
    base_url: str = "http://localhost:1234/v1",
    max_tokens: int = 24000,
    temperature: float = 0.85,
    log=print,
) -> str:
    """ローカルモデルにプロンプトを送りテキストを返す。
    Qwen3のthinkingモードを無効化（/no_think）して確実にcontentを取得。"""
    client = get_client(base_url)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    # Qwen3 の thinking モードを無効化: ユーザーメッセージの先頭に /no_think を付ける
    no_think_prompt = f"/no_think\n\n{prompt}"
    messages.append({"role": "user", "content": no_think_prompt})

    for attempt in range(3):
        try:
            log("  [ローカル生成中...]")
            # 非ストリームで呼び出し（reasoning_content + content を確実に取得）
            resp = client.chat.completions.create(
                model="local-model",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
            )
            msg = resp.choices[0].message
            text = (msg.content or "").strip()

            if not text:
                log(f"  [content空、finish_reason={resp.choices[0].finish_reason}、max_tokens増やして再試行]")
                # max_tokens が不足している可能性 → 増やして再試行
                resp2 = client.chat.completions.create(
                    model="local-model",
                    messages=messages,
                    max_tokens=min(max_tokens * 2, 32000),
                    temperature=temperature,
                    stream=False,
                )
                text = (resp2.choices[0].message.content or "").strip()

            # 出力プレビュー
            print(text[:300] if text else "(empty)")
            print()

            # コードブロック除去
            text = re.sub(r"```[a-z]*\n?", "", text)
            text = re.sub(r"```", "", text)
            return text.strip()
        except Exception as e:
            if attempt < 2:
                log(f"  ローカルモデルエラー: {e} → 3秒後にリトライ...")
                time.sleep(3)
            else:
                raise


def parse_json_local(
    prompt: str,
    system: str = "",
    base_url: str = "http://localhost:1234/v1",
    max_retry: int = 3,
    log=print,
) -> dict:
    """ローカルモデルでJSON生成、失敗時はリトライ"""
    for attempt in range(max_retry):
        raw = generate_local(prompt, system, base_url, log=log)
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
