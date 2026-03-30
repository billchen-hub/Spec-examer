@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   Spec Benchmark 考試系統
echo ========================================
echo.
echo   1. 完整考試（答題 + Nexus 評分）
echo   2. 僅答題（帶回 Claude Code 評分）
echo.
set /p choice="  請選擇模式 (1/2): "

if "%choice%"=="2" (
    echo.
    python exam_runner.py --answer-only
) else (
    echo.
    python exam_runner.py
)

echo.
pause
