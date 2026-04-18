"""
test_voice_pipeline.py - 音声コンテンツのパイプラインを単独テスト

Gemini 不要: テスト用固定スクリプトを使用
参照音声: Alibaba 公開サンプル (clone_2.wav) を使用（Apache 2.0 ライセンス）
"""
import sys
import os
import json
import subprocess
import tempfile
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# ─── テスト設定 ────────────────────────────────────────────────────
# Alibaba が公開している参照音声 URL (英語 / Apache 2.0)
REF_AUDIO = "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone_2.wav"
REF_TEXT  = ("Okay. Yeah. I resent you. I love you. I respect you. "
             "But you know what? You blew it! And thanks to you.")

# テスト用音声スクリプト (psychology: 相手の気持ち解説系)
TEST_TITLE  = "既読スルーの本当の意味"
TEST_FORMAT = "psychology"
TEST_SCRIPT = (
    "好きな人からの既読スルー、すごく不安になりますよね。"
    "でも実は、既読スルーにはいくつかのパターンがあって、"
    "必ずしも嫌われているわけじゃないんです。"
    "たとえば、返信の内容を考えすぎてタイミングを逃してしまうタイプの人は、"
    "好きな相手ほど慎重になりすぎて、気づいたら何日も経ってた、"
    "なんてことがよくあります。"
    "もし相手が普段はマメに返信する人なのに急に遅くなったなら、"
    "それはあなたのことを意識している可能性が高いサインかもしれません。"
    "焦らずに、少し時間を置いて、また別の話題で連絡してみてください。"
    "あなたの気持ちは、きっと伝わっています。"
)

# 出力先
ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
CARD_PATH  = os.path.join(config.SCREENSHOTS_DIR, f"test_voice_card_{ts}.png")
WAV_PATH   = os.path.join(
    getattr(config, "VOICE_OUTPUT_DIR", os.path.join(config.BASE_DIR, "voice_output")),
    f"test_voice_{ts}.wav"
)
VIDEO_PATH = os.path.join(config.OUTPUT_DIR, f"test_voice_{ts}.mp4")

TTS_PYTHON = getattr(config, "TTS_PYTHON",
                     r"C:\qwen3tts-jp\Qwen3-TTS-JP\.venv\Scripts\python.exe")
TTS_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_worker.py")


def step(label):
    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}")


def main():
    print(f"テスト開始: {ts}")
    print(f"タイトル  : {TEST_TITLE}")
    print(f"スクリプト: {len(TEST_SCRIPT)}文字")
    t0 = time.time()

    # ── STEP 1: タイトルカード生成 ──────────────────────────────────
    step("STEP 1/3: タイトルカード生成")
    os.makedirs(os.path.dirname(CARD_PATH), exist_ok=True)

    from card_generator import generate_card
    generate_card(TEST_TITLE, CARD_PATH, style="voice_title")
    print(f"カード保存: {CARD_PATH}  ({os.path.getsize(CARD_PATH):,} bytes)")

    # ── STEP 2: TTS 音声生成 ─────────────────────────────────────────
    step("STEP 2/3: TTS 音声生成（モデルロードで1〜2分かかります）")
    os.makedirs(os.path.dirname(WAV_PATH), exist_ok=True)

    args_dict = {
        "script":      TEST_SCRIPT,
        "ref_audio":   REF_AUDIO,
        "ref_text":    REF_TEXT,
        "output_path": WAV_PATH,
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(args_dict, tf, ensure_ascii=False)
        args_json = tf.name

    print(f"TTS Python: {TTS_PYTHON}")
    print(f"参照音声  : {REF_AUDIO}")
    try:
        result = subprocess.run(
            [TTS_PYTHON, TTS_WORKER, args_json],
            capture_output=False,   # stdout をリアルタイム表示
            timeout=600,
            env={**os.environ},
        )
        rc = result.returncode
    except subprocess.TimeoutExpired:
        print("ERROR: TTS タイムアウト (10分)")
        return
    finally:
        try:
            os.unlink(args_json)
        except Exception:
            pass

    if rc != 0 or not os.path.exists(WAV_PATH):
        print(f"ERROR: TTS 生成失敗 (rc={rc})")
        return

    wav_size = os.path.getsize(WAV_PATH)
    print(f"\nWAV 保存  : {WAV_PATH}  ({wav_size:,} bytes)")

    # ── STEP 3: 動画合成 ─────────────────────────────────────────────
    step("STEP 3/3: 動画合成")
    os.makedirs(os.path.dirname(VIDEO_PATH), exist_ok=True)

    from composer import compose_voice_video
    compose_voice_video(CARD_PATH, WAV_PATH, VIDEO_PATH)
    print(f"動画保存  : {VIDEO_PATH}  ({os.path.getsize(VIDEO_PATH):,} bytes)")

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"  完了! 所要時間: {elapsed:.0f}秒")
    print(f"{'='*50}")
    print(f"動画: {VIDEO_PATH}")

    # ── 動画を開く ──────────────────────────────────────────────────
    print("動画を開いています...")
    os.startfile(VIDEO_PATH)


if __name__ == "__main__":
    main()
