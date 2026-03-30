@echo off
chcp 65001 >nul
echo ================================
echo   Spec Benchmark - Setup
echo ================================
echo.
echo Installing Python packages...
pip install -r requirements.txt
echo.
echo ================================
echo   Setup complete!
echo   Please edit config.yaml to fill in Nexus credentials
echo ================================
pause
