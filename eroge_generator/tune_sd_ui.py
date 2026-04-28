#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SD 画質チューニング UI
2枚ずつ表示 → ★で評価 → ベスト設定に収束させる
"""
import gradio as gr
import json, base64, pathlib, urllib.request, sys, re
from PIL import Image
import io

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import sd_client

OUTPUT_DIR = pathlib.Path(__file__).parent / "output" / "tune_ui"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SD_URL  = "http://localhost:7860"
TIMEOUT = 600
SEED    = 4011264758   # 安定してたシード

SCORE_TAGS   = "score_9, score_8_up, score_7_up, score_6_up"
QUALITY_BASE = (
    "masterpiece, best quality, ultra-detailed, absurdres, highres, "
    "intricate details, beautiful detailed face, perfect anatomy, beautiful lighting"
)
COMMON_NEG = (
    "worst quality, low quality, normal quality, lowres, "
    "bad anatomy, bad hands, bad fingers, extra fingers, missing fingers, "
    "extra limbs, missing limbs, deformed hands, long neck, "
    "bad face, ugly face, asymmetrical eyes, "
    "mutation, disfigured, malformed, "
    "text, watermark, signature, "
    "blurry, jpeg artifacts, compression artifacts, "
    "3d, cgi, render, photo, realistic, "
    "tanned skin, dark skin, tan lines, sunburn, "
    "sketch, rough sketch, draft, unfinished, messy lines, "
    "comic panels, manga panels, split image, multiple views, multiple panels"
)

EROTIC_PROMPT = (
    "1girl, long pink hair, blue eyes, blushing, "
    "lying on bed, nude, large breasts, sex, missionary position, "
    "sweating, tears, pleasured expression, bedroom, night, dim light, sheets"
)

STYLES = {
    "なし":      "",
    "game_cg":   "game cg, visual novel cg, soft shading, gradient shading, delicate coloring",
    "soft":      "soft focus, dreamy, pastel colors, gentle atmosphere",
    "doujin":    "doujinshi style, hand-drawn feel, expressive lines",
    "light_novel": "light novel illustration, clean lines, commercial art",
}

# ── バリエーション定義（Euler a 軸で小さく変化） ──────────────────
# まず現行設定に近いものから試す
VARIATIONS = [
    # ① 現行設定そのまま（ベースライン）
    {"sampler": "Euler a",          "cfg": 7.0, "denoise": 0.50, "steps": 28, "style": "なし"},
    # ② CFG少し下
    {"sampler": "Euler a",          "cfg": 6.5, "denoise": 0.50, "steps": 28, "style": "なし"},
    # ③ CFGさらに下
    {"sampler": "Euler a",          "cfg": 6.0, "denoise": 0.50, "steps": 28, "style": "なし"},
    # ④ CFG上げ
    {"sampler": "Euler a",          "cfg": 7.5, "denoise": 0.50, "steps": 28, "style": "なし"},
    # ⑤ Hiresノイズ下げ（シャープに）
    {"sampler": "Euler a",          "cfg": 7.0, "denoise": 0.40, "steps": 28, "style": "なし"},
    # ⑥ Hiresノイズ上げ（柔らかく）
    {"sampler": "Euler a",          "cfg": 7.0, "denoise": 0.60, "steps": 28, "style": "なし"},
    # ⑦ game cgスタイル
    {"sampler": "Euler a",          "cfg": 7.0, "denoise": 0.50, "steps": 28, "style": "game_cg"},
    # ⑧ softスタイル
    {"sampler": "Euler a",          "cfg": 7.0, "denoise": 0.50, "steps": 28, "style": "soft"},
    # ⑨ DPM++ 2M Karras（サンプラー比較）
    {"sampler": "DPM++ 2M Karras",  "cfg": 7.0, "denoise": 0.50, "steps": 30, "style": "なし"},
    # ⑩ DPM++ SDE Karras
    {"sampler": "DPM++ SDE Karras", "cfg": 7.0, "denoise": 0.50, "steps": 28, "style": "なし"},
]


def var_label(v: dict) -> str:
    style = f" [{v['style']}]" if v["style"] != "なし" else ""
    return f"{v['sampler']}  CFG {v['cfg']}  noise {v['denoise']}{style}"


def _post(payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{SD_URL}/sdapi/v1/txt2img", data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def generate_one(v: dict) -> Image.Image:
    style_str = STYLES.get(v["style"], "")
    parts = [SCORE_TAGS, QUALITY_BASE]
    if style_str:
        parts.append(style_str)
    parts.append(EROTIC_PROMPT)
    positive = ", ".join(parts)

    payload = {
        "prompt":          positive,
        "negative_prompt": COMMON_NEG,
        "width":  832, "height": 1216,
        "steps":           v["steps"],
        "cfg_scale":       v["cfg"],
        "sampler_name":    v["sampler"],
        "batch_size": 1,
        "seed":            SEED,
        "enable_hr":             True,
        "hr_scale":              1.5,
        "hr_upscaler":           "R-ESRGAN 4x+ Anime6B",
        "hr_second_pass_steps":  20,
        "denoising_strength":    v["denoise"],
        "hr_additional_modules": [],
    }
    if sd_client._check_adetailer():
        payload["alwayson_scripts"] = sd_client._adetailer_args(face=True)

    result = _post(payload)
    png    = base64.b64decode(result["images"][0])
    return Image.open(io.BytesIO(png))


def apply_to_sdclient(v: dict):
    client_path = pathlib.Path(__file__).parent / "sd_client.py"
    text = client_path.read_text(encoding="utf-8")

    text = re.sub(r'"sampler_name":\s*"[^"]*"',
                  f'"sampler_name":    "{v["sampler"]}"', text)
    text = re.sub(r'("cfg_scale":\s*)[\d.]+',
                  lambda m: f'{m.group(1)}{v["cfg"]}', text)
    text = re.sub(r'("denoising_strength":\s*)[\d.]+',
                  lambda m: f'{m.group(1)}{v["denoise"]}', text)

    style_str = STYLES.get(v["style"], "")
    if style_str:
        new_prefix = (
            'QUALITY_PREFIX = (\n'
            '    "masterpiece, best quality, ultra-detailed, absurdres, "\n'
            '    "highres, intricate details, beautiful detailed face, "\n'
            f'    "perfect anatomy, beautiful lighting, "\n'
            f'    "{style_str}"\n'
            ')'
        )
    else:
        new_prefix = (
            'QUALITY_PREFIX = (\n'
            '    "masterpiece, best quality, ultra-detailed, absurdres, "\n'
            '    "highres, intricate details, beautiful detailed face, "\n'
            '    "perfect anatomy, beautiful lighting"\n'
            ')'
        )
    text = re.sub(r'QUALITY_PREFIX = \(.*?\)', new_prefix, text, flags=re.DOTALL)
    client_path.write_text(text, encoding="utf-8")


# ── Gradio UI ─────────────────────────────────────────────────────
def do_generate(state):
    idx = state["idx"]
    if idx + 1 >= len(VARIATIONS):
        return (
            None, None,
            "（全バリエーション完了）", "（全バリエーション完了）",
            f"## 全{len(VARIATIONS)}枚完了\nもう一度最初から試すには再起動してください。",
            state
        )

    v1 = VARIATIONS[idx]
    v2 = VARIATIONS[idx + 1]

    progress = f"生成中… ({idx+1}/{len(VARIATIONS)} & {idx+2}/{len(VARIATIONS)})"
    img1 = generate_one(v1)
    img2 = generate_one(v2)

    state = {**state, "idx": idx + 2,
             "last_v1": v1, "last_v2": v2}

    best = state.get("best")
    best_txt = f"**現在のベスト:** {var_label(best['var'])} → {best['score']}点" if best else "まだ評価なし"

    return (
        img1, img2,
        f"**左 ({idx+1}):** {var_label(v1)}",
        f"**右 ({idx+2}):** {var_label(v2)}",
        best_txt,
        state
    )


def do_rate(score_left, score_right, state):
    v1 = state.get("last_v1")
    v2 = state.get("last_v2")
    if v1 is None:
        return "先に生成してください。", state

    ratings = state.get("ratings", [])
    if score_left > 0:
        ratings.append({"var": v1, "score": score_left})
    if score_right > 0:
        ratings.append({"var": v2, "score": score_right})

    best = max(ratings, key=lambda x: x["score"]) if ratings else None
    state = {**state, "ratings": ratings, "best": best}

    lines = []
    for r in sorted(ratings, key=lambda x: -x["score"]):
        lines.append(f"- {r['score']}点: {var_label(r['var'])}")
    summary = "### 評価履歴\n" + "\n".join(lines)
    return summary, state


def do_apply(state):
    best = state.get("best")
    if best is None:
        return "まだ評価がありません。"
    apply_to_sdclient(best["var"])
    return f"✅ sd_client.py に適用しました！\n\n{var_label(best['var'])}"


# ── レイアウト ────────────────────────────────────────────────────
with gr.Blocks(title="SD 画質チューナー") as demo:
    gr.Markdown("# 🎨 SD 画質チューナー\n2枚ずつ生成 → ★で評価 → ベスト設定を自動適用")

    state = gr.State({"idx": 0, "ratings": [], "best": None,
                      "last_v1": None, "last_v2": None})

    with gr.Row():
        gen_btn = gr.Button("▶ 次の2枚を生成", variant="primary", scale=2)
        apply_btn = gr.Button("✅ ベスト設定を適用", variant="secondary", scale=1)

    best_md = gr.Markdown("まだ評価なし")

    with gr.Row():
        with gr.Column():
            img_left  = gr.Image(label="左", type="pil", height=500)
            lbl_left  = gr.Markdown("設定待ち")
            score_left = gr.Radio(
                choices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                label="左の点数", value=None
            )
        with gr.Column():
            img_right  = gr.Image(label="右", type="pil", height=500)
            lbl_right  = gr.Markdown("設定待ち")
            score_right = gr.Radio(
                choices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                label="右の点数", value=None
            )

    rate_btn = gr.Button("⭐ 点数を送信", variant="primary")
    history_md = gr.Markdown("### 評価履歴")
    apply_result = gr.Markdown()

    # ── イベント ──
    gen_btn.click(
        fn=do_generate,
        inputs=[state],
        outputs=[img_left, img_right, lbl_left, lbl_right, best_md, state]
    )
    rate_btn.click(
        fn=do_rate,
        inputs=[score_left, score_right, state],
        outputs=[history_md, state]
    )
    apply_btn.click(
        fn=do_apply,
        inputs=[state],
        outputs=[apply_result]
    )


if __name__ == "__main__":
    print("SD 画質チューナー起動中...")
    demo.launch(inbrowser=True, theme=gr.themes.Soft())
