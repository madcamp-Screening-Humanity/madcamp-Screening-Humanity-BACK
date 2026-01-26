# Phase 5 설정 가이드: 채팅 인터페이스(vLLM + TTS)

## 목차
1. [개요](#1-개요)
2. [Server A 설정 (GPU 서버)](#2-server-a-설정-gpu-서버)
3. [Server B 설정 (CPU 서버)](#3-server-b-설정-cpu-서버)
4. [서비스 구축 및 배포](#4-서비스-구축-및-배포)
5. [통합 테스트](#5-통합-테스트)
6. [문제 해결](#6-문제-해결)

---

## ⚠️ 미구현 기능 목록 (2026-01-26)

### Phase 5.1: 기본 채팅 기능 (현재 진행 중)
- ✅ vLLM 서버 설정 및 실행 ✅
- ✅ GPT-SoVITS WebAPI 구동 ✅
- ✅ Server A NPM 설정 ✅
- ✅ Backend API 연동 (Mock 제거, 실제 API 호출 구현 완료) ✅
- ✅ 로그인/로그아웃 시스템 통합 완료 ✅
- ⚠️ Frontend 연동 (진행 중)

### Phase 5.2: 컨텍스트 절약 요약 기능 (필수, 미구현)
- **구현 시기**: Phase 5.1 완료 후 즉시
- **우선순위**: 높음 (필수)
- **구현 위치**: `server-b/backend/app/services/context_manager.py` (신규 생성)
- **상세 내용**: [Phase 5.2-5.4 구현 가이드 - Phase 5.2](#51-phase-52-컨텍스트-절약-요약-기능-구현) 섹션 참조

### Phase 5.3: 동시 접속 제한 (필수, 미구현)
- **구현 시기**: Phase 5.1 완료 후 즉시
- **우선순위**: 높음 (필수)
- **구현 위치**: `server-b/backend/app/core/rate_limiter.py` (신규 생성)
- **상세 내용**: [Phase 5.2-5.4 구현 가이드 - Phase 5.3](#52-phase-53-동시-접속-제한-구현) 섹션 참조

### Phase 5.4: Frontend 턴 제한 설정화 ✅ **구현 완료**
- **구현 시기**: Phase 5.1 완료 후
- **구현 위치**: `components/chat-room.tsx`
- **구현 상태**: ✅ **구현 완료** (2026-01-26)
- **상세 내용**: [Phase 5.2-5.4 구현 가이드 - Phase 5.4](#53-phase-54-frontend-턴-제한-설정화-구현-완료) 섹션 참조

### 최근 구현 완료 기능 (2026-01-26)
- ✅ **ChatRoom API 연동 및 TTS 통합** (7단계)
  - Backend ChatRequest/ChatResponse 확장
  - Backend TTS 통합
  - Frontend 타입 확장
  - ChatRoom 컴포넌트 수정
  - TTS 설정 모달
- ✅ **페르소나 전달 방식 개선** (8단계)
  - format_persona_for_roleplay() 함수 구현
  - 시나리오 정보 포함
  - 대화 컨텍스트 관리
- ✅ **TTS 음성 목록 조회 API** (`GET /api/tts/voices`)
  - 구현 완료 (2026-01-26)
- ✅ **인증 제거 및 프롬프트 전달 수정** (2026-01-26)
  - `/api/chat`, `/api/chat/models` 인증 제거
  - `/api/tts`, `/api/tts/voices` 인증 제거
  - `/api/generate` 인증 제거 (user_id="anonymous")
  - `/api/characters/*` 모든 엔드포인트 인증 제거
  - 프론트엔드에서 persona, scenario, session_id, character_id 전달 확인
  - 백엔드에서 request.persona를 system 메시지로 포맷팅 확인

**참고 자료**:
- GPT-SoVITS 포트 구분 및 적용법: [Notion 문서](https://www.notion.so/1d6d3e41a6c0809b8f6afb53f7b985c3?v=1d6d3e41a6c081928e59000c47330846&source=copy_link), [Arca.live 게시판들](https://arca.live/b/characterai/114903135?)

---

## 1. 개요

### 1.1 Phase 5 목표
- LLM(vLLM)과 TTS(GPT-SoVITS)를 연동하여 캐릭터와 텍스트/음성으로 대화할 수 있는 기능 구현
- LLM 모델: Gemma 3 27B IT (기본)
- **무제한 대화 지원**: 턴 제한 설정화 (환경 변수 지원), 컨텍스트 절약 요약 기능으로 긴 대화 지원 (Phase 5.2에서 구현 예정)
- **동시 접속 제한**: 최대 20명 동시 접속 (추후 증가 예정)

### 1.2 Phase 5 세부 단계 (2026-01-26)

**Phase 5.1: 기본 채팅 기능 (현재 진행 중)**
- vLLM 서버 설정 및 실행
- GPT-SoVITS WebAPI 구동
- Backend API 연동
- Frontend 연동

**Phase 5.2: 컨텍스트 절약 요약 기능 (Phase 5.1 완료 후 즉시, 필수, 미구현)**
- Redis 또는 메모리 캐시 설정
- `ContextManager` 서비스 구현
- 세션 기반 히스토리 관리
- 자동 요약 로직 구현
- Backend API에 통합

**Phase 5.3: 동시 접속 제한 (Phase 5.1 완료 후 즉시, 필수, 미구현)**
- Redis 설정 (세션 카운터용)
- `ConcurrentUserLimiter` 구현
- Middleware 또는 Dependency로 통합
- 환경 변수 설정 (`MAX_CONCURRENT_USERS=20`)

**Phase 5.4: Frontend 턴 제한 설정화** ✅ **구현 완료** (2026-01-26)
- `chat-room.tsx`에서 턴 제한 설정화 (환경 변수 지원)
- 세션 관리 로직 추가
- 실제 API 연동 완료
- TTS 통합 완료
- 무제한 대화 UI 개선
- 세션 관리 로직 추가

### 1.2 모델 용량 요약

| 모델 | 용량 | 저장 위치 |
|------|------|----------|
| Gemma 3 27B IT (4-bit 양자화) | ~13-15GB | Server A `/mnt/shared_models/llm/gemma-3-27b-it/` |
| GPT-SoVITS | 소스 코드 + Conda 환경 (~5-9GB) | `/opt/GPT-SoVITS` (Conda 환경 직접 설치) |
| **총합** | **~18-24GB** | Server A에 직접 저장 (100GB 여유 공간 활용, 용량 절약) |

### 1.3 아키텍처 개요

```
사용자 → Server B (Main Backend) → Server A (NPM) → LLM/TTS 서비스
                                              ↓
                                    /mnt/shared_models (모델 파일)
```

---

## 2. Server A 설정 (GPU 서버)

### 2.1 사전 요구사항 확인

**⚠️ 매우 중요: nvidia-smi 필수 요구사항**

**Server A는 반드시 NVIDIA GPU가 있어야 하며, `nvidia-smi` 명령어가 정상 작동해야 합니다.**
- `nvidia-smi`가 작동하지 않으면 GPU 서버로 사용할 수 없습니다
- NVIDIA 드라이버가 설치되어 있지 않거나 GPU가 인식되지 않으면 모든 AI 서비스가 작동하지 않습니다
- 설치 전 반드시 `nvidia-smi`로 GPU 상태를 확인하세요

```bash
# NVIDIA 드라이버 확인 (필수!)
nvidia-smi

# Docker 설치 확인
docker --version
docker-compose --version

# 디스크 공간 확인 (최소 50GB 여유 필요)
df -h
```

**예상 출력**:
- `nvidia-smi`: NVIDIA 드라이버 버전 및 GPU 정보 표시 (⚠️ 필수, 없으면 진행 불가)
- `docker`: Docker 24.0 이상
- `docker-compose`: docker-compose 2.0 이상
- 디스크 여유 공간: 50GB 이상 권장

**nvidia-smi 오류 시**:
- NVIDIA 드라이버가 설치되지 않았거나 GPU가 인식되지 않는 경우
- 이 경우 Server A를 GPU 서버로 사용할 수 없으므로 설치를 중단해야 합니다

### 2.2 NVIDIA Container Toolkit 설치

#### Ubuntu 22.04 기준 설치 스크립트

```bash
#!/bin/bash
# Server A - NVIDIA Container Toolkit 설치 스크립트

set -e  # 오류 발생 시 스크립트 중단

echo "=========================================="
echo "NVIDIA Container Toolkit 설치 시작"
echo "=========================================="

# 1. 패키지 저장소 및 GPG 키 설정
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 2. 패키지 목록 업데이트
sudo apt-get update

# 3. NVIDIA Container Toolkit 설치
sudo apt-get install -y nvidia-container-toolkit

# 4. Docker 런타임 설정
sudo nvidia-ctk runtime configure --runtime=docker

# 5. Docker 데몬 재시작
sudo systemctl restart docker

# 6. 설치 확인
echo "=========================================="
echo "GPU 컨테이너 테스트"
echo "=========================================="
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

echo "=========================================="
echo "✅ NVIDIA Container Toolkit 설치 완료"
echo "=========================================="
```

### 2.3 모델 파일 저장 디렉터리 생성

```bash
#!/bin/bash
# Server A - 모델 파일 저장 디렉터리 설정

set -e

echo "=========================================="
echo "모델 파일 저장 디렉터리 생성"
echo "=========================================="

# 모델 파일 저장 디렉터리 생성
sudo mkdir -p /mnt/shared_models/llm/gemma-3-27b-it
# GPT-SoVITS는 /opt/GPT-SoVITS에 Conda 환경으로 설치하므로 별도 디렉터리 생성 불필요

# 권한 설정
CURRENT_USER=$(whoami)
sudo chown -R $CURRENT_USER:$CURRENT_USER /mnt/shared_models
sudo chmod -R 755 /mnt/shared_models

echo "✅ 디렉터리 생성 완료"
echo "   소유자: $CURRENT_USER"
echo ""
echo "디렉터리 구조:"
tree -L 3 /mnt/shared_models 2>/dev/null || find /mnt/shared_models -type d -maxdepth 2 | sort
```

### 2.4 LLM 모델 다운로드

#### 2.4.1 사전 준비

**⚠️ 중요**: Ubuntu 22.04+에서는 시스템 Python 환경이 보호되어 직접 pip install이 불가능합니다.

**방법 1: Hugging Face 공식 CLI 설치 (권장)**

Hugging Face 공식 CLI(`hf`)를 standalone installer로 설치:

```bash
# Hugging Face 공식 CLI 설치 (가장 간단한 방법)
curl -LsSf https://hf.co/cli/install.sh | bash

# 설치 확인
hf --version

# 또는 도움말 확인
hf --help
```

이 방법은 가상 환경 없이도 작동하며, `hf download` 명령어를 바로 사용할 수 있습니다.

**방법 2: 가상 환경에서 Python API 사용**

```bash
# 1. Python 가상 환경 생성
python3 -m venv ~/venv

# 2. 가상 환경 활성화
source ~/venv/bin/activate

# 활성화 확인: 프롬프트 앞에 (venv)가 표시되어야 함
# 예: (venv) root@camp-gpu-5:~#

# 3. Hugging Face Hub 라이브러리 설치
pip install --upgrade huggingface_hub

# 4. 설치 확인
python -c "from huggingface_hub import __version__; print(f'huggingface_hub 버전: {__version__}')"
python -c "import huggingface_hub; print('✅ huggingface_hub 정상 설치됨')"
```

이 방법은 Python API(`snapshot_download`)를 직접 사용합니다.

# Git LFS 설치 (필요시)
sudo apt-get install -y git-lfs
git lfs install
```

**문제 해결**:

- `python3 -m venv` 명령이 없다면:
  ```bash
  sudo apt-get install -y python3-venv python3-full
  python3 -m venv ~/venv
  ```

- 가상 환경 활성화가 안 되면:
  ```bash
  # 경로 확인
  ls -la ~/venv/bin/activate
  
  # 직접 실행
  . ~/venv/bin/activate
  ```

**방법 3: pipx 사용**

```bash
# pipx 설치
sudo apt-get install -y pipx
pipx ensurepath

# Hugging Face Hub를 독립 실행형으로 설치
pipx install huggingface_hub

# 사용 시 (Python API만 사용 가능, CLI는 없을 수 있음)
python -c "from huggingface_hub import snapshot_download; print('✅ 설치 완료')"
```

**참고**: 
- `hf` CLI는 standalone installer로 설치하는 것이 가장 간단합니다
- `--break-system-packages` 플래그는 사용하지 마세요. 시스템 Python 환경을 손상시킬 수 있습니다

#### 2.4.2 Gemma 3 27B IT 모델 다운로드

**요구사항**:
- 모델 ID: `unsloth/gemma-3-27b-it-bnb-4bit` (4-bit 양자화 버전)
- VRAM: ~13-15GB (4-bit 양자화)
- 컨텍스트 길이: 128K tokens
- 디스크 용량: ~13-15GB
- 특징: 멀티모달 (텍스트 + 이미지 입력), 140개 이상 언어 지원, 양자화로 용량/VRAM 절약

**다운로드 스크립트**:

```bash
#!/bin/bash
# Gemma 3 27B IT 모델 다운로드

set -e

# 가상 환경 활성화 (또는 pipx로 설치한 경우 이 줄 제거)
if [ -f ~/venv/bin/activate ]; then
    source ~/venv/bin/activate
fi

MODEL_DIR="/mnt/shared_models/llm/gemma-3-27b-it"
MODEL_REPO="unsloth/gemma-3-27b-it-bnb-4bit"

echo "=========================================="
echo "Gemma 3 27B IT 모델 다운로드 (4-bit 양자화)"
echo "=========================================="
echo "⚠️  주의: 4-bit 양자화 버전 (~13-15GB)"
echo "   다운로드에 시간이 걸릴 수 있습니다."
echo "   양자화로 용량과 VRAM 사용량이 크게 줄어듭니다."
echo ""

# 디렉터리 확인
if [ -d "$MODEL_DIR" ] && [ "$(ls -A $MODEL_DIR)" ]; then
    echo "⚠️  디렉터리가 이미 존재하고 파일이 있습니다: $MODEL_DIR"
    read -p "   덮어쓰시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   건너뜀"
        exit 0
    else
        echo "   기존 파일 삭제 중..."
        rm -rf "$MODEL_DIR"/*
    fi
fi

echo "다운로드 중: $MODEL_REPO"
echo "저장 위치: $MODEL_DIR"
echo ""
echo "⚠️  참고: Gemma 모델은 Hugging Face 로그인이 필요할 수 있습니다."
echo "   hf auth login 또는 HF_TOKEN 환경 변수 설정이 필요합니다."

cd "$(dirname $MODEL_DIR)"

# 방법 1: Hugging Face 공식 CLI 사용 (권장, 가장 간단)
if command -v hf &> /dev/null; then
    echo "Hugging Face CLI(hf) 사용"
    hf download "$MODEL_REPO" --local-dir "$(basename $MODEL_DIR)"
# 방법 2: Python API 사용
else
    echo "Python API 사용"
    python3 << PYTHON_SCRIPT
import sys
from huggingface_hub import snapshot_download
import os

model_repo = "$MODEL_REPO"
local_dir = "$(basename $MODEL_DIR)"
full_path = os.path.join("$(dirname $MODEL_DIR)", local_dir)

print(f"다운로드 중: {model_repo}")
print(f"저장 위치: {full_path}")

try:
    snapshot_download(
        repo_id=model_repo,
        local_dir=full_path,
        local_dir_use_symlinks=False,
        resume_download=True
    )
    print(f"✅ 다운로드 완료: {full_path}")
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    print("   Hugging Face 로그인이 필요할 수 있습니다: hf auth login")
    sys.exit(1)
PYTHON_SCRIPT
fi

echo "✅ Gemma 3 27B IT 다운로드 완료"
du -sh "$MODEL_DIR"
```

**또는 Git LFS 사용**:

```bash
cd /mnt/shared_models/llm
git lfs install
git clone https://huggingface.co/unsloth/gemma-3-27b-it-bnb-4bit gemma-3-27b-it
```


### 2.5 모델 파일 검증

```bash
#!/bin/bash
# 모델 파일 검증 스크립트

echo "=========================================="
echo "모델 파일 검증"
echo "=========================================="

# Gemma 3 27B IT 확인
echo "Gemma 3 27B IT:"
if [ -d "/mnt/shared_models/llm/gemma-3-27b-it" ]; then
    ls -lh /mnt/shared_models/llm/gemma-3-27b-it/ | head -10
    du -sh /mnt/shared_models/llm/gemma-3-27b-it/
else
    echo "❌ 디렉터리가 존재하지 않습니다"
fi


# GPT-SoVITS 확인 (Conda 환경 직접 설치)
echo -e "\nGPT-SoVITS:"
if [ -d "/opt/GPT-SoVITS" ]; then
    echo "✅ 소스 코드 디렉터리: /opt/GPT-SoVITS"
    du -sh /opt/GPT-SoVITS
    echo "   Conda 환경 확인:"
    conda env list | grep GPTSoVits || echo "   ⚠️  Conda 환경이 아직 생성되지 않았습니다"
    echo "   systemd 서비스 확인:"
    systemctl is-active gpt-sovits 2>/dev/null && echo "   ✅ 서비스 실행 중" || echo "   ⚠️  서비스가 실행되지 않았습니다"
else
    echo "❌ 디렉터리가 존재하지 않습니다"
    echo "   bash scripts/server-a/setup-gpt-sovits-conda.sh 실행 필요"
fi

echo -e "\n=========================================="
echo "전체 모델 디렉터리 크기:"
du -sh /mnt/shared_models/*
echo "=========================================="
```

### 2.7 모델 파일 구조 예시

```
/mnt/shared_models/
├── llm/
│   ├── gemma-3-27b-it/
│   │   ├── config.json
│   │   ├── tokenizer.json
│   │   ├── tokenizer_config.json
│   │   ├── model-*.safetensors  (4-bit 양자화된 모델 파일)
│   │   └── ...
│   └── dolphin-2.9-8b/
│       ├── config.json
│       ├── tokenizer.json
│       ├── tokenizer_config.json
│       ├── model-*.safetensors
│       └── ...
# GPT-SoVITS는 /opt/GPT-SoVITS에 Conda 환경으로 별도 설치됨
```

---

## 3. Server B 설정 (CPU 서버)

### 3.1 파일 스토리지 디렉터리 생성

```bash
#!/bin/bash
# Server B - 생성 결과 저장 디렉터리 설정

set -e

echo "=========================================="
echo "Server B 파일 스토리지 디렉터리 생성"
echo "=========================================="

# 사용자 자산 저장 디렉터리 생성 (생성 결과만 저장)
sudo mkdir -p /mnt/user_assets/models
sudo mkdir -p /mnt/user_assets/audio
sudo mkdir -p /mnt/user_assets/images

# 권한 설정
CURRENT_USER=$(whoami)
sudo chown -R $CURRENT_USER:$CURRENT_USER /mnt/user_assets
sudo chmod -R 755 /mnt/user_assets

echo "✅ 디렉터리 생성 완료"
echo "   소유자: $CURRENT_USER"
echo ""
echo "디렉터리 구조:"
tree -L 2 /mnt/user_assets 2>/dev/null || find /mnt/user_assets -type d -maxdepth 1 | sort
```

**참고**: 모델 파일은 Server A에 저장하므로 Server B에는 생성 결과만 저장합니다.

---

## 4. 서비스 구축 및 배포

### 4.1 Server A: Nginx Proxy Manager 설정

#### 4.1.1 NPM Docker 컨테이너 실행 (호스트 Conda 서비스 연결 지원)

**⚠️ 중요**: 호스트에서 실행 중인 Conda 서비스(GPT-SoVITS 등)에 접근하려면 `extra_hosts` 설정이 필요합니다.

**방법 1: 자동화 스크립트 사용 (권장)**

```bash
# NPM 설정 자동 생성 및 실행
bash scripts/server-a/setup-services.sh
# 옵션 1 선택 (NPM 설정)
```

**방법 2: 수동 설정**

```yaml
# server-a/docker-compose.yaml
version: '3.8'

services:
  npm:
    image: jc21/nginx-proxy-manager:latest
    container_name: npm
    restart: unless-stopped
    ports:
      - "80:80"
      - "81:81"
      - "443:443"
    volumes:
      - ./data/npm:/data
      - ./data/letsencrypt:/etc/letsencrypt
    networks:
      - avatar-forge-network

networks:
  avatar-forge-network:
    driver: bridge
```

**실행**:

```bash
cd server-a
docker-compose up -d npm
```

**연결 테스트**:

```bash
# 네트워크 연결 테스트
bash scripts/server-a/monitor-system.sh
# 옵션 6 선택 (NPM 연결 테스트)
```

#### 4.1.2 NPM 웹 콘솔 접속

1. 브라우저에서 `http://<Server-A-IP>:81` 접속
2. 초기 로그인:
   - Email: `admin@example.com`
   - Password: `changeme`
3. 비밀번호 변경

#### 4.1.3 Proxy Host 설정

**LLM 서비스 프록시**:
- Domain Names: `llm.server-a.local` (또는 실제 도메인)
- Scheme: `http`
- Forward Hostname/IP: `llm-service` (docker-compose 서비스 이름)
- Forward Port: `8002`
- SSL: Let's Encrypt 활성화 (또는 자체 서명 인증서)

**TTS 서비스 프록시 (호스트 Conda 서비스)**:
- Domain Names: `tts.server-a.local` (또는 실제 도메인)
- Scheme: `http` (⚠️ 중요: Conda 서비스는 HTTP이므로 반드시 http)
- Forward Hostname/IP: `172.17.0.1` (Docker bridge 게이트웨이 IP)
- Forward Port: `9872` (⚠️ 중요: TTS API 포트, WebUI가 아닌 TTS 서비스 포트)
- SSL: Let's Encrypt 활성화

**⚠️ GPT-SoVITS 포트 구분 (매우 중요!)**:

GPT-SoVITS는 **3개의 포트를 모두 사용**합니다:
- **포트 9872**: TTS API (텍스트-음성 변환 서비스) ← **NPM 프록시는 이 포트 사용**
- **포트 9873**: 반주 분리 (UVR5) 서비스 ← **사용**
- **포트 9874**: GPT-SoVITS WebUI (관리 인터페이스) ← **사용**

**NPM 프록시 설정 시 주의사항**:
- TTS 서비스로 사용하려면 **포트 9872**를 사용해야 합니다
- 포트 9873은 반주 분리(UVR5) 서비스용으로 직접 접근 또는 내부 API 호출에 사용됩니다
- 포트 9874는 WebUI(관리 인터페이스)용으로 직접 접근에 사용됩니다
- 이 정보를 모르면 502 오류나 잘못된 엔드포인트 접근이 발생할 수 있습니다

**참고 자료**: 이 포트 구분 정보는 다음 자료를 참고하여 확인되었습니다:
- [Notion 문서](https://www.notion.so/1d6d3e41a6c0809b8f6afb53f7b985c3?v=1d6d3e41a6c081928e59000c47330846&source=copy_link)
- [Arca.live - CharacterAI 게시판](https://arca.live/b/characterai/114903135?)
- [Arca.live - AISpeech 게시판 1](https://arca.live/b/aispeech/76792418)
- [Arca.live - AISpeech 게시판 2](https://arca.live/b/aispeech/77906451)

**⚠️ 중요 설정 사항**:
1. **Scheme은 반드시 `http`**: Conda 서비스는 기본적으로 HTTP로 실행됨
2. **호스트 접근 방법**: `172.17.0.1` (Docker bridge 게이트웨이 IP, 기본 bridge 네트워크 사용)
3. **포트 확인**: 실제 실행 중인 포트 확인 필요
   ```bash
   sudo journalctl -u gpt-sovits -n 50 | grep -i "running\|port"
   ```

### 4.2 Server A: vLLM 서비스 설정

#### 4.2.1 vLLM Docker 컨테이너 설정

```yaml
# server-a/docker-compose.yaml에 추가

services:
  vllm-server:
    image: vllm/vllm-openai:latest
    container_name: vllm-server
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    volumes:
      - /mnt/shared_models/llm:/models/llm:ro
    # ⚠️ vLLM 0.13+ 호환: --model 옵션 대신 positional argument 사용
    command: >
      /models/llm/gemma-3-27b-it
      --tensor-parallel-size 1
      --dtype auto
      --quantization bitsandbytes
      --max-model-len 8192
    ports:
      - "8002:8000"
    ipc: host
    environment:
      - CUDA_VISIBLE_DEVICES=0
```

#### 4.2.2 LLM 서비스 래퍼 (FastAPI)

```python
# server-a/llm-service/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import httpx
import logging
import os

logger = logging.getLogger(__name__)
app = FastAPI(title="Avatar Forge LLM Service")

# LLM 서버 URL (내부) - 환경 변수로 선택
LLM_SERVICE = os.getenv("LLM_SERVICE", "vllm")  # "vllm" 또는 "ollama"

if LLM_SERVICE == "vllm":
    LLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://vllm-server:8002")
    LLM_API_PATH = "/v1/chat/completions"
elif LLM_SERVICE == "ollama":
    LLM_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama-server:11434")
    LLM_API_PATH = "/api/chat"
else:
    raise ValueError(f"Unknown LLM_SERVICE: {LLM_SERVICE}")

class Message(BaseModel):
    role: str  # 'user' | 'assistant' | 'system'
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    persona: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    model: str = "gemma-3-27b-it"  # 기본 모델

@app.post("/chat")
async def chat(request: ChatRequest):
    """LLM 채팅 추론 수행"""
    try:
        messages = []
        
        # 페르소나 시스템 프롬프트 추가
        if request.persona:
            messages.append({
                "role": "system",
                "content": f"당신은 다음과 같은 캐릭터입니다: {request.persona}\n"
                          "캐릭터의 성격과 말투를 유지하며 대화하세요."
            })
        
        # 사용자 메시지 추가
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})
        
        # LLM 서비스 호출 (케이스별 분기)
        async with httpx.AsyncClient() as client:
            if LLM_SERVICE == "vllm":
                # 케이스 A: vLLM OpenAI API 호환 엔드포인트 호출
                response = await client.post(
                    f"{LLM_BASE_URL}{LLM_API_PATH}",
                    json={
                        "model": request.model,
                        "messages": messages,
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens
                    },
                    timeout=60.0
                )
                result = response.json()
                return {
                    "content": result["choices"][0]["message"]["content"],
                    "usage": {
                        "prompt_tokens": result["usage"]["prompt_tokens"],
                        "completion_tokens": result["usage"]["completion_tokens"]
                    }
                }
            elif LLM_SERVICE == "ollama":
                # 케이스 B: Ollama API 호출
                response = await client.post(
                    f"{LLM_BASE_URL}{LLM_API_PATH}",
                    json={
                        "model": request.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": request.temperature,
                            "num_predict": request.max_tokens
                        }
                    },
                    timeout=60.0
                )
                result = response.json()
                return {
                    "content": result["message"]["content"],
                    "usage": {
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0)
                    }
                }
    except Exception as e:
        logger.error(f"LLM 추론 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_models():
    """사용 가능한 모델 목록"""
    return {
        "models": [
            {
                "id": "gemma-3-27b-it",
                "name": "Gemma 3 27B IT (기본, 멀티모달)",
                "context_length": 131072,
                "censored": True,
                "multimodal": True
            },
            {
                "context_length": 4096,
                "censored": False
            }
        ]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "llm"}
```

#### 4.2.3 LLM 서비스 Dockerfile

```dockerfile
# server-a/llm-service/Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
```

```txt
# server-a/llm-service/requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
httpx==0.25.0
pydantic==2.5.0
```

#### 4.2.4 docker-compose에 LLM 서비스 추가

```yaml
# server-a/docker-compose.yaml에 추가

services:
  llm-service:
    build: ./llm-service
    container_name: llm-service
    restart: unless-stopped
    ports:
      - "8002:8002"
    networks:
      - avatar-forge-network
    environment:
      - VLLM_BASE_URL=http://vllm-server:8002
    depends_on:
      - vllm-server
```

### 4.3 Server A: TTS 서비스 설정

#### 4.3.1 GPT-SoVITS Conda 환경 직접 설치 (용량 절약)

GPT-SoVITS는 Docker 이미지 대신 Conda 환경에서 직접 설치하여 용량을 절약합니다.

**저장소 선택** (둘 중 하나 선택 가능):

**옵션 1: GitHub 원본 (권장, 최신 코드)**
- **GitHub**: https://github.com/RVC-Boss/GPT-SoVITS
- 장점: 최신 코드, 공식 저장소, 활발한 업데이트
- 단점: 사전 학습 모델 파일을 별도로 다운로드해야 함
- 설치: `bash install.sh --device CU128 --source HF` (모델 자동 다운로드)

**옵션 2: Hugging Face 호스팅 버전**
- **Hugging Face**: https://huggingface.co/kevinwang676/GPT-SoVITS-v4
- 장점: 모델 파일이 포함되어 있을 수 있음
- 단점: 업데이트가 GitHub보다 느릴 수 있음

**⚠️ 권장**: GitHub 원본 저장소 사용 (최신 기능 및 버그 수정 포함)

**예상 용량**:
- 소스 코드: ~500MB-1GB
- Conda 환경 + 의존성: ~3-5GB
- 사전 학습 모델 (선택): ~2-3GB
- **총합: ~5-9GB** (Docker 이미지 ~8-15GB 대비 절약)

**참고**: 
- [GitHub 원본 README](https://github.com/RVC-Boss/GPT-SoVITS) (영어/중국어)
- [한국어 README](https://github.com/RVC-Boss/GPT-SoVITS/blob/main/docs/ko/README.md)

#### 4.3.2 TTS 서비스 FastAPI 래퍼 (선택사항)

```python
# server-a/tts-service/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)
app = FastAPI(title="Avatar Forge TTS Service")

MODEL_PATH = os.getenv("MODEL_PATH", "/models/gpt-sovits")

class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "default"
    speed: float = 1.0
    language: str = "ko"

@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    """텍스트를 음성으로 변환"""
    try:
        # GPT-SoVITS API 호출
        # 실제 구현은 GPT-SoVITS 라이브러리 사용
        # 예시 코드 (실제 구현 필요)
        audio_path = await generate_speech(
            text=request.text,
            model_path=MODEL_PATH,
            voice_id=request.voice_id,
            speed=request.speed,
            language=request.language
        )
        
        return {
            "audio_url": f"/audio/{os.path.basename(audio_path)}",
            "duration": get_audio_duration(audio_path),
            "file_id": os.path.basename(audio_path).replace(".wav", "")
        }
    except Exception as e:
        logger.error(f"TTS 합성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/voices")
async def list_voices():
    """사용 가능한 음성 목록"""
    return {
        "voices": [
            {
                "id": "default",
                "name": "기본 음성",
                "language": "ko",
                "gender": "female"
            }
        ]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "tts"}
```

#### 4.3.2 VRAM 관리 전략 (중요)

**⚠️ VRAM 제약 사항**:
- RTX 3090 24GB VRAM 사용
- 각 서비스 VRAM 사용량:
  - Gemma 3 27B IT (LLM): ~13-15GB
  - GPT-SoVITS (TTS): ~3-4GB
  - CharacterGen (3D): ~12-15GB
  - Stable Diffusion: ~8-12GB

**모드 스위칭 전략**:
- 한 번에 하나의 대형 서비스만 활성화 (VRAM 절약)
- 백엔드에서 요청 시 자동으로 모드 전환:
  - `chat` 모드: vLLM 활성, TTS/3D/SD 중지
  - `tts` 모드: GPT-SoVITS 활성, vLLM/3D/SD 중지
  - `gen3d` 모드: CharacterGen 활성, vLLM/TTS/SD 중지
  - `style` 모드: Stable Diffusion 활성, vLLM/TTS/3D 중지

**결론**: Conda로 설치하든 Docker로 설치하든, VRAM 사용량은 동일합니다. 백엔드에서 TTS 요청 시 자동으로 모드가 전환되므로 VRAM 문제 없이 사용 가능합니다.

#### 4.3.3 GPT-SoVITS 설치 및 실행

**1단계: Conda 환경 생성**

```bash
# Conda 설치 확인 (없으면 설치 필요)
conda --version

# Conda Terms of Service 동의 (최신 Conda 버전에서 필요)
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# 또는 conda-forge 채널만 사용 (ToS 문제 회피, 권장)
conda config --add channels conda-forge
conda config --set channel_priority strict

# Conda 환경 생성
conda create -n GPTSoVits python=3.9 -y
conda activate GPTSoVits
```

**2단계: 저장소 클론**

```bash
# GitHub 원본 저장소에서 클론 (권장, 최신 코드)
cd /opt
git clone https://github.com/RVC-Boss/GPT-SoVITS.git GPT-SoVITS
cd GPT-SoVITS

# 또는 Hugging Face 버전 사용 시
# git clone https://huggingface.co/kevinwang676/GPT-SoVITS-v4.git GPT-SoVITS
```

**3단계: 의존성 설치**

**⚠️ 매우 중요: Python, PyTorch, torchcodec 버전 호환성**

GPT-SoVITS를 사용할 때는 **반드시 Python, PyTorch, torchcodec 버전이 호환되어야 합니다**. 잘못된 버전 조합은 ImportError, 런타임 오류 등을 발생시킬 수 있습니다.

**공식 문서를 반드시 참고하세요**:
- [GPT-SoVITS 공식 저장소](https://github.com/RVC-Boss/GPT-SoVITS)
- [GPT-SoVITS 한국어 README](https://github.com/RVC-Boss/GPT-SoVITS/blob/main/docs/ko/README.md)

**PyTorch 버전 선택 가이드**:
- CUDA 버전에 따라 PyTorch 버전이 자동으로 결정됩니다
- `install.sh --device CU126`: CUDA 12.6/12.7용 PyTorch 설치
- `install.sh --device CU128`: CUDA 12.8/13.0/13.1용 PyTorch 설치
- Python 3.9와 호환되는 PyTorch 버전이 자동으로 설치됩니다

```bash
# CUDA 버전 확인
nvidia-smi  # CUDA Version 확인

# 설치 스크립트 실행 (자동 설치, 모델 자동 다운로드 포함)
# ⚠️ PyTorch 버전은 --device 옵션에 따라 자동으로 결정됩니다
# CUDA 12.6/12.7: --device CU126
# CUDA 12.8/13.0/13.1: --device CU128
bash install.sh --device CU128 --source HF

# 설치 후 버전 확인 (권장)
python -c "import sys; print(f'Python: {sys.version}')"
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import torchcodec; print('torchcodec: 설치됨')" || echo "torchcodec: 확인 필요"

# 또는 수동 설치 (권장하지 않음, 버전 호환성 문제 가능)
# pip install -r extra-req.txt --no-deps
# pip install -r requirements.txt

# FFmpeg 설치
sudo apt install ffmpeg libsox-dev
conda install -c conda-forge 'ffmpeg<7' -y
```

**⚠️ 참고**: `install.sh` 스크립트는 사전 학습 모델도 자동으로 다운로드합니다. 수동 다운로드가 필요하면 [GPT-SoVITS Models](https://huggingface.co/lj1995/GPT-SoVITS)에서 다운로드하세요.

**4단계: systemd 서비스 등록 (자동 시작)**

**systemd 서비스를 사용하는 이유**:
1. **자동 시작**: 서버 재부팅 시 자동으로 GPT-SoVITS가 시작됨
2. **자동 재시작**: 프로세스가 비정상 종료되면 자동으로 재시작 (`Restart=always`)
3. **백그라운드 실행**: 터미널을 종료해도 계속 실행됨
4. **로그 관리**: `journalctl`로 통합 로그 확인 가능
5. **서비스 관리**: `systemctl start/stop/restart` 명령어로 간편하게 관리

```ini
# /etc/systemd/system/gpt-sovits.service 생성
[Unit]
Description=GPT-SoVITS TTS Service
After=network.target  # 네트워크가 준비된 후 실행

[Service]
Type=simple
User=root
WorkingDirectory=/opt/GPT-SoVITS
Environment="PATH=/root/miniconda3/envs/GPTSoVits/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/root/miniconda3/envs/GPTSoVits/bin/python webui.py ko-KR
Restart=always      # 프로세스 종료 시 자동 재시작
RestartSec=10       # 재시작 전 10초 대기
StandardOutput=journal  # 로그를 systemd journal에 저장
StandardError=journal   # 에러 로그도 journal에 저장

[Install]
WantedBy=multi-user.target  # 부팅 시 자동 시작
```

```bash
# 서비스 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable gpt-sovits
sudo systemctl start gpt-sovits

# 상태 확인
sudo systemctl status gpt-sovits

# 로그 확인 (실시간)
sudo journalctl -u gpt-sovits -f

# 또는 로그 확인 스크립트 사용
bash scripts/server-a/monitor-system.sh
# 옵션 3 선택 (GPT-SoVITS 로그 확인)
```

**5단계: NPM 프록시 설정**

NPM에서 TTS 서비스 프록시 설정:
- Domain Names: `tts.server-a.local` (또는 실제 도메인)
- Scheme: `http`
- Forward Hostname/IP: `127.0.0.1` (또는 `localhost`)
- Forward Port: `9874` (GPT-SoVITS WebUI 기본 포트, 실행 시 확인된 포트 사용)
- SSL: Let's Encrypt 활성화

**⚠️ GPT-SoVITS 포트 구분 (매우 중요!)**:

GPT-SoVITS는 **3개의 포트를 모두 사용**합니다:
- **포트 9872**: TTS API (텍스트-음성 변환 서비스) ← **NPM 프록시는 이 포트 사용**
- **포트 9873**: 반주 분리 (UVR5) 서비스 ← **사용**
- **포트 9874**: GPT-SoVITS WebUI (관리 인터페이스) ← **사용**

**⚠️ 중요: `0.0.0.0`은 서버 바인딩 주소입니다**
- `0.0.0.0:9872`는 "모든 네트워크 인터페이스에서 9872 포트 수신"을 의미
- 클라이언트(NPM 포함)는 `127.0.0.1:9872` 또는 `localhost:9872`로 접근해야 함
- `http://0.0.0.0:9872/`는 직접 접근할 수 없는 주소입니다

**포트 확인 방법**:
```bash
# 모든 GPT-SoVITS 포트 확인
sudo netstat -tlnp | grep -E "987[234]"
# 또는
sudo ss -tlnp | grep -E "987[234]"

# systemd 로그에서 포트 확인
sudo journalctl -u gpt-sovits -n 50 | grep -i "running\|port"

# 각 포트별 용도:
# 9872: TTS API (실제 서비스)
# 9873: 반주 분리 (UVR5)
# 9874: WebUI (관리 인터페이스)
```

**NPM 설정 단계 (호스트 Conda 서비스 연결)**:

1. **NPM 웹 콘솔 접속**: `http://<Server-A-IP>:81`
2. **"Proxy Hosts" → "Add Proxy Host" 클릭**
3. **Details 탭**:
   - Domain Names: `tts.server-a.local` (또는 실제 도메인)
   - **Scheme: `http`** (⚠️ 중요: 반드시 http, https 아님)
   - Forward Hostname/IP: `172.17.0.1` (Docker bridge 게이트웨이 IP)
   - **Forward Port: `9872`** (⚠️ 중요: TTS API 포트, WebUI 9874가 아님!)
4. **SSL 탭**:
   - SSL Certificate: "Request a new SSL Certificate" 선택
   - Force SSL: 체크 (외부 접근은 HTTPS로, 내부는 HTTP)
   - HTTP/2 Support: 체크
5. **"Save" 클릭**

**⚠️ 502 Bad Gateway 오류 시 확인 사항**:
- Scheme이 `http`인지 확인 (가장 흔한 원인)
- Forward Hostname/IP가 `172.17.0.1`인지 확인
- 포트가 실제 실행 중인 포트와 일치하는지 확인
- 연결 테스트: `bash scripts/server-a/monitor-system.sh` (옵션 6)

**접근 방법**:
- **TTS API**: `https://tts.server-a.local` (NPM을 통해, 포트 9872)
- **WebUI (직접)**: `http://<Server-A-IP>:9874` (관리 인터페이스, 개발/테스트용)
- **반주 분리 (직접)**: `http://<Server-A-IP>:9873` (UVR5 서비스, 개발/테스트용)

**⚠️ NPM에서 접근 불가 시 문제 해결**:

```bash
# 진단 스크립트 실행
bash scripts/server-a/troubleshoot-gpt-sovits-npm.sh
```

**일반적인 문제 및 해결**:

1. **서비스가 실행되지 않음**
   ```bash
   sudo systemctl status gpt-sovits
   sudo systemctl start gpt-sovits
   ```

2. **포트가 다름**
   ```bash
   # 실제 포트 확인
   sudo journalctl -u gpt-sovits -n 50 | grep -i "running\|port"
   # 또는
   sudo netstat -tlnp | grep python
   ```

3. **NPM이 bridge 네트워크인 경우 (해결됨)**
   - ✅ `172.17.0.1` 사용 (Docker bridge 게이트웨이 IP)
   - ⚠️ `127.0.0.1`은 작동하지 않음 (컨테이너 내부의 localhost를 가리킴)
   - 해결: `bash scripts/server-a/setup-services.sh` (옵션 1)로 NPM 재설정

4. **직접 접근 테스트**
   ```bash
   # TTS API 포트 (9872) 테스트
   curl http://localhost:9872
   
   # 반주 분리 포트 (9873) 테스트
   curl http://localhost:9873
   
   # WebUI 포트 (9874) 테스트
   curl http://localhost:9874
   
   # NPM 컨테이너에서 TTS API 테스트
   docker exec npm curl http://172.17.0.1:9872
   ```

**통합 스크립트 사용 (권장)**:

```bash
# GPT-SoVITS 통합 관리 (설치, 재설치, 삭제, 서비스 관리, 의존성 재설치)
bash scripts/server-a/manage-gpt-sovits.sh
```

이 스크립트는 다음 기능을 제공합니다:
1. **설치**: 처음 설치 (Conda 환경 + 소스 코드 + 의존성 + systemd 서비스)
   - ⚠️ PyTorch 버전 선택 메시지 표시 (공식 문서 참고 필수)
2. **재설치**: 완전 삭제 후 재설치
3. **삭제**: 완전 제거
4. **서비스 관리**: 시작/중지/재시작/상태 확인
5. **systemd 서비스 생성**: 서비스만 생성
6. **의존성 재설치**: 의존성만 재설치
   - ⚠️ 버전 호환성 경고 표시

**모니터링 및 정리 스크립트**:

```bash
# 시스템 모니터링 (디스크, 로그, 포트, 모델, NPM 연결)
bash scripts/server-a/monitor-system.sh

# 시스템 정리 (디스크, Docker)
bash scripts/server-a/cleanup-system.sh

# 서비스 설정 (NPM, 모델 스토리지)
bash scripts/server-a/setup-services.sh
```

**⚠️ 매우 중요: Python, PyTorch, torchcodec 버전 호환성**

GPT-SoVITS를 사용할 때는 **반드시 Python, PyTorch, torchcodec 버전이 호환되어야 합니다**. 잘못된 버전 조합은 ImportError, 런타임 오류 등을 발생시킬 수 있습니다.

**공식 문서를 반드시 참고하세요**:
- [GPT-SoVITS 공식 저장소](https://github.com/RVC-Boss/GPT-SoVITS)
- [GPT-SoVITS 한국어 README](https://github.com/RVC-Boss/GPT-SoVITS/blob/main/docs/ko/README.md)

**PyTorch 버전 선택**:
- 설치 시 `manage-gpt-sovits.sh`에서 PyTorch 버전 선택 메시지가 표시됩니다
- CUDA 버전에 따라 적절한 버전을 선택하세요
- 공식 문서의 호환성 표를 참고하세요

### 4.4 Server B: Main Backend 설정

#### 4.4.1 Main Backend FastAPI 구조

```python
# server-b/backend/app/api/chat.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import httpx
import os
import uuid
from app.services.context_manager import ContextManager
from app.core.rate_limiter import ConcurrentUserLimiter
from app.api.deps import get_current_user

router = APIRouter()

# Server A의 NPM URL
SERVER_A_NPM_URL = os.getenv("SERVER_A_NPM_URL", "https://server-a.local")

# 서비스 인스턴스
context_manager = ContextManager()
user_limiter = ConcurrentUserLimiter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    persona: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    model: str = "gemma-3-27b-it"
    session_id: Optional[str] = None  # 세션 ID (자동 생성)

@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user = Depends(get_current_user)
):
    """캐릭터와 대화 (무제한 대화 지원, 자동 요약)"""
    try:
        # 1. 동시 접속 제한 확인
        await user_limiter.check_limit(current_user.id)
        
        # 2. 세션 ID 생성/조회
        session_id = request.session_id or str(uuid.uuid4())
        
        # 3. 컨텍스트 관리 (자동 요약 포함)
        optimized_messages = await context_manager.manage_context(
            session_id=session_id,
            new_messages=request.messages,
            persona=request.persona
        )
        
        # 4. Server A의 LLM 서비스 호출
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                f"{SERVER_A_NPM_URL}/llm/chat",
                json={
                    "messages": [msg.dict() for msg in optimized_messages],
                    "persona": request.persona,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "model": request.model
                },
                timeout=60.0
            )
            result = response.json()
        
        return {
            "success": True,
            "data": {
                **result,
                "session_id": session_id,
                "context_summarized": context_manager.was_summarized(session_id)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 세션 해제는 클라이언트가 명시적으로 요청하거나 TTL로 자동 해제
        pass

@router.get("/chat/models")
async def list_models():
    """사용 가능한 모델 목록"""
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                f"{SERVER_A_NPM_URL}/llm/models",
                timeout=10.0
            )
            result = response.json()
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

```python
# server-b/backend/app/api/tts.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import os

router = APIRouter()

SERVER_A_NPM_URL = os.getenv("SERVER_A_NPM_URL", "https://server-a.local")

class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "default"
    speed: float = 1.0
    language: str = "ko"

@router.post("/tts")
async def synthesize(request: TTSRequest):
    """텍스트를 음성으로 변환"""
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                f"{SERVER_A_NPM_URL}/tts/synthesize",
                json=request.dict(),
                timeout=30.0
            )
            result = response.json()
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 5. Phase 5.2-5.4 구현 가이드 (2026-01-26)

### 5.1 Phase 5.2: 컨텍스트 절약 요약 기능 구현

**구현 위치**: `server-b/backend/app/services/context_manager.py` (신규 생성)

**구현 시기**: Phase 5.1 완료 후 즉시 구현 (우선순위: 높음, 필수 기능)

**필수 의존성**:
```bash
# Redis 설치 (세션 저장용)
# Server B에서 실행
sudo apt update
sudo apt install -y redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Python Redis 클라이언트
pip install redis tiktoken
```

**구현 단계**:

1. **ContextManager 서비스 생성**:
```python
# server-b/backend/app/services/context_manager.py
from typing import List, Dict, Optional
import tiktoken
import redis.asyncio as redis
import os
import json
from app.api.chat import Message
import httpx

class ContextManager:
    def __init__(self):
        self.redis_client = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379")
        )
        self.max_context_tokens = 4096
        self.recent_turns_to_keep = 18
        self.summary_threshold = 0.8
        self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 토큰 인코더
        
    async def manage_context(
        self,
        session_id: str,
        new_messages: List[Message],
        persona: Optional[str] = None,
        situation: Optional[str] = None
    ) -> List[Message]:
        """대화 히스토리 관리 및 자동 요약"""
        # 1. 세션 히스토리 조회
        history = await self.get_session_history(session_id)
        
        # 2. 새 메시지 추가
        history.extend(new_messages)
        
        # 3. 토큰 수 계산
        total_tokens = self.count_tokens(history, persona, situation)
        
        # 4. 요약 필요 여부 판단
        if total_tokens > self.max_context_tokens * self.summary_threshold:
            history = await self.summarize_old_messages(
                history,
                keep_recent=self.recent_turns_to_keep
            )
        
        # 5. 세션 히스토리 저장
        await self.save_session_history(session_id, history)
        
        # 6. 최종 메시지 리스트 반환
        return self.build_final_messages(history, persona, situation)
    
    async def summarize_old_messages(
        self,
        messages: List[Message],
        keep_recent: int = 18
    ) -> List[Message]:
        """오래된 메시지를 요약하여 압축"""
        if len(messages) <= keep_recent:
            return messages
        
        recent_messages = messages[-keep_recent:]
        old_messages = messages[:-keep_recent]
        
        # LLM으로 요약 생성 (vLLM 서버 사용)
        summary = await self.generate_summary(old_messages)
        
        # 요약을 시스템 메시지로 추가
        summary_message = Message(
            role="system",
            content=f"[이전 대화 요약] {summary}"
        )
        
        return [summary_message] + recent_messages
    
    async def generate_summary(self, messages: List[Message]) -> str:
        """LLM을 사용하여 대화 요약 생성"""
        # vLLM 서버로 요약 요청
        # 간단한 프롬프트로 요약 생성
        pass
```

2. **chat.py에 통합**:
```python
# server-b/backend/app/api/chat.py 수정
from app.services.context_manager import ContextManager

context_manager = ContextManager()

@router.post("/chat")
async def chat(request: ChatRequest, current_user = Depends(get_current_user)):
    # ... 기존 코드 ...
    
    # 컨텍스트 관리 추가
    optimized_messages = await context_manager.manage_context(
        session_id=request.session_id or str(uuid.uuid4()),
        new_messages=request.messages,
        persona=request.persona
    )
    
    # ... 나머지 코드 ...
```

### 5.2 Phase 5.3: 동시 접속 제한 구현

**구현 위치**: `server-b/backend/app/core/rate_limiter.py` (신규 생성)

**구현 시기**: Phase 5.1 완료 후 즉시 구현 (우선순위: 높음, 필수 기능)

**필수 의존성**: Redis (Phase 5.2와 동일)

**구현 단계**:

1. **ConcurrentUserLimiter 생성**:
```python
# server-b/backend/app/core/rate_limiter.py
from fastapi import HTTPException, status
import redis.asyncio as redis
import os

class ConcurrentUserLimiter:
    def __init__(self):
        self.redis_client = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379")
        )
        self.max_users = int(os.getenv("MAX_CONCURRENT_USERS", "20"))
        self.key_prefix = "active_sessions:"
        self.session_ttl = 3600  # 1시간
        
    async def check_limit(self, user_id: str) -> bool:
        """동시 접속 제한 확인"""
        active_count = await self.get_active_count()
        
        if active_count >= self.max_users:
            is_existing = await self.is_user_active(user_id)
            if not is_existing:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"최대 동시 접속자 수({self.max_users}명)에 도달했습니다. 잠시 후 다시 시도해주세요."
                )
        
        await self.register_session(user_id)
        return True
    
    async def get_active_count(self) -> int:
        """현재 활성 세션 수 조회"""
        keys = await self.redis_client.keys(f"{self.key_prefix}*")
        return len(keys)
    
    async def register_session(self, user_id: str):
        """세션 등록"""
        await self.redis_client.setex(
            f"{self.key_prefix}{user_id}",
            self.session_ttl,
            "active"
        )
    
    async def release_session(self, user_id: str):
        """세션 해제"""
        await self.redis_client.delete(f"{self.key_prefix}{user_id}")
```

2. **chat.py에 통합**:
```python
# server-b/backend/app/api/chat.py 수정
from app.core.rate_limiter import ConcurrentUserLimiter

user_limiter = ConcurrentUserLimiter()

@router.post("/chat")
async def chat(request: ChatRequest, current_user = Depends(get_current_user)):
    # 동시 접속 제한 확인
    await user_limiter.check_limit(current_user.id)
    
    # ... 나머지 코드 ...
```

3. **환경 변수 설정**:
```bash
# server-b/backend/.env
MAX_CONCURRENT_USERS=20
REDIS_URL=redis://localhost:6379
```

### 5.3 Phase 5.4: Frontend 턴 제한 설정화 ✅ **구현 완료**

**구현 위치**: `components/chat-room.tsx`

**구현 시기**: Phase 5.1 완료 후

**구현 상태**: ✅ **구현 완료** (2026-01-26)

**구현 완료된 단계**:

1. **턴 제한 설정화** ✅:
```typescript
// components/chat-room.tsx
// 하드코딩 제거, 환경 변수 지원
const maxTurns = typeof window !== "undefined"
  ? parseInt(process.env.NEXT_PUBLIC_MAX_TURNS || "30", 10)
  : 30
```

2. **세션 관리 추가** ✅:
```typescript
// 세션 ID 자동 생성 (crypto.randomUUID() 사용)
useEffect(() => {
  if (isVisible && !sessionId) {
    const newSessionId = crypto.randomUUID()
    setSessionId(newSessionId)
  }
}, [isVisible, sessionId, setSessionId])
```

3. **API 호출 시 session_id 포함** ✅:
```typescript
const response = await chatApi.chat({
  messages: chatMessages,
  persona: persona,
  character_id: selectedCharacter?.id,
  scenario: {
    opponent: scenario.opponent,
    situation: scenario.situation,
    background: scenario.background,
  },
  session_id: sessionId,
  tts_enabled: ttsEnabled,
  tts_mode: ttsMode,
  tts_delay_ms: ttsDelayMs,
  tts_streaming_mode: ttsStreamingMode,
})
```

**상세 구현 내역**: `docs/구현_상태_요약_2026-01-26.md`의 "ChatRoom API 연동 및 TTS 통합 구현 상세" 섹션 참조

---

### 5.4 7단계: ChatRoom API 연동 및 TTS 통합 ✅ **구현 완료**

**구현 시기**: Phase 5.1 완료 후

**구현 상태**: ✅ **구현 완료** (2026-01-26)

#### 5.4.1 Backend ChatRequest/ChatResponse 확장 ✅

**파일**: `server-b/backend/app/api/chat.py`

**구현 완료된 내용**:
- [x] `ChatRequest` 모델 확장:
  - `session_id`: 세션 ID (선택, 자동 생성)
  - `character_id`: 캐릭터 ID (voice_id 조회용)
  - `scenario`: 시나리오 정보 (opponent, situation, background)
  - `tts_enabled`: TTS 활성화 여부 (기본값: True)
  - `tts_mode`: TTS 호출 방식 ("realtime" | "delayed" | "on_click")
  - `tts_delay_ms`: 지연 시간 (밀리초)
  - `tts_streaming_mode`: GPT-SoVITS streaming_mode (0-3)
- [x] `ChatResponse` 모델 확장:
  - `session_id`: 세션 ID
  - `audio_url`: 생성된 오디오 파일 URL
  - `context_summarized`: 컨텍스트 요약 여부 (Phase 5.2에서 구현 예정)

#### 5.4.2 Backend TTS 통합 ✅

**파일**: `server-b/backend/app/api/chat.py`

**구현 완료된 내용**:
- [x] Character 조회 로직 (`get_character_by_id` 함수)
- [x] TTS 통합 로직 (채팅 응답 후 자동 TTS 호출)
- [x] `_synthesize_tts_internal` 함수 직접 호출
- [x] character.voice_id 사용 (없으면 "default")
- [x] TTS 실패 시에도 채팅 응답은 정상 반환

#### 5.4.3 Frontend 타입 확장 ✅

**파일**: `lib/api/types.ts`

**구현 완료된 내용**:
- [x] `ChatRequest` 타입 확장 (TTS 필드, scenario, character_id, session_id)
- [x] `ChatResponse` 타입 확장 (audio_url, session_id, context_summarized)
- [x] `TTSRequest` 타입 확장 (streaming_mode, return_binary 등)

#### 5.4.4 ChatRoom 컴포넌트 수정 ✅

**파일**: `components/chat-room.tsx`

**구현 완료된 내용**:
- [x] 세션 관리 (UUID 자동 생성)
- [x] 초기 메시지 API 생성 (sample_dialogue 우선, API 폴백)
- [x] 실제 API 연동 (하드코딩된 응답 완전 제거)
- [x] TTS 통합 (audio_url 처리, 오디오 재생)
- [x] 에러 처리 개선 (Toast, retryWithBackoff)
- [x] 턴 제한 설정화 (환경 변수 지원)

#### 5.4.5 TTS 설정 모달 ✅

**파일**: `components/tts-settings-modal.tsx` (신규 생성)

**구현 완료된 내용**:
- [x] TTS 호출 방식 선택 (realtime/delayed/on_click)
- [x] streaming_mode 선택 (0-3)
- [x] 지연 시간 설정 (슬라이더)
- [x] TTS 활성화/비활성화 토글
- [x] ChatRoom 헤더에 TTS 설정 버튼 추가

**상세 구현 내역**: `docs/구현_상태_요약_2026-01-26.md`의 "ChatRoom API 연동 및 TTS 통합 구현 상세" 섹션 참조

---

### 5.5 8단계: 페르소나 전달 방식 개선 ✅ **구현 완료**

**구현 시기**: Phase 5.1 완료 후

**구현 상태**: ✅ **구현 완료** (2026-01-26)

#### 5.5.1 Backend format_persona_for_roleplay() 함수 구현 ✅

**파일**: `server-b/backend/app/api/chat.py`

**구현 완료된 내용**:
- [x] `format_persona_for_roleplay()` 함수 구현
- [x] 역할극에 적합한 구조화된 형식으로 페르소나 포맷팅
- [x] 캐릭터 이름 포함 (있는 경우)
- [x] 시나리오 정보 포함 (opponent, situation, background)
- [x] 역할극 지시사항 자동 추가

**페르소나 포맷팅 형식**:
```
당신은 {character_name}입니다.

{persona}

현재 상황: {situation}
배경: {background}
상대방: {opponent}

중요 지침:
- 캐릭터의 성격과 말투를 일관되게 유지하세요.
- 사용자와 자연스럽게 대화하세요.
- 캐릭터의 특성을 반영한 응답을 생성하세요.
- 이전 대화의 맥락을 고려하여 응답하세요.
```

#### 5.5.2 ChatRequest에 scenario 필드 추가 ✅

**파일**: `server-b/backend/app/api/chat.py`

**구현 완료된 내용**:
- [x] `scenario: Optional[Dict[str, str]] = None` 필드 추가
- [x] `opponent`: 상대방 이름
- [x] `situation`: 현재 상황
- [x] `background`: 배경 설명 (선택적)

#### 5.5.3 chat 엔드포인트 수정 ✅

**파일**: `server-b/backend/app/api/chat.py`

**구현 완료된 내용**:
- [x] `format_persona_for_roleplay()` 사용
- [x] 시나리오 정보 포함
- [x] Character 조회 시 `character.name`도 사용
- [x] 매 요청마다 system 메시지 포함 (Ollama 요구사항)
- [x] 대화 히스토리와 함께 LLM에 전달

#### 5.5.4 Frontend 시나리오 정보 전달 ✅

**파일**: `components/chat-room.tsx`

**구현 완료된 내용**:
- [x] `ChatRequest` 타입에 scenario 필드 추가
- [x] `chatApi.chat()` 호출 시 scenario 정보 포함
- [x] 모든 API 호출에 scenario 정보 포함 (초기 메시지, 일반 채팅)

#### 5.5.5 로깅 기능 ✅

**구현 완료된 내용**:
- [x] Backend 로깅 (개발 환경, DEBUG 환경 변수 기반)
- [x] Frontend 로깅 (개발 환경, NODE_ENV 기반)
- [x] 페르소나 포맷팅 결과 로깅
- [x] 메시지 배열 길이 로깅

**상세 구현 내역**: `docs/구현_상태_요약_2026-01-26.md`의 "페르소나 전달 방식 개선 구현 상세" 섹션 참조

## 6. 통합 테스트

### 5.1 서비스 헬스체크

```bash
# Server A - LLM 서비스
curl http://localhost:8002/health

# Server A - TTS 서비스
curl http://localhost:8003/health

# Server B - Main Backend
curl http://localhost:8000/api/health
```

### 5.2 LLM 채팅 테스트

```bash
# Server B를 통해 LLM 호출
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "안녕하세요!"}
    ],
    "persona": "밝고 명랑한 10대 소녀 캐릭터",
    "model": "gemma-3-27b-it"
  }'
```

### 5.3 TTS 테스트

```bash
# Server B를 통해 TTS 호출
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "안녕하세요, 반갑습니다!",
    "language": "ko"
  }'
```

---

## 6. 문제 해결

### 6.1 NVIDIA Container Toolkit 관련

**문제**: `nvidia-smi`가 컨테이너 내에서 작동하지 않음
- **해결**: 
  ```bash
  sudo systemctl restart docker
  docker-compose down
  docker-compose up -d
  ```

**문제**: `nvidia-container-toolkit` 패키지를 찾을 수 없음
- **해결**: 
  ```bash
  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
  ```

### 6.2 Conda 설치 관련

**문제**: `CondaToSNonInteractiveError: Terms of Service have not been accepted`
- **원인**: 최신 Conda 버전에서 Anaconda 채널 사용 시 ToS 동의 필요
- **해결 방법 1**: ToS 수락 (권장)
  ```bash
  conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
  conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
  ```
- **해결 방법 2**: conda-forge 채널만 사용 (ToS 문제 회피)
  ```bash
  conda config --add channels conda-forge
  conda config --set channel_priority strict
  conda create -n GPTSoVits python=3.9 -y
  ```

### 6.3 디스크 사용량 관리

**전체 설치 항목 용량 확인**:

```bash
# PHASE5_SETUP.md에 설치된 모든 항목의 용량 확인
bash scripts/server-a/monitor-system.sh
# 옵션 1 선택 (전체 설치 항목 용량 확인)
```

이 스크립트는 다음을 확인합니다:
- LLM 모델 (Gemma 3 27B IT)
- TTS 모델 (GPT-SoVITS: 소스 코드 + Conda 환경)
- 3D 생성 모델 (CharacterGen)
- 스타일 변환 모델 (Stable Diffusion)
- Docker 이미지
- 캐시 파일 (Python, pip, Hugging Face, Conda)
- 전체 디스크 사용량 및 여유 공간

**GPT-SoVITS 관련 파일만 확인 및 정리**:

```bash
# GPT-SoVITS 관련 파일 크기 확인 및 정리
bash scripts/server-a/monitor-system.sh
# 옵션 2 선택 (GPT-SoVITS 디스크 사용량 확인)
```

이 스크립트는 다음을 확인합니다:
- 소스 코드 디렉터리 크기 (`/opt/GPT-SoVITS`)
- Conda 환경 크기 (`GPTSoVits`)
- Python 캐시 (`__pycache__`, `.pyc`)
- pip 캐시
- Hugging Face 캐시
- Conda 패키지 캐시

**정리 가능한 항목**:
1. Python 캐시: `__pycache__`, `.pyc` 파일 (재생성 가능)
2. pip 캐시: 패키지 다운로드 캐시 (재다운로드 가능)
3. Conda 패키지 캐시: Conda 패키지 캐시 (재다운로드 가능)
4. Hugging Face 캐시: ⚠️ 주의 - 모델 재다운로드 필요

**디스크 공간 부족 시 정리 스크립트**:

```bash
# 캐시 정리 (안전한 정리)
bash scripts/server-a/cleanup-system.sh
# 옵션 1 선택 (디스크 공간 정리)
```

이 스크립트는 다음을 정리합니다:
- pip 캐시 정리
- Hugging Face 캐시 정리 (2.0GB)
- Conda 패키지 캐시 정리 (2.7GB)
- Python 캐시 정리
- Docker 사용하지 않는 이미지 (선택)


**Docker 공간 정리**:

```bash
# Docker 공간 정리
bash scripts/server-a/cleanup-system.sh
# 옵션 2 선택 (Docker 공간 정리)
```

이 스크립트는 다음을 정리합니다:
- 사용하지 않는 이미지 삭제
- 사용하지 않는 컨테이너 삭제
- 사용하지 않는 네트워크 삭제
- 빌드 캐시 정리
- 사용하지 않는 볼륨 정리 (선택)

**정리 옵션**:
1. 사용하지 않는 이미지만 삭제 (가장 안전)
2. 사용하지 않는 모든 항목 삭제
3. 빌드 캐시만 정리
4. 볼륨 정리 (⚠️ 주의)
5. 전체 정리 (⚠️ 주의)

**현재 Docker 사용량 확인**:
```bash
docker system df
```

또는 통합 스크립트:
```bash
bash scripts/server-a/monitor-system.sh
# 옵션 1 선택 (전체 설치 항목 용량 확인 - Docker 포함)
```

### 6.4 GPT-SoVITS 포트 및 네트워크 설정

#### 6.4.1 GPT-SoVITS 포트 구분

**⚠️ 매우 중요**: GPT-SoVITS는 **3개의 포트를 모두 사용**합니다:

| 포트 | 용도 | 설명 | 접근 방법 |
|------|------|------|----------|
| **9872** | **TTS API** | 텍스트-음성 변환 서비스 (실제 TTS API) | NPM 프록시 또는 직접 접근 |
| **9873** | 반주 분리 (UVR5) | 오디오에서 반주 분리 서비스 | 직접 접근 또는 내부 API 호출 |
| **9874** | WebUI | GPT-SoVITS 관리 인터페이스 | 직접 접근 |

**참고 자료**: 이 포트 구분 정보는 다음 자료를 참고하여 확인되었습니다:
- [Notion 문서](https://www.notion.so/1d6d3e41a6c0809b8f6afb53f7b985c3?v=1d6d3e41a6c081928e59000c47330846&source=copy_link)
- [Arca.live - CharacterAI 게시판](https://arca.live/b/characterai/114903135?)
- [Arca.live - AISpeech 게시판 1](https://arca.live/b/aispeech/76792418)
- [Arca.live - AISpeech 게시판 2](https://arca.live/b/aispeech/77906451)

#### 6.4.2 NPM과 호스트 Conda 서비스 연결

**문제**: Docker 컨테이너(NPM)에서 호스트 서버의 Conda 서비스(GPT-SoVITS) 접근

**해결 방법**:

1. **NPM 컨테이너 설정**: bridge 네트워크 사용 (기본값)

2. **호스트 서비스 바인딩 확인**:
   ```bash
   # 모든 GPT-SoVITS 포트 확인
   sudo ss -tlnp | grep -E "987[234]"
   # 출력 예시:
   # 0.0.0.0:9872 ✅ (TTS API)
   # 0.0.0.0:9873 ✅ (반주 분리)
   # 0.0.0.0:9874 ✅ (WebUI)
   ```

3. **NPM 웹 콘솔 설정**:
   - Domain Names: `tts.server-a.local`
   - **Scheme: `http`** (⚠️ 중요!)
   - Forward Hostname/IP: `172.17.0.1` (Docker bridge 게이트웨이 IP)
   - **Forward Port: `9872`** (⚠️ 매우 중요: TTS API 포트, WebUI 9874가 아님!)

4. **연결 테스트**:
   ```bash
   # TTS API 포트 (9872) 테스트
   curl http://localhost:9872
   
   # NPM 컨테이너에서 테스트
   docker exec npm curl http://172.17.0.1:9872
   ```

**502 Bad Gateway 오류 해결**:
- **원인 1**: Scheme이 `https`로 설정됨 → **해결**: `http`로 변경
- **원인 2**: Forward Hostname/IP가 `127.0.0.1` → **해결**: `172.17.0.1` 사용 (Docker bridge 게이트웨이)
- **원인 3**: Forward Port가 `9874` → **해결**: `9872` 사용 (TTS API 포트)

### 6.5 GPT-SoVITS 오류 해결

#### 6.5.1 torchcodec ImportError

**증상**:
```
ImportError: TorchCodec is required for load_with_torchcodec. Please install torchcodec to use this function.
```

**원인**:
- **Python, PyTorch, torchcodec 버전 호환성 문제**
- GPT-SoVITS는 이 세 가지 버전이 반드시 호환되어야 합니다
- 잘못된 버전 조합으로 인한 오류

**해결 방법**:

**방법 1: 의존성 재설치 (빠른 시도)**
```bash
# 통합 관리 스크립트 사용 (권장)
bash scripts/server-a/manage-gpt-sovits.sh
# 옵션 6 선택 (의존성 재설치)
# 옵션 2 선택 (extra-req + requirements)
```

**방법 2: 완전 재설치 (가장 확실, 권장)**
```bash
# PyTorch 버전을 올바르게 선택하여 재설치
bash scripts/server-a/manage-gpt-sovits.sh
# 옵션 2 선택 (재설치)
# PyTorch 버전 선택 시 공식 문서 참고
```

**방법 3: 수동 해결 (권장하지 않음)**
```bash
conda activate GPTSoVits
pip install torchcodec
sudo systemctl restart gpt-sovits
```

**⚠️ 중요**: 수동 설치 시 PyTorch 버전과 호환되는 torchcodec 버전을 설치해야 합니다. 공식 문서를 반드시 참고하세요.

#### 6.5.2 디스크 공간 부족

**문제**: `OSError: [Errno 28] No space left on device`
- **원인**: 디스크 공간 부족으로 모델 다운로드 실패
- **해결**:
  ```bash
  # 1. 디스크 공간 확보
  bash scripts/server-a/cleanup-system.sh
  # 옵션 1 선택 (디스크 공간 정리)
  
  # 2. 서비스 재시작
  sudo systemctl restart gpt-sovits
  ```

#### 6.5.2 데이터셋 파일 형식 오류

**문제**: `ValueError: not enough values to unpack (expected 4, got 1)`
- **원인**: 데이터셋 `.list` 파일 형식이 잘못됨
- **올바른 형식**: `vocal_path|speaker_name|language|text`
- **해결**:
  ```bash
  # ASR 결과 파일 확인
  cat /opt/GPT-SoVITS/output/asr_opt/slicer_opt.list | head -5
  
  # 형식이 잘못된 경우 WebUI에서 ASR 단계를 다시 실행
  # 또는 파일을 수동으로 수정
  ```

#### 6.5.3 ModelScope 다운로드 실패

**문제**: `File am.mvn download incomplete`
- **원인**: 디스크 공간 부족 또는 ModelScope 캐시 손상
- **해결**:
  ```bash
  # ModelScope 캐시 정리
  rm -rf ~/.cache/modelscope/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch
  
  # WebUI에서 ASR 재실행
  ```

#### 6.5.4 Tokenization & BERT Feature Extraction 오류

**문제**: `Error: Tokenization & BERT Feature Extraction Process Output Information`
- **원인**: Transformers/tokenizers 라이브러리 문제, BERT 모델 파일 손상, 캐시 손상
- **해결**:
  ```bash
  # 방법 1: 의존성 재설치 (빠른 시도)
  bash scripts/server-a/manage-gpt-sovits.sh
  # 옵션 6 선택 (의존성 재설치)
  # 옵션 2 선택 (extra-req + requirements)
  
  # 방법 2: 완전 삭제 후 재설치 (가장 확실, 권장)
  bash scripts/server-a/manage-gpt-sovits.sh
  # 옵션 2 선택 (재설치)
  ```

#### 6.5.5 의존성 재설치

**⚠️ 매우 중요: Python, PyTorch, torchcodec 버전 호환성**

의존성 재설치 시에도 **Python, PyTorch, torchcodec 버전 호환성**을 반드시 확인해야 합니다. 버전 호환성 문제가 있다면 완전 재설치를 권장합니다.

**의존성 문제가 의심될 때**:

```bash
# 통합 관리 스크립트 사용 (권장)
bash scripts/server-a/manage-gpt-sovits.sh
# 옵션 6 선택 (의존성 재설치)
# 옵션 2 선택 (extra-req + requirements, 권장)
```

**⚠️ 주의**: 의존성 재설치 시 기존 PyTorch 버전이 유지됩니다. 버전 호환성 문제가 있다면 완전 재설치(옵션 2)를 권장합니다.

옵션:
1. requirements.txt만 재설치 (빠름)
2. extra-req.txt + requirements.txt 재설치 (권장)
3. pip 캐시 정리 후 재설치
4. 전체 재설치 (pip 업그레이드 포함)

**설치 후 버전 확인 (권장)**:
```bash
conda activate GPTSoVits
python -c "import sys; print(f'Python: {sys.version}')"
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import torchcodec; print('torchcodec: 설치됨')" || echo "torchcodec: 확인 필요"
```

**모니터링 및 정리 스크립트**:
```bash
# 시스템 모니터링 (디스크, 로그, 포트, 모델, NPM 연결)
bash scripts/server-a/monitor-system.sh

# 시스템 정리 (디스크, Docker)
bash scripts/server-a/cleanup-system.sh

# 서비스 설정 (NPM, 모델 스토리지)
bash scripts/server-a/setup-services.sh
```

### 6.6 모델 다운로드 관련

**문제**: 모델 다운로드 중 디스크 공간 부족
- **해결**: 
  ```bash
  # 디스크 공간 확인
  df -h /mnt/shared_models
  
  # 불필요한 파일 정리
  sudo apt-get clean
  sudo apt-get autoremove
  ```

**문제**: Git LFS 파일이 제대로 다운로드되지 않음
- **해결**:
  ```bash
  git lfs install
  git lfs pull
  ```

**문제**: Hugging Face 다운로드 속도가 느림
- **해결**: 
  - `HF_ENDPOINT` 환경 변수 설정 (미러 사용)
  - 또는 직접 다운로드 스크립트 작성

**문제**: `pip install` 시 `externally-managed-environment` 오류
- **해결**: 
  ```bash
  # 방법 1: 가상 환경 사용 (권장)
  # 1단계: 가상 환경 생성
  python3 -m venv ~/venv
  
  # 2단계: 가상 환경 활성화
  source ~/venv/bin/activate
  
  # 3단계: 패키지 설치
  pip install --upgrade huggingface_hub
  
  # python3-venv가 없다면:
  sudo apt-get install -y python3-venv python3-full
  ```
  
  ```bash
  # 방법 2: pipx 사용 (독립 실행형 설치)
  sudo apt-get install -y pipx
  pipx ensurepath
  pipx install huggingface_hub
  
  # 방법 3: 시스템 패키지로 설치 (가능한 경우)
  sudo apt-get install -y python3-huggingface-hub
  ```
  - ⚠️ `--break-system-packages` 플래그는 사용하지 마세요. 시스템을 손상시킬 수 있습니다.

**문제**: `source ~/venv/bin/activate` 실행 시 파일이 없다는 오류
- **원인**: 가상 환경이 아직 생성되지 않음
- **해결**:
  ```bash
  # 1. 먼저 가상 환경 생성
  python3 -m venv ~/venv
  
  # 2. 생성 확인
  ls -la ~/venv/bin/activate
  
  # 3. 그 다음 활성화
  source ~/venv/bin/activate
  ```

**문제**: `huggingface-cli: command not found` 오류
- **원인**: `huggingface_hub` 패키지는 설치되었지만 CLI 스크립트가 생성되지 않음
- **해결**: 
  ```bash
  # 방법 1: Hugging Face 공식 CLI 설치 (가장 간단, 권장)
  curl -LsSf https://hf.co/cli/install.sh | bash
  hf --version  # 확인
  
  # 방법 2: Python API 직접 사용
  # (위의 Python 스크립트 방법 사용)
  ```
  ```bash
  # 방법 1: Python 스크립트로 직접 사용 (가장 안정적, 권장)
  # huggingface_hub는 Python 라이브러리이므로 Python 코드로 직접 사용
  python3 << 'PYEOF'
  from huggingface_hub import snapshot_download
  
  
  print(f"다운로드 중: {repo_id}")
  snapshot_download(
      repo_id=repo_id,
      local_dir=local_dir,
      local_dir_use_symlinks=False,
      resume_download=True
  )
  print(f"✅ 다운로드 완료: {local_dir}")
  PYEOF
  
  # 방법 2: 재사용 가능한 스크립트 파일 생성
  cat > ~/download_hf_model.py << 'SCRIPTEOF'
  #!/usr/bin/env python3
  import sys
  from huggingface_hub import snapshot_download
  
  if len(sys.argv) < 3:
      print("사용법: python download_hf_model.py <repo_id> <local_dir>")
      sys.exit(1)
  
  repo_id = sys.argv[1]
  local_dir = sys.argv[2]
  
  print(f"다운로드 중: {repo_id}")
  snapshot_download(
      repo_id=repo_id,
      local_dir=local_dir,
      local_dir_use_symlinks=False,
      resume_download=True
  )
  print(f"✅ 다운로드 완료: {local_dir}")
  SCRIPTEOF
  
  chmod +x ~/download_hf_model.py
  
  # 사용 예시
  
  # 방법 3: 설치 확인
  python -c "import huggingface_hub; print('✅ 정상 작동')"
  ```

### 6.3 서비스 연결 관련

**문제**: Server B에서 Server A의 서비스에 접근 불가
- **해결**:
  1. Server A의 NPM이 정상 실행 중인지 확인
  2. Proxy Host 설정 확인
  3. 방화벽 설정 확인 (포트 80, 443 열려있는지)
  4. SSL 인증서 문제인 경우 `verify=False` 사용 (개발 환경)

**문제**: vLLM 서버가 모델을 찾을 수 없음
- **해결**:
  1. 모델 파일 경로 확인: `/mnt/shared_models/llm/gemma-3-27b-it/`
  2. Docker 볼륨 마운트 확인
  3. 모델 파일 권한 확인

### 6.4 VRAM 부족 관련

**문제**: 모델 로드 시 VRAM 부족 오류
- **해결**:
  1. 다른 서비스 중지 (VRAM 모드 스위칭)
  2. 양자화 설정 확인 (4-bit AWQ/GPTQ)
  3. 모델 양자화 설정 확인 (4-bit AWQ/GPTQ)

---

## 다음 단계

1. ✅ NVIDIA Container Toolkit 설치 완료
2. ✅ 모델 파일 준비 완료 (Server A에 직접 저장)
3. ✅ Server A NPM 설정 완료
4. ✅ LLM/TTS 서비스 구축 완료
5. ✅ Server B Main Backend 구축 완료
6. 다음: 프론트엔드 채팅 UI 구현
7. 다음: VRAM 관리 로직 구현 (모드 스위칭)

## 스크립트 사용법

문서에 나온 bash 스크립트들은 `scripts/` 디렉터리에 파일로 생성되어 있습니다.

### 실행 방법

```bash
# 1. 서버에 스크립트 복사 (Git 클론 또는 scp)
cd /path/to/madcamp-Screening-Humanity-AI-Server

# 2. 실행 권한 부여 (필수!)
chmod +x scripts/server-a/*.sh
chmod +x scripts/server-b/*.sh

# 3. 통합 스크립트 실행 (권장)
bash scripts/server-a/setup-services.sh
# 옵션 2 선택 (모델 스토리지 디렉터리 생성)
```

**또는 실행 권한 없이 bash로 직접 실행** (권장):
```bash
# 통합 스크립트 사용
bash scripts/server-a/setup-services.sh
# 옵션 2 선택 (모델 스토리지 디렉터리 생성)

# 모델 다운로드 (별도 스크립트)
bash scripts/server-a/download-dolphin-2.9-8b.sh
bash scripts/server-a/download-gemma-3-27b-it.sh

# 모델 검증
bash scripts/server-a/monitor-system.sh
# 옵션 5 선택 (모델 검증)
```

### 문제 해결

**"Permission denied" 오류**:
```bash
chmod +x scripts/server-a/*.sh
# 또는
bash scripts/server-a/setup-services.sh
# 옵션 2 선택 (모델 스토리지 디렉터리 생성)
```

**"No such file or directory" 오류**:
```bash
# 현재 위치 확인
pwd
# 절대 경로로 실행
bash /full/path/to/scripts/server-a/setup-model-storage.sh
```

**Windows에서 생성된 경우 줄바꿈 문제**:
```bash
dos2unix scripts/server-a/*.sh
# 또는
sed -i 's/\r$//' scripts/server-a/*.sh
```

자세한 내용은 `scripts/README.md`를 참고하세요.

---

## 참고 자료

- [NVIDIA Container Toolkit 공식 문서](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- [vLLM 공식 문서](https://github.com/vllm-project/vllm)
- [GPT-SoVITS-v4 Hugging Face](https://huggingface.co/kevinwang676/GPT-SoVITS-v4)
- [GPT-SoVITS-v4 한국어 README](https://huggingface.co/kevinwang676/GPT-SoVITS-v4/blob/main/docs/ko/README.md)
- [Hugging Face 모델 허브](https://huggingface.co/models)
- [Hugging Face CLI 공식 문서](https://huggingface.co/docs/huggingface_hub/guides/cli)
- [Nginx Proxy Manager 문서](https://nginxproxymanager.com/guide/)

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.6 | 2026-01-26 | 로그인/로그아웃 시스템 통합 완료 - Backend JWT HttpOnly Cookie 설정, Frontend NextAuth.js 제거, 인증 콜백 라우트 구현, API 클라이언트 쿠키 전달 설정, 로그아웃 엔드포인트 추가 |
| 1.5 | 2026-01-26 | Ollama 기준으로 API 구현 변경 - vLLM 코드 주석 처리, Ollama를 기본 LLM 서비스로 설정 (LLM_SERVICE 기본값: ollama), GPU_SERVER_URL 환경 변수 제거, chat.py Ollama 기준으로 재구현, 모든 문서 업데이트 |
| 1.4 | 2026-01-26 | API 경로 통일 완료 - Frontend를 `/api`로 변경 (`lib/api/client.ts`), Backend는 이미 `/api` 사용 중 확인 완료 |
| 1.3 | 2026-01-26 | Backend Mock 응답 제거 및 실제 API 호출 구현 완료 - chat.py 수정, vLLM/Ollama 분기 처리, 에러 처리 강화, session_id 지원 |
| 1.2 | 2026-01-26 | Server A 연동 상태 업데이트 - vLLM 서버 실행, GPT-SoVITS WebAPI 구동, NPM 설정 완료 반영 |
| 1.1 | 2026-01-26 | 문서 정합성 작업: API 경로 통일 (Frontend를 `/api`로 변경), 모델 이름 통일, GPT-SoVITS 포트 정보 일관화 |
| 1.0 | 2026-01-26 | 초기 문서 작성 |
