$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:CONDA_AUTO_ACTIVATE_BASE = "false"
$env:CONDA_SHLVL = "0"

if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) {
    throw "Virtual environment not found. Create .venv and install MinerU before starting the UI."
}

& (Join-Path $Root ".venv\Scripts\python.exe") (Join-Path $Root "desktop_mineru.py")
