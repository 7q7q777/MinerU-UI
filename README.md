# MinerU 777 Desktop UI

This is a Windows desktop UI overlay for an existing MinerU installation.

## What it does

- Chinese desktop window with a personalized `777` title
- Theme-based Tkinter UI via `ttkbootstrap`
- Input/output selectors
- Language, mode, and backend selectors
- GPU-oriented environment setup
- Markdown-only output cleanup
- Local image embedding into Markdown as `data:image/...;base64,...`
- UTF-8 with BOM rewrite for Windows editors
- `.bat` and `.ps1` launchers

## Files

```text
desktop_mineru.py
start_desktop_ui.bat
start_desktop_ui.ps1
requirements-ui.txt
mineru.template.json
tests/
```

## Requirements

- Windows 10/11
- Python 3.10+
- An existing MinerU environment in `.venv`
- MinerU CLI available at `.venv\Scripts\mineru.exe`

## Install

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
```

Copy the template config:

```powershell
Copy-Item mineru.template.json mineru.json
```

Then edit `mineru.json` and point `models-dir.pipeline` to your local model folder.

## Start

Double-click:

```text
start_desktop_ui.bat
```

## Model download sources

Official MinerU:

- https://github.com/opendatalab/MinerU
- https://opendatalab.github.io/MinerU/

Pipeline model sources:

- Hugging Face: https://huggingface.co/opendatalab/PDF-Extract-Kit-1.0
- ModelScope: https://modelscope.cn/models/OpenDataLab/PDF-Extract-Kit
- PDF-Extract-Kit: https://github.com/opendatalab/PDF-Extract-Kit

Example download commands:

```powershell
git lfs install
git clone https://huggingface.co/opendatalab/PDF-Extract-Kit-1.0
git clone https://www.modelscope.cn/opendatalab/PDF-Extract-Kit.git
```

## Privacy

This repository is intended for public upload and must not contain:

- virtual environments
- model files or caches
- output files
- logs
- `mineru.json`
- user documents
- machine-specific absolute paths
- usernames or device names

`.gitignore` already excludes these items.

## Test

```powershell
.venv\Scripts\python.exe -m pytest tests\test_desktop_mineru.py
```
