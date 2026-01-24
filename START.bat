@echo off
title Voice Clone Studio
color 0A

echo.
echo ========================================
echo   Voice Clone Studio
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.8+
    echo Download: https://www.python.org/downloads/
    echo.
    echo Remember to check "Add Python to PATH"
    echo.
    pause
    start https://www.python.org/downloads/
    exit
)

:: Create virtual environment
if not exist "venv" (
    echo [1/3] First run, installing...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install dependencies
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installing dependencies...
    pip install flask flask-cors requests mutagen faster-whisper -q
)

:: Create directories
if not exist "voice_clones" mkdir voice_clones
if not exist "voice_clones\output" mkdir voice_clones\output
if not exist "voice_clones\models" mkdir voice_clones\models
if not exist "voice_clones\config.json" (
    if exist "config.example.json" copy config.example.json voice_clones\config.json >nul
)

:: Start server
echo [3/3] Starting server...
echo.
echo ========================================
echo   Server started!
echo   Open: http://localhost:7860
echo   Press Ctrl+C to stop
echo ========================================
echo.

python voice_clone_flask.py

pause
