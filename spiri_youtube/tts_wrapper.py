"""
tts_wrapper.py — TTS音声生成ラッパー
優先度: edge-tts（デフォルト） > qwen3_tts Gradio API
"""
from __future__ import annotations
import asyncio
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests

from config import TTS_ENGINE, EDGE_TTS_VOICE, QWEN3_TTS_URL


# ────────────────────────────────────────────────────────
# edge-tts バックエンド
# ────────────────────────────────────────────────────────

async def _edge_tts_async(text: str, voice: str, output_path: str, rate: str = "+0%") -> None:
    """edge-ttsで非同期音声生成"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


def _generate_edge(text: str, voice: str, output_path: str, rate: str = "+0%") -> str:
    """edge-ttsでWAV/MP3生成 → output_pathに保存"""
    asyncio.run(_edge_tts_async(text, voice, output_path, rate=rate))
    return output_path


# ────────────────────────────────────────────────────────
# qwen3_tts Gradio API バックエンド
# ────────────────────────────────────────────────────────

def _qwen3_tts_available(base_url: str, timeout: float = 3.0) -> bool:
    """Gradio APIが起動しているか確認"""
    try:
        r = requests.get(f"{base_url}/info", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _generate_qwen3(text: str, base_url: str, output_path: str, voice: str = "Chelsie") -> str:
    """
    qwen3_tts Gradio API (/api/predict) を呼び出して音声を生成。
    サーバーが起動していない場合は RuntimeError を送出。
    """
    if not _qwen3_tts_available(base_url):
        raise RuntimeError(f"qwen3_tts Gradioサーバーが見つかりません: {base_url}")

    payload = {
        "data": [text, voice, None, None],
        "fn_index": 0,
    }
    resp = requests.post(f"{base_url}/api/predict", json=payload, timeout=120)
    resp.raise_for_status()

    result = resp.json()
    # Gradio v4 形式: {"data": [{"url": "..."}]}
    audio_data = result.get("data", [None])[0]
    if isinstance(audio_data, dict):
        audio_url = audio_data.get("url") or audio_data.get("path")
    elif isinstance(audio_data, str):
        audio_url = audio_data
    else:
        raise ValueError(f"予期しないAPIレスポンス形式: {audio_data}")

    # ダウンロード
    if audio_url.startswith("http"):
        r = requests.get(audio_url, timeout=60)
    else:
        # 相対パスの場合
        r = requests.get(f"{base_url}/file={audio_url}", timeout=60)
    r.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(r.content)
    return output_path


# ────────────────────────────────────────────────────────
# 公開インターフェース
# ────────────────────────────────────────────────────────

def generate_audio(
    text: str,
    output_path: str,
    engine: Optional[str] = None,
    voice: Optional[str] = None,
    rate: str = "+0%",
) -> str:
    """
    テキストから音声ファイルを生成。

    Args:
        text:        読み上げるテキスト
        output_path: 出力ファイルパス（.mp3 or .wav）
        engine:      "edge" or "qwen3"（None の場合は .env の TTS_ENGINE を使用）
        voice:       音声名（engine依存。None の場合はデフォルト）
        rate:        読み上げ速度（edge-tts 形式: "+0%", "-15%", "+10%" など）

    Returns:
        保存されたファイルパス
    """
    engine = engine or TTS_ENGINE

    if engine == "qwen3":
        v = voice or "Chelsie"
        try:
            return _generate_qwen3(text, QWEN3_TTS_URL, output_path, voice=v)
        except RuntimeError as e:
            print(f"[TTS] qwen3フォールバック: {e} → edge-ttsへ切替")
            engine = "edge"

    # edge-tts
    v = voice or EDGE_TTS_VOICE
    return _generate_edge(text, v, output_path, rate=rate)


def generate_audio_segments(
    sentences: list[str],
    out_dir: Path,
    prefix: str = "seg",
    engine: Optional[str] = None,
    voice: Optional[str] = None,
    rate: str = "+0%",
) -> list[Path]:
    """
    文リストをセグメントごとに音声生成してリストで返す。
    edge-ttsの場合、1リクエストずつ少し間を置く（レート制限回避）。

    Args:
        rate: 読み上げ速度（VideoType.tts_rate を渡す）

    Returns:
        音声ファイルパスのリスト（sentences と同順）
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, sent in enumerate(sentences):
        ext = ".mp3" if (engine or TTS_ENGINE) == "edge" else ".wav"
        out = out_dir / f"{prefix}_{i:03d}{ext}"
        print(f"[TTS] {i+1}/{len(sentences)} 生成中: {sent[:30]}...")
        generate_audio(sent, str(out), engine=engine, voice=voice, rate=rate)
        paths.append(out)
        time.sleep(0.3)  # edge-ttsレート制限対策

    return paths


def concatenate_audio_files(paths: list[Path], output_path: str) -> str:
    """
    複数の音声ファイルをFFmpegで結合する。

    Returns:
        結合後のファイルパス
    """
    import subprocess
    import tempfile

    list_file = Path(output_path).parent / "_concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{Path(p).absolute().as_posix()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-acodec", "libmp3lame",
        "-q:a", "2",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path


if __name__ == "__main__":
    # 動作確認
    test_text = "あなたの魂は、すでに答えを知っています。"
    out = "test_tts.mp3"
    generate_audio(test_text, out)
    print(f"生成完了: {out}")
