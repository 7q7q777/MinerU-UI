from __future__ import annotations

import base64
import os
import queue
import re
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import ttkbootstrap as tb
except ImportError:
    tb = None


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "output"
APP_TITLE = "MinerU 777 文档解析工作台"
THEME_NAME = "flatly"
SUPPORTED_FILETYPES = [
    ("支持的文档", "*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.docx *.pptx *.xlsx"),
    ("PDF 文件", "*.pdf"),
    ("图片", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
    ("Office 文件", "*.docx *.pptx *.xlsx"),
    ("所有文件", "*.*"),
]
LANGUAGES = [
    ("中文", "ch"),
    ("英文", "en"),
    ("繁体中文", "chinese_cht"),
    ("日文", "japan"),
    ("韩文", "korean"),
]
METHODS = ["auto", "txt", "ocr"]
BACKENDS = ["pipeline", "vlm-http-client", "hybrid-http-client", "vlm-auto-engine", "hybrid-auto-engine"]
MD_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def build_mineru_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "MINERU_TOOLS_CONFIG_JSON": str(ROOT / "mineru.json"),
            "MINERU_MODEL_SOURCE": "local",
            "MINERU_DEVICE_MODE": "cuda",
            "CUDA_VISIBLE_DEVICES": "0",
            "HF_HOME": str(ROOT / ".hf-cache"),
            "HUGGINGFACE_HUB_CACHE": str(ROOT / ".hf-cache" / "hub"),
            "MODELSCOPE_CACHE": str(ROOT / ".modelscope-cache"),
            "PIP_CACHE_DIR": str(ROOT / ".pip-cache"),
            "TORCH_HOME": str(ROOT / ".torch-cache"),
            "FTLANG_CACHE": str(ROOT / ".fasttext-cache"),
            "MINERU_PROCESSING_WINDOW_SIZE": "1",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    scripts_dir = ROOT / ".venv" / "Scripts"
    env["PATH"] = f"{scripts_dir}{os.pathsep}{env.get('PATH', '')}"
    return env


def build_mineru_command(input_path: Path, output_dir: Path, backend: str, method: str, lang: str) -> list[str]:
    mineru_exe = ROOT / ".venv" / "Scripts" / "mineru.exe"
    return [
        str(mineru_exe),
        "-p",
        str(input_path),
        "-o",
        str(output_dir),
        "-b",
        backend,
        "-m",
        method,
        "-l",
        lang,
    ]


def _guess_image_mime(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")


def embed_images_as_data_uris(md_path: Path) -> bool:
    md_text = md_path.read_text(encoding="utf-8-sig")
    base_dir = md_path.parent

    def replace(match: re.Match[str]) -> str:
        alt_text, raw_target = match.groups()
        target = raw_target.strip()
        if target.startswith("data:") or target.startswith("http://") or target.startswith("https://"):
            return match.group(0)
        image_path = (base_dir / target).resolve()
        if not image_path.exists() or not image_path.is_file():
            return match.group(0)
        mime = _guess_image_mime(image_path)
        payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"![{alt_text}](data:{mime};base64,{payload})"

    new_text = MD_IMAGE_PATTERN.sub(replace, md_text)
    if new_text == md_text:
        return False
    md_path.write_text(new_text, encoding="utf-8-sig")
    return True


def normalize_markdown_encoding(md_path: Path) -> None:
    md_text = md_path.read_text(encoding="utf-8-sig")
    md_path.write_text(md_text, encoding="utf-8-sig")


def keep_only_markdown_outputs(output_root: Path) -> list[Path]:
    kept: list[Path] = []
    if not output_root.exists():
        return kept
    for md_path in output_root.rglob("*.md"):
        if md_path.is_file():
            embed_images_as_data_uris(md_path)
            normalize_markdown_encoding(md_path)
            kept.append(md_path)
    for path in sorted(output_root.rglob("*"), reverse=True):
        if path.is_file() and path.suffix.lower() != ".md":
            path.unlink()
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    return kept


def extract_progress(line: str) -> tuple[int, int] | None:
    matches = re.findall(r"(\d+)/(\d+)", line)
    if not matches:
        return None
    current, total = matches[-1]
    try:
        return int(current), int(total)
    except ValueError:
        return None


class MinerUDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.process: subprocess.Popen[str] | None = None
        self.worker: threading.Thread | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.lang_label_var = tk.StringVar(value=LANGUAGES[0][0])
        self.method_var = tk.StringVar(value="auto")
        self.backend_var = tk.StringVar(value="pipeline")
        self.status_var = tk.StringVar(value="就绪")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="0 / 0")

        self._configure_style()
        self._build_ui()
        self._poll_logs()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"))
            style.configure("Subtitle.TLabel", font=("Microsoft YaHei UI", 10))
            style.configure("Section.TLabelframe.Label", font=("Microsoft YaHei UI", 10, "bold"))
            style.configure("Status.TLabel", font=("Microsoft YaHei UI", 10, "bold"))
            style.configure("Accent.Horizontal.TProgressbar", thickness=16)
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.root, padding=18)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="777 · MinerU 文档解析工作台", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="GPU 加速 · Markdown 输出 · 图片内嵌 · 中文界面",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")

        file_card = ttk.LabelFrame(outer, text="文件与输出", padding=14, style="Section.TLabelframe")
        file_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        file_card.columnconfigure(1, weight=1)

        ttk.Label(file_card, text="输入文件").grid(row=0, column=0, sticky="w", pady=(0, 10))
        ttk.Entry(file_card, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=10, pady=(0, 10))
        ttk.Button(file_card, text="选择文件", command=self._browse_input).grid(row=0, column=2, sticky="ew", pady=(0, 10))

        ttk.Label(file_card, text="输出目录").grid(row=1, column=0, sticky="w")
        ttk.Entry(file_card, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", padx=10)
        ttk.Button(file_card, text="选择目录", command=self._browse_output).grid(row=1, column=2, sticky="ew")

        settings = ttk.LabelFrame(outer, text="解析设置", padding=14, style="Section.TLabelframe")
        settings.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        for col in range(6):
            settings.columnconfigure(col, weight=1)

        ttk.Label(settings, text="语言").grid(row=0, column=0, sticky="w")
        self.lang_box = ttk.Combobox(
            settings,
            textvariable=self.lang_label_var,
            values=[label for label, _ in LANGUAGES],
            state="readonly",
            width=12,
        )
        self.lang_box.grid(row=0, column=1, sticky="ew", padx=(8, 18))

        ttk.Label(settings, text="解析模式").grid(row=0, column=2, sticky="w")
        ttk.Combobox(settings, textvariable=self.method_var, values=METHODS, state="readonly", width=10).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(8, 18),
        )

        ttk.Label(settings, text="后端").grid(row=0, column=4, sticky="w")
        ttk.Combobox(settings, textvariable=self.backend_var, values=BACKENDS, state="readonly", width=18).grid(
            row=0,
            column=5,
            sticky="ew",
            padx=(8, 0),
        )

        work_area = ttk.Frame(outer)
        work_area.grid(row=3, column=0, sticky="nsew")
        work_area.columnconfigure(0, weight=1)
        work_area.rowconfigure(1, weight=1)

        progress_card = ttk.LabelFrame(work_area, text="总进度", padding=14, style="Section.TLabelframe")
        progress_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        progress_card.columnconfigure(0, weight=1)

        actions = ttk.Frame(progress_card)
        actions.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        actions.columnconfigure(3, weight=1)
        self.start_button = ttk.Button(actions, text="开始解析", command=self.start_parse)
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button = ttk.Button(actions, text="停止", command=self.stop_parse, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="打开输出目录", command=self.open_output).grid(row=0, column=2, padx=(0, 8))
        ttk.Label(actions, text="输出格式：仅 Markdown").grid(row=0, column=3, sticky="e")

        ttk.Progressbar(
            progress_card,
            variable=self.progress_var,
            maximum=100,
            style="Accent.Horizontal.TProgressbar",
        ).grid(row=1, column=0, sticky="ew")
        ttk.Label(progress_card, textvariable=self.progress_text_var, width=10, anchor="e").grid(
            row=1,
            column=1,
            padx=(10, 0),
        )

        log_card = ttk.LabelFrame(work_area, text="运行日志", padding=10, style="Section.TLabelframe")
        log_card.grid(row=1, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_card,
            height=18,
            wrap="word",
            state="disabled",
            bg="#f8fafc",
            fg="#0f172a",
            insertbackground="#0f172a",
            relief="flat",
            padx=10,
            pady=10,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_card, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(title="选择文档", filetypes=SUPPORTED_FILETYPES)
        if path:
            self.input_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录", initialdir=self.output_var.get() or str(DEFAULT_OUTPUT))
        if path:
            self.output_var.set(path)

    def _language_code(self) -> str:
        selected = self.lang_label_var.get()
        return dict(LANGUAGES).get(selected, "ch")

    def _validate(self) -> tuple[Path, Path] | None:
        input_path = Path(self.input_var.get().strip())
        output_dir = Path(self.output_var.get().strip())
        mineru_exe = ROOT / ".venv" / "Scripts" / "mineru.exe"
        config_path = ROOT / "mineru.json"

        if not input_path.exists() or not input_path.is_file():
            return self._validation_error("请选择一个存在的输入文件。")
        if not str(output_dir):
            return self._validation_error("请选择输出目录。")
        if not mineru_exe.exists():
            return self._validation_error(f"找不到 MinerU 可执行文件: {mineru_exe}")
        if not config_path.exists():
            return self._validation_error(f"找不到 MinerU 配置文件: {config_path}")
        output_dir.mkdir(parents=True, exist_ok=True)
        return input_path, output_dir

    def _validation_error(self, message: str) -> None:
        self._append_log(f"错误：{message}\n")
        messagebox.showerror(APP_TITLE, message)
        return None

    def start_parse(self) -> None:
        if self.process is not None:
            return

        validated = self._validate()
        if validated is None:
            return

        input_path, output_dir = validated
        command = build_mineru_command(
            input_path=input_path,
            output_dir=output_dir,
            backend=self.backend_var.get(),
            method=self.method_var.get(),
            lang=self._language_code(),
        )
        self.progress_var.set(0.0)
        self.progress_text_var.set("0 / 0")
        self._append_log("\n开始解析...\n")
        self._append_log(" ".join(f'"{part}"' if " " in part else part for part in command) + "\n\n")
        self._set_running(True)

        self.worker = threading.Thread(target=self._run_process, args=(command,), daemon=True)
        self.worker.start()

    def _run_process(self, command: list[str]) -> None:
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(ROOT),
                env=build_mineru_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.log_queue.put(line)
            exit_code = self.process.wait()
            if exit_code == 0:
                self.log_queue.put("\nMinerU 解析完成。\n")
            else:
                self.log_queue.put(f"\nMinerU 退出，返回码 {exit_code}。\n")
        except Exception as exc:
            self.log_queue.put(f"\nERROR: {exc}\n")
        finally:
            self.log_queue.put("__MINERU_DONE__")

    def stop_parse(self) -> None:
        if self.process is None:
            return
        self._append_log("\n正在停止 MinerU...\n")
        self.process.terminate()

    def open_output(self) -> None:
        output_dir = Path(self.output_var.get().strip() or DEFAULT_OUTPUT)
        output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(output_dir)

    def _set_running(self, running: bool) -> None:
        self.status_var.set("运行中" if running else "就绪")
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def _poll_logs(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item == "__MINERU_DONE__":
                    if self.output_var.get().strip():
                        kept = keep_only_markdown_outputs(Path(self.output_var.get().strip()))
                        self._append_log(f"已整理输出：保留 {len(kept)} 个 Markdown 文件。\n")
                    self.progress_var.set(100.0)
                    self.progress_text_var.set("完成")
                    self.process = None
                    self._set_running(False)
                else:
                    progress = extract_progress(item)
                    if progress is not None:
                        current, total = progress
                        percent = 0.0 if total <= 0 else min(100.0, current / total * 100.0)
                        self.progress_var.set(percent)
                        self.progress_text_var.set(f"{current} / {total}")
                    self._append_log(item)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_logs)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def create_root() -> tk.Tk:
    if tb is not None:
        return tb.Window(themename=THEME_NAME)
    return tk.Tk()


def main() -> None:
    root = create_root()
    root.title(APP_TITLE)
    root.geometry("1080x720")
    root.minsize(900, 620)
    MinerUDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
