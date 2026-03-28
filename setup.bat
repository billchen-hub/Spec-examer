@echo off
chcp 65001 >nul
echo ================================
echo   Spec Benchmark - 環境安裝
echo ================================
echo.
echo 正在安裝 Python 套件...
pip install -r requirements.txt
echo.
echo ================================
echo   安裝完成！
echo   請先編輯 config.yaml 填入 Nexus 認證資訊
echo ================================
pause
