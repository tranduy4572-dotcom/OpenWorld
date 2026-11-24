@echo off
setlocal
cd /d "%~dp0"
echo OpenWorld Clean - local simulation
echo.
python -B examples\r0_agent_cycle.py
if errorlevel 1 (
    echo.
    echo Run failed. Check that Python 3.11 or newer is installed.
)
echo.
pause
