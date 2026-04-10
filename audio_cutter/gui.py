"""
gui.py
Audio Auto Cutter - GUI（シンプル版）
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.scrolledtext as st
import threading
import queue
import os
import sys

from core import detect_silence_cuts, analyze_speech_cuts, transcribe
from core import generate_jsx, save_srt, correct_segments

# ─── カラー ───────────────────────────────────────
BG         = "#F7F8FC"
ACCENT     = "#5C6BC0"
ACCENT2    = "#3949AB"
SUCCESS    = "#43A047"
SUCCESS2   = "#2E7D32"
WARN       = "#FB8C00"
ERROR      = "#E53935"
WHITE      = "#FFFFFF"
DARK       = "#1A1A2E"
GRAY       = "#888899"
LIGHT_GRAY = "#E4E6F0"
CARD_BG    = "#FFFFFF"

FONT_BIG   = ("Yu Gothic UI", 13)
FONT_MID   = ("Yu Gothic UI", 11)
FONT_SMALL = ("Yu Gothic UI", 9)
FONT_BOLD  = ("Yu Gothic UI", 12, "bold")

log_queue: queue.Queue = queue.Queue()


class QueueWriter:
    def __init__(self, q): self._q = q
    def write(self, text):
        if text.strip(): self._q.put(("log", text.rstrip()))
    def flush(self): pass


def merge_cuts(cuts):
    if not cuts: return []
    sc = sorted(cuts, key=lambda x: x["start"])
    merged = [sc[0].copy()]
    for c in sc[1:]:
        last = merged[-1]
        if c["start"] <= last["end"] + 0.05:
            last["end"] = max(last["end"], c["end"])
            if c["reason"] not in last["reason"]:
                last["reason"] += " + " + c["reason"]
        else:
            merged.append(c.copy())
    return merged


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audio Auto Cutter")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._running = False
        self._stop_flag = threading.Event()
        self._cuts = []
        self._build_ui()
        self._poll_queue()

    # ─── UI ───────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_file_area()
        self._build_basic_options()
        self._build_advanced_section()
        self._build_run_area()
        self._build_progress_area()
        self._build_log_section()
        tk.Frame(self, bg=BG, height=12).pack()

    # ── ヘッダー ──────────────────────────────────
    def _build_header(self):
        frm = tk.Frame(self, bg=ACCENT)
        frm.pack(fill="x")

        tk.Label(frm, text="✂  Audio Auto Cutter",
                 bg=ACCENT, fg=WHITE,
                 font=("Yu Gothic UI", 18, "bold"), pady=14
                 ).pack(side="left", padx=20)

        try:
            import torch
            if torch.cuda.is_available():
                badge = f"GPU: {torch.cuda.get_device_name(0)}"
                bc = "#1B5E20"
            else:
                badge, bc = "CPUモード", "#B71C1C"
        except ImportError:
            badge, bc = "CPUモード", "#B71C1C"

        tk.Label(frm, text=f" {badge} ", bg=bc, fg=WHITE,
                 font=FONT_SMALL, relief="flat", pady=4
                 ).pack(side="right", padx=16, pady=14)

    # ── ファイル選択 ───────────────────────────────
    def _build_file_area(self):
        card = self._card()

        tk.Label(card, text="① 動画ファイルを選んでください",
                 bg=CARD_BG, fg=DARK, font=FONT_BOLD
                 ).pack(anchor="w", padx=20, pady=(16, 6))

        row = tk.Frame(card, bg=CARD_BG)
        row.pack(fill="x", padx=20, pady=(0, 16))

        self.var_input = tk.StringVar()
        self._file_label = tk.Label(
            row,
            text="ファイルが選択されていません",
            bg=LIGHT_GRAY, fg=GRAY,
            font=FONT_MID, anchor="w",
            relief="flat", padx=12, pady=10, width=38
        )
        self._file_label.pack(side="left")

        tk.Button(
            row, text="ファイルを選択",
            command=self._browse_input,
            bg=ACCENT, fg=WHITE, font=FONT_MID,
            relief="flat", cursor="hand2",
            activebackground=ACCENT2, activeforeground=WHITE,
            padx=16, pady=8
        ).pack(side="left", padx=(10, 0))

    # ── 基本オプション ─────────────────────────────
    def _build_basic_options(self):
        card = self._card()

        tk.Label(card, text="② 何をカットしますか？",
                 bg=CARD_BG, fg=DARK, font=FONT_BOLD
                 ).pack(anchor="w", padx=20, pady=(16, 10))

        opts = tk.Frame(card, bg=CARD_BG)
        opts.pack(fill="x", padx=20, pady=(0, 4))

        # チェックボックス3つ
        self.var_fillers  = tk.BooleanVar(value=True)
        self.var_stammers = tk.BooleanVar(value=True)
        self.var_srt      = tk.BooleanVar(value=False)

        self._big_check(opts, "無音・間のカット",
                        "しゃべっていない無音部分を自動で詰めます", None, 0)
        self._big_check(opts, "「えーと」などのフィラーをカット",
                        "えーと・あのー・うーん など", self.var_fillers, 1)
        self._big_check(opts, "噛み・言い直しをカット",
                        "同じ言葉を繰り返した最初の部分を除去します", self.var_stammers, 2)

        # SRTセパレータ
        tk.Frame(card, bg=LIGHT_GRAY, height=1).pack(fill="x", padx=20, pady=(8, 0))

        srt_row = tk.Frame(card, bg=CARD_BG)
        srt_row.pack(fill="x", padx=20, pady=(8, 0))
        self._big_check_inline(
            srt_row,
            "字幕ファイル（SRT）も自動で作る",
            "文字起こし → AI校正 → SRT出力まで一括で行います",
            self.var_srt,
            command=self._on_srt_toggle
        )

        # SRT展開エリア
        self.srt_expand = tk.Frame(card, bg="#F0F2FF")
        self.srt_expand.pack(fill="x", padx=20, pady=(6, 0))
        self._build_srt_inner(self.srt_expand)
        self.srt_expand.pack_forget()

        tk.Frame(card, bg=CARD_BG, height=12).pack()

    def _big_check(self, parent, title, desc, var, row):
        frm = tk.Frame(parent, bg=CARD_BG)
        frm.grid(row=row, column=0, sticky="w", pady=4)

        if var is None:
            # 常にON（無音カットは固定）
            tk.Label(frm, text="✅", bg=CARD_BG, font=("Yu Gothic UI", 13)
                     ).pack(side="left", padx=(0, 8))
        else:
            cb = tk.Checkbutton(frm, variable=var, bg=CARD_BG,
                                 cursor="hand2", activebackground=CARD_BG)
            cb.pack(side="left", padx=(0, 4))

        right = tk.Frame(frm, bg=CARD_BG)
        right.pack(side="left")
        tk.Label(right, text=title, bg=CARD_BG, fg=DARK, font=FONT_MID,
                 anchor="w").pack(anchor="w")
        tk.Label(right, text=desc, bg=CARD_BG, fg=GRAY, font=FONT_SMALL,
                 anchor="w").pack(anchor="w")

    def _big_check_inline(self, parent, title, desc, var, command=None):
        frm = tk.Frame(parent, bg=CARD_BG)
        frm.pack(fill="x")
        cb = tk.Checkbutton(frm, variable=var, bg=CARD_BG,
                             cursor="hand2", activebackground=CARD_BG,
                             command=command)
        cb.pack(side="left", padx=(0, 4))
        right = tk.Frame(frm, bg=CARD_BG)
        right.pack(side="left")
        tk.Label(right, text=title, bg=CARD_BG, fg=DARK, font=FONT_MID
                 ).pack(anchor="w")
        tk.Label(right, text=desc, bg=CARD_BG, fg=GRAY, font=FONT_SMALL
                 ).pack(anchor="w")

    def _build_srt_inner(self, parent):
        # APIキーは埋め込み済みのため表示しない
        self.var_api_key = tk.StringVar(value="")

        # 校正ルール
        rules_header = tk.Frame(parent, bg="#F0F2FF")
        rules_header.pack(fill="x", padx=12, pady=(12, 4))

        tk.Label(rules_header, text="📝 校正ルール（AI への指示）",
                 bg="#F0F2FF", fg=DARK, font=FONT_MID
                 ).pack(side="left")

        tk.Button(rules_header, text="元に戻す",
                  command=self._reset_rules,
                  bg=LIGHT_GRAY, fg=DARK, font=FONT_SMALL,
                  relief="flat", cursor="hand2", padx=6
                  ).pack(side="right")

        tk.Button(rules_header, text="保存",
                  command=self._save_rules,
                  bg=SUCCESS, fg=WHITE, font=FONT_SMALL,
                  relief="flat", cursor="hand2", padx=8
                  ).pack(side="right", padx=(0, 6))

        self.rules_box = st.ScrolledText(
            parent, height=10, font=("Yu Gothic UI", 9),
            bg=WHITE, fg=DARK, relief="solid", bd=1, wrap="word"
        )
        self.rules_box.pack(fill="x", padx=12, pady=(0, 10))
        self.rules_box.insert("1.0", self._load_config().get(
            "correction_rules", self._default_rules()))

    # ── 詳細設定（折りたたみ） ─────────────────────
    def _build_advanced_section(self):
        toggle_frm = tk.Frame(self, bg=BG)
        toggle_frm.pack(fill="x", padx=20, pady=(6, 0))

        self.var_adv = tk.BooleanVar(value=False)
        tk.Checkbutton(
            toggle_frm,
            text="⚙  詳細設定（触らなくてもOKです）",
            variable=self.var_adv, bg=BG,
            font=FONT_SMALL, fg=GRAY, cursor="hand2",
            activebackground=BG,
            command=self._toggle_advanced
        ).pack(side="left")

        self.adv_frame = tk.Frame(self, bg=CARD_BG,
                                  highlightbackground=LIGHT_GRAY,
                                  highlightthickness=1)

        inner = tk.Frame(self.adv_frame, bg=CARD_BG)
        inner.pack(fill="x", padx=20, pady=12)

        # 余白
        self._adv_spin(inner, 0,
            label="カット後の間（秒）",
            hint="発話の前後に残す余白。0.1〜0.3が自然です",
            var_name="var_gap", default=0.15, from_=0.0, to=2.0, inc=0.05)

        # 閾値
        self._adv_spin(inner, 1,
            label="無音の感度",
            hint="数値が大きいほど積極的にカット（-45〜-35 が目安）",
            var_name="var_thresh", default=-40, from_=-70, to=-10, inc=1)

        # 最小無音
        self._adv_spin(inner, 2,
            label="カットする最小の無音（秒）",
            hint="これより短い無音は残します",
            var_name="var_min_sil", default=0.3, from_=0.05, to=5.0, inc=0.05)

        # フィラー最小
        self._adv_spin(inner, 3,
            label="フィラーの最小時間（秒）",
            hint="これより短い「えーと」は残します",
            var_name="var_filler_min", default=0.4, from_=0.1, to=3.0, inc=0.1)

        # モデル
        m_row = tk.Frame(inner, bg=CARD_BG)
        m_row.grid(row=4, column=0, columnspan=3, sticky="w", pady=6)
        tk.Label(m_row, text="文字起こし精度：",
                 bg=CARD_BG, fg=DARK, font=FONT_SMALL).pack(side="left")
        self.var_model = tk.StringVar(value="large-v3")
        ttk.Combobox(m_row, textvariable=self.var_model, width=12,
                     values=["tiny", "base", "small", "medium", "large", "large-v3"],
                     state="readonly", font=FONT_SMALL
                     ).pack(side="left", padx=(6, 12))
        tk.Label(m_row, text="large-v3 = 最高精度（推奨）  /  medium = やや速い",
                 bg=CARD_BG, fg=GRAY, font=FONT_SMALL).pack(side="left")

        # プレビューモード
        prev_row = tk.Frame(inner, bg=CARD_BG)
        prev_row.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.var_preview = tk.BooleanVar(value=False)
        tk.Checkbutton(
            prev_row,
            text="プレビューモード（実際にはカットせず、カット位置にマーカーだけ追加する）",
            variable=self.var_preview, bg=CARD_BG,
            font=FONT_SMALL, fg=WARN, cursor="hand2",
            activebackground=CARD_BG
        ).pack(side="left")

    def _adv_spin(self, parent, row, *, label, hint, var_name, default, from_, to, inc):
        tk.Label(parent, text=label + "：",
                 bg=CARD_BG, fg=DARK, font=FONT_SMALL
                 ).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        var = tk.DoubleVar(value=default)
        setattr(self, var_name, var)
        tk.Spinbox(parent, from_=from_, to=to, increment=inc,
                   textvariable=var, width=8,
                   font=FONT_SMALL, format="%.2f"
                   ).grid(row=row, column=1, sticky="w", padx=(0, 12), pady=3)
        tk.Label(parent, text=hint,
                 bg=CARD_BG, fg=GRAY, font=FONT_SMALL
                 ).grid(row=row, column=2, sticky="w", pady=3)

    # ── 実行ボタン ─────────────────────────────────
    def _build_run_area(self):
        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="x", padx=20, pady=14)

        self.btn_run = tk.Button(
            frm,
            text="▶  JSXを生成する",
            command=self._start,
            bg=SUCCESS, fg=WHITE,
            font=("Yu Gothic UI", 14, "bold"),
            relief="flat", cursor="hand2",
            activebackground=SUCCESS2, activeforeground=WHITE,
            padx=32, pady=12
        )
        self.btn_run.pack(side="left")

        self.btn_stop = tk.Button(
            frm, text="■  停止",
            command=self._stop,
            bg=LIGHT_GRAY, fg=DARK,
            font=FONT_MID,
            relief="flat", cursor="hand2",
            state="disabled", padx=16, pady=12
        )
        self.btn_stop.pack(side="left", padx=(10, 0))

        self.btn_folder = tk.Button(
            frm, text="📁  出力先を開く",
            command=self._open_folder,
            bg=LIGHT_GRAY, fg=DARK,
            font=FONT_MID, relief="flat", cursor="hand2",
            padx=16, pady=12
        )
        self.btn_folder.pack(side="right")

    # ── 進捗エリア ─────────────────────────────────
    def _build_progress_area(self):
        card = self._card(pady=0)

        self.var_status = tk.StringVar(value="ファイルを選んで「JSXを生成する」を押してください")
        tk.Label(card, textvariable=self.var_status,
                 bg=CARD_BG, fg=DARK, font=FONT_MID,
                 pady=10, anchor="w"
                 ).pack(fill="x", padx=20)

        self.progress = ttk.Progressbar(card, mode="determinate")
        self.progress.pack(fill="x", padx=20, pady=(0, 6))

        self.var_substat = tk.StringVar(value="")
        tk.Label(card, textvariable=self.var_substat,
                 bg=CARD_BG, fg=GRAY, font=FONT_SMALL,
                 pady=4, anchor="w"
                 ).pack(fill="x", padx=20)

    # ── ログ（折りたたみ） ─────────────────────────
    def _build_log_section(self):
        toggle = tk.Frame(self, bg=BG)
        toggle.pack(fill="x", padx=20, pady=(4, 0))

        self.var_log = tk.BooleanVar(value=False)
        tk.Checkbutton(
            toggle, text="処理ログを表示（エラー確認用）",
            variable=self.var_log, bg=BG,
            font=FONT_SMALL, fg=GRAY,
            command=self._toggle_log,
            activebackground=BG
        ).pack(side="left")

        self.log_frame = tk.Frame(self, bg=BG)
        self.log_box = st.ScrolledText(
            self.log_frame, width=80, height=8, state="disabled",
            bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 8), relief="flat"
        )
        self.log_box.pack(padx=20, pady=(4, 8))

    # ── ヘルパー ───────────────────────────────────
    def _card(self, pady=8) -> tk.Frame:
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="x", padx=20, pady=(pady, 0))
        inner = tk.Frame(outer, bg=CARD_BG,
                         highlightbackground=LIGHT_GRAY, highlightthickness=1)
        inner.pack(fill="x")
        return inner

    def _toggle_advanced(self):
        if self.var_adv.get():
            self.adv_frame.pack(fill="x", padx=20, pady=(4, 0))
        else:
            self.adv_frame.pack_forget()

    def _toggle_log(self):
        if self.var_log.get():
            self.log_frame.pack(fill="x")
        else:
            self.log_frame.pack_forget()

    def _on_srt_toggle(self):
        if self.var_srt.get():
            self.srt_expand.pack(fill="x", padx=20, pady=(6, 0))
        else:
            self.srt_expand.pack_forget()

    def _toggle_key_vis(self):
        pass  # APIキーは埋め込み済みのため不要

    # ── ファイル選択 ───────────────────────────────
    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="動画 / 音声ファイルを選択",
            filetypes=[
                ("動画・音声", "*.mp4 *.mov *.avi *.mkv *.mp3 *.wav *.m4a *.aac"),
                ("すべて", "*.*")
            ]
        )
        if path:
            self.var_input.set(path)
            name = os.path.basename(path)
            self._file_label.config(text=f"  {name}", fg=DARK, bg="#EEF0FF")

    def _open_folder(self):
        path = self.var_input.get()
        if path and os.path.exists(path):
            os.startfile(os.path.dirname(path))

    # ── config 保存・読込 ──────────────────────────
    def _cfg_path(self):
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
               else os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "config.json")

    def _load_config(self):
        import json
        p = self._cfg_path()
        if os.path.exists(p):
            try: return json.load(open(p, encoding="utf-8"))
            except: pass
        return {}

    def _save_config(self, data: dict):
        import json
        cfg = self._cfg_path()
        existing = self._load_config()
        existing.update(data)
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def _save_api_key(self):
        self._save_config({"gemini_api_key": self.var_api_key.get().strip()})
        messagebox.showinfo("保存完了", "APIキーを保存しました")

    def _default_rules(self):
        from core import DEFAULT_RULES
        return DEFAULT_RULES

    def _save_rules(self):
        self._save_config({"correction_rules": self.rules_box.get("1.0", "end").strip()})
        messagebox.showinfo("保存完了", "校正ルールを保存しました")

    def _reset_rules(self):
        if messagebox.askyesno("確認", "デフォルトのルールに戻しますか？"):
            self.rules_box.delete("1.0", "end")
            self.rules_box.insert("1.0", self._default_rules())

    # ── キューポーリング ───────────────────────────
    def _poll_queue(self):
        try:
            while True:
                t, d = log_queue.get_nowait()
                if t == "log":    self._append_log(d)
                elif t == "status":  self.var_status.set(d)
                elif t == "sub":     self.var_substat.set(d)
                elif t == "progress":
                    self.progress.stop()
                    self.progress.config(mode="determinate")
                    self.progress["value"] = d
                elif t == "spin":
                    self.progress.config(mode="indeterminate")
                    self.progress.start(12)
                elif t == "done":  self._on_done(d)
                elif t == "error": self._on_error(d)
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _append_log(self, text):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    # ── 実行制御 ───────────────────────────────────
    def _start(self):
        path = self.var_input.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showerror("エラー", "動画ファイルを選んでください")
            return

        self._running = True
        self._stop_flag.clear()
        self._cuts = []
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.progress["value"] = 0
        self.var_substat.set("")

        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

        sys.stdout = QueueWriter(log_queue)
        threading.Thread(target=self._worker, args=(path,), daemon=True).start()

    def _stop(self):
        self._stop_flag.set()
        log_queue.put(("log", "⚠ 停止リクエスト送信..."))

    def _on_done(self, result):
        jsx_path, srt_path = result if isinstance(result, tuple) else (result, None)
        sys.stdout = sys.__stdout__
        self._running = False
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress["value"] = 100

        n     = len(self._cuts)
        total = sum(c["end"] - c["start"] for c in self._cuts) if self._cuts else 0
        self.var_status.set(f"✅  完了！  {n} 箇所カット（合計 {total:.1f} 秒）")
        self.var_substat.set(f"出力: {jsx_path}" + (f"  /  {srt_path}" if srt_path else ""))

        mode = "プレビュー（マーカー）" if self.var_preview.get() else "リップル削除"
        msg = (f"完了しました！\n\n"
               f"カット: {n} 箇所（合計 {total:.1f} 秒）\n"
               f"モード: {mode}\n\n"
               f"Premiere Pro で実行してください:\n"
               f"ファイル → スクリプト → スクリプトを実行\n"
               f"→ {os.path.basename(jsx_path)}")
        if srt_path:
            msg += f"\n\n字幕ファイル:\n→ {os.path.basename(srt_path)}"
        messagebox.showinfo("完了", msg)

    def _on_error(self, msg):
        sys.stdout = sys.__stdout__
        self._running = False
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress["value"] = 0
        self.var_status.set("❌  エラーが発生しました")
        messagebox.showerror("エラー", msg)

    # ── バックグラウンドワーカー ───────────────────
    def _worker(self, input_path: str):
        def put(t, d): log_queue.put((t, d))

        try:
            # ① 無音検出
            put("status", "無音区間を検出中...")
            put("spin", None)
            put("log", "[1/4] 無音解析中...")
            silence_cuts = detect_silence_cuts(
                input_path,
                silence_thresh=float(self.var_thresh.get()),
                min_silence_sec=float(self.var_min_sil.get()),
                keep_gap=float(self.var_gap.get()),
            )
            put("log", f"  無音: {len(silence_cuts)} 箇所")
            put("progress", 25)

            if self._stop_flag.is_set():
                put("error", "停止しました"); return

            # ② 音声認識
            model_name   = self.var_model.get()
            use_fillers  = self.var_fillers.get()
            use_stammers = self.var_stammers.get()
            use_srt      = self.var_srt.get()
            need_whisper = use_fillers or use_stammers or use_srt

            raw_segments = None
            srt_segments = None
            speech_cuts  = []

            if need_whisper:
                put("status", "音声を文字起こし中...（しばらくお待ちください）")
                put("spin", None)
                put("log", f"[2/4] 音声認識 (Whisper {model_name})")
                srt_segments, raw_segments = transcribe(input_path, model_name=model_name)
                speech_cuts = analyze_speech_cuts(
                    input_path,
                    model_name=model_name,
                    filler_min_sec=float(self.var_filler_min.get()),
                    detect_fillers=use_fillers,
                    detect_stammers=use_stammers,
                    _raw_segments=raw_segments,
                )
            else:
                put("log", "[2/4] 音声認識: スキップ")
            put("progress", 50)

            if self._stop_flag.is_set():
                put("error", "停止しました"); return

            # ③ マージ & JSX生成
            put("status", "カット位置を計算してJSXを作成中...")
            put("log", "[3/4] カット区間を統合中...")
            merged = merge_cuts(silence_cuts + speech_cuts)
            self._cuts = merged
            put("log", f"  合計 {len(merged)} 箇所カット")

            base   = os.path.splitext(input_path)[0]
            suffix = "_preview" if self.var_preview.get() else "_cuts"
            jsx_out = base + suffix + ".jsx"
            generate_jsx(merged, jsx_out, preview_only=self.var_preview.get())
            put("log", f"  JSX: {jsx_out}")
            put("progress", 75)

            # ④ SRT生成
            srt_out = None
            if use_srt and srt_segments:
                api_key = self.var_api_key.get().strip()
                if api_key:
                    put("status", "AIが字幕を校正中...（しばらくお待ちください）")
                    put("spin", None)
                    put("log", f"[4/4] Gemini校正中（{len(srt_segments)} セグメント）...")
                    custom_rules = self.rules_box.get("1.0", "end").strip()
                    srt_segments = correct_segments(
                        srt_segments, api_key=api_key, custom_rules=custom_rules)
                    put("log", "  校正完了")
                else:
                    put("log", "[4/4] APIキー未入力 → 校正なしでSRT生成")

                srt_out = base + ".srt"
                save_srt(srt_segments, srt_out)
                put("log", f"  SRT: {srt_out}")
            else:
                put("log", "[4/4] SRT生成: スキップ")

            put("progress", 100)
            put("done", (jsx_out, srt_out))

        except Exception as e:
            import traceback
            put("log", traceback.format_exc())
            put("error", f"エラーが発生しました:\n{e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
