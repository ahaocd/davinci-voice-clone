@echo off
chcp 65001 >nul 2>&1
title Voice Clone Studio
color 0A

echo.
echo ========================================
echo   Voice Clone Studio
echo ========================================
echo.

:: ============================================
:: Step 1: Find Python
:: ============================================
set PYTHON_CMD=

:: Try python command
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :python_found
)

:: Try py command
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :python_found
)

:: Try common paths
if exist "D:\python\python.exe" (
    set PYTHON_CMD=D:\python\python.exe
    goto :python_found
)

if exist "C:\Python312\python.exe" (
    set PYTHON_CMD=C:\Python312\python.exe
    goto :python_found
)

if exist "C:\Python311\python.exe" (
    set PYTHON_CMD=C:\Python311\python.exe
    goto :python_found
)

if exist "C:\Python310\python.exe" (
    set PYTHON_CMD=C:\Python310\python.exe
    goto :python_found
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    goto :python_found
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    goto :python_found
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
    goto :python_found
)

:: Python not found
echo [ERROR] Python not found!
echo.
echo Please install Python 3.8 or higher from:
echo https://www.python.org/downloads/
echo.
echo IMPORTANT: Check "Add Python to PATH" during installation!
echo.
pause
start https://www.python.org/downloads/
exit

:python_found
echo [OK] Found Python: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

:: ============================================
:: Step 2: Create/Check Virtual Environment
:: ============================================
if exist "venv\Scripts\activate.bat" (
    echo [OK] Virtual environment exists
    goto :venv_ok
)

echo [1/3] Creating virtual environment...
echo This may take 1-2 minutes...

:: Delete corrupted venv if exists
if exist "venv" (
    echo Cleaning up corrupted venv...
    rmdir /s /q venv
)

:: Try to create venv with pip first
%PYTHON_CMD% -m venv venv >nul 2>&1

:: Check if venv was created
if not exist "venv\Scripts\python.exe" (
    echo [WARN] Standard venv creation failed, trying without pip...
    %PYTHON_CMD% -m venv venv --without-pip >nul 2>&1
    
    if not exist "venv\Scripts\python.exe" (
        echo [ERROR] Failed to create virtual environment!
        echo.
        echo Possible solutions:
        echo   1. Run as Administrator
        echo   2. Disable antivirus temporarily
        echo   3. Reinstall Python with "pip" option checked
        echo.
        pause
        exit
    )
    
    :: Install pip manually
    echo Installing pip manually...
    curl -s https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    if exist "get-pip.py" (
        venv\Scripts\python.exe get-pip.py >nul 2>&1
        del get-pip.py
    )
)

:venv_ok

:: ============================================
:: Step 3: Activate Virtual Environment
:: ============================================
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment!
    echo.
    echo Deleting corrupted venv...
    rmdir /s /q venv
    echo Please run this script again.
    echo.
    pause
    exit
)

:: ============================================
:: Step 4: Install Dependencies
:: ============================================
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installing dependencies...
    echo This may take 2-3 minutes, please wait...
    echo.
    
    :: Upgrade pip first
    python -m pip install --upgrade pip -q >nul 2>&1
    
    :: Try with default PyPI
    echo Installing: flask, flask-cors, requests, mutagen, faster-whisper...
    pip install flask flask-cors requests mutagen faster-whisper
    if errorlevel 1 (
        echo.
        echo [WARN] Default PyPI failed, trying China mirror...
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple flask flask-cors requests mutagen faster-whisper
        if errorlevel 1 (
            echo.
            echo [ERROR] Failed to install dependencies!
            echo.
            echo Please check:
            echo   1. Internet connection is working
            echo   2. Firewall is not blocking pip
            echo   3. Disk space is sufficient
            echo.
            pause
            exit
        )
    )
    echo.
    echo [OK] Dependencies installed successfully
) else (
    echo [OK] Dependencies already installed
)

:: ============================================
:: Step 5: Create Directories
:: ============================================
if not exist "voice_clones" mkdir voice_clones
if not exist "voice_clones\output" mkdir voice_clones\output
if not exist "voice_clones\models" mkdir voice_clones\models

:: Create config file
if not exist "voice_clones\config.json" (
    if exist "config.example.json" (
        copy config.example.json voice_clones\config.json >nul
        echo [OK] Config file created
    )
)

:: ============================================
:: Step 6: Start Server
:: ============================================
echo [3/3] Starting server...
echo.
echo ========================================
echo   Server started!
echo   Open: http://localhost:7860
echo   Press Ctrl+C to stop
echo ========================================
echo.

python voice_clone_flask.py

:: ============================================
:: Error Handling
:: ============================================
if errorlevel 1 (
    echo.
    echo ========================================
    echo   [ERROR] Server crashed!
    echo ========================================
    echo.
    echo Common issues:
    echo   1. Port 7860 already in use
    echo   2. Missing config file
    echo   3. Python version too old
    echo.
    echo Try:
    echo   - Close other programs using port 7860
    echo   - Check voice_clones\config.json exists
    echo   - Update Python to 3.8 or higher
    echo.
)

pause
