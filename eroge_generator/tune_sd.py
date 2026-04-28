#!/usr/bin/env python3
"""
SD 画質チューニングツール
各バリエーションを生成 → 点数入力 → 高得点設定を軸に次ラウンドへ
"""
import json, base64, os, pathlib, urllib.request, subprocess, re
from datetime import datetime

SD_URL  = "http://localhost:7860"
TIMEOUT = 600
OUTPUT_BASE = pathlib.Path(__file__).parent / "output" / "tune"

# ── 固定シード（同条件で比較するため） ──────────────────────────────
SEED = 42

# ── テスト用プロンプト ───────────────────────────────────────────────
PROMPTS = {
    "立ち絵":  "1girl, long pink hair, blue eyes, blushing, smile, school uniform, simple white background, full body, looking at viewer",
    "キス":    "1boy, 1girl, long pink hair, blue eyes, kissing, romantic, school uniform, window, upper body",
    "ベッド":  "1girl, long pink hair, blue eyes, lying on bed, embarrassed, white lingerie, bedroom, upper body, looking at viewer",
}
ACTIVE_PROMPT = "キス"   # ← ここを変えるとテストシーンを切り替えられる

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
    "oversaturated, overexposed, blown out highlights, "
    "3d, cgi, render, photo, realistic, "
    "tanned skin, dark skin, tan lines, sunburn, "
    "sketch, rough sketch, draft, unfinished, rough lines, messy lines"
)

# ── スタイルタグのバリエーション ─────────────────────────────────────
STYLES = {
    "なし":          "",
    "game_cg":       "game cg, visual novel cg, soft shading, gradient shading, delicate coloring",
    "painterly":     "painterly, artistic, expressive brushwork, textured",
    "soft":          "soft focus, dreamy, hazy light, pastel colors, gentle atmosphere",
    "doujin":        "doujinshi style, hand-drawn feel, energetic lines, indie art",
    "light_novel":   "light novel illustration, clean lines, commercial art",
    "watercolor":    "watercolor, soft watercolor, transparent coloring",
}

# ── パラメータ空間 ────────────────────────────────────────────────────
SAMPLERS = [
    "Euler a",
    "DPM++ 2M Karras",
    "DPM++ SDE Karras",
    "DPM++ 2S a Karras",
    "DDIM",
    "UniPC",
]
CFG_RANGE     = [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5]
DENOISE_RANGE = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]
STEPS_RANGE   = [20, 25, 28, 32, 40]

# ── ラウンド1: 多様な初期バリエーション ──────────────────────────────
INITIAL_VARIATIONS = [
    {"id": "A", "sampler": "Euler a",           "cfg": 7.0, "style": "なし",        "denoise": 0.5, "steps": 28},
    {"id": "B", "sampler": "DPM++ 2M Karras",   "cfg": 7.0, "style": "なし",        "denoise": 0.5, "steps": 30},
    {"id": "C", "sampler": "DPM++ SDE Karras",  "cfg": 6.5, "style": "なし",        "denoise": 0.4, "steps": 28},
    {"id": "D", "sampler": "Euler a",           "cfg": 5.5, "style": "なし",        "denoise": 0.5, "steps": 28},
    {"id": "E", "sampler": "Euler a",           "cfg": 7.0, "style": "game_cg",    "denoise": 0.5, "steps": 28},
    {"id": "F", "sampler": "DPM++ 2M Karras",   "cfg": 6.0, "style": "soft",       "denoise": 0.4, "steps": 30},
    {"id": "G", "sampler": "Euler a",           "cfg": 7.0, "style": "doujin",     "denoise": 0.5, "steps": 28},
    {"id": "H", "sampler": "DPM++ 2S a Karras", "cfg": 7.0, "style": "なし",        "denoise": 0.45,"steps": 28},
]


