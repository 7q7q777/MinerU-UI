# MinerU 777 Desktop UI

中文 / English

这是一个面向 Windows 的 MinerU 桌面界面覆盖包。它为已有的 MinerU 安装增加中文 UI、主题外观、总进度条和 Markdown 后处理。

This is a Windows desktop UI overlay for an existing MinerU installation. It adds a Chinese UI, theme styling, a global progress bar, and Markdown post-processing.

## 功能 / Features

- 中文桌面窗口，标题为 `777 · MinerU 文档解析工作台`
- 基于 `ttkbootstrap` 的主题化 Tkinter UI
- 输入/输出目录选择
- 支持单文件、多文件和文件夹批量处理
- 语言、模式和后端选择
- GPU 环境变量启动
- 解析完成后只保留 Markdown 文件
- 将本地图片嵌入为 `data:image/...;base64,...`
- Markdown 统一写为 `UTF-8 with BOM`
- `.bat` 和 `.ps1` 启动脚本

- Chinese desktop window with a personalized `777` title
- Theme-based Tkinter UI via `ttkbootstrap`
- Input/output selectors
- Single-file, multi-file, and folder batch processing
- Language, mode, and backend selectors
- GPU-oriented environment setup
- Keep Markdown only after parsing
- Embed local images into Markdown as `data:image/...;base64,...`
- Rewrite Markdown as `UTF-8 with BOM`
- `.bat` and `.ps1` launchers

## 文件 / Files

```text
desktop_mineru.py
start_desktop_ui.bat
MinerU文档解析工作台v2.0 -777.bat
start_desktop_ui.ps1
requirements-ui.txt
mineru.template.json
tests/
```

## 环境要求 / Requirements

- Windows 10/11
- Python 3.10+
- An existing MinerU environment in `.venv`
- MinerU CLI available at `.venv\Scripts\mineru.exe`

## 安装 / Install

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
```

复制模板配置 / Copy the template config:

```powershell
Copy-Item mineru.template.json mineru.json
```

然后编辑 `mineru.json`，把 `models-dir.pipeline` 指向你的本地模型目录。

Then edit `mineru.json` and point `models-dir.pipeline` to your local model folder.

## 启动 / Start

双击运行：

```text
MinerU文档解析工作台v2.0 -777.bat
```

## 批量处理 / Batch Processing

界面提供三种输入方式：

- `选择文件`：处理单个文档
- `批量文件`：一次选择多个文档
- `选择文件夹`：递归收集文件夹中的支持格式文件

The UI provides three input modes:

- `选择文件`: process one document
- `批量文件`: select multiple documents at once
- `选择文件夹`: recursively collect supported files from a folder

批量处理会按顺序逐个调用 MinerU。总进度条会综合显示当前文件进度和整体文件数量进度。

Batch processing runs MinerU sequentially for each file. The global progress bar combines the current file progress with the total file count.

Double-click:

```text
MinerU文档解析工作台v2.0 -777.bat
```

## 模型来源 / Model Sources

官方 MinerU / Official MinerU:

- https://github.com/opendatalab/MinerU
- https://opendatalab.github.io/MinerU/

PDF-Extract-Kit / Pipeline model sources:

- Hugging Face: https://huggingface.co/opendatalab/PDF-Extract-Kit-1.0
- ModelScope: https://modelscope.cn/models/OpenDataLab/PDF-Extract-Kit
- PDF-Extract-Kit: https://github.com/opendatalab/PDF-Extract-Kit

示例下载命令 / Example download commands:

```powershell
git lfs install
git clone https://huggingface.co/opendatalab/PDF-Extract-Kit-1.0
git clone https://www.modelscope.cn/opendatalab/PDF-Extract-Kit.git
```

## 隐私 / Privacy

这个仓库用于公开上传，不应包含：

- 虚拟环境
- 模型文件或缓存
- 输出文件
- 日志
- `mineru.json`
- 用户文档
- 机器相关绝对路径
- 用户名或设备名

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

## 测试 / Test

```powershell
.venv\Scripts\python.exe -m pytest tests\test_desktop_mineru.py
```
