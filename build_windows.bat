@echo off
chcp 65001 >nul 2>&1
title ITN Fitness 안내방송 시스템 - Windows 빌드

echo ╔════════════════════════════════════════╗
echo ║  ITN Fitness 안내방송 시스템             ║
echo ║  Windows 빌드 스크립트 v1.0.0           ║
echo ╚════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ================================================================
:: 1. Python 확인
:: ================================================================
echo [1/4] 빌드 환경 확인 중...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python이 설치되지 않았습니다.
    echo https://www.python.org/downloads/ 에서 설치해주세요.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   %%i 발견
echo.

:: ================================================================
:: 2. 가상환경 및 PyInstaller 준비
:: ================================================================
echo [2/4] 빌드 환경 준비 중...

if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat

python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet

echo   빌드 환경 준비 완료
echo.

:: ================================================================
:: 3. 기존 빌드 정리
:: ================================================================
echo [3/4] 기존 빌드 정리 중...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "*.spec" del /q *.spec
echo   정리 완료
echo.

:: ================================================================
:: 4. PyInstaller 빌드
:: ================================================================
echo [4/4] PyInstaller 빌드 중...
echo   (약 2-5분 소요됩니다)
echo.

pyinstaller ^
    --name="ITN Fitness 안내방송" ^
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
    echo 빌드 실패!
    pause
    exit /b 1
)

:: config 폴더를 dist에도 복사 (수정 가능하도록)
xcopy /E /I /Y config "dist\config" >nul

echo.
echo ╔════════════════════════════════════════╗
echo ║  빌드 완료!                            ║
echo ╠════════════════════════════════════════╣
echo ║                                        ║
echo ║  실행 파일:                             ║
echo ║  dist\ITN Fitness 안내방송\             ║
echo ║     ITN Fitness 안내방송.exe            ║
echo ║                                        ║
echo ╚════════════════════════════════════════╝
echo.
echo 배포 방법:
echo   dist\ITN Fitness 안내방송\ 폴더를 ZIP으로 압축하여 배포
echo.

pause
