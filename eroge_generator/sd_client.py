"""
Stable Diffusion WebUI (Forge) API クライアント
http://localhost:7860 の /sdapi/v1/txt2img を使ってキャラ立ち絵・背景を生成する
"""
import base64
import json
import re
from pathlib import Path
import urllib.request
import urllib.error

SD_URL = "http://localhost:7860"
TIMEOUT = 600  # Hires fix込みで最大10分

# SDXL向け推奨解像度
SPRITE_W, SPRITE_H = 832, 1216   # 縦長（立ち絵）
BG_W,     BG_H     = 1216, 832   # 横長（背景）

# ── 品質タグ ──────────────────────────────────────────────────────
# ポジティブ先頭に付ける共通品質タグ
QUALITY_PREFIX = (
    "masterpiece, best quality, ultra-detailed, absurdres, "
    "highres, intricate details, beautiful detailed face, "
    "perfect anatomy, beautiful lighting"
)

# Pony / NoobAI / Illustrious 系モデル用スコアタグ
SCORE_TAGS = "score_9, score_8_up, score_7_up, score_6_up"

# 総合ネガティブプロンプト（SD1.5・SDXL共通）
COMMON_NEGATIVE = (
    "worst quality, low quality, normal quality, lowres, "
    "bad anatomy, bad hands, bad fingers, extra fingers, missing fingers, "
    "extra limbs, missing limbs, deformed hands, long neck, "
    "bad face, ugly face, asymmetrical eyes, uneven eyes, "
    "mutation, disfigured, malformed, "
    "text, watermark, signature, username, artist name, "
    "blurry, jpeg artifacts, compression artifacts, "
    "oversaturated, overexposed, blown out highlights, overlit, "
    "underexposed, cropped, out of frame, duplicate, "
    "3d, cgi, render, photo, realistic, "
    "tanned skin, dark skin, tan lines, sunburn"
)

# ADetailer が使えるかどうかのキャッシュ
_adetailer_available: bool | None = None


