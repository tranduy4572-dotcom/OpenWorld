@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================
echo Tao thu muc OpenWorld_Clean - KHONG xoa ban goc
echo ===============================================
where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0tao_openworld_clean.py" %*
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Khong tim thay Python. Hay cai Python 3.11+.
    ) else (
        python "%~dp0tao_openworld_clean.py" %*
    )
)
echo.
echo Nhan phim bat ky de dong cua so...
pause >nul
