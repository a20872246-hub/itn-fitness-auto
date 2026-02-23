@echo off
chcp 65001 >nul 2>&1
title ITN Fitness 자동 안내방송 시스템

echo ╔════════════════════════════════════════╗
echo ║  ITN Fitness 자동 안내방송 시스템       ║
echo ║  v1.0.0                               ║
echo ╚════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ================================================================
:: STEP 1: Python 확인
:: ================================================================
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   STEP 1/3: Python 확인
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python이 설치되지 않았습니다.
    echo.
    echo 다음 링크에서 Python을 설치해주세요:
    echo   https://www.python.org/downloads/
    echo.
    echo [중요] 설치 시 "Add Python to PATH" 체크 필수!
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   %PYVER% 발견
echo.

:: ================================================================
:: STEP 2: VLC 확인
:: ================================================================
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   STEP 2/3: VLC 확인
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

if exist "C:\Program Files\VideoLAN\VLC\vlc.exe" (
    echo   VLC Media Player 발견
) else if exist "C:\Program Files (x86)\VideoLAN\VLC\vlc.exe" (
    echo   VLC Media Player 발견
) else (
    echo   VLC Media Player가 설치되지 않았습니다.
    echo   다운로드: https://www.videolan.org/vlc/
    echo   VLC 설치 후 다시 실행해주세요.
    echo.
    pause
    exit /b 1
)
echo.

:: ================================================================
:: STEP 3: 패키지 설치 및 실행
:: ================================================================
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   STEP 3/3: 패키지 설치 및 실행
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

if not exist "venv" (
    echo   처음 실행입니다. 환경 설정 중...
    echo   (약 1-2분 소요됩니다)
    echo.

    python -m venv venv
    if %errorlevel% neq 0 (
        echo 가상환경 생성 실패
        pause
        exit /b 1
    )

    call venv\Scripts\activate.bat

    echo   pip 업그레이드 중...
    python -m pip install --upgrade pip --quiet

    echo   패키지 설치 중...
    python -m pip install -r requirements.txt --quiet

    if %errorlevel% neq 0 (
        echo.
        echo   첫 번째 설치 실패. 재시도 중...
        python -m pip install -r requirements.txt --quiet
        if %errorlevel% neq 0 (
            echo   패키지 설치 실패
            echo   수동 설치: venv\Scripts\activate ^& pip install -r requirements.txt
            pause
            exit /b 1
        )
    )

    echo.
    echo   환경 설정 완료!
    echo.
) else (
    call venv\Scripts\activate.bat
    echo   환경 활성화 완료

    python -c "import vlc, schedule, yaml, edge_tts" 2>nul
    if %errorlevel% neq 0 (
        echo   일부 패키지가 누락되었습니다. 재설치 중...
        python -m pip install -r requirements.txt --quiet
    ) else (
        echo   패키지 확인 완료
    )
)
echo.

:: 기본 디렉토리 생성
if not exist "assets\announcements\general" mkdir "assets\announcements\general"
if not exist "assets\announcements\safety" mkdir "assets\announcements\safety"
if not exist "assets\announcements\class" mkdir "assets\announcements\class"
if not exist "assets\announcements\event" mkdir "assets\announcements\event"
if not exist "assets\announcements\emergency" mkdir "assets\announcements\emergency"
if not exist "logs" mkdir "logs"

echo ===========================================
echo   시스템 시작!
echo ===========================================
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo 안내방송 시스템이 오류로 종료되었습니다.
    echo 오류 코드: %errorlevel%
    echo.
    echo 문제 해결:
    echo   1. VLC Media Player 설치 확인
    echo   2. 인터넷 연결 확인
    echo   3. config\ 폴더의 설정 파일 확인
    echo.
) else (
    echo.
    echo 안내방송 시스템이 정상 종료되었습니다.
    echo.
)

pause
