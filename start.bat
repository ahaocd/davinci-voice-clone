@echo off
chcp 65001 >nul
title Voice Clone Studio

:: 设置日志文件
set LOGFILE=startup.log
echo ======================================== > %LOGFILE%
echo Voice Clone Studio Startup Log >> %LOGFILE%
echo Date: %date% %time% >> %LOGFILE%
echo ======================================== >> %LOGFILE%

echo ========================================
echo   Voice Clone Studio
echo ========================================
echo.
echo [INFO] Log file: %cd%\%LOGFILE%
echo.

:: 检查 Python
echo [1/5] Checking Python...
echo. >> %LOGFILE%
echo [STEP 1] Checking Python >> %LOGFILE%
python --version >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! >> %LOGFILE%
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.8+ from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    echo See %LOGFILE% for details.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [OK] Python %PYVER% found >> %LOGFILE%
echo [OK] Python %PYVER%

:: 创建虚拟环境
echo. >> %LOGFILE%
echo [STEP 2] Virtual Environment >> %LOGFILE%
if not exist "venv" (
    echo [2/5] Creating virtual environment...
    echo Creating venv... >> %LOGFILE%
    python -m venv venv >> %LOGFILE% 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to create venv >> %LOGFILE%
        echo [ERROR] Failed to create virtual environment
        echo See %LOGFILE% for details.
        pause
        exit /b 1
    )
    echo [OK] venv created >> %LOGFILE%
) else (
    echo [2/5] Virtual environment exists
    echo [OK] venv already exists >> %LOGFILE%
)

:: 激活虚拟环境
echo Activating venv... >> %LOGFILE%
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate venv >> %LOGFILE%
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] venv activated >> %LOGFILE%

:: 安装依赖
echo. >> %LOGFILE%
echo [STEP 3] Dependencies >> %LOGFILE%
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [3/5] Installing dependencies...
    echo This may take 2-3 minutes...
    echo.
    
    echo Installing flask flask-cors requests mutagen... >> %LOGFILE%
    python -m pip install --upgrade pip >> %LOGFILE% 2>&1
    python -m pip install flask flask-cors requests mutagen >> %LOGFILE% 2>&1
    if errorlevel 1 (
        echo [ERROR] pip install failed >> %LOGFILE%
        echo [ERROR] Failed to install dependencies
        echo.
        echo See %LOGFILE% for details.
        pause
        exit /b 1
    )
    echo [OK] Basic packages installed >> %LOGFILE%
    
    echo Installing faster-whisper... >> %LOGFILE%
    python -m pip install faster-whisper >> %LOGFILE% 2>&1
    if errorlevel 1 (
        echo [WARN] faster-whisper install failed >> %LOGFILE%
        echo [WARN] faster-whisper failed - subtitles will use estimated timestamps
    ) else (
        echo [OK] faster-whisper installed >> %LOGFILE%
    )
    echo [OK] Dependencies installed
) else (
    echo [3/5] Dependencies already installed
    echo [OK] Dependencies already installed >> %LOGFILE%
)

:: 创建目录
echo. >> %LOGFILE%
echo [STEP 4] Directories >> %LOGFILE%
echo [4/5] Creating directories...
if not exist "voice_clones" mkdir voice_clones
if not exist "voice_clones\output" mkdir voice_clones\output
if not exist "voice_clones\voices" mkdir voice_clones\voices
if not exist "voice_clones\models" mkdir voice_clones\models
echo [OK] Directories created >> %LOGFILE%

:: 创建配置文件
if not exist "voice_clones\config.json" (
    if exist "config.example.json" (
        copy config.example.json voice_clones\config.json >nul
        echo [OK] Config file created >> %LOGFILE%
    ) else (
        echo [WARN] config.example.json not found >> %LOGFILE%
    )
)

:: 检查 Whisper 模型
echo. >> %LOGFILE%
echo [STEP 5] Whisper Model >> %LOGFILE%
echo [5/5] Checking Whisper model...
python check_whisper.py >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo [WARN] Whisper model not found >> %LOGFILE%
    echo [WARN] Whisper model not found - using estimated timestamps
    echo.
    echo To enable accurate timestamps, download model from:
    echo https://hf-mirror.com/Systran/faster-whisper-small
    echo Put files in: voice_clones\models\faster-whisper-small\
    echo.
) else (
    echo [OK] Whisper model found >> %LOGFILE%
    echo [OK] Whisper model found
)

:: 启动服务器
echo. >> %LOGFILE%
echo [STEP 6] Starting Server >> %LOGFILE%
echo.
echo ========================================
echo   Starting Voice Clone Studio...
echo ========================================
echo.
echo   URL: http://localhost:7860
echo   Press Ctrl+C to stop
echo.
echo ========================================
echo.

echo Starting Flask server... >> %LOGFILE%
python voice_clone_flask.py 2>> %LOGFILE%
set EXITCODE=%errorlevel%

echo. >> %LOGFILE%
echo Server exited with code: %EXITCODE% >> %LOGFILE%
echo Exit time: %date% %time% >> %LOGFILE%

if %EXITCODE% neq 0 (
    echo.
    echo ========================================
    echo   [ERROR] Server crashed!
    echo ========================================
    echo.
    echo Exit code: %EXITCODE%
    echo.
    echo Common issues:
    echo   1. Port 7860 already in use
    echo   2. Missing dependencies
    echo   3. Config file error
    echo.
    echo Check %LOGFILE% for details.
    echo.
)

echo.
echo Press any key to exit...
pause >nul
