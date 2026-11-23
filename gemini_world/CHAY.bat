@echo off
chcp 65001 >nul
set PYTHONDONTWRITEBYTECODE=1
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python -B "app\menu.py"
) else (
    py -3 -B "app\menu.py"
)
if errorlevel 1 pause
