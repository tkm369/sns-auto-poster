"""
speech_analyzer.py
Whisperを使ったフィラーワード検出・噛み検出
"""
from faster_whisper import WhisperModel
from difflib import SequenceMatcher
from typing import List, Dict


# カット対象フィラーワード（日本語）
FILLER_WORDS = [
    "えーと", "えっと", "えー", "えっ",
    "あのー", "あのう", "あの",
    "うーん", "うーむ", "うん",
    "まあ", "まー",
    "なんか",
    "そのー", "そのう",
    "ちょっと",
    "ねー",
]


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _extract_words(segments) -> List[Dict]:
    """faster-whisperのセグメントから全単語リストを作成"""
    words = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if not text:
                continue
            words.append({
                "word": text,
                "start": w.start,
                "end": w.end,
                "duration": w.end - w.start,
            })
    return words


def _detect_fillers(words: List[Dict], min_sec: float) -> List[Dict]:
    """フィラーワード検出：min_sec以上続くフィラーをカット"""
    cuts = []
    for w in words:
        if w["duration"] < min_sec:
            continue
        for filler in FILLER_WORDS:
            if filler in w["word"]:
                cuts.append({
                    "start": round(w["start"], 4),
                    "end": round(w["end"], 4),
                    "reason": f"filler: 「{w['word']}」({w['duration']:.2f}s)",
                })
                break
    return cuts


def _detect_stammers(words: List[Dict], gap_limit: float = 0.6) -> List[Dict]:
    """
    噛み・言い直し検出。
    - 単語レベル: word[i] と word[i+1] が類似 → word[i] をカット
    - フレーズレベル (2〜4語): フレーズが繰り返された場合、最初のフレーズをカット
    """
    cuts = []
    used = set()  # すでにカット対象にしたインデックス

    i = 0
    while i < len(words):
        if i in used:
            i += 1
            continue

        # --- フレーズレベル（長い順にチェック）---
        matched_phrase = False
        for window in [4, 3, 2]:
            if i + window * 2 > len(words):
                continue
            phrase1_words = words[i:i + window]
            phrase2_words = words[i + window:i + window * 2]

            # フレーズ間ギャップ（phrase1末尾 → phrase2先頭）
            gap = phrase2_words[0]["start"] - phrase1_words[-1]["end"]
            if gap > gap_limit:
                continue

            phrase1 = "".join(w["word"] for w in phrase1_words)
            phrase2 = "".join(w["word"] for w in phrase2_words)

            if _similarity(phrase1, phrase2) >= 0.78:
                cuts.append({
                    "start": round(phrase1_words[0]["start"], 4),
                    "end": round(phrase1_words[-1]["end"], 4),
                    "reason": f"re-take: 「{phrase1[:15]}」→「{phrase2[:15]}」",
                })
                for idx in range(i, i + window):
                    used.add(idx)
                i += window
                matched_phrase = True
                break

        if matched_phrase:
            continue

        # --- 単語レベル ---
        if i + 1 < len(words) and (i + 1) not in used:
            w1, w2 = words[i], words[i + 1]
            gap = w2["start"] - w1["end"]
            if gap < gap_limit and _similarity(w1["word"], w2["word"]) >= 0.75:
                cuts.append({
                    "start": round(w1["start"], 4),
                    "end": round(w1["end"], 4),
                    "reason": f"stammer: 「{w1['word']}」→「{w2['word']}」",
                })
                used.add(i)
                i += 1
                continue

        i += 1

    return cuts


def _load_whisper(model_name: str):
    """Whisperモデルをロード（GPU/CPU自動判定・同梱モデル優先）"""
    try:
        import torch
        use_cuda = torch.cuda.is_available()
    except ImportError:
        use_cuda = False

    device = "cuda" if use_cuda else "cpu"
    compute_type = "float16" if use_cuda else "int8"

    import sys, os
    base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
               else os.path.dirname(os.path.abspath(__file__))
    local_model_path = os.path.join(base_dir, "models", model_name)

    if os.path.isdir(local_model_path):
        model_source = local_model_path
        print(f"  同梱モデルを使用: {model_source}")
    else:
        model_source = model_name
        print(f"  モデルをダウンロード中: {model_name}（初回のみ）")

    print(f"  デバイス: {device.upper()} / {compute_type}")
    return WhisperModel(model_source, device=device, compute_type=compute_type)


def transcribe(audio_path: str, model_name: str = "large-v3") -> List[Dict]:
    """
    音声を文字起こしし、セグメントリストを返す。
    SRT生成・AI校正の入力として使用する。

    Returns:
        [{"start": float, "end": float, "text": str}]
    """
    model = _load_whisper(model_name)
    print("  音声認識中...")
    raw_segments, _ = model.transcribe(
        audio_path,
        language="ja",
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    raw_segments = list(raw_segments)

    segments = [
        {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
        for seg in raw_segments
        if seg.text.strip()
    ]
    print(f"  セグメント数: {len(segments)}")
    return segments, raw_segments


def analyze_speech_cuts(
    audio_path: str,
    model_name: str = "large-v3",
    filler_min_sec: float = 0.4,
    detect_fillers: bool = True,
    detect_stammers: bool = True,
    _raw_segments=None,   # transcribe()済みの場合は再実行を省略
) -> List[Dict]:
    """
    Whisperで文字起こしし、フィラー・噛みのカットリストを返す。

    Returns:
        [{"start": float, "end": float, "reason": str}]
    """
    if _raw_segments is None:
        model = _load_whisper(model_name)
        print("  音声認識中...")
        raw_segments, _ = model.transcribe(
            audio_path,
            language="ja",
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        _raw_segments = list(raw_segments)

    words = _extract_words(_raw_segments)
    if not words:
        print("  警告: 単語が検出されませんでした")
        return []

    print(f"  検出単語数: {len(words)}")

    cuts = []
    if detect_fillers:
        filler_cuts = _detect_fillers(words, filler_min_sec)
        print(f"  フィラー検出: {len(filler_cuts)} 箇所")
        cuts.extend(filler_cuts)

    if detect_stammers:
        stammer_cuts = _detect_stammers(words)
        print(f"  噛み検出: {len(stammer_cuts)} 箇所")
        cuts.extend(stammer_cuts)

    return cuts
