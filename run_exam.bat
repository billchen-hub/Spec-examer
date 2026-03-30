@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   Spec Benchmark Exam System
echo ========================================
echo.
echo   1. Full exam (answer + judge by Nexus)
echo   2. Answer only (judge later by Claude Code)
echo.
set /p choice="  Select mode (1/2): "

if "%choice%"=="2" (
    echo.
    python exam_runner.py --answer-only
) else (
    echo.
    python exam_runner.py
)

echo.
pause
