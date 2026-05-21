@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo MinerU 777 Desktop UI
echo ========================================
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found.
    echo Expected: .venv\Scripts\python.exe
    echo.
    echo This launcher only starts the UI. It does not create or install the MinerU environment.
    pause
    exit /b 1
)

if not exist "%~dp0desktop_mineru.py" (
    echo [ERROR] desktop_mineru.py was not found.
    pause
    exit /b 1
)

if not exist "%~dp0mineru.json" (
    echo [ERROR] mineru.json was not found.
    echo Copy mineru.template.json to mineru.json and configure your local model directory first.
    pause
    exit /b 1
)

echo Starting UI...
echo Logs:
echo   desktop_ui_start.log
echo   desktop_ui_error.log
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_desktop_ui.ps1" 1>"%~dp0desktop_ui_start.log" 2>"%~dp0desktop_ui_error.log"
if errorlevel 1 (
    echo.
    echo MinerU 777 desktop UI failed to start.
    echo Error log: "%~dp0desktop_ui_error.log"
    pause
    exit /b 1
)
