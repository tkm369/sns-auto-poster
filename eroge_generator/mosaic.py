# -*- coding: utf-8 -*-
"""
mosaic.py — DLSite販売用 モザイク処理モジュール

NudeNet で性器・アナルを検出し、ピクセルモザイクをかける。
日本の法律（猥褻物頒布等の罪）およびDLSite規約に準拠。

対象ラベル（修正必須）:
  FEMALE_GENITALIA_EXPOSED  — 女性器
  MALE_GENITALIA_EXPOSED    — 男性器
  ANUS_EXPOSED              — 肛門
  MALE_GENITALIA_COVERED    — 覆われていても念のため（挿入シーン等）

非対象（日本法では不要）:
  FEMALE_BREAST_EXPOSED     — 乳首（日本では修正義務なし）
"""

from __future__ import annotations
from pathlib import Path
import io

# 修正必須カテゴリ
CENSOR_LABELS = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    # 挿入シーン等で覆われていない可能性が高い場合も念のため
    "MALE_GENITALIA_COVERED",
}

# モザイクの粗さ（大きいほど粗い）— DLSite基準の目安は10〜20px
MOSAIC_BLOCK_SIZE = 15

# NudeNet の信頼度スレッショルド
CONFIDENCE_THRESHOLD = 0.25

# 検出領域を少し広げる（見切れ防止）
EXPAND_RATIO = 0.15

_detector = None  # 遅延ロード

def _get_detector():
    global _detector
    if _detector is None:
        from nudenet import NudeDetector
        _detector = NudeDetector()
    return _detector


def _pixelate_region(img, x: int, y: int, w: int, h: int, block: int = MOSAIC_BLOCK_SIZE):
    """指定領域をピクセルモザイク処理"""
    from PIL import Image
    region = img.crop((x, y, x + w, y + h))
    small_w = max(1, w // block)
    small_h = max(1, h // block)
    small   = region.resize((small_w, small_h), Image.NEAREST)
    mosaic  = small.resize((w, h), Image.NEAREST)
    img.paste(mosaic, (x, y))


def apply_mosaic(image_path: str | Path, output_path: str | Path | None = None,
                 block_size: int = MOSAIC_BLOCK_SIZE,
                 log=print) -> Path:
    """
    画像ファイルにモザイク処理を施して保存する。

    Parameters
    ----------
    image_path  : 入力PNG/JPEGパス
    output_path : 出力先（None の場合は image_path を上書き）
    block_size  : ピクセルブロックサイズ（大きいほど粗い）
    log         : ログ関数

    Returns
    -------
    出力ファイルのPath
    """
    from PIL import Image

    image_path  = Path(image_path)
    output_path = Path(output_path) if output_path else image_path

    try:
        detector = _get_detector()
    except Exception as e:
        log(f"  [mosaic] NudeNet 初期化失敗: {e} — スキップ")
        return image_path

    try:
        detections = detector.detect(str(image_path))
    except Exception as e:
        log(f"  [mosaic] 検出失敗: {e} — スキップ")
        return image_path

    img  = Image.open(image_path).convert("RGBA")
    iw, ih = img.size
    applied = 0

    for det in detections:
        label = det.get("class", "")
        score = det.get("score", 0)
        if label not in CENSOR_LABELS:
            continue
        if score < CONFIDENCE_THRESHOLD:
            continue

        box = det.get("box", [])
        if len(box) < 4:
            continue

        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])

        # 領域を少し拡張（見切れ防止）
        ex = int((x2 - x1) * EXPAND_RATIO)
        ey = int((y2 - y1) * EXPAND_RATIO)
        x1 = max(0,  x1 - ex)
        y1 = max(0,  y1 - ey)
        x2 = min(iw, x2 + ex)
        y2 = min(ih, y2 + ey)
        w, h = x2 - x1, y2 - y1
        if w <= 0 or h <= 0:
            continue

        _pixelate_region(img, x1, y1, w, h, block_size)
        applied += 1
        log(f"  [mosaic] {label} ({score:.2f}) → ({x1},{y1})〜({x2},{y2}) ブロック{block_size}px")

    if applied == 0:
        log(f"  [mosaic] 対象なし（{image_path.name}）")
    else:
        log(f"  [mosaic] {applied}箇所にモザイク適用 → {output_path.name}")

    # RGBAをRGBに変換して保存（PNG透過対応）
    if output_path.suffix.lower() == ".png":
        img.save(str(output_path), "PNG")
    else:
        img.convert("RGB").save(str(output_path))

    return output_path


def apply_mosaic_to_dir(directory: str | Path, pattern: str = "*.png",
                        block_size: int = MOSAIC_BLOCK_SIZE,
                        log=print) -> int:
    """
    ディレクトリ内の画像ファイルすべてにモザイクをかける。
    Returns: 処理したファイル数
    """
    directory = Path(directory)
    files     = list(directory.glob(pattern))
    count     = 0
    for f in files:
        apply_mosaic(f, block_size=block_size, log=log)
        count += 1
    return count
