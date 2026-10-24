#!/usr/bin/env python3
"""Local desktop control panel for the YouTube Shorts production pipeline."""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter as tk


ROOT = Path(__file__).resolve().parent
EXAMPLE_CONFIG = ROOT / "pipeline.example.json"
LOCAL_CONFIG = ROOT / "pipeline.local.json"
UPLOAD_MANIFEST = ROOT / "generated" / "upload_config.json"


def read_config(path):
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def resolve_local_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def build_upload_manifest(config, privacy):
    videos = []
    for scene in config.get("videos", []):
        file_path = resolve_local_path(scene.get("file", ""))
        if not file_path.is_file():
            raise ValueError(f"ملف الفيديو غير موجود للمشهد {scene.get('id', '?')}: {file_path}")
        videos.append(
            {
                "file": str(file_path.resolve()),
                "title": scene["title"],
                "description": scene.get("description", ""),
                "tags": scene.get("tags", []),
                "privacy": privacy,
                "made_for_kids": scene.get("made_for_kids", True),
            }
        )
    if not videos:
        raise ValueError("لا توجد مشاهد في الإعداد المحلي.")
    return {"videos": videos}


class ShortsControlPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("Shorts Studio | التحكم المحلي")
        self.root.geometry("1120x790")
        self.root.minsize(920, 680)
        self.config = {}
        self.current_scene_id = None
        self.process = None
        self.output_queue = queue.Queue()
        self.busy = False
        self.privacy_var = tk.StringVar(value="unlisted")
        self.no_render_var = tk.BooleanVar(value=False)
        self.api_url_var = tk.StringVar(value=self.config.get("comfyui_url", ""))
        self.workflow_var = tk.StringVar(value=self.config.get("workflow_file", ""))
        self.output_dir_var = tk.StringVar(value=self.config.get("output_dir", "generated"))

        self._load_local_config()
        self._build_ui()
        self._refresh_scene_list()
        self._refresh_readiness()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _load_local_config(self):
        defaults = read_config(EXAMPLE_CONFIG)
        if not LOCAL_CONFIG.exists():
            self.config = defaults
            LOCAL_CONFIG.write_text(
                json.dumps(self.config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            self.config = read_config(LOCAL_CONFIG)
            for key in ("comfyui_url", "workflow_file", "output_dir"):
                if not self.config.get(key):
                    self.config[key] = defaults[key]

    def _build_ui(self):
        style = ttk.Style(self.root)
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", padding=(8, 5))

        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Shorts Studio", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="إدارة الإنتاج المحلي ورفع YouTube", anchor="e").pack(
            side="right", fill="x", expand=True, padx=(12, 0)
        )

        status_frame = ttk.LabelFrame(outer, text="حالة البيئة", padding=(10, 6))
        status_frame.pack(fill="x", pady=(0, 12))
        self.status_text = tk.StringVar(value="جارٍ فحص المتطلبات...")
        ttk.Label(status_frame, textvariable=self.status_text, style="Status.TLabel").pack(
            side="left", fill="x", expand=True
        )
        self.refresh_button = ttk.Button(
            status_frame, text="تحديث الفحص", command=self._refresh_readiness
        )
        self.refresh_button.pack(side="right")

        main = ttk.Panedwindow(outer, orient="horizontal")
        main.pack(fill="both", expand=True)

        scene_frame = ttk.LabelFrame(main, text="المشاهد الخمسة", padding=8)
        editor_frame = ttk.LabelFrame(main, text="تفاصيل المشهد", padding=10)
        main.add(scene_frame, weight=1)
        main.add(editor_frame, weight=3)

        self.scene_tree = ttk.Treeview(
            scene_frame,
            columns=("asset",),
            show="tree headings",
            selectmode="browse",
            height=13,
        )
        self.scene_tree.heading("#0", text="المشهد")
        self.scene_tree.heading("asset", text="الفيديو")
        self.scene_tree.column("#0", width=175, stretch=True)
        self.scene_tree.column("asset", width=88, stretch=False)
        self.scene_tree.pack(fill="both", expand=True)
        self.scene_tree.bind("<<TreeviewSelect>>", self._on_scene_select)

        file_actions = ttk.Frame(scene_frame)
        file_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(file_actions, text="اختيار MP4", command=self._choose_video).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(file_actions, text="فتح المخرجات", command=self._open_output).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )

        editor_frame.columnconfigure(1, weight=1)
        editor_frame.rowconfigure(5, weight=1)
        self.title_var = tk.StringVar()
        self.description_var = tk.StringVar()
        self.file_var = tk.StringVar()
        self._field(editor_frame, 0, "العنوان", self.title_var)
        self._field(editor_frame, 1, "الوصف", self.description_var)
        ttk.Label(editor_frame, text="ملف الفيديو").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(editor_frame, textvariable=self.file_var).grid(
            row=2, column=1, sticky="ew", pady=5
        )
        ttk.Button(editor_frame, text="استعراض", command=self._choose_video).grid(
            row=2, column=2, padx=(6, 0), pady=5
        )
        ttk.Label(editor_frame, text="البرومبت").grid(row=3, column=0, sticky="nw", pady=5)
        self.prompt_text = scrolledtext.ScrolledText(
            editor_frame, height=10, wrap="word", font=("Segoe UI", 10)
        )
        self.prompt_text.grid(row=3, column=1, columnspan=2, sticky="nsew", pady=5)
        ttk.Label(editor_frame, text="الوسوم (افصل بينها بفاصلة)").grid(
            row=4, column=0, sticky="w", pady=5
        )
        self.tags_var = tk.StringVar()
        ttk.Entry(editor_frame, textvariable=self.tags_var).grid(
            row=4, column=1, columnspan=2, sticky="ew", pady=5
        )
        editor_frame.rowconfigure(3, weight=1)

        settings = ttk.LabelFrame(outer, text="إعدادات التشغيل", padding=8)
        settings.pack(fill="x", pady=(12, 8))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)
        ttk.Label(settings, text="ComfyUI API").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(settings, textvariable=self.api_url_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=4, pady=4
        )
        ttk.Label(settings, text="Workflow API").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(settings, textvariable=self.workflow_var).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=4, pady=4
        )
        ttk.Button(settings, text="استعراض", command=self._choose_workflow).grid(
            row=1, column=3, padx=4, pady=4
        )
        ttk.Label(settings, text="مجلد النتائج").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(settings, textvariable=self.output_dir_var).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=4, pady=4
        )
        ttk.Button(settings, text="اختيار", command=self._choose_output_dir).grid(
            row=2, column=3, padx=4, pady=4
        )
        options = ttk.Frame(settings)
        options.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Label(options, text="خصوصية الرفع").pack(side="left")
        ttk.Combobox(
            options,
            textvariable=self.privacy_var,
            values=("private", "unlisted", "public"),
            state="readonly",
            width=12,
        ).pack(side="left", padx=8)
        ttk.Checkbutton(
            options, text="تجاوز تحويل FFmpeg", variable=self.no_render_var
        ).pack(side="left", padx=12)
        ttk.Button(options, text="فتح JSON", command=self._open_local_config).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(options, text="حفظ الإعدادات", command=self._save_config).pack(
            side="right"
        )

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))
        self.generate_button = ttk.Button(
            actions, text="توليد المشاهد الخمسة", command=self._generate
        )
        self.generate_button.pack(side="left")
        self.upload_button = ttk.Button(
            actions, text="رفع ملفات الفيديو", command=self._upload
        )
        self.upload_button.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(actions, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=(16, 0))

        log_frame = ttk.LabelFrame(outer, text="سجل التشغيل", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=9, wrap="word", state="disabled", font=("Consolas", 9)
        )
        self.log_text.pack(fill="both", expand=True)
        self._log(f"الإعداد المحلي: {LOCAL_CONFIG.name}")
        self._log("الرفع منفصل عن التوليد؛ افحص النتائج قبل النشر.")

    @staticmethod
    def _field(parent, row, label, variable):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=5
        )

    def _refresh_scene_list(self):
        self.scene_tree.delete(*self.scene_tree.get_children())
        for scene in self.config.get("videos", []):
            path = resolve_local_path(scene.get("file", ""))
            status = "جاهز" if path.is_file() else "لا يوجد"
            self.scene_tree.insert(
                "", "end", iid=scene["id"], text=scene["title"], values=(status,)
            )
        if self.config.get("videos"):
            first_id = self.config["videos"][0]["id"]
            self.scene_tree.selection_set(first_id)
            self._show_scene(first_id)

    def _selected_scene(self):
        if not self.current_scene_id:
            return None
        return next(
            (scene for scene in self.config.get("videos", []) if scene["id"] == self.current_scene_id),
            None,
        )

    def _save_current_scene(self):
        scene = self._selected_scene()
        if not scene:
            return
        title = self.title_var.get().strip()
        if title:
            scene["title"] = title
        scene["description"] = self.description_var.get().strip()
        scene["file"] = self.file_var.get().strip()
        scene["prompt"] = self.prompt_text.get("1.0", "end-1c").strip()
        scene["tags"] = [tag.strip() for tag in self.tags_var.get().split(",") if tag.strip()]

    def _show_scene(self, scene_id):
        self._save_current_scene()
        scene = next(
            (item for item in self.config.get("videos", []) if item["id"] == scene_id),
            None,
        )
        if not scene:
            return
        self.current_scene_id = scene_id
        self.title_var.set(scene.get("title", ""))
        self.description_var.set(scene.get("description", ""))
        self.file_var.set(scene.get("file", ""))
        self.tags_var.set(", ".join(scene.get("tags", [])))
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", scene.get("prompt", ""))

    def _on_scene_select(self, _event=None):
        selection = self.scene_tree.selection()
        if selection:
            self._show_scene(selection[0])

    def _choose_video(self):
        path = filedialog.askopenfilename(
            title="اختيار فيديو للمشهد",
            initialdir=str(ROOT),
            filetypes=(("Video", "*.mp4 *.webm *.mov *.mkv"), ("All files", "*.*")),
        )
        if path:
            self.file_var.set(path)
            self._save_current_scene()
            self._refresh_scene_list()
            self._refresh_readiness()

    def _choose_workflow(self):
        path = filedialog.askopenfilename(
            title="اختيار ComfyUI API workflow",
            initialdir=str(ROOT),
            filetypes=(("JSON", "*.json"), ("All files", "*.*")),
        )
        if path:
            self.workflow_var.set(path)
            self._save_config()

    def _choose_output_dir(self):
        path = filedialog.askdirectory(title="اختيار مجلد النتائج", initialdir=str(ROOT))
        if path:
            self.output_dir_var.set(path)
            self._save_config()

    def _open_local_config(self):
        self._save_config()
        try:
            os.startfile(LOCAL_CONFIG)
        except OSError as exc:
            messagebox.showerror("تعذر فتح الإعداد", str(exc))

    def _save_config(self):
        self._save_current_scene()
        self.config["comfyui_url"] = self.api_url_var.get().strip()
        self.config["workflow_file"] = self.workflow_var.get().strip()
        self.config["output_dir"] = self.output_dir_var.get().strip() or "generated"
        LOCAL_CONFIG.write_text(
            json.dumps(self.config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._refresh_scene_list()
        self._log(f"تم حفظ الإعدادات: {LOCAL_CONFIG.name}")
        self._refresh_readiness()

    def _refresh_readiness(self):
        if self.busy:
            return
        self._save_current_scene()
        self._save_config_silent()
        self.status_text.set("جارٍ فحص ComfyUI وFFmpeg وملفات الفيديو...")
        self.refresh_button.configure(state="disabled")
        config_snapshot = json.loads(json.dumps(self.config))
        no_render = self.no_render_var.get()
        threading.Thread(
            target=self._readiness_worker,
            args=(config_snapshot, no_render),
            daemon=True,
        ).start()

    def _save_config_silent(self):
        self.config["comfyui_url"] = self.api_url_var.get().strip()
        self.config["workflow_file"] = self.workflow_var.get().strip()
        self.config["output_dir"] = self.output_dir_var.get().strip() or "generated"
        LOCAL_CONFIG.write_text(
            json.dumps(self.config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _readiness_worker(self, config, no_render):
        issues = []
        api_url = config.get("comfyui_url", "http://127.0.0.1:8188").rstrip("/")
        try:
            with urllib.request.urlopen(f"{api_url}/system_stats", timeout=2) as response:
                response.read(1)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            issues.append("ComfyUI غير متصل")

        workflow = resolve_local_path(config.get("workflow_file", ""))
        if not workflow.is_file():
            issues.append("workflow API غير موجود")

        render = config.get("render", {})
        if render.get("enabled", True) and not no_render:
            if not shutil.which(render.get("ffmpeg", "ffmpeg")):
                issues.append("FFmpeg غير موجود")
            if not shutil.which(render.get("ffprobe", "ffprobe")):
                issues.append("ffprobe غير موجود")

        missing_videos = sum(
            not resolve_local_path(scene.get("file", "")).is_file()
            for scene in config.get("videos", [])
        )
        oauth_ready = (ROOT / "client_secrets.json").is_file()
        summary = {
            "issues": issues,
            "missing_videos": missing_videos,
            "oauth_ready": oauth_ready,
        }
        self.root.after(0, lambda: self._show_readiness(summary))

    def _show_readiness(self, summary):
        self.refresh_button.configure(state="normal")
        issues = summary["issues"]
        details = list(issues)
        if summary["missing_videos"]:
            details.append(f"{summary['missing_videos']} فيديو ناقص")
        if not summary["oauth_ready"]:
            details.append("OAuth YouTube غير مهيأ")
        if issues:
            self.status_text.set("التوليد غير جاهز: " + "، ".join(details))
        elif details:
            self.status_text.set("التوليد جاهز؛ يلزم استكمال الرفع: " + "، ".join(details))
        else:
            self.status_text.set("التوليد والرفع جاهزان")
        if not self.busy:
            self.generate_button.configure(state="normal" if not issues else "disabled")
            upload_ready = summary["missing_videos"] == 0 and summary["oauth_ready"]
            self.upload_button.configure(state="normal" if upload_ready else "disabled")
        self._log(
            f"فحص الجاهزية: {len(issues)} عوائق للتوليد، "
            f"{summary['missing_videos']} ملفات فيديو ناقصة، "
            f"OAuth {'متوفر' if summary['oauth_ready'] else 'غير موجود'}."
        )

    def _generate(self):
        self._save_config()
        command = [sys.executable, "-u", str(ROOT / "pipeline.py"), "--config", str(LOCAL_CONFIG)]
        if self.no_render_var.get():
            command.append("--no-render")
        self._start_process(command, "التوليد")

    def _upload(self):
        self._save_config()
        if not (ROOT / "client_secrets.json").is_file():
            messagebox.showerror(
                "OAuth غير مهيأ",
                "ضع client_secrets.json محليًا من Google Cloud Console قبل الرفع. لا ترفعه إلى GitHub.",
            )
            return
        privacy = self.privacy_var.get()
        if privacy == "public" and not messagebox.askyesno(
            "تأكيد النشر العام",
            "سيُنشر كل فيديو موجود للعامة. هل راجعت الملفات والعناوين وتصنيف الأطفال؟",
        ):
            return
        try:
            manifest = build_upload_manifest(self.config, privacy)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("الفيديوهات غير جاهزة", str(exc))
            return
        UPLOAD_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        UPLOAD_MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        command = [
            sys.executable,
            "-u",
            str(ROOT / "upload_shorts.py"),
            "--config",
            str(UPLOAD_MANIFEST),
            "--privacy",
            privacy,
        ]
        self._start_process(command, "الرفع")

    def _start_process(self, command, operation):
        if self.busy:
            return
        self.busy = True
        self.generate_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.progress.start(12)
        self._log(f"بدء {operation}: {' '.join(command)}")
        try:
            self.process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            self._finish_process(f"تعذر تشغيل العملية: {exc}")
            return
        threading.Thread(target=self._read_process_output, daemon=True).start()
        self.root.after(100, self._drain_output)

    def _read_process_output(self):
        if not self.process or not self.process.stdout:
            return
        for line in self.process.stdout:
            self.output_queue.put(line.rstrip())
        self.output_queue.put(None)

    def _drain_output(self):
        finished = False
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if line is None:
                finished = True
            elif line:
                self._log(line)
        if finished and self.process:
            code = self.process.wait()
            self.process = None
            self._finish_process(f"انتهت العملية برمز {code}.")
            self._refresh_readiness()
        elif self.busy:
            self.root.after(100, self._drain_output)

    def _finish_process(self, message):
        self._log(message)
        self.busy = False
        self.progress.stop()
        self.generate_button.configure(state="normal")
        self.upload_button.configure(state="normal")
        self.refresh_button.configure(state="normal")

    def _log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _open_output(self):
        output_dir = resolve_local_path(self.config.get("output_dir", "generated"))
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(output_dir)
        except OSError as exc:
            messagebox.showerror("تعذر فتح المجلد", str(exc))

    def _close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("عملية جارية", "هل تريد إيقاف العملية وإغلاق اللوحة؟"):
                return
            self.process.terminate()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ShortsControlPanel(root)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        messagebox.showerror("تعذر تحميل الإعدادات", str(exc))
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())