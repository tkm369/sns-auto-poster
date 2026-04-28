"""
エロゲ自動生成パイプライン — Gradio WebUI  (R18専用)
起動方法: python app.py
ブラウザで http://localhost:7863 を開く
"""
import os
import sys
import threading
import queue
from pathlib import Path

# Windows CP932 対策
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import time
import re
import gradio as gr

from presets import (
    GENRES, SCENARIOS, HEROINE_ARCHETYPES, H_TAGS,
    LENGTHS, ART_STYLES,
    RPG_EROGE_SCENARIOS, RPG_H_INTENSITY,
)

ENV_FILE = Path(__file__).parent / ".env"

# ── ドロップダウン用ラベル ────────────────────────────────────────
def _choices(d: dict) -> list:
    return [
        f"[{k}] {v['name']} — {v.get('description', v.get('atmosphere', v.get('setting', '')))}"
        for k, v in d.items()
    ]

def _key(label: str) -> str:
    return label.split("]")[0].lstrip("[")

GENRE_CHOICES     = _choices(GENRES)
SCENARIO_CHOICES  = _choices(SCENARIOS)
ARCHETYPE_CHOICES = [f"[{k}] {v['name']} — {v['description']}" for k, v in HEROINE_ARCHETYPES.items()]
H_TAG_CHOICES     = [f"{v['name']}" for v in H_TAGS.values()]
LENGTH_CHOICES    = _choices(LENGTHS)
ART_CHOICES       = _choices(ART_STYLES)

RPG_GENRE_CHOICES = [
    "ダークファンタジー — 剣と魔法、魔王討伐とヒロイン救出",
    "異世界ハーレム — 転生主人公が複数の女性と関係を築く",
    "和風エロRPG — 江戸・遊郭・妖怪娘との絡み",
    "現代エロRPG — 学園・会社・日常を舞台にしたエロ",
    "魔法少女堕ち — 正義の戦士が快楽に堕ちる",
    "奴隷・調教RPG — 捕獲した女性キャラを調教するシステム",
]

GODOT_GENRE_CHOICES = [
    "野球拳スタイル・カードバトル脱衣ゲーム — カードで勝負してヒロインを脱がせる",
    "エロアクション — モンスター娘を倒すと絡みシーン",
    "脱衣アクション — 敵を倒すとヒロインの衣装が剥がれる",
    "捕獲・調教アクション — 女性敵を捕まえて調教",
    "サキュバス — 魔物娘に精気を吸われるサバイバル",
    "逆レ◯プアクション — ヒロインが敵に犯されながら進むダンジョン",
    "ハーレムアクション — 女の子を仲間にして進む探索系",
]

UNITY_GENRE_CHOICES = [
    "学園エロVN — 学校を舞台にしたヒロイン攻略",
    "異世界ハーレムVN — 異世界転生×複数ヒロイン",
    "会社・社内恋愛エロVN — 上司・部下・同僚との関係",
    "和風エロVN — 和の舞台×巫女・忍・花魁",
    "触手・モンスター娘VN — 異種族との交流と絡み",
    "調教・支配VN — 主人と奴隷、命令プレイ系",
]

UNITY_GAME_TYPE_CHOICES = [
    "エロVN（ビジュアルノベル）",
    "育成シミュレーション（パラメーター管理＋Hシーン）",
    "触り系インタラクション（クリックでリアクション）",
]

DLSITE_GENRES_R18 = [
    "ビジュアルノベル・ADV（R18）",
    "RPG（R18）",
    "アクション（R18）",
    "シミュレーション・育成（R18）",
    "催眠・洗脳もの",
    "調教・支配もの",
    "NTR・寝取られ",
    "ハーレム",
    "百合・GL",
    "異種族・モンスター娘",
    "孕ませ",
    "野外露出・命令プレイ",
]

# ── APIキー読み込み・保存 ─────────────────────────────────────────
def _load_api_key() -> str:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key and key != "ここにキーを貼り付け":
                    return key
    return os.environ.get("GEMINI_API_KEY", "")

