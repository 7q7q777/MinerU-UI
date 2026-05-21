@echo off
setlocal
cd /d "%~dp0"
echo Starting MinerU 777 desktop UI...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_desktop_ui.ps1" 1>"%~dp0desktop_ui_start.log" 2>"%~dp0desktop_ui_error.log"
if errorlevel 1 (
    echo.
    echo MinerU 777 desktop UI failed to start.
    echo Error log: "%~dp0desktop_ui_error.log"
    pause
)
