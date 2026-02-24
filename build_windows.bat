@echo off
chcp 65001 >nul 2>&1
title ITN Fitness - Windows Build

echo ========================================
echo   ITN Fitness Announcement System
echo   Windows Build Script v1.0.0
echo ========================================
echo.

cd /d "%~dp0"

:: ================================================================
:: 1. Python check
:: ================================================================
echo [1/4] Checking build environment...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   %%i found
echo.

:: ================================================================
:: 2. Prepare venv and PyInstaller
:: ================================================================
echo [2/4] Preparing build environment...

if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat

python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet

echo   Build environment ready
echo.

:: ================================================================
:: 3. Clean previous build
:: ================================================================
echo [3/4] Cleaning previous build...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "*.spec" del /q *.spec
echo   Clean done
echo.

:: ================================================================
:: 4. PyInstaller build
:: ================================================================
echo [4/4] Building with PyInstaller...
echo   (This may take 2-5 minutes)
echo.

pyinstaller ^
    --name="ITN_Fitness" ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --add-data="config;config" ^
    --add-data="assets;assets" ^
    --add-data="remote/templates;remote/templates" ^
    --hidden-import=vlc ^
    --hidden-import=edge_tts ^
    --hidden-import=yt_dlp ^
    --hidden-import=schedule ^
    --hidden-import=yaml ^
    --hidden-import=pydub ^
    --hidden-import=fastapi ^
    --hidden-import=uvicorn ^
    --hidden-import=bcrypt ^
    --hidden-import=multipart ^
    --hidden-import=jinja2 ^
    --hidden-import=tkinter ^
    --hidden-import=aiohttp ^
    --collect-all=edge_tts ^
    --collect-all=yt_dlp ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

:: Copy config folder to dist (for user editing)
xcopy /E /I /Y config "dist\config" >nul

echo.
echo ========================================
echo   Build complete!
echo.
echo   Output: dist\ITN_Fitness\ITN_Fitness.exe
echo.
echo   To distribute: ZIP the dist\ITN_Fitness\ folder
echo ========================================
echo.

pause
