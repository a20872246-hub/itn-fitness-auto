#!/bin/bash

# ================================================================
# ITN Fitness 자동 안내방송 시스템 런처
# ================================================================
# - Python 자동 설치
# - VLC Media Player 확인 및 설치 안내
# - FFmpeg 자동 설치
# - 패키지 자동 설치 (최대 3번 재시도)
# - 안내방송 시스템 실행
# ================================================================

clear
echo "╔════════════════════════════════════════╗"
echo "║  ITN Fitness 자동 안내방송 시스템       ║"
echo "║  v1.0.0                               ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 현재 디렉토리로 이동
cd "$(dirname "$0")"

# ================================================================
# STEP 1: Python 3 확인 및 자동 설치
# ================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 1/4: Python 확인"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "Python 3이 설치되지 않았습니다."
    echo ""

    if command -v brew &> /dev/null; then
        echo "Homebrew 발견. Python 3 자동 설치를 시작합니다..."
        echo "(약 2-3분 소요됩니다)"
        echo ""
        brew install python3

        if [ $? -eq 0 ]; then
            echo ""
            echo "Python 3 설치 완료!"
        else
            echo "Python 3 설치 실패"
            echo "수동 설치: https://www.python.org/downloads/"
            read -p "Enter 키를 눌러 종료..."
            exit 1
        fi
    else
        echo "Python 3을 자동으로 설치하시겠습니까?"
        echo ""
        echo "1) 예 - Homebrew와 Python 3을 자동으로 설치합니다 (권장)"
        echo "2) 아니오 - 수동으로 설치하겠습니다"
        echo ""
        read -p "선택 (1 또는 2): " choice

        if [ "$choice" = "1" ]; then
            echo ""
            echo "Homebrew 설치 중..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

            if [ $? -eq 0 ]; then
                # Add brew to PATH for current session
                eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null)"
                echo "Homebrew 설치 완료! Python 3 설치 중..."
                brew install python3

                if [ $? -ne 0 ]; then
                    echo "Python 3 설치 실패"
                    read -p "Enter 키를 눌러 종료..."
                    exit 1
                fi
            else
                echo "Homebrew 설치 실패"
                read -p "Enter 키를 눌러 종료..."
                exit 1
            fi
        else
            echo "수동 설치: https://www.python.org/downloads/"
            read -p "Enter 키를 눌러 종료..."
            exit 1
        fi
    fi
fi

PYTHON_VERSION=$(python3 --version)
echo "  $PYTHON_VERSION 발견"
echo ""

# ================================================================
# STEP 2: VLC & FFmpeg 확인
# ================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 2/4: VLC & FFmpeg 확인"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# VLC 확인
VLC_APP="/Applications/VLC.app"

if [ ! -d "$VLC_APP" ]; then
    echo "VLC Media Player가 설치되지 않았습니다."
    echo "(BGM 재생과 안내방송에 필수입니다)"
    echo ""

    if command -v brew &> /dev/null; then
        echo "VLC를 자동으로 설치하시겠습니까?"
        echo ""
        echo "1) 예 - Homebrew로 VLC 자동 설치 (권장)"
        echo "2) 아니오 - 수동으로 설치하겠습니다"
        echo ""
        read -p "선택 (1 또는 2): " vlc_choice

        if [ "$vlc_choice" = "1" ]; then
            echo "VLC 설치 중... (약 1-2분 소요)"
            brew install --cask vlc

            if [ $? -eq 0 ]; then
                echo "VLC 설치 완료!"
            else
                echo "VLC 자동 설치 실패"
                echo "수동 설치: https://www.videolan.org/vlc/"
                read -p "VLC 설치 후 Enter 키를 눌러 계속..."
            fi
        else
            echo "수동 설치: https://www.videolan.org/vlc/"
            read -p "VLC 설치 후 Enter 키를 눌러 계속..."
        fi
    else
        echo "수동 설치: https://www.videolan.org/vlc/"
        read -p "VLC 설치 후 Enter 키를 눌러 계속..."
    fi

    if [ ! -d "$VLC_APP" ]; then
        echo "VLC가 아직 감지되지 않습니다."
        echo "BGM 재생 기능이 작동하지 않을 수 있습니다."
        sleep 3
    fi
