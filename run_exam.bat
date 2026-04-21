@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
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

if "!choice!"=="2" (
    echo.
    python exam_runner.py --answer-only
) else if "!choice!"=="3" (
    echo.
    echo   Enter a spec file or folder path.
    echo   Supports: .pdf .md .txt .log (folders are scanned recursively)
    echo   For multiple files, run: python exam_runner.py --generate path1 path2 ...
    echo.
    set /p specfile="  Spec path: "
    python exam_runner.py --generate "!specfile!"
) else (
    echo.
    python exam_runner.py
)

echo.
endlocal
pause
