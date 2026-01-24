@echo off
echo ========================================
echo   Voice Clone Studio - Debug Test
echo ========================================
echo.

:: 测试 1: 检查 Python
echo [TEST 1] Checking Python...
python --version
if errorlevel 1 (
    echo [FAIL] python command not found
    echo Trying python3...
    python3 --version
    if errorlevel 1 (
        echo [FAIL] python3 command not found
        echo Trying py...
        py --version
        if errorlevel 1 (
            echo [FAIL] No Python found!
            echo.
            echo Please install Python 3.8+ from:
            echo https://www.python.org/downloads/
            echo.
            goto :end
        ) else (
            echo [OK] Found: py
            set PYTHON_CMD=py
        )
    ) else (
        echo [OK] Found: python3
        set PYTHON_CMD=python3
    )
) else (
    echo [OK] Found: python
    set PYTHON_CMD=python
)

echo.
echo ========================================
echo   Python Command: %PYTHON_CMD%
echo ========================================
echo.

:: 测试 2: 检查文件
echo [TEST 2] Checking files...
if exist "voice_clone_flask.py" (
    echo [OK] voice_clone_flask.py found
) else (
    echo [FAIL] voice_clone_flask.py NOT found!
)

if exist "config.example.json" (
    echo [OK] config.example.json found
) else (
    echo [FAIL] config.example.json NOT found!
)

if exist "requirements.txt" (
    echo [OK] requirements.txt found
) else (
    echo [FAIL] requirements.txt NOT found!
)

echo.
echo ========================================
echo   Test Complete
echo ========================================
echo.

:end
echo Press any key to exit...
pause >nul
