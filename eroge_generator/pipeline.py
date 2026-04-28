"""
エロゲ全自動生成パイプライン オーケストレーター

呼び出し方:
    from pipeline import run_pipeline
    run_pipeline(settings, log_callback=print)

settings dict:
    genre_key, format_key, length_key, art_key, adult, use_voice
"""
import sys
import os
import threading
from pathlib import Path

# qwen3_tts パスを通す
QWEN_TTS_DIR = Path(__file__).parent.parent / "qwen3_tts"
if str(QWEN_TTS_DIR) not in sys.path:
    sys.path.insert(0, str(QWEN_TTS_DIR))

from presets import GENRES, SCENARIOS, LENGTHS, ART_STYLES, HEROINE_ARCHETYPES, H_TAGS
from generator import (
    generate_concept, generate_outline,
    generate_char_defs, generate_all_scenes, generate_assets
)
from renpy_writer import write_project, OUTPUT_DIR
from sd_client import generate_sprites, generate_backgrounds, is_available as sd_available, auto_start as sd_auto_start


def run_pipeline(settings: dict, log=print,
                 cancel_event: threading.Event = None,
                 pause_event: threading.Event = None) -> Path:
    """
    全工程を実行してプロジェクトフォルダのPathを返す

    settings keys:
        genre_key   : "1"〜"6"
        format_key  : "1"〜"6"
        length_key  : "1"〜"3"
        art_key     : "1"〜"2"
        adult       : bool
        use_voice   : bool
        gemini_key  : str (APIキー)
    """
    import google.generativeai as genai

    def _check_cancel():
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("ユーザーによりキャンセルされました")
        import time as _t
        while pause_event and pause_event.is_set():
            _t.sleep(0.3)
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("ユーザーによりキャンセルされました")

    # ── 設定解決 ──────────────────────────────────────────
    genre      = GENRES[settings["genre_key"]]
    fmt        = SCENARIOS[settings["format_key"]]   # SCENARIOS に変更
    num_scenes = LENGTHS[settings["length_key"]]["scenes"]
    h_scenes   = LENGTHS[settings["length_key"]].get("h_scenes", num_scenes // 2)
    art_style  = ART_STYLES[settings["art_key"]]
    adult      = True   # 常にR18
    use_voice  = settings.get("use_voice", False)

    # ヒロイン属性・Hタグ
    archetype_key = settings.get("heroine_archetype", "1")
    archetype = HEROINE_ARCHETYPES.get(archetype_key, HEROINE_ARCHETYPES["1"])
    h_tag_keys = settings.get("h_tags", [])
    h_tag_names = [H_TAGS[k]["name"] for k in h_tag_keys if k in H_TAGS]

    # モデルモード設定
    model_mode = settings.get("model_mode", "gemini")  # gemini / hybrid / local
    local_url  = settings.get("local_url", "http://localhost:1234/v1")

    # Gemini 初期化（ローカルのみモード以外）
    api_key = settings.get("gemini_key") or os.environ.get("GEMINI_API_KEY")
    if model_mode != "local" and not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません。")
    model = None
    if model_mode != "local" and api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

    # ローカルモデルクライアント設定
    local_client = None
    if model_mode in ("hybrid", "local"):
        from local_model import is_available as local_available
        if local_available(local_url):
            local_client = {"base_url": local_url}
            log(f"  ローカルモデル接続確認: OK ({local_url})")
        else:
            log(f"  ⚠ LM Studio に接続できません ({local_url})")
            log("    → LM Studio を起動してモデルをロードしてください")
            if model_mode == "local":
                raise ConnectionError(
                    "LM Studio が起動していないかモデルが未ロードです。"
                    "LM Studio を起動してモデルを選択してから再実行してください。"
                )
            log("    → ハイブリッドモードですが、Gemini のみで続行します")

    # フルローカルモード：Gemini の代わりにローカルモデルを使う
    if model_mode == "local" and local_client:
        from local_model import generate_local, parse_json_local
        # ローカルモデルをGeminiのwrapperに見せかけるadapter
        class LocalModelAdapter:
            def __init__(self, base_url):
                self._base_url = base_url
            def generate_content(self, prompt, stream=False):
                raise NotImplementedError("Use generate_local directly")
        model = LocalModelAdapter(local_url)

    # AIプロデューサーとの相談内容
    extra_context = settings.get("extra_context", {})

    log("━━━ エロゲ生成開始（R18） ━━━")
    log(f"ジャンル: {genre['name']} / シナリオ: {fmt['name']}")
    log(f"ヒロイン属性: {archetype['name']}")
    log(f"Hタグ: {', '.join(h_tag_names) if h_tag_names else 'バニラ'}")
    log(f"シーン数: {num_scenes}（うちHシーン: {h_scenes}） / スタイル: {art_style['name']}")
    log(f"ボイス: {'ON' if use_voice else 'OFF'}")
    mode_label = {"gemini": "Gemini のみ", "hybrid": "ハイブリッド（HシーンはQwen3.5）", "local": "フルローカル（Qwen3.5）"}
    log(f"AIモード: {mode_label.get(model_mode, model_mode)}")
    log("")

    # ── Step 1: コンセプト生成 ─────────────────────────────
    _check_cancel()
    log("▶ [1/6] コンセプト生成（タイトル・キャラ・設定）")
    # フルローカルモード時はすべてローカルクライアント経由
    lc = local_client if model_mode in ("hybrid", "local") else None

    concept = generate_concept(model, genre, fmt, adult,
                               archetype=archetype, h_tags=h_tag_names,
                               extra_context=extra_context, log=log,
                               local_client=lc if model_mode == "local" else None)
    log(f"  タイトル: {concept['title']}")
    log(f"  ヒロイン: {', '.join(h['name'] for h in concept['heroines'])}")

    project_dir = OUTPUT_DIR / concept["title"]

    # ── Step 2: あらすじ / キャラ定義 / 画像素材 を並列生成 ──────────
    # 3つともコンセプトのみに依存 → 同時に走らせる
    _check_cancel()
    log("\n▶ [2/6] あらすじ・キャラ定義・画像素材を並列生成")

    if model_mode == "local" or lc:
        # ローカルモデルは逐次
        outline = generate_outline(model, concept, genre, fmt, num_scenes, adult,
                                   h_scenes=h_scenes, h_tags=h_tag_names, log=log,
                                   local_client=lc)
        char_defs = generate_char_defs(model, concept, log=log, local_client=lc)
        assets    = generate_assets(model, concept, outline, art_style, adult,
                                    log=log, local_client=lc)
    else:
        import concurrent.futures as _cf
        with _cf.ThreadPoolExecutor(max_workers=3) as ex:
            f_outline = ex.submit(
                generate_outline, model, concept, genre, fmt, num_scenes, adult,
                h_scenes, h_tag_names, log, None)
            f_chars   = ex.submit(generate_char_defs, model, concept, log, None)
            f_assets  = ex.submit(
                generate_assets, model, concept, "", art_style, adult, log, None)
            outline   = f_outline.result(); log("  ✓ あらすじ完了")
            char_defs = f_chars.result();   log("  ✓ キャラ定義完了")
            assets    = f_assets.result();  log("  ✓ 画像素材完了")

    # ── Step 3: シーンスクリプト生成 ──────────────────────
    _check_cancel()
    log(f"\n▶ [3/6] シーンスクリプト生成（{num_scenes}シーン）")
    scenes = generate_all_scenes(model, concept, outline, char_defs,
                                 num_scenes, adult, log=log,
                                 cancel_event=cancel_event, h_tags=h_tag_names,
                                 local_client=lc)

    # Ren'Py プロジェクト出力（スクリプト + assets/）
    write_project(concept, char_defs, scenes, art_style, assets)
    log(f"  Ren'Py プロジェクト: {project_dir}")

    # ── Step 5: SD で画像を実際に生成 ─────────────────────
    _check_cancel()
    log("\n▶ [5/6] 画像生成（SD Forge）")
    sd_ok = sd_auto_start(log=log, wait_sec=300)
    if sd_ok:
        log("  SD Forge 起動中 → 画像を自動生成します")
        img_dir = project_dir / "game" / "images"

        # 立ち絵
        for heroine in concept["heroines"]:
            _check_cancel()
            log(f"  立ち絵: {heroine['name']}")
                generate_sprites(heroine, art_style,
                             img_dir / "characters", log=log,
                             apply_mosaic=settings.get("apply_mosaic", False),
                             mosaic_block=settings.get("mosaic_block", 15))

        # 背景
        bgs = assets.get("backgrounds", [])
        if bgs:
            _check_cancel()
            log(f"  背景: {len(bgs)}枚")
            generate_backgrounds(concept, art_style, bgs,
                                 img_dir / "backgrounds", log=log)
    else:
        log("  SD Forge の起動に失敗 → 画像生成をスキップ")

    # ── Step 6: ボイス生成 ─────────────────────────────────
    _check_cancel()
    if use_voice:
        log("\n▶ [6/6] ボイス生成（Qwen3 TTS）")
        try:
            from voice_generator import generate_voices
            generate_voices(project_dir, concept, log=log)
        except Exception as e:
            log(f"  !! ボイス生成エラー: {e}")
    else:
        log("\n▶ [6/6] ボイス生成: スキップ")

    # ── DLSite販売戦略レポート ────────────────────────────────
    _check_cancel()
    log("\n▶ [+] DLSite販売戦略レポート生成")
    try:
        from dlsite_advisor import generate_full_report
        genre_label = f"{genre['name']}（{genre['setting']}）"
        report_md = generate_full_report(
            model, concept,
            game_type="ビジュアルノベル（Ren'Py）",
            genre=genre_label,
            adult=adult,
            log=log,
            local_client=lc if model_mode == "local" else None,
        )
        report_path = project_dir / "DLSITE_STRATEGY.md"
        report_path.write_text(report_md, encoding="utf-8")
        log(f"  販売戦略レポート: {report_path}")
    except Exception as e:
        log(f"  !! 販売戦略レポート生成エラー（スキップ）: {e}")

    log("\n━━━ 完成！ ━━━")
    log(f"出力先: {project_dir}")
    log("Ren'Py SDK (https://www.renpy.org/) で開いて遊べます。")
    return project_dir