def save_api_key(key: str) -> str:
    key = key.strip()
    if not key:
        return "⚠️ キーが空です"
    lines = []
    replaced = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                lines.append(f"GEMINI_API_KEY={key}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.append(f"GEMINI_API_KEY={key}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "✅ .env に保存しました"

# ── キャンセル・一時停止フラグ ─────────────────────────────────────
_cancel_event = threading.Event()
_pause_event  = threading.Event()

def cancel_run():
    """中止：キャンセルフラグをセット＆一時停止解除（ワーカーがキャンセルに気付けるよう）"""
    _cancel_event.set()
    _pause_event.clear()
    return gr.update(value="⏸️ 一時停止"), "⏹️ 中止しました"

def cancel_run_gen():
    """生成タブ用中止: ログ・進捗・pause・出力の4コンポーネントをクリア（エラー表示を消す）"""
    _cancel_event.set()
    _pause_event.clear()
    return "⏹️ 中止しました\n", "⏹️ 中止", gr.update(value="⏸️ 一時停止"), ""

def toggle_pause():
    """一時停止 ↔ 再開 トグル"""
    if _pause_event.is_set():
        _pause_event.clear()
        return gr.update(value="⏸️ 一時停止")
    else:
        _pause_event.set()
        return gr.update(value="▶️ 再開")

# ── RPG ボリュームプリセット ─────────────────────────────────────
_RPG_PRESETS = {
    "小（~1時間）":    dict(town=2, dungeon=2, floors=1, chapters=1, quests=0,  enemy=8),
    "中（~3時間）":    dict(town=3, dungeon=3, floors=2, chapters=3, quests=5,  enemy=15),
    "大（~6時間以上）": dict(town=6, dungeon=6, floors=3, chapters=6, quests=15, enemy=30),
}

def apply_rpg_preset(preset_label):
    p = _RPG_PRESETS.get(preset_label, _RPG_PRESETS["中（~3時間）"])
    return p["town"], p["dungeon"], p["floors"], p["chapters"], p["quests"], p["enemy"]


def get_quick_rpg_tips(genre, eroge_scenario, gemini_key):
    """RPGジャンル×Hシーン設定のDLSite売れ筋アドバイスを素早く生成"""
    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()
    if not api_key:
        return "❌ APIキーを入力してください"

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""DLSiteでエロRPGを販売したい。以下の設定を見て、売れるためのアドバイスを教えてください。

ジャンル: {genre}
Hシーンの発生: {eroge_scenario}

以下の形式で答えてください（簡潔に、実用的に）:

## このジャンルで売れる要素 TOP5
（箇条書き）

## DLSiteで付けるべき人気タグ
（タグを羅列、10個程度）

## 差別化ポイント
（他作品と差をつけるには）

## 注意点
（やりがちなNG・失敗パターン）

## 価格帯の目安
（DLSiteでの推奨価格）"""

    try:
        result = model.generate_content(prompt)
        return result.text
    except Exception as e:
        return f"❌ エラー: {e}"

# ── タイミング付きキュー読み出しヘルパー ─────────────────────────
# RPG: "■ Step X/Y: name"  /  Godot: "▶ [X/Y] name"  /  VN: "▶ Step X/Y name"
_STEP_PAT = re.compile(r'(?:■ Step|▶ \[|▶ Step)\s*(\d+)[/／](\d+)[\]:]?\s*(.*)')

def _fmt_time(secs: int) -> str:
    m, s = divmod(max(0, secs), 60)
    return f"{m:02d}:{s:02d}"

def _drain_queue_with_status(q, t):
    """
    キューからメッセージを読み出しながら、
    ( ログ本文, ステータス行, pause_btnリセット, "" ) の4タプルを yield する。

    ステータス行:  ⏱ 経過 MM:SS  |  ■ Step X/Y: name  |  予想残り MM:SS  [|  ⏸️ 一時停止中]
    """
    start_ts   = time.time()
    step_cur   = [0]
    step_total = [0]
    step_name  = ["開始中"]
    log_lines  = []
    first      = [True]     # 最初のyieldでpause_btnをリセット

    def _status():
        elapsed  = int(time.time() - start_ts)
        parts    = [f"⏱ 経過 {_fmt_time(elapsed)}"]
        n, tot   = step_cur[0], step_total[0]
        if tot > 0:
            parts.append(f"■ Step {n}/{tot}: {step_name[0]}")
            # ETA は「完了済みステップ数」が1つ以上になってから計算
            # （Step1実行中は完了ステップ=0なので計算不能）
            completed = n - 1
            if completed >= 1:
                per_step  = (time.time() - start_ts) / completed
                remaining = int(per_step * (tot - completed))
                parts.append(f"予想残り {_fmt_time(remaining)}")
            else:
                parts.append("予想残り 計算中...")
        if _pause_event.is_set():
            parts.append("⏸️ 一時停止中")
        return "  |  ".join(parts)

    def _emit():
        log_text = "".join(log_lines)
        pb_update = gr.update(value="⏸️ 一時停止") if first[0] else gr.update()
        first[0] = False
        return log_text, _status(), pb_update, ""

    while True:
        try:
            msg = q.get(timeout=0.4)
        except queue.Empty:
            if not t.is_alive():
                break
            yield _emit()
            continue
        if msg is None:
            break
        m = _STEP_PAT.search(msg)
        if m:
            step_cur[0]   = int(m.group(1))
            step_total[0] = int(m.group(2))
            step_name[0]  = m.group(3).strip() or step_name[0]
        log_lines.append(msg + "\n")
        yield _emit()

# ── ビジュアルノベル パイプライン ─────────────────────────────────
def run_vn(genre_label, scenario_label, archetype_label, h_tags_selected,
           length_label, art_label, use_voice, use_mosaic, gemini_key,
           model_mode="hybrid", local_url="http://localhost:1234/v1"):
    global _cancel_event
    _cancel_event = threading.Event()
    _pause_event.clear()

    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()

    if model_mode != "local" and not api_key:
        yield "❌ Gemini API キーが未入力です。（フルローカルモードなら不要）", "", gr.update(value="⏸️ 一時停止"), ""
        return

    h_tag_keys = [k for k, v in H_TAGS.items() if v["name"] in (h_tags_selected or [])]

    settings = {
        "genre_key":         _key(genre_label),
        "format_key":        _key(scenario_label),
        "length_key":        _key(length_label),
        "art_key":           _key(art_label),
        "adult":             True,
        "use_voice":         use_voice,
        "apply_mosaic":      bool(use_mosaic),
        "gemini_key":        api_key,
        "heroine_archetype": _key(archetype_label) if archetype_label else "1",
        "h_tags":            h_tag_keys,
        "model_mode":        {"Gemini のみ": "gemini",
                              "ハイブリッド（HシーンはQwen3.5）": "hybrid",
                              "フルローカル（Qwen3.5のみ・APIキー不要）": "local"}.get(model_mode, "gemini"),
        "local_url":         local_url.strip() or "http://localhost:1234/v1",
    }

    q = queue.Queue()
    result_holder = [None]
    error_holder  = [None]

    def _worker():
        try:
            from pipeline import run_pipeline
            result_holder[0] = run_pipeline(settings,
                                            log=lambda m: q.put(m),
                                            cancel_event=_cancel_event,
                                            pause_event=_pause_event)
        except Exception as e:
            error_holder[0] = e
        finally:
            q.put(None)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    log_text = status = ""
    for log_text, status, pb, _ in _drain_queue_with_status(q, t):
        yield log_text, status, pb, ""

    if _cancel_event.is_set():
        yield log_text + "\n⏹️ キャンセルされました。\n", status, gr.update(value="⏸️ 一時停止"), ""
        return
    if error_holder[0]:
        yield log_text + f"\n❌ エラー: {error_holder[0]}\n", status, gr.update(value="⏸️ 一時停止"), ""
        return

    path = result_holder[0]
    if path:
        yield (log_text + f"\n✅ 完成！\n出力先: {path}\nRen'Py SDK で開いて遊べます。",
               "✅ 生成完了", gr.update(value="⏸️ 一時停止"), str(path))
    else:
        yield log_text, status, gr.update(value="⏸️ 一時停止"), ""

# ── RPGツクールMZ パイプライン ────────────────────────────────────
def run_rpg(rpg_genre, rpg_eroge_scenario, rpg_h_intensity,
            rpg_party_size, rpg_town_count, rpg_dungeon_count,
            rpg_enemy_count, rpg_difficulty, rpg_gender,
            rpg_floors, rpg_chapters, rpg_quests,
            rpg_use_sd, gemini_key):
    global _cancel_event
    _cancel_event = threading.Event()
    _pause_event.clear()

    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()
    if not api_key:
        yield "❌ Gemini API キーが未入力です。", "", gr.update(value="⏸️ 一時停止"), ""
        return

    settings = {
        "adult":              True,
        "eroge_scenario":     rpg_eroge_scenario,
        "h_intensity":        rpg_h_intensity,
        "party_size":         int(rpg_party_size),
        "town_count":         int(rpg_town_count),
        "dungeon_count":      int(rpg_dungeon_count),
        "enemy_count":        int(rpg_enemy_count),
        "difficulty":         rpg_difficulty,
        "protagonist_gender": rpg_gender.split("（")[0],
        "floors_per_dungeon": int(rpg_floors),
        "chapter_count":      int(rpg_chapters),
        "side_quest_count":   int(rpg_quests),
        "atmosphere":         "エロRPG",
        "focus":              "バトル重視",
    }

    q = queue.Queue()
    result_holder = [None]
    error_holder  = [None]

    def _worker():
        try:
            from rpgmaker_mz_writer import run_full_pipeline
            result_holder[0] = run_full_pipeline(
                genre=rpg_genre,
                api_key=api_key,
                log=lambda m: q.put(m),
                cancel_event=_cancel_event,
                pause_event=_pause_event,
                settings=settings,
                use_sd=bool(rpg_use_sd),
            )
        except Exception as e:
            error_holder[0] = e
        finally:
            q.put(None)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    log_text = status = ""
    for log_text, status, pb, _ in _drain_queue_with_status(q, t):
        yield log_text, status, pb, ""

    if _cancel_event.is_set():
        yield log_text + "\n⏹️ キャンセルされました。\n", status, gr.update(value="⏸️ 一時停止"), ""
        return
    if error_holder[0]:
        yield log_text + f"\n❌ エラー: {error_holder[0]}\n", status, gr.update(value="⏸️ 一時停止"), ""
        return

    path = result_holder[0]
    if path:
        yield (log_text + f"\n✅ 完成！\n出力先: {path}\nRPGツクールMZで開いて遊べます。",
               "✅ 生成完了", gr.update(value="⏸️ 一時停止"), str(path))
    else:
        yield log_text, status, gr.update(value="⏸️ 一時停止"), ""

# ── Godot 2Dアクション パイプライン ───────────────────────────────
def run_godot(godot_genre, godot_use_sd, gemini_key):
    global _cancel_event
    _cancel_event = threading.Event()
    _pause_event.clear()

    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()
    if not api_key:
        yield "❌ Gemini API キーが未入力です。", "", gr.update(value="⏸️ 一時停止"), ""
        return

    q = queue.Queue()
    result_holder = [None]
    error_holder  = [None]

    def _worker():
        try:
            from godot_2d_writer import run_full_pipeline
            result_holder[0] = run_full_pipeline(
                genre=godot_genre,
                api_key=api_key,
                log=lambda m: q.put(m),
                cancel_event=_cancel_event,
                pause_event=_pause_event,
                use_sd=bool(godot_use_sd),
            )
        except Exception as e:
            error_holder[0] = e
        finally:
            q.put(None)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    log_text = status = ""
    for log_text, status, pb, _ in _drain_queue_with_status(q, t):
        yield log_text, status, pb, ""

    if _cancel_event.is_set():
        yield log_text + "\n⏹️ キャンセルされました。\n", status, gr.update(value="⏸️ 一時停止"), ""
        return
    if error_holder[0]:
        yield log_text + f"\n❌ エラー: {error_holder[0]}\n", status, gr.update(value="⏸️ 一時停止"), ""
        return

    path = result_holder[0]
    if path:
        yield (log_text + f"\n✅ 完成！\n出力先: {path}\nGodot 4 でプロジェクトを開いて遊べます。",
               "✅ 生成完了", gr.update(value="⏸️ 一時停止"), str(path))
    else:
        yield log_text, status, gr.update(value="⏸️ 一時停止"), ""

# ── Unity パイプライン ────────────────────────────────────────────
def run_unity(unity_genre, unity_game_type, gemini_key):
    global _cancel_event
    _cancel_event = threading.Event()
    _pause_event.clear()

    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()
    if not api_key:
        yield "❌ Gemini API キーが未入力です。", "", gr.update(value="⏸️ 一時停止"), ""
        return

    q = queue.Queue()
    result_holder = [None]
    error_holder  = [None]

    def _worker():
        try:
            from unity_writer import run_full_pipeline
            result_holder[0] = run_full_pipeline(
                genre=unity_genre,
                api_key=api_key,
                game_type=unity_game_type,
                log=lambda m: q.put(m),
                cancel_event=_cancel_event,
                pause_event=_pause_event,
            )
        except Exception as e:
            error_holder[0] = e
        finally:
            q.put(None)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    log_text = status = ""
    for log_text, status, pb, _ in _drain_queue_with_status(q, t):
        yield log_text, status, pb, ""

    if _cancel_event.is_set():
        yield log_text + "\n⏹️ キャンセルされました。\n", status, gr.update(value="⏸️ 一時停止"), ""
        return
    if error_holder[0]:
        yield log_text + f"\n❌ エラー: {error_holder[0]}\n", status, gr.update(value="⏸️ 一時停止"), ""
        return

    path = result_holder[0]
    if path:
        yield (log_text + f"\n✅ 完成！\n出力先: {path}\nUnity Hubで開いて遊べます。",
               "✅ 生成完了", gr.update(value="⏸️ 一時停止"), str(path))
    else:
        yield log_text, status, gr.update(value="⏸️ 一時停止"), ""


# ── DLSite市場分析パイプライン ────────────────────────────────────
def run_dlsite_analysis(game_type, genre, target_income_str, gemini_key):
    global _cancel_event
    _cancel_event = threading.Event()

    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()
    if not api_key:
        yield "❌ Gemini API キーが未入力です。", ""
        return

    try:
        target_income = int(str(target_income_str).replace(",", "").replace("円", "").strip())
    except (ValueError, TypeError):
        target_income = 1_000_000

    q = queue.Queue()
    result_holder = [None]
    error_holder  = [None]

    def _worker():
        try:
            from dlsite_advisor import run_market_analysis
            result_holder[0] = run_market_analysis(
                game_type=game_type,
                genre=genre,
                adult=True,   # 常にR18分析
                target_income=target_income,
                api_key=api_key,
                log=lambda m: q.put(m),
            )
        except Exception as e:
            error_holder[0] = e
        finally:
            q.put(None)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    log_text = ""
    for log_text, _s, _pb, _ in _drain_queue_with_status(q, t):
        yield log_text, ""

    if error_holder[0]:
        yield log_text + f"\n❌ エラー: {error_holder[0]}\n", ""
        return

    report = result_holder[0] or ""
    yield log_text + "\n✅ 分析完了！", report

# ── AIプロデュース相談 ────────────────────────────────────────────

# 相談セッションの設定を保持するグローバル辞書
_consult_session = {"game_type": "", "settings_summary": "", "history": []}

def consult_start(game_type, genre, scenario, archetype, h_tags,
                  length, art, rpg_genre, rpg_eroge, rpg_hint,
                  rpg_party, rpg_town, rpg_dungeon, rpg_enemy, rpg_diff, rpg_gender,
                  godot_genre, gemini_key):
    """相談開始ボタン — 現在の設定を読み取ってAIに最初のメッセージを生成させる"""
    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()
    if not api_key:
        return [], "❌ APIキーを設定してください"

    from concept_consultant import start_consultation, build_settings_summary

    # 設定サマリー作成
    if game_type == "ビジュアルノベル（Ren'Py）":
        settings = {
            "genre": genre, "scenario": scenario, "archetype": archetype,
            "h_tags": h_tags or [], "length": length, "art_style": art,
        }
        summary = build_settings_summary("ビジュアルノベル", settings)
        gtype = "ビジュアルノベル"
    elif game_type == "RPGツクールMZ（エロRPG）":
        settings = {
            "genre": rpg_genre, "eroge_scenario": rpg_eroge, "h_intensity": rpg_hint,
            "party_size": rpg_party, "town_count": rpg_town, "dungeon_count": rpg_dungeon,
            "enemy_count": rpg_enemy, "difficulty": rpg_diff,
        }
        summary = build_settings_summary("RPGツクールMZ", settings)
        gtype = "RPGツクールMZ"
    else:
        settings = {"genre": godot_genre}
        summary = build_settings_summary("Godotアクション", settings)
        gtype = "Godotアクション"

    _consult_session["game_type"] = gtype
    _consult_session["settings_summary"] = summary
    _consult_session["history"] = []
    _consult_session["api_key"] = api_key

    try:
        first_msg = start_consultation(gtype, summary, api_key)
    except Exception as e:
        first_msg = f"（エラー: {e}）"

    # Gradio 6.x はタプル形式 [[user, ai], ...]
    chatbot_history = [[None, first_msg]]
    _consult_session["history"] = [("assistant", first_msg)]
    return chatbot_history, ""


def consult_chat(user_message, chatbot_history):
    """ユーザーメッセージに対してAIが返答"""
    if not user_message.strip():
        return chatbot_history, ""

    api_key = _consult_session.get("api_key") or _load_api_key()
    if not api_key:
        return chatbot_history, ""

    from concept_consultant import continue_consultation

    history = _consult_session.get("history", [])
    gtype   = _consult_session.get("game_type", "")
    summary = _consult_session.get("settings_summary", "")

    try:
        ai_reply = continue_consultation(user_message, history, gtype, summary, api_key)
    except Exception as e:
        ai_reply = f"（エラー: {e}）"

    # 履歴更新
    history.append(("user", user_message))
    history.append(("assistant", ai_reply))
    _consult_session["history"] = history

    # Gradio 6.x タプル形式
    new_history = chatbot_history + [[user_message, ai_reply]]
    return new_history, ""


def consult_generate(game_type, genre, scenario, archetype, h_tags,
                     length, art, use_voice, use_mosaic,
                     rpg_genre, rpg_eroge, rpg_hint, rpg_party, rpg_town,
                     rpg_dungeon, rpg_enemy, rpg_diff, rpg_gender,
                     godot_genre, gemini_key):
    """相談内容を踏まえてゲームを生成する"""
    global _cancel_event
    _cancel_event = threading.Event()
    _pause_event.clear()

    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()
    if not api_key:
        yield "❌ APIキーを設定してください", "", gr.update(value="⏸️ 一時停止"), ""
        return

    history = _consult_session.get("history", [])
    gtype   = _consult_session.get("game_type", "") or game_type

    extra_context = {}
    if history:
        try:
            from concept_consultant import extract_final_concept
            extra_context = extract_final_concept(
                history, gtype,
                _consult_session.get("settings_summary", ""),
                api_key
            )
        except Exception:
            pass

    q = queue.Queue()
    result_holder = [None]
    error_holder  = [None]

    if gtype == "ビジュアルノベル" or game_type == "ビジュアルノベル（Ren'Py）":
        h_tag_keys = [k for k, v in H_TAGS.items() if v["name"] in (h_tags or [])]
        settings = {
            "genre_key":         _key(genre),
            "format_key":        _key(scenario),
            "length_key":        _key(length),
            "art_key":           _key(art),
            "adult":             True,
            "use_voice":         use_voice,
            "apply_mosaic":      bool(use_mosaic),
            "gemini_key":        api_key,
            "heroine_archetype": _key(archetype) if archetype else "1",
            "h_tags":            h_tag_keys,
            "extra_context":     extra_context,
        }
        def _worker():
            try:
                from pipeline import run_pipeline
                result_holder[0] = run_pipeline(settings,
                                                log=lambda m: q.put(m),
                                                cancel_event=_cancel_event,
                                                pause_event=_pause_event)
            except Exception as e:
                error_holder[0] = e
            finally:
                q.put(None)
        finish_msg = "Ren'Py SDK で開いて遊べます。"

    elif gtype == "RPGツクールMZ" or game_type == "RPGツクールMZ（エロRPG）":
        settings = {
            "adult": True,
            "eroge_scenario": rpg_eroge,
            "h_intensity":    rpg_hint,
            "party_size":     int(rpg_party),
            "town_count":     int(rpg_town),
            "dungeon_count":  int(rpg_dungeon),
            "enemy_count":    int(rpg_enemy),
            "difficulty":     rpg_diff,
            "protagonist_gender": rpg_gender.split("（")[0],
            "atmosphere":     "エロRPG",
            "focus":          "バトル重視",
            "extra_context":  extra_context,
        }
        def _worker():
            try:
                from rpgmaker_mz_writer import run_full_pipeline
                result_holder[0] = run_full_pipeline(
                    genre=rpg_genre, api_key=api_key,
                    log=lambda m: q.put(m),
                    cancel_event=_cancel_event,
                    pause_event=_pause_event,
                    settings=settings)
            except Exception as e:
                error_holder[0] = e
            finally:
                q.put(None)
        finish_msg = "RPGツクールMZで開いて遊べます。"

    else:
        settings = {"extra_context": extra_context}
        def _worker():
            try:
                from godot_2d_writer import run_full_pipeline
                result_holder[0] = run_full_pipeline(
                    genre=godot_genre, api_key=api_key,
                    log=lambda m: q.put(m),
                    cancel_event=_cancel_event,
                    pause_event=_pause_event)
            except Exception as e:
                error_holder[0] = e
            finally:
                q.put(None)
        finish_msg = "Godot 4 で開いて遊べます。"

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    log_text = status = ""
    for log_text, status, pb, _ in _drain_queue_with_status(q, t):
        yield log_text, status, pb, ""

    if _cancel_event.is_set():
        yield log_text + "\n⏹️ キャンセルされました。\n", status, gr.update(value="⏸️ 一時停止"), ""
        return
    if error_holder[0]:
        yield log_text + f"\n❌ エラー: {error_holder[0]}\n", status, gr.update(value="⏸️ 一時停止"), ""
        return

    path = result_holder[0]
    if path:
        yield (log_text + f"\n✅ 完成！\n出力先: {path}\n{finish_msg}",
               "✅ 生成完了", gr.update(value="⏸️ 一時停止"), str(path))
    else:
        yield log_text, status, gr.update(value="⏸️ 一時停止"), ""


# ── プロジェクトエディタ ──────────────────────────────────────────
# セッション中のプロジェクト情報を保持
_editor_project: dict = {}

def editor_load(project_path: str):
    """プロジェクトを読み込んでファイル選択肢を返す"""
    from project_editor import detect_project, files_to_choices
    info = detect_project(project_path)
    _editor_project.clear()
    _editor_project.update(info)

    if info["type"] == "unknown":
        msg = "❌ プロジェクトが見つかりません。フォルダパスを確認してください。"
        return gr.update(choices=[], value=None), msg, ""

    choices = files_to_choices(info["files"])
    title_line = f"✅ [{info['type'].upper()}] {info['title']}  |  {len(choices)}ファイル"
    return gr.update(choices=choices, value=choices[0] if choices else None), title_line, ""


def editor_select_file(choice: str):
    """ファイルを選択してエディタに内容を表示"""
    if not choice or not _editor_project:
        return ""
    from project_editor import choice_to_rel_path, load_file
    rel = choice_to_rel_path(choice, _editor_project.get("files", {}))
    if not rel:
        return ""
    return load_file(str(_editor_project["path"]), rel)


def editor_save(choice: str, content: str):
    """エディタの内容を保存"""
    if not choice or not _editor_project:
        return "❌ プロジェクトが読み込まれていません"
    from project_editor import choice_to_rel_path, save_file
    rel = choice_to_rel_path(choice, _editor_project.get("files", {}))
    if not rel:
        return "❌ ファイルが選択されていません"
    return save_file(str(_editor_project["path"]), rel, content)


def editor_ai_edit(choice: str, content: str, instruction: str, gemini_key: str):
    """AIに修正させてエディタに反映"""
    if not instruction.strip():
        yield content, "⚠️ 修正指示を入力してください"
        return
    if not choice or not _editor_project:
        yield content, "❌ プロジェクトが読み込まれていません"
        return

    api_key = gemini_key.strip() if gemini_key else ""
    if not api_key:
        api_key = _load_api_key()
    if not api_key:
        yield content, "❌ APIキーを設定してください"
        return

    from project_editor import choice_to_rel_path, ai_edit
    rel = choice_to_rel_path(choice, _editor_project.get("files", {}))
    if not rel:
        yield content, "❌ ファイルが選択されていません"
        return

    yield content, "⏳ AI修正中..."
    log_msgs = []
    new_content = ai_edit(
        str(_editor_project["path"]), rel, content, instruction, api_key,
        log=lambda m: log_msgs.append(m)
    )
    if new_content.startswith("❌"):
        yield content, new_content
    else:
        yield new_content, "✅ AI修正完了 — 確認して「💾 保存」を押してください"


def editor_regen_image(choice: str, new_prompt: str,
                       apply_mosaic: bool, gemini_key: str):
    """画像をSD Forgeで再生成"""
    if not choice or not _editor_project:
        return "❌ プロジェクトが読み込まれていません"
    if not new_prompt.strip():
        return "⚠️ 新しいプロンプトを入力してください"

    from project_editor import choice_to_rel_path, regenerate_image
    rel = choice_to_rel_path(choice, _editor_project.get("files", {}))
    if not rel:
        return "❌ ファイルが選択されていません"

    image_path = str(_editor_project["path"] / rel)
    msgs = []
    result = regenerate_image(image_path, new_prompt,
                              apply_mosaic=apply_mosaic,
                              log=lambda m: msgs.append(m))
    return result


# ── Gradio UI ────────────────────────────────────────────────────
CSS = """
/* 中止・キャンセル時のエラーバッジを非表示 */
span.error { display: none !important; }

#log_box textarea, #rpg_log_box textarea, #godot_log_box textarea, #unity_log_box textarea, #dlsite_log_box textarea, #consult_log_box textarea {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    background: #1e1e2e;
    color: #cdd6f4;
}
.dark #log_box textarea, .dark #rpg_log_box textarea,
.dark #godot_log_box textarea, .dark #dlsite_log_box textarea { background: #1e1e2e; }
#rpg_progress textarea, #vn_progress textarea, #godot_progress textarea, #unity_progress textarea, #consult_progress textarea {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    background: #2a2d3e;
    color: #a6e3a1;
    border: 1px solid #45475a;
}
#editor_content textarea {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    background: #1e1e2e;
    color: #cdd6f4;
}
"""

_initial_key = _load_api_key()

with gr.Blocks(title="エロゲ自動生成", css=CSS) as demo:

    gr.Markdown("# 🔞 エロゲ自動生成パイプライン")

    # ── APIキー設定 ────────────────────────────────────────────────
    with gr.Accordion("🔑 APIキー設定", open=not bool(_initial_key)):
        with gr.Row():
            gemini_key_tb = gr.Textbox(
                label="Gemini APIキー",
                placeholder="AIza... （aistudio.google.com で無料取得）",
                value="●●●●●●●" if _initial_key else "",
                type="password",
                lines=1,
                scale=4,
            )
            save_key_btn = gr.Button("保存", size="sm", scale=1)
        save_status = gr.Textbox(label="", interactive=False, lines=1, placeholder="保存ステータス")

    # ── タブ ──────────────────────────────────────────────────────
    with gr.Tabs():

        # ===== タブ1: RPGエロゲ =====
        with gr.Tab("⚔️ RPGエロゲ"):
            with gr.Row():
                rpg_gen_btn   = gr.Button("🚀 生成開始", variant="primary", scale=4)
                rpg_pause_btn = gr.Button("⏸️ 一時停止", scale=1)
                rpg_stop_btn  = gr.Button("⏹️ 中止", scale=1)
            rpg_progress_tb = gr.Textbox(label="", interactive=False, lines=1,
                                         placeholder="⏱ 生成状況がここに表示されます",
                                         elem_id="rpg_progress")

            with gr.Row():
                with gr.Column(scale=1):
                    rpg_genre_dd = gr.Dropdown(
                        RPG_GENRE_CHOICES,
                        value=RPG_GENRE_CHOICES[0],
                        label="ジャンル",
                        allow_custom_value=True,
                    )
                    rpg_eroge_dd = gr.Dropdown(
                        [f"{v['name']} — {v['description']}" for v in RPG_EROGE_SCENARIOS.values()],
                        value=f"{list(RPG_EROGE_SCENARIOS.values())[0]['name']} — {list(RPG_EROGE_SCENARIOS.values())[0]['description']}",
                        label="Hシーンの発生タイミング",
                    )
                    rpg_hint_dd = gr.Dropdown(
                        [f"{v['name']}" for v in RPG_H_INTENSITY.values()],
                        value=list(RPG_H_INTENSITY.values())[1]["name"],
                        label="エロの濃さ",
                    )

                    with gr.Accordion("📊 売れ筋アドバイス", open=False):
                        rpg_tips_btn = gr.Button("DLSite市場を分析してもらう", variant="secondary")
                        rpg_tips_box = gr.Markdown("ボタンを押すとAIがアドバイスします")

                    with gr.Accordion("⚙️ 詳細設定", open=False):
                        rpg_preset_dd = gr.Dropdown(
                            ["小（~1時間）", "中（~3時間）", "大（~6時間以上）"],
                            value="中（~3時間）",
                            label="ボリューム",
                        )
                        with gr.Row():
                            rpg_party_sl  = gr.Slider(1, 4, value=4, step=1, label="パーティ人数")
                            rpg_gender_dd = gr.Dropdown(
                                ["male（男主人公）", "female（女主人公）", "any（自由）"],
                                value="male（男主人公）",
                                label="主人公の性別",
                            )
                        with gr.Row():
                            rpg_town_sl    = gr.Slider(1, 10, value=3, step=1, label="町の数")
                            rpg_dungeon_sl = gr.Slider(1, 10, value=3, step=1, label="ダンジョン数")
                        with gr.Row():
                            rpg_floors_sl   = gr.Slider(1, 5, value=1, step=1, label="ダンジョン階数")
                            rpg_chapters_sl = gr.Slider(1, 6, value=1, step=1, label="章数")
                        rpg_quests_sl = gr.Slider(0, 20, value=0, step=1, label="サブクエスト数")
                        with gr.Row():
                            rpg_enemy_sl = gr.Slider(5, 50, value=10, step=1, label="敵の種類")
                            rpg_diff_dd  = gr.Dropdown(
                                ["簡単", "普通", "難しい"],
                                value="普通",
                                label="難易度",
                            )
                        rpg_use_sd_cb = gr.Checkbox(
                            label="🖼️ SD Forge で画像生成（タイトル・戦闘背景・CG）",
                            value=False,
                            info="SD Forge が起動済みの場合に有効。IllustriousXL等のモデルが必要"
                        )

                with gr.Column(scale=2):
                    rpg_log_box = gr.Textbox(label="生成ログ", lines=20, max_lines=40,
                                             interactive=False, elem_id="rpg_log_box",
                                             placeholder="ログがここに流れます...")
                    rpg_output_tb = gr.Textbox(label="出力先フォルダ", interactive=False,
                                               placeholder="完成するとパスが表示されます")

        # ===== タブ2: ビジュアルノベル =====
        with gr.Tab("📖 ビジュアルノベル"):
            with gr.Row():
                vn_gen_btn   = gr.Button("🚀 生成開始", variant="primary", scale=4)
                vn_pause_btn = gr.Button("⏸️ 一時停止", scale=1)
                vn_stop_btn  = gr.Button("⏹️ 中止", scale=1)
            vn_progress_tb = gr.Textbox(label="", interactive=False, lines=1,
                                        placeholder="⏱ 生成状況がここに表示されます",
                                        elem_id="vn_progress")

            with gr.Row():
                with gr.Column(scale=1):
                    genre_dd     = gr.Dropdown(GENRE_CHOICES,    value=GENRE_CHOICES[0],    label="ジャンル", allow_custom_value=True)
                    scenario_dd  = gr.Dropdown(SCENARIO_CHOICES, value=SCENARIO_CHOICES[0], label="シナリオ形式", allow_custom_value=True)
                    archetype_dd = gr.Dropdown(ARCHETYPE_CHOICES, value=ARCHETYPE_CHOICES[0], label="ヒロインの属性", allow_custom_value=True)
                    h_tags_cb    = gr.CheckboxGroup(H_TAG_CHOICES, value=["バニラ（甘め）"], label="Hシーンのタグ（複数可）")

                    with gr.Accordion("⚙️ 詳細設定", open=False):
                        length_dd     = gr.Dropdown(LENGTH_CHOICES, value=LENGTH_CHOICES[1], label="長さ・Hシーン数")
                        art_dd        = gr.Dropdown(ART_CHOICES, value=ART_CHOICES[0], label="アートスタイル")
                        voice_cb      = gr.Checkbox(label="🎤 ボイス生成（Qwen3 TTS）", value=False)
                        mosaic_cb     = gr.Checkbox(label="🔲 モザイク処理（DLSite販売用）", value=True,
                                                    info="ONにすると性器・アナルを自動検出してピクセルモザイクをかけます")
                        model_mode_dd = gr.Dropdown(
                            ["Gemini のみ", "ハイブリッド（HシーンはQwen3.5）", "フルローカル（Qwen3.5のみ・APIキー不要）"],
                            value="ハイブリッド（HシーンはQwen3.5）",
                            label="テキスト生成モード",
                        )
                        local_url_tb = gr.Textbox(value="http://localhost:1234/v1", label="LM Studio URL", lines=1)

                with gr.Column(scale=2):
                    log_box      = gr.Textbox(label="生成ログ", lines=20, max_lines=40,
                                              interactive=False, elem_id="log_box",
                                              placeholder="ログがここに流れます...")
                    vn_output_tb = gr.Textbox(label="出力先フォルダ", interactive=False,
                                              placeholder="完成するとパスが表示されます")

        # ===== タブ3: Godotアクション =====
        with gr.Tab("🎮 アクション"):
            with gr.Row():
                godot_gen_btn   = gr.Button("🚀 生成開始", variant="primary", scale=4)
                godot_pause_btn = gr.Button("⏸️ 一時停止", scale=1)
                godot_stop_btn  = gr.Button("⏹️ 中止", scale=1)
            godot_progress_tb = gr.Textbox(label="", interactive=False, lines=1,
                                           placeholder="⏱ 生成状況がここに表示されます",
                                           elem_id="godot_progress")

            with gr.Row():
                with gr.Column(scale=1):
                    godot_genre_dd = gr.Dropdown(
                        GODOT_GENRE_CHOICES,
                        value=GODOT_GENRE_CHOICES[0],
                        label="ゲームジャンル",
                        allow_custom_value=True,
                    )
                    godot_use_sd_cb = gr.Checkbox(
                        label="🖼️ SD Forge で背景画像生成",
                        value=False,
                        info="SD Forge が起動済みの場合に有効"
                    )

                with gr.Column(scale=2):
                    godot_log_box   = gr.Textbox(label="生成ログ", lines=20, max_lines=40,
                                                 interactive=False, elem_id="godot_log_box",
                                                 placeholder="ログがここに流れます...")
                    godot_output_tb = gr.Textbox(label="出力先フォルダ", interactive=False,
                                                 placeholder="完成するとパスが表示されます")

        # ===== タブ4: Unity =====
        with gr.Tab("🎮 Unity"):
            with gr.Row():
                unity_gen_btn   = gr.Button("🚀 生成開始", variant="primary", scale=4)
                unity_pause_btn = gr.Button("⏸️ 一時停止", scale=1)
                unity_stop_btn  = gr.Button("⏹️ 中止", scale=1)
            unity_progress_tb = gr.Textbox(label="", interactive=False, lines=1,
                                           placeholder="⏱ 生成状況がここに表示されます",
                                           elem_id="unity_progress")

            with gr.Row():
                with gr.Column(scale=1):
                    unity_genre_dd = gr.Dropdown(
                        UNITY_GENRE_CHOICES,
                        value=UNITY_GENRE_CHOICES[0],
                        label="ジャンル",
                        allow_custom_value=True,
                    )
                    unity_game_type_dd = gr.Dropdown(
                        UNITY_GAME_TYPE_CHOICES,
                        value=UNITY_GAME_TYPE_CHOICES[0],
                        label="ゲームタイプ",
                    )
                    gr.Markdown("""
