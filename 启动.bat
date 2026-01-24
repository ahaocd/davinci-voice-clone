@echo off
title Voice Clone Studio
color 0A

echo.
echo ========================================
echo   Voice Clone Studio
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装 Python！
    echo.
    echo 请先安装 Python 3.8 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    echo.
    echo 安装时记得勾选 "Add Python to PATH"
    echo.
    pause
    start https://www.python.org/downloads/
    exit
)

:: 创建虚拟环境
if not exist "venv" (
    echo [1/3] 首次运行，正在安装...
    python -m venv venv
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装依赖
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [2/3] 正在安装依赖包...
    pip install flask flask-cors requests mutagen faster-whisper -q
)

:: 创建目录和配置
if not exist "voice_clones" mkdir voice_clones
if not exist "voice_clones\output" mkdir voice_clones\output
if not exist "voice_clones\models" mkdir voice_clones\models
if not exist "voice_clones\config.json" (
    if exist "config.example.json" copy config.example.json voice_clones\config.json >nul
)

:: 启动服务器
echo [3/3] 正在启动服务器...
echo.
echo ========================================
echo   服务器已启动！
echo   打开浏览器访问: http://localhost:7860
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.

python voice_clone_flask.py

pause
