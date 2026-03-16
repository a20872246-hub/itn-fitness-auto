#!/bin/bash

# ===================================
# ITN Fitness 안내방송 시스템
# macOS 배포용 빌드 스크립트
# PyInstaller를 사용하여 .app 생성
# ===================================

set -e

APP_NAME="ITN Fitness 안내방송"
VERSION="1.0.0"

echo "╔════════════════════════════════════════╗"
echo "║  ITN Fitness 안내방송 시스템             ║"
echo "║  macOS 빌드 스크립트 v${VERSION}        ║"
echo "╚════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# ================================================================
# 1. 가상환경 및 PyInstaller 준비
# ================================================================
echo "[1/4] 빌드 환경 준비 중..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

echo "  빌드 환경 준비 완료"
echo ""

# ================================================================
# 2. 기존 빌드 정리
# ================================================================
echo "[2/4] 기존 빌드 정리 중..."
rm -rf build/ dist/ *.spec
echo "  정리 완료"
echo ""

# ================================================================
# 3. PyInstaller 빌드
# ================================================================
echo "[3/4] PyInstaller 빌드 중..."
echo "  (약 1-3분 소요됩니다)"
echo ""

pyinstaller \
    --name="${APP_NAME}" \
    --windowed \
    --noconfirm \
    --clean \
    --add-data="config:config" \
    --add-data="assets:assets" \
    --add-data="remote/templates:remote/templates" \
    --hidden-import=vlc \
    --hidden-import=edge_tts \
    --hidden-import=yt_dlp \
    --hidden-import=schedule \
    --hidden-import=yaml \
    --hidden-import=pydub \
    --hidden-import=fastapi \
    --hidden-import=uvicorn \
    --hidden-import=bcrypt \
    --hidden-import=multipart \
    --hidden-import=jinja2 \
    --hidden-import=tkinter \
    --hidden-import=aiohttp \
    --collect-all=edge_tts \
    --collect-all=yt_dlp \
    main.py

echo ""
echo "  빌드 완료"
echo ""

# ================================================================
# 4. 배포 패키지 생성
# ================================================================
echo "[4/4] 배포 패키지 생성 중..."

DIST_DIR="dist"
ZIP_NAME="ITN_Fitness_v${VERSION}_macOS.zip"

# config를 수정 가능하도록 앱 외부에도 복사
cp -r config "${DIST_DIR}/"

cd "$DIST_DIR"
zip -r "../${ZIP_NAME}" "${APP_NAME}.app" config/ \
    -x "*.DS_Store" "*/__pycache__/*" "*.pyc"
cd ..

# Copy to Desktop
DESKTOP_PATH="$HOME/Desktop"
if [ -d "$DESKTOP_PATH" ]; then
    cp "${ZIP_NAME}" "$DESKTOP_PATH/" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo ""
        echo "✓ 배포 파일을 바탕화면에 복사했습니다"
    fi
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║                                                        ║"
echo "║              ✅ 빌드 완료!                             ║"
echo "║                                                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "  📦 배포 파일:  ${ZIP_NAME}"
echo "  📁 앱 위치:    dist/${APP_NAME}.app"
echo ""
echo "┌────────────────────────────────────────────────────────┐"
echo "│  📍 배포 파일 위치                                      │"
echo "└────────────────────────────────────────────────────────┘"
echo ""
echo "  ▸ 프로젝트 폴더: ${ZIP_NAME}"
echo "  ▸ 바탕화면:     $DESKTOP_PATH/${ZIP_NAME}"
echo ""
echo "┌────────────────────────────────────────────────────────┐"
echo "│  🚀 테스트 실행                                         │"
echo "└────────────────────────────────────────────────────────┘"
echo ""
echo "  open \"dist/${APP_NAME}.app\""
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  배포 준비 완료! 바탕화면의 ZIP 파일을 전달하세요"
echo "═══════════════════════════════════════════════════════════"
echo ""

deactivate 2>/dev/null
