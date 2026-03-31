@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   Spec Benchmark Exam System
echo ========================================
echo.
echo   1. Full exam (answer + judge by Nexus)
echo   2. Answer only (judge later by Claude Code)
echo   3. Generate questions (Nexus AI creates question bank)
echo.
set /p choice="  Select mode (1/2/3): "

if "%choice%"=="2" (
    echo.
    python exam_runner.py --answer-only
) else if "%choice%"=="3" (
    echo.
    set /p specfile="  Spec file path: "
    python exam_runner.py --generate %specfile%
) else (
    echo.
    python exam_runner.py
)

echo.
pause
