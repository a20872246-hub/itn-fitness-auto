@echo off
chcp 65001 >nul 2>&1
title ITN Fitness - Windows Build
color 0A

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   ITN Fitness Announcement System        ║
echo  ║   Windows EXE Build Script v2.0          ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ================================================================
:: 1. Python / VLC check
:: ================================================================
echo [1/5] Checking build environment...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Python not found!
    echo   https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   %%i found

:: Find VLC path for bundling
set VLC_PATH=
if exist "C:\Program Files\VideoLAN\VLC" (
    set "VLC_PATH=C:\Program Files\VideoLAN\VLC"
    echo   VLC found: 64-bit
) else if exist "C:\Program Files (x86)\VideoLAN\VLC" (
    set "VLC_PATH=C:\Program Files (x86)\VideoLAN\VLC"
    echo   VLC found: 32-bit
) else (
    echo.
    echo   [WARNING] VLC not found!
    echo   VLC Media Player must be installed for BGM playback.
    echo   Download: https://www.videolan.org/vlc/
    echo.
    echo   The build will continue, but users must install VLC separately.
    echo.
)
echo.

:: ================================================================
:: 2. Prepare venv and install dependencies
:: ================================================================
echo [2/5] Preparing build environment...

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
echo [3/5] Cleaning previous build...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "ITN_Fitness_*.zip" del /q "ITN_Fitness_*.zip"
echo   Clean done
echo.

:: ================================================================
:: 4. PyInstaller build
:: ================================================================
echo [4/5] Building EXE with PyInstaller...
echo   (This may take 3-5 minutes, please wait...)
echo.

:: Build PyInstaller command
set PYINST_CMD=pyinstaller
set PYINST_CMD=%PYINST_CMD% --name="ITN_Fitness"
set PYINST_CMD=%PYINST_CMD% --windowed
set PYINST_CMD=%PYINST_CMD% --noconfirm
set PYINST_CMD=%PYINST_CMD% --clean
set PYINST_CMD=%PYINST_CMD% --add-data="config;config"
set PYINST_CMD=%PYINST_CMD% --add-data="assets;assets"
set PYINST_CMD=%PYINST_CMD% --add-data="remote/templates;remote/templates"
set PYINST_CMD=%PYINST_CMD% --hidden-import=vlc
set PYINST_CMD=%PYINST_CMD% --hidden-import=edge_tts
set PYINST_CMD=%PYINST_CMD% --hidden-import=edge_tts.communicate
set PYINST_CMD=%PYINST_CMD% --hidden-import=yt_dlp
set PYINST_CMD=%PYINST_CMD% --hidden-import=schedule
set PYINST_CMD=%PYINST_CMD% --hidden-import=yaml
set PYINST_CMD=%PYINST_CMD% --hidden-import=pydub
set PYINST_CMD=%PYINST_CMD% --hidden-import=fastapi
set PYINST_CMD=%PYINST_CMD% --hidden-import=fastapi.responses
set PYINST_CMD=%PYINST_CMD% --hidden-import=fastapi.staticfiles
set PYINST_CMD=%PYINST_CMD% --hidden-import=fastapi.templating
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn.logging
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn.protocols.http
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn.protocols.http.auto
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn.protocols.http.h11_impl
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn.protocols.websockets
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn.protocols.websockets.auto
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn.lifespan
set PYINST_CMD=%PYINST_CMD% --hidden-import=uvicorn.lifespan.on
set PYINST_CMD=%PYINST_CMD% --hidden-import=bcrypt
set PYINST_CMD=%PYINST_CMD% --hidden-import=multipart
set PYINST_CMD=%PYINST_CMD% --hidden-import=python_multipart
set PYINST_CMD=%PYINST_CMD% --hidden-import=jinja2
set PYINST_CMD=%PYINST_CMD% --hidden-import=tkinter
set PYINST_CMD=%PYINST_CMD% --hidden-import=asyncio
set PYINST_CMD=%PYINST_CMD% --hidden-import=aiohttp
set PYINST_CMD=%PYINST_CMD% --collect-all=edge_tts
set PYINST_CMD=%PYINST_CMD% --collect-all=yt_dlp
set PYINST_CMD=%PYINST_CMD% --collect-all=holidays

:: Add VLC DLLs if found
if defined VLC_PATH (
    set PYINST_CMD=%PYINST_CMD% --add-binary="%VLC_PATH%\libvlc.dll;."
    set PYINST_CMD=%PYINST_CMD% --add-binary="%VLC_PATH%\libvlccore.dll;."
    set PYINST_CMD=%PYINST_CMD% --add-binary="%VLC_PATH%\plugins;plugins"
)