else
    echo "  VLC Media Player 발견"
fi

# FFmpeg 확인
if ! command -v ffmpeg &> /dev/null; then
    echo "  FFmpeg이 설치되지 않았습니다."

    if command -v brew &> /dev/null; then
        echo "  FFmpeg 자동 설치 중..."
        brew install ffmpeg
        if [ $? -eq 0 ]; then
            echo "  FFmpeg 설치 완료!"
        else
            echo "  FFmpeg 설치 실패 (BGM 기능이 제한될 수 있습니다)"
        fi
    else
        echo "  FFmpeg은 Homebrew 설치 후 'brew install ffmpeg'로 설치 가능합니다."
    fi
else
    echo "  FFmpeg 발견"
fi
echo ""

# ================================================================
# STEP 3: 가상환경 및 패키지 설치
# ================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 3/4: 패키지 설치"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ ! -d "venv" ]; then
    echo "  처음 실행입니다. 환경 설정 중..."
    echo "  (약 1-2분 소요됩니다)"
    echo ""

    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "가상환경 생성 실패"
        read -p "Enter 키를 눌러 종료..."
        exit 1
    fi

    source venv/bin/activate

    echo "  pip 업그레이드 중..."
    python3 -m pip install --upgrade pip --quiet

    echo "  패키지 설치 중..."
    echo "  (yt-dlp, python-vlc, FastAPI 등)"
    echo ""

    INSTALL_SUCCESS=0
    for attempt in 1 2 3; do
        echo "  설치 시도 $attempt/3..."
        python3 -m pip install -r requirements.txt --quiet

        if [ $? -eq 0 ]; then
            INSTALL_SUCCESS=1
            break
        else
            if [ $attempt -lt 3 ]; then
                echo "  설치 실패. 5초 후 재시도..."
                sleep 5
            fi
        fi
    done

    if [ $INSTALL_SUCCESS -eq 0 ]; then
        echo ""
        echo "패키지 설치가 3번 실패했습니다."
        echo ""
        echo "수동 해결:"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
        echo "  python3 main.py"
        echo ""
        read -p "Enter 키를 눌러 종료..."
        exit 1
    fi

    echo ""
    echo "  환경 설정 완료!"
    echo ""
else
    source venv/bin/activate
    echo "  환경 활성화 완료"

    # 패키지 상태 확인
    if ! python3 -c "import vlc, schedule, yaml, gtts" 2>/dev/null; then
        echo "  일부 패키지가 누락되었습니다. 재설치 중..."
        python3 -m pip install -r requirements.txt --quiet
    else
        echo "  패키지 확인 완료"
    fi
fi
echo ""

# ================================================================
# STEP 4: 안내방송 시스템 실행
# ================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 4/4: 안내방송 시스템 시작"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 기본 디렉토리 생성
mkdir -p assets/announcements/{general,safety,class,event,emergency}
mkdir -p logs

LOCAL_IP=$(python3 -c "
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    print(s.getsockname()[0])
    s.close()
except:
    print('localhost')
" 2>/dev/null)

echo "  ITN Fitness 자동 안내방송 시스템을 시작합니다!"
echo ""
echo "  원격 제어: http://${LOCAL_IP}:8585"
echo ""
echo "==========================================="
echo "  시스템 시작!"
echo "==========================================="
echo ""
sleep 1

python3 main.py

EXIT_CODE=$?
deactivate 2>/dev/null

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "안내방송 시스템이 오류로 종료되었습니다."
    echo "오류 코드: $EXIT_CODE"
    echo ""
    echo "문제 해결:"
    echo "  1. VLC Media Player 설치 확인"
    echo "  2. 인터넷 연결 확인"
    echo "  3. config/ 폴더의 설정 파일 확인"
    echo ""
    read -p "Enter 키를 눌러 종료..."
else
    echo ""
    echo "안내방송 시스템이 정상 종료되었습니다."
    echo ""
fi
