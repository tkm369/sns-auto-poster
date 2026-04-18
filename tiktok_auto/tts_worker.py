"""
tts_worker.py - Qwen3-TTS-12Hz-1.7B-Baseで音声を生成するサブプロセスワーカー

呼び出し方:
    python tts_worker.py <args_json_path>

args_json_path: 以下のキーを持つJSONファイル
    {
        "script":      "読み上げテキスト",
        "ref_audio":   "C:\\path\\to\\ref.wav",
        "ref_text":    "参照音声の書き起こし（空文字可）",
        "output_path": "C:\\path\\to\\output.wav"
    }

stdout の出力フォーマット:
    INFO:...        # ログメッセージ
    DURATION:xx.xx  # 生成音声の秒数
    SUCCESS:<path>  # 成功時、出力ファイルパス
    ERROR:<msg>     # エラー時
"""
import sys
import os
import json


def main():
    if len(sys.argv) < 2:
        print("ERROR:引数不足 (args_json_path が必要)", flush=True)
        sys.exit(1)

    args_file = sys.argv[1]
    if not os.path.exists(args_file):
        print(f"ERROR:argsファイルが見つかりません: {args_file}", flush=True)
        sys.exit(1)

    with open(args_file, "r", encoding="utf-8") as f:
        args = json.load(f)

    script_text = args.get("script", "")
    ref_audio   = args.get("ref_audio", "")
    ref_text    = args.get("ref_text", "")
    output_path = args.get("output_path", "")

    if not script_text:
        print("ERROR:スクリプトテキストが空です", flush=True)
        sys.exit(1)
    if not output_path:
        print("ERROR:output_pathが未設定", flush=True)
        sys.exit(1)
    is_url = ref_audio.startswith("http://") or ref_audio.startswith("https://")
    if not ref_audio or (not is_url and not os.path.exists(ref_audio)):
        print(f"ERROR:参照音声ファイルが存在しません: {ref_audio}", flush=True)
        sys.exit(1)

    print(f"INFO:TTS生成開始 (script={len(script_text)}文字)", flush=True)
    print(f"INFO:ref_audio={ref_audio}", flush=True)
    print(f"INFO:output_path={output_path}", flush=True)

    try:
        import torch
    except ImportError:
        print("ERROR:PyTorchがインストールされていません", flush=True)
        sys.exit(1)

    try:
        import soundfile as sf
    except ImportError:
        print("ERROR:soundfileがインストールされていません (pip install soundfile)", flush=True)
        sys.exit(1)

    try:
        from qwen_tts import Qwen3TTSModel
    except ImportError as e:
        print(f"ERROR:qwen_ttsのインポート失敗: {e}", flush=True)
        print("ERROR:config.py の TTS_PYTHON (Qwen3-TTS venv) で実行してください", flush=True)
        sys.exit(1)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype  = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    print(f"INFO:デバイス: {device}", flush=True)

    try:
        print("INFO:モデルロード中 (Qwen3-TTS-12Hz-1.7B-Base)...", flush=True)
        tts = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device_map=device,
            dtype=dtype,
        )
        print("INFO:モデルロード完了", flush=True)
    except Exception as e:
        print(f"ERROR:モデルロード失敗: {e}", flush=True)
        sys.exit(1)

    try:
        print("INFO:音声生成中...", flush=True)
        wavs, sr = tts.generate_voice_clone(
            text=script_text,
            language="Japanese",
            ref_audio=ref_audio,
            ref_text=ref_text if ref_text else None,
            max_new_tokens=4096,
            do_sample=True,
            top_k=50,
            top_p=1.0,
            temperature=0.9,
            repetition_penalty=1.05,
        )
    except Exception as e:
        print(f"ERROR:generate_voice_clone失敗: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    # 出力先フォルダを作成してWAV保存
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    try:
        sf.write(output_path, wavs[0], sr)
    except Exception as e:
        print(f"ERROR:WAV書き込み失敗: {e}", flush=True)
        sys.exit(1)

    duration = len(wavs[0]) / sr
    print(f"INFO:音声生成完了: {duration:.1f}秒", flush=True)
    print(f"DURATION:{duration:.2f}", flush=True)
    print(f"SUCCESS:{output_path}", flush=True)


if __name__ == "__main__":
    main()