%PYINST_CMD% main.py

if %errorlevel% neq 0 (
    echo.
    echo   [ERROR] Build failed!
    echo   Check the error messages above.
    pause
    exit /b 1
)

echo.
echo   EXE build complete!
echo.

:: ================================================================
:: 5. Package as ZIP
:: ================================================================
echo [5/5] Creating distributable ZIP...

:: Copy editable config to dist folder (so users can edit settings)
xcopy /E /I /Y config "dist\ITN_Fitness\config" >nul 2>&1

:: Create empty directories that the app needs
mkdir "dist\ITN_Fitness\assets\announcements\general" 2>nul
mkdir "dist\ITN_Fitness\assets\announcements\safety" 2>nul
mkdir "dist\ITN_Fitness\assets\announcements\class" 2>nul
mkdir "dist\ITN_Fitness\assets\announcements\event" 2>nul
mkdir "dist\ITN_Fitness\assets\announcements\emergency" 2>nul
mkdir "dist\ITN_Fitness\logs" 2>nul

:: Create VBS launcher (silent, no console window)
(
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WshShell.CurrentDirectory = CreateObject^("Scripting.FileSystemObject"^).GetParentFolderName^(WScript.ScriptFullName^)
echo WshShell.Run "ITN_Fitness.exe", 0, False
echo Set WshShell = Nothing
) > "dist\ITN_Fitness\ITN Fitness 실행.vbs"

:: Create backup batch launcher
(
echo @echo off
echo cd /d "%%~dp0"
echo start "" "ITN_Fitness.exe"
) > "dist\ITN_Fitness\ITN_Fitness_실행.bat"

:: Create simple quick start guide
(
echo ═══════════════════════════════════════════════════════════
echo.
echo    ITN Fitness 자동 안내방송 시스템
echo.
echo    🚀 빠른 시작: "ITN Fitness 실행.vbs" 파일을 더블클릭!
echo.
echo    📖 자세한 사용법은 "사용안내.txt" 파일을 참고하세요
echo.
echo ═══════════════════════════════════════════════════════════
) > "dist\ITN_Fitness\README.txt"

:: Create detailed user manual
(
echo ╔═══════════════════════════════════════════════════════════╗
echo ║                                                           ║
echo ║         ITN Fitness 자동 안내방송 시스템                    ║
echo ║                  사용 설명서                               ║
echo ║                                                           ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.
echo.
echo ┌─────────────────────────────────────────────────────────┐
echo │  📌 빠른 시작 가이드                                      │
echo └─────────────────────────────────────────────────────────┘
echo.
echo   1. "ITN Fitness 실행.vbs" 파일을 더블클릭하세요
echo      ^(또는 ITN_Fitness.exe를 직접 실행^)
echo.
echo   2. 프로그램이 자동으로 실행됩니다
echo.
echo   3. 끝! 바로 사용하실 수 있습니다
echo.
echo.
echo ┌─────────────────────────────────────────────────────────┐
echo │  ⚙️  필수 사항                                            │
echo └─────────────────────────────────────────────────────────┘
echo.
echo   ✓ VLC Media Player 설치 필요 ^(무료^)
echo     다운로드: https://www.videolan.org/vlc/
echo.
echo     ※ 반드시 설치해야 BGM이 재생됩니다!
echo     ※ 64비트 Windows → 64비트 VLC 설치
echo     ※ 32비트 Windows → 32비트 VLC 설치
echo.
echo   ✓ 인터넷 연결 필요
echo     - YouTube BGM 스트리밍
echo     - TTS 음성 생성
echo.
echo.
echo ┌─────────────────────────────────────────────────────────┐
echo │  📁 폴더 구조                                             │
echo └─────────────────────────────────────────────────────────┘
echo.
echo   ITN Fitness 실행.vbs     ← 이 파일을 더블클릭하세요!
echo   ITN_Fitness.exe         - 메인 프로그램
echo   config\                 - 설정 파일 ^(수정 가능^)
echo   assets\                 - 안내방송 음성/차임벨 파일
echo   logs\                   - 로그 파일
echo.
echo.
echo ┌─────────────────────────────────────────────────────────┐
echo │  🔧 문제 해결                                             │
echo └─────────────────────────────────────────────────────────┘
echo.
echo   Q: 프로그램이 실행되지 않아요
echo   A: 1. VLC Media Player가 설치되어 있는지 확인
echo      2. Windows Defender 경고 시:
echo         "추가 정보" 클릭 → "실행" 클릭
echo.
echo   Q: BGM 소리가 안 나요
echo   A: 1. VLC가 제대로 설치되었는지 확인
echo      2. 인터넷 연결 확인
echo      3. Windows 볼륨 설정 확인
echo.
echo   Q: 안내방송 소리가 안 나요
echo   A: 1. VLC가 제대로 설치되었는지 확인
echo      2. 인터넷 연결 확인 ^(TTS 음성 생성 필요^)
echo      3. logs\ 폴더의 로그 파일 확인
echo.
echo   Q: VBS 파일이 실행되지 않아요
echo   A: ITN_Fitness.exe 파일을 직접 더블클릭하세요
echo.
echo.
echo ┌─────────────────────────────────────────────────────────┐
echo │  📞 추가 도움말                                           │
echo └─────────────────────────────────────────────────────────┘
echo.
echo   - 설정 변경: 프로그램 내 "설정" 탭에서 가능
echo   - 스케줄 편집: "스케줄" 탭에서 시간/요일 설정
echo   - 안내방송 편집: "안내방송" 탭에서 내용 수정
echo   - BGM 변경: "BGM" 탭에서 YouTube URL 입력
echo.
echo.
echo ═══════════════════════════════════════════════════════════
echo   설치 완료! 이제 ITN Fitness 실행.vbs를 더블클릭하세요
echo ═══════════════════════════════════════════════════════════
echo.
) > "dist\ITN_Fitness\사용안내.txt"