def _post(endpoint: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        f"{SD_URL}{endpoint}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return json.loads(res.read())


def _get(endpoint: str) -> dict:
    with urllib.request.urlopen(f"{SD_URL}{endpoint}", timeout=10) as res:
        return json.loads(res.read())


SD_BAT = r"C:\StableDiffusion\webui-user.bat"


def is_available() -> bool:
    """SDが起動しているか確認"""
    try:
        urllib.request.urlopen(f"{SD_URL}/sdapi/v1/sd-models", timeout=5)
        return True
    except Exception:
        return False


def auto_start(log=print, wait_sec: int = 180) -> bool:
    """SD Forge が未起動なら自動起動して ready になるまで待つ"""
    if is_available():
        return True

    import os, subprocess, time
    if not os.path.exists(SD_BAT):
        log(f"  SD Forge bat が見つかりません: {SD_BAT}")
        return False

    log("  SD Forge を自動起動中... (初回は数分かかります)")
    subprocess.Popen(
        ["cmd", "/c", SD_BAT],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=str(Path(SD_BAT).parent),
    )

    for i in range(wait_sec // 5):
        time.sleep(5)
        if is_available():
            log(f"  SD Forge 起動完了 ({(i+1)*5}秒)")
            return True
        if i % 6 == 5:
            log(f"  SD Forge 起動待ち... ({(i+1)*5}/{wait_sec}秒)")

    log(f"  SD Forge が {wait_sec}秒以内に起動しませんでした")
    return False


# ── モデル情報の取得 ──────────────────────────────────────────────
def _get_model_type() -> str:
    """現在ロード中のモデルタイプを返す: 'xl' / 'pony' / 'sd15'
    'pony' = score_9タグが必要なモデル（Pony / Illustrious / NoobAI系）
    """
    try:
        opts = _get("/sdapi/v1/options")
        model_name = opts.get("sd_model_checkpoint", "").lower()
        # score_9タグが必要なモデル群
        if any(k in model_name for k in ["pony", "noob", "illustrious", "pdxl", "wai"]):
            return "pony"
        if any(k in model_name for k in ["xl", "sdxl"]):
            return "xl"
        return "sd15"
    except Exception:
        return "pony"  # IllustriousXLがデフォルトなのでpony想定


def _quality_positive(base_positive: str, model_type: str) -> str:
    """モデルに合わせた品質タグをポジティブプロンプト先頭に付加"""
    if model_type == "pony":
        return f"{SCORE_TAGS}, {QUALITY_PREFIX}, {base_positive}"
    else:
        return f"{QUALITY_PREFIX}, {base_positive}"


# ── ADetailer 検出 ────────────────────────────────────────────────
def _check_adetailer() -> bool:
    """ADetailer 拡張機能が使えるか確認"""
    global _adetailer_available
    if _adetailer_available is not None:
        return _adetailer_available
    try:
        scripts = _get("/sdapi/v1/scripts")
        names = [s.lower() for s in scripts.get("txt2img", [])]
        _adetailer_available = any("adetailer" in n for n in names)
    except Exception:
        _adetailer_available = False
    return _adetailer_available


def _adetailer_args(face: bool = True, hand: bool = False) -> dict:
    """ADetailer の alwayson_scripts 設定を返す"""
    args = []
    if face:
        args.append({
            "ad_model":              "face_yolov8n.pt",
            "ad_prompt":             "beautiful detailed face, perfect eyes",
            "ad_negative_prompt":    "bad face, ugly, deformed",
            "ad_confidence":         0.3,
            "ad_dilate_erode":       4,
            "ad_steps":              28,
            "ad_cfg_scale":          7,
            "ad_denoising_strength": 0.3,
            "ad_inpaint_only_masked": True,
            "ad_inpaint_only_masked_padding": 32,
        })
    if hand:
        args.append({
            "ad_model":              "hand_yolov8n.pt",
            "ad_prompt":             "beautiful detailed hands, perfect fingers",
            "ad_negative_prompt":    "bad hands, bad fingers, extra fingers",
            "ad_confidence":         0.3,
            "ad_denoising_strength": 0.4,
        })
    return {"ADetailer": {"args": args}} if args else {}


# ── 画像生成コア ──────────────────────────────────────────────────
def txt2img(positive: str, negative: str = "", width: int = 832,
            height: int = 1216, steps: int = 28, cfg: float = 7.0,
            seed: int = -1, hires: bool = False,
            use_adetailer: bool = True,
            apply_mosaic: bool = False,
            mosaic_block: int = 15,
            sampler_override: str = "") -> tuple[bytes, int]:
    """
    画像を生成してPNGバイト列と使用したシードを返す

    hires=True のとき Hires fix（1.5倍アップスケール）を有効化
    use_adetailer=True のとき ADetailer で顔・手を自動修正
    """
    neg = negative or COMMON_NEGATIVE

    payload = {
        "prompt":          positive,
        "negative_prompt": neg,
        "width":           width,
        "height":          height,
        "steps":           steps,
        "cfg_scale":       cfg,
        # デフォルト: DPM++ 2M Karras / NoobAI XLはEuler aで上書き可
        "sampler_name":    sampler_override if sampler_override else "DPM++ 2M Karras",
        "batch_size":      1,
        "seed":            seed,
    }

    # Hires fix: 低解像度で構図を決めてから高解像度に引き伸ばす
    # → 歪みなく解像感が上がる（生成時間は約2倍）
    if hires:
        payload.update({
            "enable_hr":             True,
            "hr_scale":              1.5,
            "hr_upscaler":           "R-ESRGAN 4x+ Anime6B",
            "hr_second_pass_steps":  20,
            "denoising_strength":    0.3,
            "hr_additional_modules": [],  # Forge必須パラメータ
        })

    # ADetailer: 顔・手を自動検出して再描画（最も効果的な品質向上）
    if use_adetailer and _check_adetailer():
        payload["alwayson_scripts"] = _adetailer_args(face=True, hand=False)

    result = _post("/sdapi/v1/txt2img", payload)
    png = base64.b64decode(result["images"][0])

    try:
        info = json.loads(result.get("info", "{}"))
        used_seed = info.get("seed", -1)
    except Exception:
        used_seed = -1

    # ── モザイク処理（DLSite販売用）────────────────────────────────
    if apply_mosaic:
        try:
            import tempfile
            from mosaic import apply_mosaic as _mosaic
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(png)
                tmp_path = tmp.name
            _mosaic(tmp_path, block_size=mosaic_block, log=lambda m: None)
            with open(tmp_path, "rb") as f:
                png = f.read()
            import os; os.unlink(tmp_path)
        except Exception:
            pass  # モザイク失敗しても元画像は返す

    return png, used_seed


def img2img(positive: str, negative: str, init_image_bytes: bytes,
            denoising_strength: float = 0.55,
            width: int = 832, height: int = 1216,
            steps: int = 28, cfg: float = 6.0,
            seed: int = -1,
            use_adetailer: bool = True,
            sampler_override: str = "Euler a") -> tuple[bytes, int]:
    """
    img2img: init_image_bytes を元画像として変形生成。
    denoising_strength が小さいほど元画像に近い（顔が維持される）。
    0.45〜0.60 が服だけ変えつつ顔を維持するのに適切。
    """
    import base64 as _b64
    init_b64 = _b64.b64encode(init_image_bytes).decode("utf-8")
    neg = negative or COMMON_NEGATIVE

    payload = {
        "init_images":        [init_b64],
        "prompt":             positive,
        "negative_prompt":    neg,
        "width":              width,
        "height":             height,
        "steps":              steps,
        "cfg_scale":          cfg,
        "sampler_name":       sampler_override if sampler_override else "Euler a",
        "denoising_strength": denoising_strength,
        "seed":               seed,
        "batch_size":         1,
    }

    if use_adetailer and _check_adetailer():
        payload["alwayson_scripts"] = _adetailer_args(face=True, hand=False)

    result = _post("/sdapi/v1/img2img", payload)
    png = base64.b64decode(result["images"][0])

    try:
        info = json.loads(result.get("info", "{}"))
        used_seed = info.get("seed", -1)
    except Exception:
        used_seed = -1

    return png, used_seed


# ── キャラクタースプライト生成 ────────────────────────────────────
EXPRESSIONS_JP = {
    "通常":   "neutral expression, calm face, serene",
    "笑顔":   "smile, happy expression, cheerful",
    "照れ":   "blushing, embarrassed, shy, red cheeks",
    "驚き":   "surprised, shocked expression, wide eyes",
    "悲しみ": "sad expression, teary eyes, downcast",
    "怒り":   "angry expression, frowning, fierce eyes",
}
EXPRESSIONS_EN = {
    "neutral":   "neutral expression, calm face, serene",
    "smile":     "smile, happy expression, cheerful",
    "blush":     "blushing, embarrassed, shy, red cheeks",
    "surprised": "surprised, shocked expression, wide eyes",
    "sad":       "sad expression, teary eyes, downcast",
    "angry":     "angry expression, frowning, fierce eyes",
}


def generate_sprites(heroine: dict, art_style: dict,
                     output_dir: Path, log=print,
                     hires: bool = True,
                     apply_mosaic: bool = False,
                     mosaic_block: int = 15) -> dict:
    """
    ヒロイン1人分の立ち絵を全表情生成して保存する
    最初の表情で生成したシードを記録し、以降は同じシードで
    キャラクターの顔・体型の一貫性を保つ。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    var   = heroine["var_name"]
    name  = heroine["name"]
    base  = art_style.get("sd_base_positive", "anime style, beautiful girl")
    neg   = art_style.get("sd_base_negative", COMMON_NEGATIVE)

    model_type  = _get_model_type()
    adet_avail  = _check_adetailer()
    log(f"  モデルタイプ: {model_type} / ADetailer: {'ON' if adet_avail else 'OFF'} / Hires: {'ON' if hires else 'OFF'}")

    expressions = (EXPRESSIONS_EN if art_style.get("mode") == "3d"
                   else EXPRESSIONS_JP)

    saved      = {}
    first_seed = -1

    for expr_name, expr_prompt in expressions.items():
        fname = output_dir / f"{var}_{expr_name}.png"
        if fname.exists():
            log(f"  [skip] {fname.name} (既存)")
            saved[expr_name] = str(fname)
            continue

        # 品質タグを先頭に付加してからキャラ情報を続ける
        base_prompt = (
            f"{base}, {heroine['appearance']}, "
            f"{expr_prompt}, "
            f"fair skin, light skin, soft skin, "
            f"solo, standing, full body, simple white background, "
            f"visual novel sprite, looking at viewer, "
            f"beautifully detailed hair, detailed eyes, perfect face"
        )
        positive = _quality_positive(base_prompt, model_type)

        log(f"  生成: {name} [{expr_name}] ...")
        try:
            png, used_seed = txt2img(
                positive, neg,
                width=SPRITE_W, height=SPRITE_H,
                steps=30, cfg=7.0,
                seed=first_seed,
                hires=hires,
                use_adetailer=True,
                apply_mosaic=apply_mosaic,
                mosaic_block=mosaic_block,
            )
            if first_seed == -1:
                first_seed = used_seed
                log(f"    シード固定: {first_seed}")
            fname.write_bytes(png)
            saved[expr_name] = str(fname)
            log(f"    -> {fname.name}" + (" [モザイク済]" if apply_mosaic else ""))
        except Exception as e:
            log(f"    !! 失敗 ({type(e).__name__}): {e}")

    return saved


# ── 背景生成 ──────────────────────────────────────────────────────
def generate_backgrounds(concept: dict, art_style: dict,
                         bg_list: list, output_dir: Path,
                         log=print, hires: bool = True,
                         apply_mosaic: bool = False,
                         mosaic_block: int = 15) -> dict:
    """背景画像を生成して保存する"""
    output_dir.mkdir(parents=True, exist_ok=True)
    bg_style   = art_style.get("bg_style", "anime background, detailed scenery")
    neg        = art_style.get("sd_base_negative", COMMON_NEGATIVE)
    model_type = _get_model_type()
    saved      = {}

    for bg in bg_list:
        bg_name = bg.get("name", "bg_unknown")
        fname   = output_dir / f"{bg_name}.png"
        if fname.exists():
            log(f"  [skip] {fname.name} (既存)")
            saved[bg_name] = str(fname)
            continue

        base_prompt = (
            f"{bg_style}, {bg.get('positive', concept['setting'])}, "
            f"no humans, beautiful scenery, cinematic lighting, "
            f"depth of field, atmospheric perspective"
        )
        positive = _quality_positive(base_prompt, model_type)
        bg_neg   = bg.get("negative", neg)

        log(f"  生成: {bg.get('label', bg_name)} ...")
        try:
            # 背景は Hires fix デフォルトON（解像感が重要）
            png, _ = txt2img(
                positive, bg_neg,
                width=BG_W, height=BG_H,
                steps=35, cfg=7.0,
                hires=hires,
                use_adetailer=False,  # 背景に顔検出は不要
                apply_mosaic=False,   # 背景にモザイク不要
                mosaic_block=mosaic_block,
            )
            fname.write_bytes(png)
            saved[bg_name] = str(fname)
            log(f"    -> {fname.name}")
        except Exception as e:
            log(f"    !! 失敗 ({type(e).__name__}): {e}")

    return saved
