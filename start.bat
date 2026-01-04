@echo off
chcp 65001 >nul
title Voice Clone Studio

echo ========================================
echo   Voice Clone Studio
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.8+ from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

:: Create venv
if not exist "venv" (
    echo [1/4] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
)

:: Activate venv
call venv\Scripts\activate.bat

:: Check dependencies
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [2/4] Installing dependencies...
    echo This may take 2-3 minutes...
    echo.
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    echo.
    echo [OK] Dependencies installed
)

:: Create directories
if not exist "voice_clones" mkdir voice_clones
if not exist "voice_clones\output" mkdir voice_clones\output
if not exist "voice_clones\voices" mkdir voice_clones\voices
if not exist "voice_clones\models" mkdir voice_clones\models

:: Create config
if not exist "voice_clones\config.json" (
    echo [3/4] Creating config file...
    copy config.example.json voice_clones\config.json >nul
    echo [OK] Config created
)

:: Check Whisper model
echo [4/4] Checking Whisper model...
python check_whisper.py
if errorlevel 1 (
    echo.
    echo ========================================
    echo   Whisper Model Not Found
    echo ========================================
    echo.
    echo Whisper model is needed for subtitle timestamps.
    echo.
    echo Model location: voice_clones\models\
    echo.
    echo === Download Options ===
    echo.
    echo 1. China Mirror (Recommended):
    echo    https://hf-mirror.com/Systran/faster-whisper-small
    echo.
    echo 2. Official HuggingFace:
    echo    https://huggingface.co/Systran/faster-whisper-small
    echo.
    echo === Manual Download Steps ===
    echo.
    echo 1. Download all files from the link above
    echo 2. Create folder: voice_clones\models\faster-whisper-small\
    echo 3. Put all downloaded files in that folder
    echo 4. Restart this script
    echo.
    echo === Or Continue Without Whisper ===
    echo.
    echo Press any key to continue without Whisper...
    echo (Subtitles will use estimated timestamps)
    echo.
    pause
)

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

:: Start server
python voice_clone_flask.py

pause