:: Create ZIP using PowerShell (available on all modern Windows)
set ZIPNAME=ITN_Fitness_Windows.zip
powershell -Command "Compress-Archive -Path 'dist\ITN_Fitness' -DestinationPath '%ZIPNAME%' -Force"

if %errorlevel% neq 0 (
    echo   [WARNING] ZIP creation failed. You can manually zip the dist\ITN_Fitness folder.
) else (
    echo   ZIP created: %ZIPNAME%

    :: Copy to Desktop
    set DESKTOP=%USERPROFILE%\Desktop
    copy "%ZIPNAME%" "%DESKTOP%\%ZIPNAME%" >nul 2>&1
    if %errorlevel% equ 0 (
        echo   Desktop copy: %DESKTOP%\%ZIPNAME%
    )
)

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║              ✅ Build Complete!                          ║
echo  ║                                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo   📦 배포 파일:  %ZIPNAME%
echo   📁 배포 폴더:  dist\ITN_Fitness\
echo.
echo  ┌──────────────────────────────────────────────────────────┐
echo  │  📋 배포 방법                                             │
echo  └──────────────────────────────────────────────────────────┘
echo.
echo    1. "%ZIPNAME%" 파일을 사용자에게 전달
echo.
echo    2. 사용자가 압축 해제
echo.
echo    3. "ITN Fitness 실행.vbs" 파일을 더블클릭
echo       ^(또는 ITN_Fitness.exe 직접 실행^)
echo.
echo    4. 끝! 바로 사용 가능합니다
echo.
echo  ┌──────────────────────────────────────────────────────────┐
echo  │  ⚠️  사용자 필수 요구사항                                  │
echo  └──────────────────────────────────────────────────────────┘
echo.
echo    ✓ VLC Media Player 설치 필요 ^(무료^)
echo      https://www.videolan.org/vlc/
echo.
echo    ✓ 인터넷 연결 ^(YouTube BGM, TTS 음성 생성^)
echo.
echo  ┌──────────────────────────────────────────────────────────┐
echo  │  📂 배포 패키지 내용물                                     │
echo  └──────────────────────────────────────────────────────────┘
echo.
echo    ▸ ITN Fitness 실행.vbs      ← 사용자가 이 파일 더블클릭!
echo    ▸ ITN_Fitness.exe          - 메인 프로그램
echo    ▸ ITN_Fitness_실행.bat      - 백업 런처
echo    ▸ README.txt               - 빠른 시작 가이드
echo    ▸ 사용안내.txt              - 자세한 설명서
echo    ▸ config\                  - 설정 파일
echo    ▸ assets\                  - 리소스 파일
echo    ▸ logs\                    - 로그 폴더
echo.
echo  ┌──────────────────────────────────────────────────────────┐
echo  │  📍 배포 파일 위치                                         │
echo  └──────────────────────────────────────────────────────────┘
echo.
echo    ▸ 프로젝트 폴더: %ZIPNAME%
echo    ▸ 바탕화면: %USERPROFILE%\Desktop\%ZIPNAME%
echo.
echo  ═══════════════════════════════════════════════════════════
echo    배포 준비 완료! 바탕화면의 ZIP 파일을 전달하세요
echo  ═══════════════════════════════════════════════════════════
echo.

pause
