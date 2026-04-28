"""
Qwen3 TTS を使ったボイス自動生成モジュール

使い方:
  1. eroge_generator/voice_refs/ にキャラごとの参照WAVを置く
     例: voice_refs/sakura.wav, voice_refs/narrator.wav
  2. main.py --voice で自動呼び出し、または単独実行
     python voice_generator.py --project "output/タイトル"

生成物:
  output/タイトル/game/audio/voice/scene1_sakura_001.wav ...
  script.rpy に voice タグを自動挿入
"""
import re
import sys
import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

# qwen3_tts パッケージへのパスを通す
QWEN_TTS_DIR = Path(__file__).parent.parent / "qwen3_tts"
if str(QWEN_TTS_DIR) not in sys.path:
    sys.path.insert(0, str(QWEN_TTS_DIR))

from qwen_tts import Qwen3TTSModel

# ── 定数 ──────────────────────────────────────────────────────
MODEL_PATH   = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
VOICE_REFS   = Path(__file__).parent / "voice_refs"  # 参照音声フォルダ
DEFAULT_VOICE = VOICE_REFS / "default.wav"            # デフォルト参照音声

GEN_KWARGS = dict(
    max_new_tokens=2048,
    do_sample=True,
    top_k=50,
    top_p=1.0,
    temperature=0.9,
    repetition_penalty=1.05,
    subtalker_dosample=True,
    subtalker_top_k=50,
    subtalker_top_p=1.0,
    subtalker_temperature=0.9,
)

# Ren'Py キャラ台詞行のパターン: `変数名 "台詞"`
DIALOGUE_RE = re.compile(r'^(\s*)((\w+)\s+"((?:[^"\\]|\\.)+)")', re.MULTILINE)
# ナレーター行（変数名なし）: `narrator "テキスト"` または `"テキスト"`
NARRATOR_RE = re.compile(r'^(\s*)(narrator\s+"((?:[^"\\]|\\.)+)")', re.MULTILINE)


# ── TTS モデルロード ──────────────────────────────────────────
def load_tts() -> Qwen3TTSModel:
    print("Qwen3 TTS モデルをロード中...")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype  = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    tts = Qwen3TTSModel.from_pretrained(
        MODEL_PATH,
        device_map=device,
        dtype=dtype,
    )
    print(f"  モデルロード完了 (device={device})")
    return tts


# ── 参照音声マップを構築 ──────────────────────────────────────
def build_voice_map(concept: dict) -> dict:
    """
    キャラの var_name → 参照WAVパス のマップを作る。
    voice_refs/<var_name>.wav があればそれを使い、なければ default.wav。
    """
    VOICE_REFS.mkdir(exist_ok=True)
    voice_map = {}

    all_vars = ["narrator"] + [h["var_name"] for h in concept.get("heroines", [])]

    for var in all_vars:
        wav = VOICE_REFS / f"{var}.wav"
        if wav.exists():
            voice_map[var] = str(wav)
            print(f"  {var}: {wav.name}")
        elif DEFAULT_VOICE.exists():
            voice_map[var] = str(DEFAULT_VOICE)
            print(f"  {var}: default.wav (参照音声なし)")
        else:
            voice_map[var] = None
            print(f"  {var}: 参照音声なし → スキップ")

    return voice_map


# ── スクリプト解析：台詞行を抽出 ─────────────────────────────
def extract_dialogue_lines(script_text: str) -> list:
    """
    script.rpy から台詞行を抽出する。
    戻り値: [{"var": "sakura", "text": "こんにちは", "line_start": 100, "line_end": 120}, ...]
    """
    lines = script_text.split("\n")
    dialogue = []
    for i, line in enumerate(lines):
        # キャラ台詞: `    sakura "台詞"`
        m = re.match(r'(\s*)(\w+)\s+"((?:[^"\\]|\\.)+)"', line)
        if m:
            var = m.group(2)
            # define / scene / show / jump / label など Ren'Py キーワードを除外
            if var not in ("define", "scene", "show", "hide", "jump", "label",
                           "call", "return", "play", "stop", "voice", "pause",
                           "window", "menu", "if", "else", "elif", "with"):
                dialogue.append({
                    "line_idx": i,
                    "var": var,
                    "text": m.group(3).replace('\\"', '"'),
                    "indent": m.group(1),
                })
    return dialogue


