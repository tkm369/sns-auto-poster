"""
B-Roll Auto Inserter
SRTファイルから自動でフリー素材をDLしてPremiere Pro用スクリプトを生成する
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os

from srt_parser import parse_srt
from keyword_extractor import text_to_search_query
from stock_fetcher import PexelsClient
from downloader import download_video
from premiere_bridge import generate_extendscript

# ---- カラー定義 ----
BG = "#F5F5F5"
ACCENT = "#2196F3"
SUCCESS = "#4CAF50"
WARN = "#FF9800"
ERROR = "#F44336"
WHITE = "#FFFFFF"
DARK = "#212121"
GRAY = "#757575"
LIGHT_GRAY = "#E0E0E0"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("B-Roll Auto Inserter")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._running = False
        self._thread = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_header()
        self._build_step1()
        self._build_step2()
        self._build_run_section()
        self._build_status_section()
        self._build_log_section()

    def _build_header(self):
        frm = tk.Frame(self, bg=ACCENT)
        frm.pack(fill="x")
        tk.Label(frm, text="🎬  B-Roll Auto Inserter",
                 bg=ACCENT, fg=WHITE, font=("Yu Gothic UI", 16, "bold"),
                 pady=12).pack(side="left", padx=16)
        self._key_label = tk.Label(frm, text="", bg=ACCENT, fg=WHITE,
                                    font=("Yu Gothic UI", 9))
        self._key_label.pack(side="right", padx=16)

    def _build_step1(self):
        frm = self._card("STEP 1　SRTファイルを選んでください")

        tk.Label(frm, text="Premiere Proから書き出したSRTファイルを選択します",
                 bg=WHITE, fg=GRAY, font=("Yu Gothic UI", 9)).pack(anchor="w", padx=16, pady=(0, 8))

        row = tk.Frame(frm, bg=WHITE)
        row.pack(fill="x", padx=16, pady=(0, 12))

        self.var_srt = tk.StringVar()
        entry = tk.Entry(row, textvariable=self.var_srt, width=48,
                         font=("Yu Gothic UI", 10), relief="solid", bd=1)
        entry.pack(side="left", ipady=4)

        self._btn(row, "ファイルを選択", self._browse_srt, ACCENT).pack(side="left", padx=(8, 0))

    def _build_step2(self):
        frm = self._card("STEP 2　素材の保存先フォルダを選んでください")

        tk.Label(frm, text="ダウンロードした動画素材の保存場所を指定します",
                 bg=WHITE, fg=GRAY, font=("Yu Gothic UI", 9)).pack(anchor="w", padx=16, pady=(0, 8))

        row = tk.Frame(frm, bg=WHITE)
        row.pack(fill="x", padx=16, pady=(0, 8))

        self.var_out = tk.StringVar()
        entry = tk.Entry(row, textvariable=self.var_out, width=48,
                         font=("Yu Gothic UI", 10), relief="solid", bd=1)
        entry.pack(side="left", ipady=4)

        self._btn(row, "フォルダを選択", self._browse_out, ACCENT).pack(side="left", padx=(8, 0))

        # OP/ED スキップ設定
        range_frm = tk.Frame(frm, bg="#F9F9F9", relief="solid", bd=1)
        range_frm.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(range_frm, text="  OP / ED のスキップ範囲",
                 bg="#F9F9F9", fg=DARK, font=("Yu Gothic UI", 9, "bold")).grid(
                 row=0, column=0, columnspan=6, sticky="w", pady=(6, 2), padx=4)

        tk.Label(range_frm, text="  挿入を開始する時間：",
                 bg="#F9F9F9", fg=DARK, font=("Yu Gothic UI", 9)).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.var_start_mm = tk.StringVar(value="0")
        self.var_start_ss = tk.StringVar(value="00")
        tk.Entry(range_frm, textvariable=self.var_start_mm, width=4,
                 font=("Yu Gothic UI", 10), justify="center").grid(row=1, column=1, padx=2)
        tk.Label(range_frm, text="分", bg="#F9F9F9", font=("Yu Gothic UI", 9)).grid(row=1, column=2)
        tk.Entry(range_frm, textvariable=self.var_start_ss, width=4,
                 font=("Yu Gothic UI", 10), justify="center").grid(row=1, column=3, padx=2)
        tk.Label(range_frm, text="秒　から", bg="#F9F9F9", font=("Yu Gothic UI", 9)).grid(row=1, column=4, padx=(0, 20))

        tk.Label(range_frm, text="挿入を終了する時間：",
                 bg="#F9F9F9", fg=DARK, font=("Yu Gothic UI", 9)).grid(row=1, column=5, sticky="w", padx=4)
        self.var_end_mm = tk.StringVar(value="")
        self.var_end_ss = tk.StringVar(value="")
        tk.Entry(range_frm, textvariable=self.var_end_mm, width=4,
                 font=("Yu Gothic UI", 10), justify="center").grid(row=1, column=6, padx=2)
        tk.Label(range_frm, text="分", bg="#F9F9F9", font=("Yu Gothic UI", 9)).grid(row=1, column=7)
        tk.Entry(range_frm, textvariable=self.var_end_ss, width=4,
                 font=("Yu Gothic UI", 10), justify="center").grid(row=1, column=8, padx=2)
        tk.Label(range_frm, text="秒　まで（空白=最後まで）",
                 bg="#F9F9F9", fg=GRAY, font=("Yu Gothic UI", 9)).grid(row=1, column=9, padx=(0, 8), pady=4)

        # オプション
        opt = tk.Frame(frm, bg=WHITE)
        opt.pack(fill="x", padx=16, pady=(4, 12))

        tk.Label(opt, text="短い字幕をスキップ（秒以下）:",
                 bg=WHITE, fg=DARK, font=("Yu Gothic UI", 9)).pack(side="left")
        self.var_min_dur = tk.DoubleVar(value=1.5)
        tk.Spinbox(opt, from_=0.5, to=10.0, increment=0.5,
                   textvariable=self.var_min_dur, width=5,
                   font=("Yu Gothic UI", 10)).pack(side="left", padx=(4, 16))

        self.var_skip = tk.BooleanVar(value=False)
        tk.Checkbutton(opt, text="1件おきに間引く（素材数を半分にする）",
                       variable=self.var_skip, bg=WHITE,
                       font=("Yu Gothic UI", 9)).pack(side="left")

    def _build_run_section(self):
        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="x", padx=20, pady=8)

        self.btn_start = tk.Button(
            frm, text="▶  実行する", width=18,
            bg=SUCCESS, fg=WHITE, font=("Yu Gothic UI", 13, "bold"),
            relief="flat", cursor="hand2", command=self._start,
            activebackground="#388E3C", activeforeground=WHITE
        )
        self.btn_start.pack(side="left", ipady=8)

        self.btn_stop = tk.Button(
            frm, text="■  停止", width=10,
            bg=LIGHT_GRAY, fg=DARK, font=("Yu Gothic UI", 11),
            relief="flat", cursor="hand2", state="disabled",
            command=self._stop
        )
        self.btn_stop.pack(side="left", padx=(8, 0), ipady=8)

        self.btn_folder = tk.Button(
            frm, text="📁  フォルダを開く", width=14,
            bg=LIGHT_GRAY, fg=DARK, font=("Yu Gothic UI", 11),
            relief="flat", cursor="hand2", command=self._open_folder
        )
        self.btn_folder.pack(side="right", ipady=8)

    def _build_status_section(self):
        frm = self._card(None, pady=0)

        # 大きなステータス表示
        self.var_big_status = tk.StringVar(value="待機中")
        tk.Label(frm, textvariable=self.var_big_status,
                 bg=WHITE, fg=DARK, font=("Yu Gothic UI", 13, "bold"),
                 pady=6).pack(anchor="w", padx=16)

        # プログレスバー
        self.progress = ttk.Progressbar(frm, length=540, mode="determinate")
        self.progress.pack(fill="x", padx=16, pady=(0, 4))

        # カウンター
        self.var_count = tk.StringVar(value="")
        tk.Label(frm, textvariable=self.var_count,
                 bg=WHITE, fg=GRAY, font=("Yu Gothic UI", 9),
                 pady=4).pack(anchor="w", padx=16)

    def _build_log_section(self):
        # 折りたたみログ
        toggle_frm = tk.Frame(self, bg=BG)
        toggle_frm.pack(fill="x", padx=20, pady=(4, 0))

        self.var_log_open = tk.BooleanVar(value=False)
        tk.Checkbutton(toggle_frm, text="詳細ログを表示",
                       variable=self.var_log_open, bg=BG,
                       font=("Yu Gothic UI", 9), fg=GRAY,
                       command=self._toggle_log).pack(side="left")

        self.log_frame = tk.Frame(self, bg=BG)
        # 最初は非表示

        import tkinter.scrolledtext as st
        self.log_box = st.ScrolledText(
            self.log_frame, width=70, height=10, state="disabled",
            bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 9),
            relief="flat"
        )
        self.log_box.pack(padx=20, pady=(4, 12))

        tk.Frame(self, bg=BG, height=8).pack()  # 下余白

    # ------------------------------------------------------------------
    # パーツ生成ヘルパー
    # ------------------------------------------------------------------
    def _card(self, title: str | None, pady: int = 8) -> tk.Frame:
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="x", padx=20, pady=(8, 0))

        inner = tk.Frame(outer, bg=WHITE, relief="flat",
                         highlightbackground=LIGHT_GRAY, highlightthickness=1)
        inner.pack(fill="x")

        if title:
            tk.Label(inner, text=title, bg=ACCENT, fg=WHITE,
                     font=("Yu Gothic UI", 10, "bold"),
                     anchor="w", pady=6, padx=12).pack(fill="x")

        return inner

    def _btn(self, parent, text: str, cmd, color: str) -> tk.Button:
        return tk.Button(parent, text=text, command=cmd,
                         bg=color, fg=WHITE, font=("Yu Gothic UI", 10),
                         relief="flat", cursor="hand2",
                         activebackground=color, activeforeground=WHITE,
                         padx=10, pady=4)

    # ------------------------------------------------------------------
    # ログ折りたたみ
    # ------------------------------------------------------------------
    def _toggle_log(self):
        if self.var_log_open.get():
            self.log_frame.pack(fill="x")
        else:
            self.log_frame.pack_forget()

    # ------------------------------------------------------------------
    # ボタンアクション
    # ------------------------------------------------------------------
    def _browse_srt(self):
        path = filedialog.askopenfilename(
            filetypes=[("SRT ファイル", "*.srt"), ("すべて", "*.*")])
        if path:
            self.var_srt.set(path)

    def _browse_out(self):
        path = filedialog.askdirectory()
        if path:
            self.var_out.set(path)

    def _open_folder(self):
        folder = self.var_out.get()
        if folder and os.path.isdir(folder):
            os.startfile(folder)
        else:
            messagebox.showinfo("情報", "先に出力フォルダを選択してください")

    def _parse_time_range(self):
        """開始・終了時間をパースして秒で返す。空欄はNone"""
        def to_sec(mm_var, ss_var):
            mm = mm_var.get().strip()
            ss = ss_var.get().strip()
            if not mm and not ss:
                return None
            try:
                return int(mm or 0) * 60 + float(ss or 0)
            except ValueError:
                return None

        start_sec = to_sec(self.var_start_mm, self.var_start_ss)
        end_sec = to_sec(self.var_end_mm, self.var_end_ss)
        return start_sec or 0.0, end_sec

    def _start(self):
        srt_path = self.var_srt.get().strip()
        out_dir = self.var_out.get().strip()

        if not srt_path or not os.path.isfile(srt_path):
            messagebox.showerror("エラー", "SRTファイルを選択してください")
            return
        if not out_dir:
            messagebox.showerror("エラー", "保存先フォルダを選択してください")
            return

        os.makedirs(out_dir, exist_ok=True)

        self._running = True
        self.btn_start.config(state="disabled", bg=LIGHT_GRAY, fg=GRAY)
        self.btn_stop.config(state="normal", bg=ERROR, fg=WHITE)
        self.progress["value"] = 0
        self._log_clear()

        start_sec, end_sec = self._parse_time_range()

        self._thread = threading.Thread(
            target=self._run_worker,
            args=(srt_path, out_dir, start_sec, end_sec),
            daemon=True,
        )
        self._thread.start()

    def _stop(self):
        self._running = False
        self._set_big_status("停止中...", WARN)

    # ------------------------------------------------------------------
    # スレッドセーフUI更新
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        self.after(0, self._log_ui, msg)

    def _log_ui(self, msg: str):
        self.log_box.config(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def _log_clear(self):
        self.after(0, lambda: (
            self.log_box.config(state="normal"),
            self.log_box.delete("1.0", "end"),
            self.log_box.config(state="disabled")
        ))

    def _set_progress(self, value: float):
        self.after(0, lambda: self.progress.configure(value=value))

    def _set_big_status(self, msg: str, color: str = DARK):
        self.after(0, lambda: (
            self.var_big_status.set(msg),
            # ラベルの色を変える
        ))

    def _set_count(self, msg: str):
        self.after(0, lambda: self.var_count.set(msg))

    def _set_key_label(self, msg: str):
        self.after(0, lambda: self._key_label.config(text=msg))

    def _finish(self):
        self.after(0, self._finish_ui)

    def _finish_ui(self):
        self._running = False
        self.btn_start.config(state="normal", bg=SUCCESS, fg=WHITE)
        self.btn_stop.config(state="disabled", bg=LIGHT_GRAY, fg=DARK)

    # ------------------------------------------------------------------
    # メイン処理（バックグラウンド）
    # ------------------------------------------------------------------
    def _run_worker(self, srt_path: str, out_dir: str, start_sec: float = 0.0, end_sec=None):
        try:
            self._set_big_status("SRTを読み込み中...")

            entries = parse_srt(srt_path)
            min_dur = self.var_min_dur.get()
            skip = self.var_skip.get()

            targets = [e for e in entries if e.duration() >= min_dur]

            # OP/ED スキップ
            if start_sec > 0:
                targets = [e for e in targets if e.start_seconds >= start_sec]
            if end_sec is not None:
                targets = [e for e in targets if e.end_seconds <= end_sec]

            if skip:
                targets = targets[::2]

            if not targets:
                self._set_big_status("対象の字幕がありませんでした", ERROR)
                messagebox.showwarning("注意", "処理対象の字幕が0件です。\n時間範囲や秒数設定を確認してください。")
                self._finish()
                return

            total = len(targets)
            range_msg = ""
            if start_sec > 0 or end_sec is not None:
                s = f"{int(start_sec//60)}分{int(start_sec%60):02d}秒"
                e = f"{int(end_sec//60)}分{int(end_sec%60):02d}秒" if end_sec else "最後"
                range_msg = f"  （範囲: {s} 〜 {e}）"
            self._log(f"字幕 {len(entries)}件 → 処理対象 {total}件{range_msg}")
            self._set_count(f"0 / {total} 件処理済み")

            client = PexelsClient()
            self._set_key_label(client.current_key_label)

            clips = []
            ok = 0
            ng = 0

            for i, entry in enumerate(targets):
                if not self._running:
                    self._log("停止しました")
                    break

                self._set_big_status(f"検索中... [{i+1}/{total}]  {entry.text[:20]}")
                self._log(f"\n[{i+1}/{total}] {entry.text}")

                query = text_to_search_query(entry.text)
                self._log(f"  検索: {query}")

                try:
                    video = client.search(query)
                    self._set_key_label(client.current_key_label)
                except RuntimeError as e:
                    self._set_big_status(str(e), ERROR)
                    messagebox.showerror("APIエラー", str(e))
                    break
                except Exception as e:
                    self._log(f"  ✗ 検索失敗: {e}")
                    ng += 1
                    continue

                if not video:
                    self._log(f"  ✗ 素材が見つかりませんでした")
                    ng += 1
                    continue

                url = client.get_download_url(video)
                if not url:
                    self._log(f"  ✗ URLが取得できませんでした")
                    ng += 1
                    continue

                file_name = f"broll_{i+1:03d}.mp4"
                file_path = os.path.join(out_dir, file_name)

                self._set_big_status(f"ダウンロード中... [{i+1}/{total}]  {file_name}")

                def make_cb(idx, tot, fname):
                    def cb(pct):
                        self._set_big_status(f"ダウンロード中... [{idx}/{tot}]  {fname}  {pct}%")
                    return cb

                try:
                    download_video(url, file_path, make_cb(i+1, total, file_name))
                except Exception as e:
                    self._log(f"  ✗ DL失敗: {e}")
                    ng += 1
                    continue

                self._log(f"  ✓ {file_name}")
                clips.append({
                    "file_path": file_path.replace("\\", "/"),
                    "file_name": file_name,
                    "start_seconds": entry.start_seconds,
                    "end_seconds": entry.end_seconds,
                    "subtitle_text": entry.text,
                })
                ok += 1
                self._set_count(f"{ok} / {total} 件処理済み（失敗 {ng} 件）")
                self._set_progress((i + 1) / total * 100)

            # ExtendScript生成
            if clips:
                jsx_path = os.path.join(out_dir, "insert_broll.jsx")
                generate_extendscript(clips, jsx_path)
                self._log(f"\n✓ Premiere用スクリプト生成: {jsx_path}")

                self._set_big_status(f"完了！  {ok}件の素材を取得しました", SUCCESS)
                self._set_count(f"成功 {ok} 件 / 失敗 {ng} 件")
                self._set_progress(100)

                messagebox.showinfo(
                    "完了",
                    f"{ok}件の素材をダウンロードしました。\n\n"
                    "次の手順：\n"
                    "Premiere Proを開いて\n"
                    "「ファイル → スクリプト → スクリプトを実行」から\n"
                    "insert_broll.jsx を選択してください。"
                )
            else:
                self._set_big_status("素材が取得できませんでした", ERROR)

        except Exception as e:
            self._log(f"\n予期しないエラー: {e}")
            self._set_big_status(f"エラーが発生しました", ERROR)
        finally:
            self._finish()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