**必要なもの（すべて無料）**
- [Unity Hub](https://unity.com/ja/download) をインストール
- Unity 2022.3 LTS をインストール
- 生成後: `Tools > タイトル > 完全セットアップ` を実行
""")

                with gr.Column(scale=2):
                    unity_log_box   = gr.Textbox(label="生成ログ", lines=20, max_lines=40,
                                                 interactive=False, elem_id="unity_log_box",
                                                 placeholder="ログがここに流れます...")
                    unity_output_tb = gr.Textbox(label="出力先フォルダ", interactive=False,
                                                 placeholder="完成するとパスが表示されます")

        # ===== タブ5: AI相談 ＆ 販売戦略 =====
        with gr.Tab("💬 相談・戦略"):
            with gr.Row():
                consult_game_type_dd = gr.Dropdown(
                    ["ビジュアルノベル（Ren'Py）", "RPGツクールMZ（エロRPG）", "Godotアクション"],
                    value="ビジュアルノベル（Ren'Py）",
                    label="ゲームタイプ",
                    scale=3,
                )
                consult_start_btn = gr.Button("相談開始", variant="secondary", scale=1)

            consult_chatbot = gr.Chatbot(label="AIプロデューサー", height=400)

            with gr.Row():
                consult_input    = gr.Textbox(
                    placeholder="返答・質問・路線変更など...",
                    label="",
                    lines=2,
                    scale=5,
                )
                consult_send_btn = gr.Button("送信", variant="primary", scale=1)

            consult_status = gr.Textbox(label="", interactive=False, lines=1, visible=False)

            with gr.Row():
                consult_gen_btn   = gr.Button("🚀 この内容で生成開始", variant="primary", scale=4)
                consult_pause_btn = gr.Button("⏸️ 一時停止", scale=1)
                consult_stop_btn  = gr.Button("⏹️ 中止", scale=1)
            consult_progress_tb = gr.Textbox(label="", interactive=False, lines=1,
                                             placeholder="⏱ 生成状況がここに表示されます",
                                             elem_id="consult_progress")

            consult_log_box   = gr.Textbox(label="生成ログ", lines=10, max_lines=30,
                                           interactive=False, elem_id="consult_log_box",
                                           placeholder="生成の進捗がここに表示されます...")
            consult_output_tb = gr.Textbox(label="出力先フォルダ", interactive=False,
                                           placeholder="完成するとパスが表示されます")

            with gr.Accordion("💰 DLSite R18販売戦略レポート", open=False):
                with gr.Row():
                    dlsite_gen_btn  = gr.Button("📊 市場分析レポートを生成", variant="secondary", scale=4)
                    dlsite_stop_btn = gr.Button("⏹️ 中止", scale=1)
                with gr.Row():
                    with gr.Column(scale=1):
                        dlsite_type_dd = gr.Dropdown(
                            ["ビジュアルノベル（R18）", "エロRPG（RPGツクール）",
                             "エロアクション（Godot）", "シミュレーション育成（R18）"],
                            value="ビジュアルノベル（R18）",
                            label="ゲームタイプ",
                        )
                        dlsite_genre_dd = gr.Dropdown(
                            DLSITE_GENRES_R18,
                            value=DLSITE_GENRES_R18[0],
                            label="カテゴリ・ジャンル",
                            allow_custom_value=True,
                        )
                        dlsite_income_tb = gr.Textbox(
                            label="目標年収（円）",
                            value="1000000",
                        )
                    with gr.Column(scale=2):
                        dlsite_log_box = gr.Textbox(label="", lines=4, max_lines=8,
                                                    interactive=False, elem_id="dlsite_log_box",
                                                    placeholder="分析の進捗...")
                        dlsite_report_box = gr.Textbox(
                            label="レポート",
                            lines=20,
                            max_lines=60,
                            interactive=False,
                            placeholder="レポートがここに表示されます",
                        )

        # ===== タブ5: プロジェクト修正・編集 =====
        with gr.Tab("🔧 修正・編集"):
            gr.Markdown("生成済みのゲームプロジェクトを開いて、任意の部分をAIで修正・再生成できます。")

            with gr.Row():
                editor_path_tb = gr.Textbox(
                    label="プロジェクトフォルダ",
                    placeholder=r"例: C:\Users\inoue\Desktop\ai-project\output\MyGame",
                    lines=1, scale=4,
                )
                editor_load_btn = gr.Button("📂 読み込む", variant="secondary", scale=1)

            editor_info_tb = gr.Textbox(label="", interactive=False, lines=1,
                                        placeholder="プロジェクト情報がここに表示されます")

            with gr.Row():
                editor_file_dd = gr.Dropdown(
                    choices=[], label="編集するファイル", scale=3,
                    allow_custom_value=False,
                )
                editor_reload_btn = gr.Button("🔄 再読み込み", scale=1)

            editor_content_tb = gr.Textbox(
                label="内容",
                lines=25, max_lines=60,
                interactive=True,
                placeholder="ファイルを選択するとここに内容が表示されます\n直接編集も可能です",
                elem_id="editor_content",
            )

            with gr.Row():
                editor_save_btn   = gr.Button("💾 保存", variant="primary", scale=1)
                editor_save_msg   = gr.Textbox(label="", interactive=False, lines=1, scale=3)

            gr.Markdown("---")
            gr.Markdown("### 🤖 AIで修正")

            editor_instruction_tb = gr.Textbox(
                label="修正指示",
                placeholder="例: 主人公の名前を「剣士タケル」に変えて\n例: Hシーンをもっと激しい描写にして\n例: ボスの名前と設定を和風に変えて\n例: 台詞をもっと口語的にして",
                lines=3,
            )

            with gr.Row():
                editor_ai_btn    = gr.Button("✨ AIで修正する", variant="primary", scale=3)
                editor_ai_status = gr.Textbox(label="", interactive=False, lines=1, scale=2)

            gr.Markdown("---")
            gr.Markdown("### 🖼️ 画像を再生成（SD Forge）")

            editor_img_prompt_tb = gr.Textbox(
                label="新しいプロンプト（英語推奨）",
                placeholder="例: beautiful anime girl, red hair, maid outfit, blushing",
                lines=2,
            )
            with gr.Row():
                editor_mosaic_cb  = gr.Checkbox(label="🔲 モザイク処理", value=True, scale=1)
                editor_regen_btn  = gr.Button("🖼️ この画像を再生成", variant="secondary", scale=2)
                editor_regen_msg  = gr.Textbox(label="", interactive=False, lines=1, scale=2)

    # ── イベントバインド ───────────────────────────────────────────
    save_key_btn.click(fn=save_api_key, inputs=[gemini_key_tb], outputs=[save_status])

    rpg_preset_dd.change(
        fn=apply_rpg_preset,
        inputs=[rpg_preset_dd],
        outputs=[rpg_town_sl, rpg_dungeon_sl, rpg_floors_sl, rpg_chapters_sl, rpg_quests_sl, rpg_enemy_sl],
    )

    # ── 生成イベント（戻り値を変数に保持 → cancelに使う） ────────────
    rpg_event = rpg_gen_btn.click(
        fn=run_rpg,
        inputs=[
            rpg_genre_dd, rpg_eroge_dd, rpg_hint_dd,
            rpg_party_sl, rpg_town_sl, rpg_dungeon_sl,
            rpg_enemy_sl, rpg_diff_dd, rpg_gender_dd,
            rpg_floors_sl, rpg_chapters_sl, rpg_quests_sl,
            rpg_use_sd_cb, gemini_key_tb,
        ],
        outputs=[rpg_log_box, rpg_progress_tb, rpg_pause_btn, rpg_output_tb],
    )

    vn_event = vn_gen_btn.click(
        fn=run_vn,
        inputs=[genre_dd, scenario_dd, archetype_dd, h_tags_cb,
                length_dd, art_dd, voice_cb, mosaic_cb, gemini_key_tb,
                model_mode_dd, local_url_tb],
        outputs=[log_box, vn_progress_tb, vn_pause_btn, vn_output_tb],
    )

    godot_event = godot_gen_btn.click(
        fn=run_godot,
        inputs=[godot_genre_dd, godot_use_sd_cb, gemini_key_tb],
        outputs=[godot_log_box, godot_progress_tb, godot_pause_btn, godot_output_tb],
    )

    unity_event = unity_gen_btn.click(
        fn=run_unity,
        inputs=[unity_genre_dd, unity_game_type_dd, gemini_key_tb],
        outputs=[unity_log_box, unity_progress_tb, unity_pause_btn, unity_output_tb],
    )

    # ── 中止ボタン（cancels= で Gradio ジェネレーターも強制終了） ────
    rpg_stop_btn.click(
        fn=cancel_run_gen,
        outputs=[rpg_log_box, rpg_progress_tb, rpg_pause_btn, rpg_output_tb],
        cancels=[rpg_event],
    )
    vn_stop_btn.click(
        fn=cancel_run_gen,
        outputs=[log_box, vn_progress_tb, vn_pause_btn, vn_output_tb],
        cancels=[vn_event],
    )
    godot_stop_btn.click(
        fn=cancel_run_gen,
        outputs=[godot_log_box, godot_progress_tb, godot_pause_btn, godot_output_tb],
        cancels=[godot_event],
    )

    unity_stop_btn.click(
        fn=cancel_run_gen,
        outputs=[unity_log_box, unity_progress_tb, unity_pause_btn, unity_output_tb],
        cancels=[unity_event],
    )

    # ── 一時停止ボタン ─────────────────────────────────────────────
    rpg_pause_btn.click(fn=toggle_pause,   outputs=[rpg_pause_btn])
    vn_pause_btn.click(fn=toggle_pause,    outputs=[vn_pause_btn])
    godot_pause_btn.click(fn=toggle_pause, outputs=[godot_pause_btn])
    unity_pause_btn.click(fn=toggle_pause, outputs=[unity_pause_btn])

    # ── 売れ筋アドバイス ───────────────────────────────────────────
    rpg_tips_btn.click(
        fn=get_quick_rpg_tips,
        inputs=[rpg_genre_dd, rpg_eroge_dd, gemini_key_tb],
        outputs=[rpg_tips_box],
    )

    # ── DLSite販売戦略 ─────────────────────────────────────────────
    dlsite_event = dlsite_gen_btn.click(
        fn=run_dlsite_analysis,
        inputs=[dlsite_type_dd, dlsite_genre_dd, dlsite_income_tb, gemini_key_tb],
        outputs=[dlsite_log_box, dlsite_report_box],
    )
    dlsite_stop_btn.click(fn=cancel_run, outputs=[save_status, save_status], cancels=[dlsite_event])

    # ── 相談タブのバインド ─────────────────────────────────────────
    _all_settings_inputs = [
        consult_game_type_dd,
        genre_dd, scenario_dd, archetype_dd, h_tags_cb, length_dd, art_dd,
        rpg_genre_dd, rpg_eroge_dd, rpg_hint_dd,
        rpg_party_sl, rpg_town_sl, rpg_dungeon_sl,
        rpg_enemy_sl, rpg_diff_dd, rpg_gender_dd,
        godot_genre_dd,
        gemini_key_tb,
    ]

    consult_start_btn.click(
        fn=consult_start,
        inputs=_all_settings_inputs,
        outputs=[consult_chatbot, consult_status],
    )

    consult_send_btn.click(
        fn=consult_chat,
        inputs=[consult_input, consult_chatbot],
        outputs=[consult_chatbot, consult_input],
    )
    consult_input.submit(
        fn=consult_chat,
        inputs=[consult_input, consult_chatbot],
        outputs=[consult_chatbot, consult_input],
    )

    _gen_inputs = [
        consult_game_type_dd,
        genre_dd, scenario_dd, archetype_dd, h_tags_cb, length_dd, art_dd, voice_cb, mosaic_cb,
        rpg_genre_dd, rpg_eroge_dd, rpg_hint_dd,
        rpg_party_sl, rpg_town_sl, rpg_dungeon_sl,
        rpg_enemy_sl, rpg_diff_dd, rpg_gender_dd,
        godot_genre_dd,
        gemini_key_tb,
    ]
    consult_event = consult_gen_btn.click(
        fn=consult_generate,
        inputs=_gen_inputs,
        outputs=[consult_log_box, consult_progress_tb, consult_pause_btn, consult_output_tb],
    )
    consult_stop_btn.click(
        fn=cancel_run_gen,
        outputs=[consult_log_box, consult_progress_tb, consult_pause_btn, consult_output_tb],
        cancels=[consult_event],
    )
    consult_pause_btn.click(fn=toggle_pause, outputs=[consult_pause_btn])

    # ── プロジェクトエディタ ────────────────────────────────────────
    editor_load_btn.click(
        fn=editor_load,
        inputs=[editor_path_tb],
        outputs=[editor_file_dd, editor_info_tb, editor_content_tb],
    )
    editor_path_tb.submit(
        fn=editor_load,
        inputs=[editor_path_tb],
        outputs=[editor_file_dd, editor_info_tb, editor_content_tb],
    )
    editor_file_dd.change(
        fn=editor_select_file,
        inputs=[editor_file_dd],
        outputs=[editor_content_tb],
    )
    editor_reload_btn.click(
        fn=editor_select_file,
        inputs=[editor_file_dd],
        outputs=[editor_content_tb],
    )
    editor_save_btn.click(
        fn=editor_save,
        inputs=[editor_file_dd, editor_content_tb],
        outputs=[editor_save_msg],
    )
    editor_ai_btn.click(
        fn=editor_ai_edit,
        inputs=[editor_file_dd, editor_content_tb, editor_instruction_tb, gemini_key_tb],
        outputs=[editor_content_tb, editor_ai_status],
    )
    editor_regen_btn.click(
        fn=editor_regen_image,
        inputs=[editor_file_dd, editor_img_prompt_tb, editor_mosaic_cb, gemini_key_tb],
        outputs=[editor_regen_msg],
    )

    # 生成完了後にエディタパスを自動入力
    rpg_output_tb.change(
        fn=lambda p: gr.update(value=p) if p else gr.update(),
        inputs=[rpg_output_tb], outputs=[editor_path_tb],
    )
    vn_output_tb.change(
        fn=lambda p: gr.update(value=p) if p else gr.update(),
        inputs=[vn_output_tb], outputs=[editor_path_tb],
    )
    godot_output_tb.change(
        fn=lambda p: gr.update(value=p) if p else gr.update(),
        inputs=[godot_output_tb], outputs=[editor_path_tb],
    )
    unity_output_tb.change(
        fn=lambda p: gr.update(value=p) if p else gr.update(),
        inputs=[unity_output_tb], outputs=[editor_path_tb],
    )


if __name__ == "__main__":
    print("=" * 50)
    print("  エロゲ自動生成パイプライン WebUI (R18)")
    print("  http://localhost:7863")
    print("=" * 50)
    demo.launch(
        server_name="0.0.0.0",
        server_port=7863,
        share=False,
        inbrowser=True,
        theme=gr.themes.Soft(),
    )
