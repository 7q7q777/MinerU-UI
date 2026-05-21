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
SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".docx", ".pptx", ".xlsx"}
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
    python_exe = ROOT / ".venv" / "Scripts" / "python.exe"
    return [
        str(python_exe),
        "-m",
        "mineru.cli.client",
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


def collect_supported_files(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES)


def summarize_input_paths(paths: list[Path]) -> str:
    if not paths:
        return ""
    if len(paths) == 1:
        return str(paths[0])
    return f"已选择 {len(paths)} 个文件"



def expected_output_roots(input_paths: list[Path], output_dir: Path) -> list[Path]:
    return [output_dir / input_path.stem for input_path in input_paths]


def keep_current_task_markdown_outputs(input_paths: list[Path], output_dir: Path) -> list[Path]:
    kept: list[Path] = []
    for task_output_root in expected_output_roots(input_paths, output_dir):
        kept.extend(keep_only_markdown_outputs(task_output_root))
    return kept


def snapshot_markdown_outputs(output_dir: Path) -> dict[Path, int]:
    if not output_dir.exists():
        return {}
    return {path: path.stat().st_mtime_ns for path in output_dir.rglob("*.md") if path.is_file()}


def keep_changed_markdown_outputs(output_dir: Path, before: dict[Path, int]) -> list[Path]:
    changed: list[Path] = []
    for md_path in output_dir.rglob("*.md") if output_dir.exists() else []:
        if md_path.is_file() and before.get(md_path) != md_path.stat().st_mtime_ns:
            embed_images_as_data_uris(md_path)
            normalize_markdown_encoding(md_path)
            changed.append(md_path)
    return changed

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
        self.input_paths: list[Path] = []
        self.current_task_input_paths: list[Path] = []
        self.current_task_output_dir: Path | None = None
        self.markdown_snapshot: dict[Path, int] = {}
        self.stop_requested = False

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
            text="GPU 加速 · 批量处理 · Markdown 输出 · 图片内嵌 · 中文界面",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")

        file_card = ttk.LabelFrame(outer, text="文件与输出", padding=14, style="Section.TLabelframe")
        file_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        file_card.columnconfigure(1, weight=1)

        ttk.Label(file_card, text="输入文件").grid(row=0, column=0, sticky="w", pady=(0, 10))
        ttk.Entry(file_card, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=10, pady=(0, 10))
        input_actions = ttk.Frame(file_card)
        input_actions.grid(row=0, column=2, sticky="ew", pady=(0, 10))
        ttk.Button(input_actions, text="选择文件", command=self._browse_input).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(input_actions, text="批量文件", command=self._browse_inputs).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(input_actions, text="选择文件夹", command=self._browse_input_folder).grid(row=0, column=2)

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
        ttk.Label(progress_card, textvariable=self.progress_text_var, width=14, anchor="e").grid(
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
            self.input_paths = [Path(path)]
            self.input_var.set(summarize_input_paths(self.input_paths))

    def _browse_inputs(self) -> None:
        paths = filedialog.askopenfilenames(title="选择多个文档", filetypes=SUPPORTED_FILETYPES)
        if paths:
            self.input_paths = [Path(path) for path in paths]
            self.input_var.set(summarize_input_paths(self.input_paths))

    def _browse_input_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择批量输入文件夹")
        if folder:
            self.input_paths = collect_supported_files(Path(folder))
            self.input_var.set(summarize_input_paths(self.input_paths) or "未找到支持的文件")
            self._append_log(f"从文件夹收集到 {len(self.input_paths)} 个支持的文件。\n")

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录", initialdir=self.output_var.get() or str(DEFAULT_OUTPUT))
        if path:
            self.output_var.set(path)

    def _language_code(self) -> str:
        selected = self.lang_label_var.get()
        return dict(LANGUAGES).get(selected, "ch")

    def _validate(self) -> tuple[list[Path], Path] | None:
        input_paths = self.input_paths
        output_dir = Path(self.output_var.get().strip())
        python_exe = ROOT / ".venv" / "Scripts" / "python.exe"
        config_path = ROOT / "mineru.json"

        if not input_paths and self.input_var.get().strip():
            input_paths = [Path(self.input_var.get().strip())]
        input_paths = [path for path in input_paths if path.exists() and path.is_file()]

        if not input_paths:
            return self._validation_error("请选择一个或多个存在的输入文件。")
        if not str(output_dir):
            return self._validation_error("请选择输出目录。")
        if not python_exe.exists():
            return self._validation_error(f"??? Python ????: {python_exe}")
        if not config_path.exists():
            return self._validation_error(f"找不到 MinerU 配置文件: {config_path}")
        output_dir.mkdir(parents=True, exist_ok=True)
        return input_paths, output_dir

    def _validation_error(self, message: str) -> None:
        self._append_log(f"错误：{message}\n")
        messagebox.showerror(APP_TITLE, message)
        return None

    def start_parse(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return

        validated = self._validate()
        if validated is None:
            return

        input_paths, output_dir = validated
        self.current_task_input_paths = input_paths
        self.current_task_output_dir = output_dir
        self.markdown_snapshot = snapshot_markdown_outputs(output_dir)
        self.stop_requested = False
        self.progress_var.set(0.0)
        self.progress_text_var.set(f"0 / {len(input_paths)}")
        self._append_log(f"\n开始解析，共 {len(input_paths)} 个文件。\n")
        self._set_running(True)

        args = (input_paths, output_dir, self.backend_var.get(), self.method_var.get(), self._language_code())
        self.worker = threading.Thread(target=self._run_batch, args=args, daemon=True)
        self.worker.start()

    def _run_batch(self, input_paths: list[Path], output_dir: Path, backend: str, method: str, lang: str) -> None:
        total_files = len(input_paths)
        completed = 0
        failures = 0
        for index, input_path in enumerate(input_paths, start=1):
            if self.stop_requested:
                self.log_queue.put(f"\n已停止，剩余 {total_files - completed} 个文件未处理。\n")
                break
            command = build_mineru_command(input_path, output_dir, backend, method, lang)
            self.log_queue.put(f"\n[{index}/{total_files}] 开始解析：{input_path.name}\n")
            self.log_queue.put(" ".join(f'"{part}"' if " " in part else part for part in command) + "\n")
            exit_code = self._run_process(command, index - 1, total_files)
            if exit_code == 0:
                completed += 1
                self.log_queue.put(f"[{index}/{total_files}] 完成：{input_path.name}\n")
            else:
                failures += 1
                self.log_queue.put(f"[{index}/{total_files}] 失败，返回码 {exit_code}：{input_path.name}\n")
            self.log_queue.put(f"__MINERU_FILE_DONE__{completed}|{total_files}|{failures}")
        self.log_queue.put("__MINERU_DONE__")

    def _run_process(self, command: list[str], completed_before: int, total_files: int) -> int:
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
                progress = extract_progress(line)
                if progress is not None:
                    current, total = progress
                    self.log_queue.put(f"__MINERU_PROGRESS__{completed_before}|{total_files}|{current}|{total}")
                self.log_queue.put(line)
            return self.process.wait()
        except Exception as exc:
            self.log_queue.put(f"\nERROR: {exc}\n")
            return 1
        finally:
            self.process = None

    def stop_parse(self) -> None:
        self.stop_requested = True
        if self.process is not None:
            self._append_log("\n正在停止当前 MinerU 进程...\n")
            self.process.terminate()

    def open_output(self) -> None:
        output_dir = Path(self.output_var.get().strip() or DEFAULT_OUTPUT)
        output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(output_dir)

    def _set_running(self, running: bool) -> None:
        self.status_var.set("运行中" if running else "就绪")
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def _set_batch_progress(self, completed_before: int, total_files: int, current: int, total: int) -> None:
        page_fraction = 0.0 if total <= 0 else min(1.0, current / total)
        percent = min(100.0, (completed_before + page_fraction) / total_files * 100.0)
        self.progress_var.set(percent)
        self.progress_text_var.set(f"{completed_before}/{total_files} · {current}/{total}")

    def _poll_logs(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item == "__MINERU_DONE__":
                    if self.current_task_output_dir is not None:
                        kept = keep_changed_markdown_outputs(self.current_task_output_dir, self.markdown_snapshot)
                        self._append_log(f"Current task output cleaned: kept {len(kept)} Markdown file(s).\n")
                    self.progress_var.set(100.0)
                    self.progress_text_var.set("完成")
                    self._set_running(False)
                elif item.startswith("__MINERU_FILE_DONE__"):
                    completed, total, failures = [int(value) for value in item.removeprefix("__MINERU_FILE_DONE__").split("|")]
                    self.progress_var.set(min(100.0, completed / total * 100.0))
                    self.progress_text_var.set(f"{completed} / {total}")
                    if failures:
                        self.status_var.set(f"运行中 · 失败 {failures}")
                elif item.startswith("__MINERU_PROGRESS__"):
                    completed_before, total_files, current, total = [
                        int(value) for value in item.removeprefix("__MINERU_PROGRESS__").split("|")
                    ]
                    self._set_batch_progress(completed_before, total_files, current, total)
                else:
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
    root.geometry("1180x740")
    root.minsize(980, 640)
    MinerUDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
