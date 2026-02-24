@echo off
chcp 65001 >nul 2>&1
title ITN Fitness

echo ========================================
echo   ITN Fitness Auto Announcement System
echo   v1.0.0
echo ========================================
echo.

cd /d "%~dp0"

:: ================================================================
:: STEP 1: Python check
:: ================================================================
echo [STEP 1/3] Python...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found.
    echo   Download: https://www.python.org/downloads/
    echo   Install with "Add Python to PATH" checked!
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   %PYVER% OK
echo.

:: ================================================================
:: STEP 2: VLC check
:: ================================================================
echo [STEP 2/3] VLC Media Player...

if exist "C:\Program Files\VideoLAN\VLC\vlc.exe" (
    echo   VLC OK
) else if exist "C:\Program Files (x86)\VideoLAN\VLC\vlc.exe" (
    echo   VLC OK
) else (
    echo [ERROR] VLC Media Player not found.
    echo   Download: https://www.videolan.org/vlc/
    echo.
    pause
    exit /b 1
)
echo.

:: ================================================================
:: STEP 3: Install packages and run
:: ================================================================
echo [STEP 3/3] Packages...
echo.

if not exist "venv" (
    echo   First run - setting up environment...
    echo   This may take 1-2 minutes.
    echo.

    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )

    call venv\Scripts\activate.bat

    echo   Upgrading pip...
    python -m pip install --upgrade pip --quiet

    echo   Installing packages...
    python -m pip install -r requirements.txt --quiet

    if %errorlevel% neq 0 (
        echo.
        echo   Retrying install...
        python -m pip install -r requirements.txt --quiet
        if %errorlevel% neq 0 (
            echo [ERROR] Package install failed.
            echo   Manual install: venv\Scripts\activate ^& pip install -r requirements.txt
            pause
            exit /b 1
        )
    )

    echo.
    echo   Setup complete!
    echo.
) else (
    call venv\Scripts\activate.bat
    echo   Environment activated.

    python -c "import vlc, schedule, yaml, edge_tts" 2>nul
    if %errorlevel% neq 0 (
        echo   Some packages missing. Reinstalling...
        python -m pip install -r requirements.txt --quiet
    ) else (
        echo   Packages OK
    )
)
echo.

:: Create default directories
if not exist "assets\announcements\general" mkdir "assets\announcements\general"
if not exist "assets\announcements\safety" mkdir "assets\announcements\safety"
if not exist "assets\announcements\class" mkdir "assets\announcements\class"
if not exist "assets\announcements\event" mkdir "assets\announcements\event"
if not exist "assets\announcements\emergency" mkdir "assets\announcements\emergency"
if not exist "logs" mkdir "logs"

echo ========================================
echo   Starting system...
echo ========================================
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] System exited with error code: %errorlevel%
    echo.
    echo Troubleshooting:
    echo   1. Check VLC installation
    echo   2. Check internet connection
    echo   3. Check config\ folder
    echo.
) else (
    echo.
    echo System stopped normally.
    echo.
)

pause