# ── 音声生成 ─────────────────────────────────────────────────
def generate_voice_for_line(tts: Qwen3TTSModel, text: str, ref_wav: str) -> tuple:
    """1行分の音声を生成して (wav_array, sample_rate) を返す"""
    wavs, sr = tts.generate_voice_clone(
        text=text,
        language="Japanese",
        ref_audio=ref_wav,
        x_vector_only_mode=True,   # 参照テキスト不要モード
        **GEN_KWARGS,
    )
    return wavs[0], sr


# ── メイン処理 ───────────────────────────────────────────────
def generate_voices(project_dir: Path, concept: dict, dry_run: bool = False):
    """
    project_dir: output/タイトル/
    concept:     generator.py が生成したキャラ情報dict
    dry_run:     True なら音声生成せず voice タグだけ挿入（テスト用）
    """
    script_path = project_dir / "game" / "script.rpy"
    if not script_path.exists():
        print(f"ERROR: script.rpy が見つかりません: {script_path}")
        return

    audio_dir = project_dir / "game" / "audio" / "voice"
    audio_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== ボイス生成開始 ===\n")
    voice_map = build_voice_map(concept)

    # モデルロード（dry_run時はスキップ）
    tts = None if dry_run else load_tts()

    script_text = script_path.read_text(encoding="utf-8")
    lines = script_text.split("\n")
    dialogues = extract_dialogue_lines(script_text)

    print(f"\n台詞行数: {len(dialogues)} 行\n")

    # 台詞行に voice タグを挿入（後ろから処理してインデックスズレを防ぐ）
    counters = {}  # var_name → 連番カウンタ
    insertions = []  # (line_idx, voice_line_str) のリスト

    for d in dialogues:
        var   = d["var"]
        text  = d["text"]
        idx   = d["line_idx"]
        indent = d["indent"]
        ref   = voice_map.get(var)

        # ファイル名決定
        counters[var] = counters.get(var, 0) + 1
        scene_num = _guess_scene(lines, idx)
        fname = f"{scene_num}_{var}_{counters[var]:03d}.wav"
        rel_path = f"audio/voice/{fname}"
        abs_path = audio_dir / fname

        # 音声生成
        if not dry_run and ref and not abs_path.exists():
            print(f"  生成: {fname}  「{text[:20]}...」")
            try:
                wav, sr = generate_voice_for_line(tts, text, ref)
                sf.write(str(abs_path), wav, sr)
            except Exception as e:
                print(f"    !! 生成失敗: {e}")
                rel_path = None
        elif dry_run:
            print(f"  [dry] {fname}  「{text[:20]}」")

        if rel_path:
            voice_line = f'{indent}voice "{rel_path}"'
            insertions.append((idx, voice_line))

    # スクリプトに voice タグを挿入（後ろから処理）
    for idx, voice_line in sorted(insertions, reverse=True):
        # すでに voice タグがある場合はスキップ
        if idx > 0 and lines[idx - 1].strip().startswith("voice "):
            continue
        lines.insert(idx, voice_line)

    new_script = "\n".join(lines)
    script_path.write_text(new_script, encoding="utf-8")
    print(f"\n  -> script.rpy に voice タグを挿入しました ({len(insertions)} 行)")
    print(f"  -> 音声ファイル: {audio_dir}")
    print("\n=== ボイス生成完了 ===")


def _guess_scene(lines: list, line_idx: int) -> str:
    """その台詞行より前で最後に出現した label scene_N を返す"""
    for i in range(line_idx, -1, -1):
        m = re.match(r'\s*label\s+(scene_\d+)', lines[i])
        if m:
            return m.group(1)
    return "scene_0"


# ── 単独実行エントリポイント ──────────────────────────────────
def main():
    import json
    p = argparse.ArgumentParser(description="Qwen3 TTS ボイス生成")
    p.add_argument("--project", required=True, help="プロジェクトフォルダ (output/タイトル)")
    p.add_argument("--dry-run", action="store_true", help="音声生成せず voice タグだけ挿入")
    args = p.parse_args()

    project_dir = Path(args.project)
    concept_path = project_dir / "concept.json"
    if not concept_path.exists():
        print(f"ERROR: concept.json が見つかりません: {concept_path}")
        sys.exit(1)

    concept = json.loads(concept_path.read_text(encoding="utf-8"))
    generate_voices(project_dir, concept, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