# ── API ────────────────────────────────────────────────────────────
def _post(payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{SD_URL}/sdapi/v1/txt2img", data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _check_adetailer() -> bool:
    try:
        with urllib.request.urlopen(f"{SD_URL}/sdapi/v1/scripts", timeout=10) as r:
            scripts = json.loads(r.read())
        return any("adetailer" in s.lower() for s in scripts.get("txt2img", []))
    except Exception:
        return False


def _adetailer_args():
    return {"ADetailer": {"args": [{
        "ad_model":               "face_yolov8n.pt",
        "ad_prompt":              "beautiful detailed face, perfect eyes",
        "ad_negative_prompt":     "bad face, ugly, deformed",
        "ad_confidence":          0.3,
        "ad_dilate_erode":        4,
        "ad_steps":               28,
        "ad_cfg_scale":           7,
        "ad_denoising_strength":  0.3,
        "ad_inpaint_only_masked": True,
        "ad_inpaint_only_masked_padding": 32,
    }]}}


# ── プロンプト組み立て ───────────────────────────────────────────────
def build_positive(style_key: str) -> str:
    style = STYLES.get(style_key, "")
    parts = [SCORE_TAGS, QUALITY_BASE]
    if style:
        parts.append(style)
    parts.append(PROMPTS[ACTIVE_PROMPT])
    return ", ".join(parts)


# ── 1枚生成 ──────────────────────────────────────────────────────────
def generate_variant(var: dict, out_dir: pathlib.Path, round_num: int) -> pathlib.Path:
    label = f"r{round_num:02d}_{var['id']}"
    fname = out_dir / f"{label}.png"
    if fname.exists():
        print(f"  [{var['id']}] スキップ（既存）")
        return fname

    positive = build_positive(var["style"])
    payload  = {
        "prompt":          positive,
        "negative_prompt": COMMON_NEG,
        "width":  832, "height": 1216,
        "steps":           var["steps"],
        "cfg_scale":       var["cfg"],
        "sampler_name":    var["sampler"],
        "batch_size": 1,
        "seed":            SEED,
        "enable_hr":             True,
        "hr_scale":              1.5,
        "hr_upscaler":           "R-ESRGAN 4x+ Anime6B",
        "hr_second_pass_steps":  20,
        "denoising_strength":    var["denoise"],
        "hr_additional_modules": [],
    }
    if _check_adetailer():
        payload["alwayson_scripts"] = _adetailer_args()

    result = _post(payload)
    fname.write_bytes(base64.b64decode(result["images"][0]))
    return fname


# ── 点数入力 ──────────────────────────────────────────────────────────
def get_ratings(variations: list) -> dict:
    print("\n" + "="*60)
    print("  各画像に点数をつけてください（1〜10）")
    print("="*60)
    for v in variations:
        style_disp = v["style"] if v["style"] != "なし" else "-"
        print(f"  [{v['id']}] {v['sampler']:<22} CFG:{v['cfg']:.1f}  "
              f"ノイズ:{v['denoise']}  style:{style_disp}")
    print()

    ratings = {}
    for v in variations:
        while True:
            try:
                raw = input(f"  [{v['id']}] 点数 (1-10 / Enterでスキップ): ").strip()
                if raw == "":
                    ratings[v["id"]] = None
                    break
                score = int(raw)
                if 1 <= score <= 10:
                    ratings[v["id"]] = score
                    break
                print("    ※ 1〜10で入力してください")
            except (ValueError, EOFError):
                ratings[v["id"]] = None
                break
    return ratings


# ── 次ラウンドのバリエーション生成 ────────────────────────────────────
def next_variations(ratings: dict, variations: list) -> list:
    # 有効な点数のみ
    valid = {k: v for k, v in ratings.items() if v is not None}
    if not valid:
        return INITIAL_VARIATIONS  # fallback

    # ベスト2を取得
    ranked  = sorted(valid.items(), key=lambda x: x[1], reverse=True)
    best2   = [r[0] for r in ranked[:2]]
    top_var = [v for v in variations if v["id"] in best2]

    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    nexts   = []
    used    = set()

    def add(v):
        if len(nexts) >= 8:
            return
        key = (v["sampler"], v["cfg"], v["style"], v["denoise"])
        if key not in used:
            used.add(key)
            nexts.append({**v, "id": letters[len(nexts)]})

    for base in top_var:
        # CFGを上下
        for delta in [-0.5, +0.5]:
            nc = round(base["cfg"] + delta, 1)
            if 4.0 <= nc <= 9.0:
                add({**base, "cfg": nc})

        # hires denoising を上下
        for delta in [-0.1, +0.1]:
            nd = round(base["denoise"] + delta, 2)
            if 0.25 <= nd <= 0.65:
                add({**base, "denoise": nd})

        # 試していないスタイルを1つ
        tried_styles = {v["style"] for v in variations}
        for s in STYLES:
            if s not in tried_styles:
                add({**base, "style": s})
                break

        # 試していないサンプラーを1つ
        tried_smp = {v["sampler"] for v in variations}
        for s in SAMPLERS:
            if s not in tried_smp:
                add({**base, "sampler": s})
                break

        # stepsを変えて試す
        tried_steps = {v["steps"] for v in variations}
        for st in STEPS_RANGE:
            if st not in tried_steps:
                add({**base, "steps": st})
                break

    # まだ空きがあれば未試サンプラー×ベスト設定
    for smp in SAMPLERS:
        tried_smp = {v["sampler"] for v in variations}
        if smp not in tried_smp:
            add({**top_var[0], "sampler": smp})

    return nexts


# ── ベスト設定を sd_client.py に書き込む ──────────────────────────────
def apply_to_sdclient(var: dict):
    client_path = pathlib.Path(__file__).parent / "sd_client.py"
    text = client_path.read_text(encoding="utf-8")

    # sampler_name
    text = re.sub(
        r'"sampler_name":\s*"[^"]*"',
        f'"sampler_name":    "{var["sampler"]}"',
        text
    )
    # cfg_scale (txt2img の payload 内)
    text = re.sub(
        r'("cfg_scale":\s*)[\d.]+',
        lambda m: f'{m.group(1)}{var["cfg"]}',
        text
    )
    # denoising_strength (hires fix)
    text = re.sub(
        r'("denoising_strength":\s*)[\d.]+',
        lambda m: f'{m.group(1)}{var["denoise"]}',
        text
    )
    # steps (payload)
    text = re.sub(
        r'("steps":\s*)[\d]+',
        lambda m: f'{m.group(1)}{var["steps"]}',
        text
    )

    # スタイルタグを QUALITY_PREFIX に反映（styleが"なし"以外の場合）
    style_str = STYLES.get(var["style"], "")
    if style_str:
        new_prefix = (
            f'QUALITY_PREFIX = (\n'
            f'    "masterpiece, best quality, ultra-detailed, absurdres, "\n'
            f'    "highres, intricate details, beautiful detailed face, "\n'
            f'    "perfect anatomy, beautiful lighting, "\n'
            f'    "{style_str}"\n'
            f')'
        )
    else:
        new_prefix = (
            f'QUALITY_PREFIX = (\n'
            f'    "masterpiece, best quality, ultra-detailed, absurdres, "\n'
            f'    "highres, intricate details, beautiful detailed face, "\n'
            f'    "perfect anatomy, beautiful lighting"\n'
            f')'
        )
    text = re.sub(
        r'QUALITY_PREFIX = \(.*?\)',
        new_prefix,
        text,
        flags=re.DOTALL
    )

    client_path.write_text(text, encoding="utf-8")
    print(f"\n  sd_client.py を更新しました:")
    print(f"    サンプラー  : {var['sampler']}")
    print(f"    CFG         : {var['cfg']}")
    print(f"    Steps       : {var['steps']}")
    print(f"    Hires noise : {var['denoise']}")
    print(f"    スタイル    : {var['style']}")


# ── メインループ ──────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  SD 画質チューニングツール")
    print(f"  テストシーン: {ACTIVE_PROMPT}")
    print("  各画像に1〜10点を付けると、次ラウンドで")
    print("  高得点設定を軸に自動調整します。")
    print("=" * 60)

    ts      = datetime.now().strftime("%m%d_%H%M")
    out_dir = OUTPUT_BASE / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    history        = []
    current_vars   = INITIAL_VARIATIONS
    round_num      = 1
    overall_best   = None
    overall_best_score = 0

    while True:
        print(f"\n【ラウンド {round_num}】 {len(current_vars)}枚生成します...")
        for i, var in enumerate(current_vars):
            style_disp = var["style"] if var["style"] != "なし" else "-"
            print(f"  [{var['id']}] {var['sampler']:<22} CFG={var['cfg']}  "
                  f"style={style_disp}  ({i+1}/{len(current_vars)})", end="", flush=True)
            try:
                generate_variant(var, out_dir, round_num)
                print("  ✓")
            except Exception as e:
                print(f"  !! 失敗: {e}")

        # フォルダを開く
        subprocess.Popen(["explorer", str(out_dir)])
        print(f"\n  画像フォルダを開きました: {out_dir}")
        print("  ファイル名の r01_A, r01_B ... がラウンド番号+ID です。")

        # 点数入力
        ratings = get_ratings(current_vars)
        valid   = {k: v for k, v in ratings.items() if v is not None}

        if valid:
            best_id    = max(valid.items(), key=lambda x: x[1])
            best_var   = next(v for v in current_vars if v["id"] == best_id[0])
            best_score = best_id[1]

            print(f"\n  ★ ラウンド{round_num}ベスト [{best_id[0]}]: {best_score}点")
            style_disp = best_var["style"] if best_var["style"] != "なし" else "-"
            print(f"     サンプラー: {best_var['sampler']}")
            print(f"     CFG: {best_var['cfg']}  Steps: {best_var['steps']}")
            print(f"     Hires denoising: {best_var['denoise']}")
            print(f"     スタイル: {style_disp}")

            if best_score > overall_best_score:
                overall_best_score = best_score
                overall_best       = best_var

            history.append({
                "round":      round_num,
                "variations": current_vars,
                "ratings":    ratings,
                "best_id":    best_id[0],
                "best_score": best_score,
            })

        # 続けるか確認
        print()
        ans = input("  [Enter]=次ラウンド  [q]=終了: ").strip().lower()
        if ans == "q":
            break

        current_vars = next_variations(ratings, current_vars)
        round_num   += 1

    # 最終結果
    (out_dir / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if overall_best:
        print(f"\n{'='*60}")
        print(f"  全ラウンドベスト: {overall_best_score}点")
        style_disp = overall_best["style"] if overall_best["style"] != "なし" else "-"
        print(f"  サンプラー: {overall_best['sampler']}")
        print(f"  CFG: {overall_best['cfg']}  Steps: {overall_best['steps']}")
        print(f"  Hires denoising: {overall_best['denoise']}")
        print(f"  スタイル: {style_disp}")
        print(f"{'='*60}")

        ans = input("\nこの設定を sd_client.py に適用しますか？ [Enter]=適用  [n]=スキップ: ").strip().lower()
        if ans != "n":
            apply_to_sdclient(overall_best)

    print(f"\n履歴: {out_dir / 'history.json'}")
    print("完了！")


if __name__ == "__main__":
    main()
