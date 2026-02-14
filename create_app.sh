#!/bin/bash

# ===================================
# ITN Fitness 안내방송 시스템
# macOS 앱 번들 자동 생성 스크립트
# ===================================

APP_NAME="ITN Fitness 안내방송"
BUNDLE_ID="com.itnfitness.broadcast"
VERSION="1.0.0"

APP_DIR="${APP_NAME}.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
PROJECT_DIR="$RESOURCES_DIR/PythonProject"

echo "╔════════════════════════════════════════╗"
echo "║  ITN Fitness 안내방송 시스템             ║"
echo "║  macOS 앱 번들 생성기 v${VERSION}       ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "앱 번들 생성 중: $APP_NAME"

# 기존 앱 삭제
rm -rf "$APP_DIR"

# 디렉토리 구조 생성
mkdir -p "$MACOS_DIR"
mkdir -p "$PROJECT_DIR"

# 1. Info.plist 생성
cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <string>0</string>
</dict>
</plist>
EOF

# 2. MacOS/launcher 실행 파일 생성
cat > "$MACOS_DIR/launcher" <<'LAUNCHER'
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PROJECT_DIR="$APP_DIR/Contents/Resources/PythonProject"

osascript <<EOFAPPLE
tell application "Terminal"
    activate
    do script "cd '$PROJECT_DIR' && ./launcher.sh"
end tell
EOFAPPLE
LAUNCHER

chmod +x "$MACOS_DIR/launcher"

# 3. 프로젝트 파일 복사
echo "프로젝트 파일 복사 중..."

cp main.py "$PROJECT_DIR/"
cp requirements.txt "$PROJECT_DIR/"

# 모듈 디렉토리 복사
[ -d core ] && cp -r core "$PROJECT_DIR/"
[ -d gui ] && cp -r gui "$PROJECT_DIR/"
[ -d remote ] && cp -r remote "$PROJECT_DIR/"

# 설정 파일 복사
[ -d config ] && cp -r config "$PROJECT_DIR/"

# 에셋 복사
[ -d assets ] && cp -r assets "$PROJECT_DIR/"

# 로그 디렉토리 생성
mkdir -p "$PROJECT_DIR/logs"

# 4. launcher.sh 복사
cp launcher.sh "$PROJECT_DIR/"
chmod +x "$PROJECT_DIR/launcher.sh"

# 5. 앱 아이콘 복사 (있는 경우)
[ -f "assets/icon.icns" ] && cp "assets/icon.icns" "$RESOURCES_DIR/Icon.icns"

echo ""
echo "앱 번들 생성 완료: $APP_DIR"
echo ""
echo "다음 단계:"
echo "  1. '$APP_DIR' 더블클릭하여 테스트"
echo "  2. 정상 작동 확인 후 ZIP으로 압축"
echo ""
echo "ZIP 생성:"
echo "  zip -r \"ITN_Fitness_v${VERSION}_macOS.zip\" \"$APP_DIR\" -x \"*.DS_Store\" \"*/venv/*\" \"*/__pycache__/*\" \"*.pyc\""
