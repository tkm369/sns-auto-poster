import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import tempfile
import yt_dlp
import whisper

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]


class VideoTool:
    def __init__(self, root):
        self.root = root
        self.root.title("動画ツール - DL & 文字起こし")
        self.root.geometry("700x620")
        self.root.resizable(True, True)

        self._whisper_model = None
        self._current_model_name = None
        self.save_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.do_download = tk.BooleanVar(value=False)
        self.do_transcribe = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 5}

        # --- URL入力 ---
        url_frame = tk.LabelFrame(self.root, text="URL (Chrome / Firefox / Edge など)",
                                  font=("Arial", 10, "bold"))
        url_frame.pack(fill="x", **pad)

        url_inner = tk.Frame(url_frame)
        url_inner.pack(fill="x", padx=8, pady=8)
        self.url_entry = tk.Entry(url_inner, font=("Arial", 11))
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda e: self._start())
        tk.Button(url_inner, text="貼り付け", command=self._paste_url).pack(side="left", padx=(6, 0))

        # --- モード選択 ---
        mode_frame = tk.LabelFrame(self.root, text="実行する処理", font=("Arial", 10, "bold"))
        mode_frame.pack(fill="x", **pad)
        mode_inner = tk.Frame(mode_frame)
        mode_inner.pack(fill="x", padx=8, pady=6)
        tk.Checkbutton(mode_inner, text="動画をダウンロード", variable=self.do_download,
                       font=("Arial", 11), command=self._toggle_panels).pack(side="left", padx=8)
        tk.Checkbutton(mode_inner, text="文字起こし", variable=self.do_transcribe,
                       font=("Arial", 11), command=self._toggle_panels).pack(side="left", padx=8)

        # --- ダウンロード設定パネル ---
        self.dl_panel = tk.LabelFrame(self.root, text="ダウンロード設定", font=("Arial", 10, "bold"))
        dl_inner = tk.Frame(self.dl_panel)
        dl_inner.pack(fill="x", padx=8, pady=8)
        tk.Entry(dl_inner, textvariable=self.save_dir, font=("Arial", 10)).pack(
            side="left", fill="x", expand=True)
        tk.Button(dl_inner, text="参照...", command=self._browse_dir).pack(side="left", padx=(6, 0))

        # --- 文字起こし設定パネル ---
        self.tr_panel = tk.LabelFrame(self.root, text="文字起こし設定", font=("Arial", 10, "bold"))
        model_inner = tk.Frame(self.tr_panel)
        model_inner.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(model_inner, text="モデル:", font=("Arial", 10)).pack(side="left")
        self.model_var = tk.StringVar(value="small")
        for name in WHISPER_MODELS:
            tk.Radiobutton(model_inner, text=name, variable=self.model_var,
                           value=name, font=("Arial", 10)).pack(side="left", padx=4)
        tk.Label(model_inner, text="← 速い / 精度高い →",
                 font=("Arial", 9), fg="#888").pack(side="left", padx=8)
        lang_inner = tk.Frame(self.tr_panel)
        lang_inner.pack(fill="x", padx=8, pady=(2, 8))
        tk.Label(lang_inner, text="言語:", font=("Arial", 10)).pack(side="left")
        self.lang_var = tk.StringVar(value="ja")
        ttk.Combobox(lang_inner, textvariable=self.lang_var, width=8,
                     values=["ja", "en", "zh", "ko", "auto"],
                     state="readonly").pack(side="left", padx=6)
        tk.Label(lang_inner, text="(autoで自動判定)", font=("Arial", 9), fg="#888").pack(side="left")

        # --- 実行ボタン ---
        self.run_btn = tk.Button(
            self.root, text="実行", font=("Arial", 13, "bold"),
            bg="#ff2d55", fg="white", activebackground="#cc0044",
            command=self._start, height=2
        )
        self.run_btn.pack(fill="x", padx=12, pady=(4, 2))

        # --- 進捗 ---
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=12, pady=(0, 2))
        self.status_var = tk.StringVar(value="URLを貼り付けて実行してください")
        tk.Label(self.root, textvariable=self.status_var, font=("Arial", 10),
                 wraplength=680, justify="left", fg="#444").pack(padx=12, anchor="w")
        self.dl_result_var = tk.StringVar()
        self.dl_result_label = tk.Label(self.root, textvariable=self.dl_result_var,
                                        font=("Arial", 9), fg="#0066cc",
                                        wraplength=680, justify="left", cursor="hand2")
        self.dl_result_label.pack(padx=12, anchor="w")
        self.dl_result_label.bind("<Button-1>", self._open_folder)

        # --- 文字起こし結果 ---
        result_frame = tk.LabelFrame(self.root, text="文字起こし結果", font=("Arial", 10, "bold"))
        result_frame.pack(fill="both", expand=True, padx=12, pady=5)
        text_inner = tk.Frame(result_frame)
        text_inner.pack(fill="both", expand=True, padx=6, pady=6)
        sb = tk.Scrollbar(text_inner)
        sb.pack(side="right", fill="y")
        self.result_text = tk.Text(text_inner, font=("Arial", 11), wrap="word",
                                   yscrollcommand=sb.set, state="disabled")
        self.result_text.pack(fill="both", expand=True)
        sb.config(command=self.result_text.yview)
        tk.Button(result_frame, text="テキストをコピー", command=self._copy_result).pack(
            anchor="e", padx=6, pady=(0, 6))

        self._toggle_panels()

    def _toggle_panels(self):
        if self.do_download.get():
            self.dl_panel.pack(fill="x", padx=12, pady=5, before=self.tr_panel)
        else:
            self.dl_panel.pack_forget()
        if self.do_transcribe.get():
            self.tr_panel.pack(fill="x", padx=12, pady=5, before=self.run_btn)
        else:
            self.tr_panel.pack_forget()

    def _paste_url(self):
        try:
            text = self.root.clipboard_get().strip()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, text)
        except Exception:
            pass

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.save_dir.get())
        if d:
            self.save_dir.set(d)

    def _start(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL未入力", "URLを入力してください。")
            return
        if not self.do_download.get() and not self.do_transcribe.get():
            messagebox.showwarning("未選択", "処理を1つ以上選択してください。")
            return
        if self.do_download.get() and not os.path.isdir(self.save_dir.get()):
            messagebox.showerror("エラー", "保存先フォルダが存在しません。")
            return

        self.run_btn.config(state="disabled")
        self.dl_result_var.set("")
        self._set_result("")
        self.progress.start(10)
        self._set_status("処理を開始します...")
        threading.Thread(target=self._run, args=(url,), daemon=True).start()

    def _run(self, url):
        try:
            dl_path = None
            if self.do_download.get():
                self._set_status("動画をダウンロード中...")
                save_path = self.save_dir.get()
                ydl_opts = {
                    "outtmpl": os.path.join(save_path, "%(uploader)s_%(id)s.%(ext)s"),
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "no_warnings": True,
                    "progress_hooks": [self._dl_progress_hook],
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    dl_path = ydl.prepare_filename(info)
                    if not os.path.exists(dl_path):
                        dl_path = os.path.splitext(dl_path)[0] + ".mp4"

            transcript = None
            if self.do_transcribe.get():
                with tempfile.TemporaryDirectory() as tmpdir:
                    self._set_status("音声をダウンロード中...")
                    ydl_opts = {
                        "outtmpl": os.path.join(tmpdir, "audio.%(ext)s"),
                        "format": "bestaudio/best",
                        "postprocessors": [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "128",
                        }],
                        "quiet": True,
                        "no_warnings": True,
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                    audio_file = os.path.join(tmpdir, "audio.mp3")
                    if not os.path.exists(audio_file):
                        raise FileNotFoundError("音声ファイルの取得に失敗しました。")

                    model_name = self.model_var.get()
                    if self._current_model_name != model_name:
                        self._set_status(f"Whisperモデル '{model_name}' を読み込み中...")
                        self._whisper_model = whisper.load_model(model_name)
                        self._current_model_name = model_name

                    self._set_status("文字起こし中...")
                    lang = self.lang_var.get()
                    options = {} if lang == "auto" else {"language": lang}
                    result = self._whisper_model.transcribe(audio_file, **options)
                    transcript = result["text"].strip()

            self.root.after(0, self._on_success, dl_path, transcript)
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _dl_progress_hook(self, d):
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            if total:
                self._set_status(f"ダウンロード中... {downloaded / total * 100:.1f}%")
            else:
                self._set_status(f"ダウンロード中... {downloaded / 1024 / 1024:.1f} MB")

    def _on_success(self, dl_path, transcript):
        self.progress.stop()
        self.run_btn.config(state="normal")
        parts = []
        if dl_path:
            parts.append("ダウンロード完了")
            self._saved_dir = os.path.dirname(dl_path)
            self.dl_result_var.set(f"保存先: {dl_path}  (クリックでフォルダを開く)")
        if transcript is not None:
            parts.append("文字起こし完了")
            self._set_result(transcript)
        self._set_status(" / ".join(parts) + "!")

    def _on_error(self, msg):
        self.progress.stop()
        self.run_btn.config(state="normal")
        self._set_status("エラーが発生しました")
        messagebox.showerror("エラー", f"エラー内容:\n{msg}")

    def _set_status(self, msg):
        self.root.after(0, self.status_var.set, msg)

    def _set_result(self, text):
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        if text:
            self.result_text.insert(tk.END, text)
        self.result_text.config(state="disabled")

    def _copy_result(self):
        text = self.result_text.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("コピー完了", "テキストをクリップボードにコピーしました。")

    def _open_folder(self, event=None):
        d = getattr(self, "_saved_dir", self.save_dir.get())
        if os.path.isdir(d):
            os.startfile(d)


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoTool(root)
    root.mainloop()
