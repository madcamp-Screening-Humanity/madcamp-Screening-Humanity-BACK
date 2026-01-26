# 프로젝트 API 사용 현황 정리

**작성일**: 2026-01-26  
**버전**: 1.7

---

## 📋 목차

1. [API 개요](#1-api-개요)
2. [Server B Backend API (외부 노출)](#2-server-b-backend-api-외부-노출)
3. [Server A vLLM API (내부 호출)](#3-server-a-vllm-api-내부-호출)
4. [Server A GPT-SoVITS API (내부 호출)](#4-server-a-gpt-sovits-api-내부-호출)
5. [API 호출 흐름](#5-api-호출-흐름)
6. [미구현 API 기능](#6-미구현-api-기능)

---

## 1. API 개요

프로젝트는 3개의 주요 서버에서 API를 제공합니다:

- **Server B Backend (FastAPI)**: 외부에 노출되는 메인 API (포트 8000)
- **Server A LLM 서비스**: LLM 서비스 API
  - **케이스 B: Ollama** (포트 11434) - Ollama 자체 API (기본 사용)
  - **케이스 A: vLLM** (포트 8002) - OpenAI 호환 API (코드에 주석으로 보관)
- **Server A GPT-SoVITS**: TTS 서비스 API (포트 9880)

**⚠️ 중요**: vLLM과 Ollama는 동시에 실행할 수 없습니다 (VRAM 제약). 하나만 선택하여 사용하세요.

---

## 2. Server B Backend API (외부 노출)

**포트**: 8000  
**기본 URL**: `http://localhost:8000` 또는 `https://your-domain.com`  
**프레임워크**: FastAPI

### 2.1 채팅 API

#### `POST /api/chat` ✅ **구현됨**
- **용도**: LLM을 통한 캐릭터와 대화 (TTS 통합 포함)
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **쿠키 전달**: Frontend에서 `credentials: 'include'` 설정됨
- **요청 예시**:
  ```json
  {
    "messages": [
      { "role": "user", "content": "안녕하세요!" },
      { "role": "assistant", "content": "안녕! 만나서 반가워~" }
    ],
    "persona": "밝고 명랑한 10대 소녀 캐릭터. 반말을 사용하며 귀엽게 말함.",
    "character_id": "hermione",  // 선택, 캐릭터 ID (voice_id 자동 추출)
    "scenario": {  // 선택, 시나리오 정보
      "opponent": "헤르미온느 그레인저",
      "situation": "호그와트 도서관에서 만남",
      "background": "마법 세계 배경"
    },
    "session_id": "uuid-string",  // 선택, 자동 생성 (없으면 UUID 생성)
    "temperature": 0.7,
    "max_tokens": 512,
    "model": "gemma-3-27b-it",
    // TTS 관련 필드
    "tts_enabled": true,  // TTS 활성화 여부 (기본값: true)
    "tts_mode": "realtime",  // "realtime" | "delayed" | "on_click"
    "tts_delay_ms": 0,  // 지연 시간 (밀리초, delayed 모드에서 사용)
    "tts_streaming_mode": 0  // GPT-SoVITS streaming_mode (0-3)
  }
  ```
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "content": "안녕! 만나서 반가워~",
      "usage": { "prompt_tokens": 45, "completion_tokens": 12 },
      "session_id": "uuid-string",
      "audio_url": "/mnt/user_assets/{user_id}/audio/{file_id}.wav",  // TTS 생성된 오디오 URL (tts_enabled=true일 때)
      "context_summarized": false  // 이번 요청에서 요약이 발생했는지 (Phase 5.2에서 구현 예정)
    }
  }
  ```
- **내부 처리 과정**:
  1. **세션 ID 생성**: 요청에 session_id가 없으면 UUID 자동 생성
  2. **페르소나 포맷팅**: `format_persona_for_roleplay()` 함수로 역할극에 적합한 형식으로 변환
     - 프론트엔드에서 전달된 `persona` 사용
     - 시나리오 정보 포함 (opponent, situation, background)
     - 역할극 지시사항 자동 추가
  3. **System 메시지 구성**: 포맷팅된 페르소나를 system 메시지로 추가
  4. **Ollama API 호출**: 
     - 엔드포인트: `POST {OLLAMA_BASE_URL}/api/chat`
     - 요청 형식: `{"model": str, "messages": List[Dict], "stream": false, "options": {"temperature": float, "num_predict": int}}`
     - 응답 형식: `{"message": Dict, "prompt_eval_count": int, "eval_count": int}`
  5. **TTS 통합** (임시 비활성화):
     - 인증 제거로 인해 TTS 통합 로직 임시 비활성화
     - 필요 시 별도 `/api/tts` 엔드포인트 사용
- **⚠️ 미구현 기능**:
  - 컨텍스트 절약 요약 기능 (Phase 5.2)
  - 동시 접속 제한 (Phase 5.3)

#### `GET /api/chat/models` ✅ **구현됨**
- **용도**: 사용 가능한 LLM 모델 목록 조회
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "models": [
        {"id": "gemma-3-27b-it", "name": "Gemma 3 27B IT (Default)"},
        {"id": "dolphin-2.9-8b", "name": "Dolphin 2.9 8B (Uncensored)"}
      ]
    }
  }
  ```

### 2.2 TTS API

#### `POST /api/tts` ✅ **구현됨**
- **용도**: 텍스트를 음성으로 변환
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **요청 예시**:
  ```json
  {
    "text": "안녕하세요, 반갑습니다!",
    "voice_id": "default",
    "text_lang": "ko",
    "prompt_lang": "ko",
    "streaming_mode": 0,
    "return_binary": false,
    "media_type": "wav"
  }
  ```
- **응답 예시** (return_binary=false):
  ```json
  {
    "success": true,
    "data": {
      "audio_url": "/mnt/user_assets/{user_id}/audio/{file_id}.wav",
      "file_id": "abc123",
      "duration": 2.5,
      "file_size": 44100,
      "format": "wav",
      "voice_id": "default",
      "created_at": "2026-01-26T10:00:00Z",
      "cached": false
    }
  }
  ```
- **응답** (return_binary=true): 오디오 바이너리 직접 반환
- **내부 호출**: `POST {TTS_BASE_URL}/{TTS_API_PATH}` (GPT-SoVITS)
- **주요 기능**:
  - 캐싱 시스템 (데이터베이스 기반, text_hash + voice_id + format 기준)
  - 오디오 메타데이터 분석 (mutagen 사용)
  - 사용자별 파일 저장 (`/mnt/user_assets/{user_id}/audio/`)
  - streaming_mode 지원 (0-3)
  - voice_id 매핑 시스템 (`app/config/voices.json`)
- **상태**: ✅ 구현 완료 (2026-01-26)

#### `GET /api/tts/voices` ✅ **구현됨**
- **용도**: 사용 가능한 음성 목록 조회
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "voices": [
        {
          "id": "default",
          "name": "기본 음성",
          "language": "ko",
          "description": "기본 한국어 음성"
        }
      ],
      "default_voice_id": "default"
    }
  }
  ```
- **설정 파일**: `app/config/voices.json`
- **상태**: ✅ 구현 완료 (2026-01-26)

### 2.3 3D 생성 API

#### `POST /api/generate` ✅ **구현됨**
- **용도**: 3D 생성 작업 시작 (이미지 업로드)
- **인증**: 불필요 (인증 제거됨, user_id="anonymous"로 설정, 2026-01-26)
- **요청**: `multipart/form-data`
  - `image`: 이미지 파일 (PNG/JPG)
  - `options`: JSON 문자열 (선택)
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status_url": "/api/generate/status/550e8400-e29b-41d4-a716-446655440000",
      "estimated_time": 300
    }
  }
  ```

#### `GET /api/generate/status/{job_id}` ✅ **구현됨**
- **용도**: 생성 작업 상태 조회
- **인증**: 선택적
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "job_id": "...",
      "status": "processing",
      "progress": 45,
      "current_step": "3D 메쉬 생성 중...",
      "result_url": null,
      "error": null
    }
  }
  ```

### 2.4 인증 API

#### `GET /api/auth/google/login` ✅ **구현됨**
- **용도**: Google 로그인 페이지로 리다이렉트
- **인증**: 불필요

#### `GET /api/auth/google/callback` ✅ **구현됨**
- **용도**: Google OAuth 콜백 처리 및 JWT 발급
- **인증**: 불필요
- **응답**: 
  - JWT 토큰을 HttpOnly Cookie로 설정
  - 프론트엔드로 리다이렉트 (`http://localhost:3000/auth/callback`)
  - 쿠키 설정: `access_token` (HttpOnly, SameSite=Lax)

#### `GET /api/auth/me` ✅ **구현됨**
- **용도**: 현재 로그인한 사용자 정보 조회
- **인증**: 필요 (HttpOnly Cookie 또는 Bearer Token)
- **응답 예시**:
  ```json
  {
    "id": "user-uuid",
    "email": "user@example.com",
    "username": "사용자 이름",
    "picture": "https://...",
    "provider": "google"
  }
  ```

### 2.5 캐릭터 API ✅ **구현됨**

#### `GET /api/characters/presets` ✅ **구현됨**
- **용도**: 사전설정 캐릭터 목록 조회
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "characters": [
        {
          "id": "hermione",
          "name": "헤르미온느 그레인저",
          "persona": "똑똑하고 책을 좋아하는 마법사...",
          "voice_id": "default",
          "description": "해리포터 시리즈의 똑똑한 마법사...",
          "category": "소설",
          "tags": ["해리포터", "마법사", "똑똑함"],
          "sample_dialogue": "안녕하세요! 오늘도 새로운 마법을 배울 수 있어서...",
          "image_url": "/images/characters/hermione.jpg",
          "is_preset": true
        }
      ]
    }
  }
  ```
- **캐싱**: 파일 변경 감지 기반 (mtime 추적)
- **설정 파일**: `app/config/characters.json`

#### `GET /api/characters` ✅ **구현됨**
- **용도**: 사용자가 생성한 캐릭터 목록 조회
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **응답**: 위와 동일한 형식 (is_preset=false)

#### `POST /api/characters` ✅ **구현됨**
- **용도**: 새 캐릭터 생성
- **인증**: 불필요 (인증 제거됨, user_id="anonymous"로 설정, 2026-01-26)
- **요청 예시**:
  ```json
  {
    "name": "나만의 캐릭터",
    "persona": "밝고 명랑한 성격...",
    "voice_id": "default",
    "description": "캐릭터 설명",
    "category": "커스텀",
    "tags": ["태그1", "태그2"],
    "image_url": "/images/characters/custom.jpg"
  }
  ```
- **응답**: 생성된 캐릭터 정보

#### `GET /api/characters/{character_id}` ✅ **구현됨**
- **용도**: 캐릭터 상세 조회
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **권한**: 모든 캐릭터 조회 가능

#### `PUT /api/characters/{character_id}` ✅ **구현됨**
- **용도**: 캐릭터 수정
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **권한**: 사전설정 캐릭터는 수정 불가 (403 에러)

#### `DELETE /api/characters/{character_id}` ✅ **구현됨**
- **용도**: 캐릭터 삭제
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **권한**: 사전설정 캐릭터는 삭제 불가 (403 에러)

**상태**: ✅ 구현 완료 (2026-01-26)  
**상세 구현 내역**: `docs/구현_상태_요약_2026-01-26.md` 참조

---

#### `POST /api/auth/logout` ✅ **구현됨**
- **용도**: 로그아웃 처리 및 쿠키 삭제
- **인증**: 불필요
- **응답**: 쿠키 삭제 후 프론트엔드로 리다이렉트 (`http://localhost:3000/`)

### 2.5 시스템 API

#### `GET /api/health` ✅ **구현됨**
- **용도**: 전체 시스템 및 각 서비스의 상태 확인
- **인증**: 불필요
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "backend": "healthy",
      "llm": "healthy",
      "tts": "healthy",
      "gen3d": "unhealthy",
      "style": "unhealthy",
      "timestamp": "2026-01-23T15:00:00Z"
    }
  }
  ```

#### `GET /` ✅ **구현됨**
- **용도**: 루트 엔드포인트
- **응답**: "Avatar Forge Backend Running"

#### `GET /docs` ✅ **구현됨**
- **용도**: Swagger UI 문서 (대화형 API 문서)
- **접근**: `http://localhost:8000/docs` 또는 `https://your-domain.com/docs`
- **기능**: API 엔드포인트 테스트, 요청/응답 스키마 확인, 인증 테스트

#### `GET /redoc` ✅ **구현됨**
- **용도**: ReDoc 문서 (대체 API 문서 형식)
- **접근**: `http://localhost:8000/redoc` 또는 `https://your-domain.com/redoc`
- **기능**: API 엔드포인트 문서화, 요청/응답 예시 확인

#### `GET /api/openapi.json` ✅ **구현됨**
- **용도**: OpenAPI 스키마 (JSON 형식)
- **접근**: `http://localhost:8000/api/openapi.json` 또는 `https://your-domain.com/api/openapi.json`
- **기능**: OpenAPI 3.0 스키마 다운로드, API 클라이언트 코드 생성에 사용

---

## 3. Server A LLM API (내부 호출)

**⚠️ 중요**: vLLM과 Ollama 중 하나만 선택하여 사용합니다.  
**현재 기본값**: Ollama (vLLM 코드는 주석 처리되어 있음)

---

### 케이스 B: Ollama API (기본 사용)

**포트**: 11434  
**기본 URL**: `http://server-a:11434` 또는 `http://localhost:11434`  
**API 표준**: Ollama 자체 API

#### `POST /api/chat` ✅ **사용 중 (채팅용)**
- **용도**: 채팅 완료 생성 (메시지 히스토리 지원)
- **호출자**: Server B Backend (`/api/chat`)
- **요청 예시**:
  ```json
  {
    "model": "gemma-3-27b-it",
    "messages": [
      {"role": "system", "content": "당신은 친절한 AI 어시스턴트입니다."},
      {"role": "user", "content": "안녕하세요"}
    ],
    "stream": false,
    "options": {
      "temperature": 0.7,
      "num_predict": 512
    }
  }
  ```
- **응답 예시**:
  ```json
  {
    "model": "gemma-3-27b-it",
    "created_at": "2026-01-26T12:00:00Z",
    "message": {
      "role": "assistant",
      "content": "안녕하세요! 무엇을 도와드릴까요?"
    },
    "done": true,
    "total_duration": 1234567890,
    "load_duration": 1234567,
    "prompt_eval_count": 10,
    "prompt_eval_duration": 1234567,
    "eval_count": 20,
    "eval_duration": 1234567890
  }
  ```

#### `GET /api/tags` ✅ **사용 가능**
- **용도**: 사용 가능한 모델 목록 조회
- **호출자**: Server B Backend (`/api/chat/models`)

#### `GET /api/version` ✅ **사용 가능**
- **용도**: Ollama 버전 정보 조회

**⚠️ 참고**: 
- Ollama는 OpenAI 호환 API를 제공하지 않습니다.
- Server B Backend에서 Ollama를 기본으로 사용합니다 (코드에 구현됨).
- 모델 이름은 Ollama에 등록된 이름을 사용합니다 (예: `gemma-3-27b-it`).

**참고 문서**:
- **Ollama 공식 문서**: https://docs.ollama.com/api/introduction
- **프로젝트 내 문서**: `docs/FINALFINAL.md`의 "옵션 B: Ollama 서버 실행" 섹션

---

### 케이스 A: vLLM API (OpenAI 호환, 주석 처리됨)

**⚠️ 참고**: vLLM 코드는 `chat.py`에 주석으로 보관되어 있습니다. 필요 시 주석을 해제하고 `LLM_SERVICE=vllm`으로 설정하여 사용할 수 있습니다.

**포트**: 8002 (외부) → 8000 (내부 컨테이너)  
**기본 URL**: `http://server-a:8002` 또는 `http://localhost:8002`  
**API 표준**: OpenAI 호환 API

**포트**: 8002 (Docker 포트 매핑)  
**내부 URL**: `http://localhost:8002` 또는 `http://172.17.0.4:8002`  
**외부 URL (리버스 프록시)**: `http://gpugpt.duckdns.org/` (설정된 경우)  
**프레임워크**: vLLM OpenAI 호환 API

### 3.0 리버스 프록시 설정 시 API 호출 방법

리버스 프록시가 `http://172.17.0.4:8002`를 `http://gpugpt.duckdns.org/`로 설정된 경우:

**프록시 설정 (해결 방법)**:
- **백엔드 주소**: `172.17.0.1:8000` (Docker bridge 네트워크 게이트웨이 IP 사용)
- **포트**: `8000` (컨테이너 내부 포트)
- **참고**: `172.17.0.1`은 Docker bridge 네트워크의 게이트웨이 IP로, 프록시 서버에서 vLLM 컨테이너에 접근할 수 있습니다.

**루트 경로(`/`)로 프록시한 경우**:
- 기존: `http://172.17.0.4:8002/v1/chat/completions`
- 변경: `http://gpugpt.duckdns.org/v1/chat/completions`
- 헬스체크: `http://gpugpt.duckdns.org/health` (⚠️ 일부 프록시 설정에서 502 에러 발생 가능)
- 모델 목록: `http://gpugpt.duckdns.org/v1/models` ✅ (작동 확인됨)

**특정 경로(예: `/vllm`)로 프록시한 경우**:
- 기존: `http://172.17.0.4:8002/v1/chat/completions`
- 변경: `http://gpugpt.duckdns.org/vllm/v1/chat/completions`
- 헬스체크: `http://gpugpt.duckdns.org/vllm/health`
- 모델 목록: `http://gpugpt.duckdns.org/vllm/v1/models`

**⚠️ 중요**: Server B Backend에서 vLLM을 호출할 때는 환경 변수나 설정 파일에서 URL을 변경해야 합니다:
- 환경 변수: `VLLM_BASE_URL=http://gpugpt.duckdns.org` (또는 `/vllm` 경로 포함 시 `http://gpugpt.duckdns.org/vllm`)
- 내부 네트워크에서 직접 호출하는 경우: `http://172.17.0.4:8002` (변경 불필요)

### 3.1 사용 중인 API

#### `POST /v1/chat/completions` ✅ **사용 중**
- **용도**: 채팅 완료 생성
- **호출자**: Server B Backend (`/api/chat`)
- **요청 예시**:
  ```json
  {
    "model": "unsloth/gemma-3-27b-it-bnb-4bit",
    "messages": [
      {"role": "system", "content": "당신은 친절한 AI 어시스턴트입니다."},
      {"role": "user", "content": "안녕하세요"}
    ],
    "max_tokens": 512,
    "temperature": 0.7
  }
  ```
- **응답**: OpenAI 호환 형식

### 3.2 선택적 API

#### `GET /health` ✅ **사용 가능**
- **용도**: 헬스체크
- **호출자**: Server B Backend (`/api/health`)
- **응답**: `OK` (텍스트) 또는 `{"status": "ok"}` (JSON)
- **⚠️ 주의**: 일부 프록시 설정에서 `/health` 경로가 502 에러를 반환할 수 있습니다. 이 경우 `/v1/models`를 헬스체크 대용으로 사용할 수 있습니다.

#### `GET /v1/models` ✅ **사용 가능**
- **용도**: 모델 목록 조회
- **호출자**: Server B Backend (`/api/chat/models`)
- **응답 예시**:
  ```json
  {
    "object": "list",
    "data": [
      {
        "id": "unsloth/gemma-3-27b-it-bnb-4bit",
        "object": "model",
        "created": 1769364590,
        "owned_by": "vllm"
      }
    ]
  }
  ```

### 3.3 API 문서 엔드포인트

vLLM은 OpenAI 호환 API를 제공하지만, Swagger/ReDoc 같은 대화형 API 문서는 제공하지 않습니다.

**참고 문서**:
- **OpenAI API 공식 문서**: https://platform.openai.com/docs/api-reference
- **vLLM 공식 문서**: https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html
- **프로젝트 내 문서**: `docs/VLLM_TEST_GUIDE.md`, `docs/PROJECT_API_SUMMARY.md`

**⚠️ 참고**: vLLM은 FastAPI 기반이 아니므로 `/docs`, `/redoc`, `/openapi.json` 같은 엔드포인트를 제공하지 않습니다. 대신 OpenAI API 표준을 따릅니다.

### 3.4 미사용 API (향후 활용 가능)

- `POST /v1/completions` - 텍스트 생성 (채팅 템플릿 없음)
- `POST /v1/responses` - 텍스트 생성 (OpenAI Responses API 호환)
- `POST /v1/embeddings` - 임베딩
- `POST /v1/audio/transcriptions` - 음성 인식

---

(케이스 B는 위로 이동됨)

---

## 4. Server A GPT-SoVITS API (내부 호출)

**포트**: 9880  
**내부 URL**: `http://localhost:9880` 또는 `http://172.17.0.1:9880`  
**프레임워크**: GPT-SoVITS WebAPI (api_v2.py)

### 4.1 사용 중인 API

#### `POST /tts` ✅ **사용 중**
- **용도**: 텍스트-음성 변환
- **호출자**: Server B Backend (`/api/tts`)
- **요청 예시**:
  ```json
  {
    "text": "안녕하세요, 반갑습니다.",
    "text_lang": "ko",
    "ref_audio_path": "path/to/ref.wav",
    "prompt_lang": "ko",
    "speed_factor": 1.0,
    "media_type": "wav"
  }
  ```
- **응답**: 오디오 바이너리 스트림 (wav, ogg, aac 등)

#### `GET /tts` ✅ **사용 가능**
- **용도**: 텍스트-음성 변환 (GET 방식, 간편 테스트용)
- **호출자**: 직접 호출 또는 테스트용

### 4.2 관리용 API (선택적)

#### `GET /set_gpt_weights` ⚠️ **미사용**
- **용도**: GPT 모델 변경
- **상태**: 관리용, 현재 미사용

#### `GET /set_sovits_weights` ⚠️ **미사용**
- **용도**: SoVITS 모델 변경
- **상태**: 관리용, 현재 미사용

#### `GET /control?command=restart` ⚠️ **미사용**
- **용도**: 서버 재시작
- **상태**: 관리용, 현재 미사용

---

## 5. API 호출 흐름

### 5.1 채팅 요청 흐름

```
Frontend (Next.js)
    ↓ POST /api/chat
Server B Backend (FastAPI, 포트 8000)
    ↓ POST /v1/chat/completions
Server A vLLM (포트 8002)
    ↓ 응답 반환
Server B Backend
    ↓ 응답 반환
Frontend
```

### 5.2 TTS 요청 흐름

**직접 TTS 요청**:
```
Frontend (Next.js)
    ↓ POST /api/tts
Server B Backend (FastAPI, 포트 8000)
    ↓ POST /tts
Server A GPT-SoVITS (포트 9880)
    ↓ 오디오 바이너리 반환
Server B Backend
    ↓ 파일 저장 후 URL 반환
Frontend
```

**Chat API를 통한 자동 TTS 요청** (ChatRoom에서 사용):
```
Frontend (Next.js)
    ↓ POST /api/chat (tts_enabled=true)
Server B Backend (FastAPI, 포트 8000)
    ├─→ POST {OLLAMA_BASE_URL}/api/chat (LLM 응답 생성)
    │   ↓ 응답 반환
    └─→ _synthesize_tts_internal() (TTS 자동 호출)
        ↓ POST {TTS_BASE_URL}/tts
        Server A GPT-SoVITS (포트 9880)
        ↓ 오디오 바이너리 반환
        Server B Backend
        ↓ 파일 저장 후 audio_url 포함
Frontend (audio_url 포함된 응답 수신)
```

### 5.3 헬스체크 흐름

```
Frontend 또는 모니터링 도구
    ↓ GET /api/health
Server B Backend
    ├─→ GET /health (vLLM)
    └─→ GET /health (GPT-SoVITS, 선택적)
    ↓ 집계된 상태 반환
Frontend
```

---

## 6. 미구현 API 기능

### 6.1 Phase 5.2: 컨텍스트 절약 요약 기능 ⚠️ **미구현**

**영향받는 API**: `POST /api/chat`

**구현 필요 사항**:
- `app/services/context_manager.py` 신규 생성
- 세션별 대화 히스토리 저장/조회 (Redis 또는 메모리 캐시)
- 토큰 수 계산 및 모니터링
- 자동 요약 트리거 (컨텍스트 80% 사용 시)
- 슬라이딩 윈도우 전략 (최근 15-18턴 유지, 이전 턴 요약)
- 요약 캐싱 (성능 최적화)

**구현 시기**: Phase 5.1 완료 후 즉시 (우선순위: 높음, 필수)

**참고 문서**:
- `docs/FINALFINAL.md` - 컨텍스트 절약 요약 기능 구현 상세
- `docs/PHASE5_SETUP.md` - Phase 5.2 구현 가이드
- `docs/Backend_프로젝트_현황_명세서.md` - ContextManager 서비스 설명

### 6.2 Phase 5.3: 동시 접속 제한 ⚠️ **미구현**

**영향받는 API**: `POST /api/chat`

**구현 필요 사항**:
- `app/core/rate_limiter.py` 신규 생성
- 활성 세션 수 추적 (Redis 기반)
- 최대 동시 접속자 수 제한 (기본: 20명, 환경 변수로 설정 가능)
- 세션 등록/해제
- 503 에러 반환 (제한 초과 시)

**구현 시기**: Phase 5.1 완료 후 즉시 (우선순위: 높음, 필수)

**참고 문서**:
- `docs/FINALFINAL.md` - 동시 접속 제한 구현 상세
- `docs/PHASE5_SETUP.md` - Phase 5.3 구현 가이드
- `docs/Backend_프로젝트_현황_명세서.md` - ConcurrentUserLimiter 설명

### 6.3 Phase 5.4: Frontend 턴 제한 설정화 ✅ **구현 완료**

**영향받는 API**: `POST /api/chat` (Frontend 연동)

**구현 완료 사항**:
- [x] `components/chat-room.tsx`에서 턴 제한 설정화 완료 (환경 변수 지원) ✅
- [x] 세션 관리 로직 추가 완료 (세션 ID 생성/유지, `crypto.randomUUID()`) ✅
- [x] API 호출 시 `session_id` 포함 완료 ✅
- [x] 턴 제한 설정화 완료 (환경 변수 `NEXT_PUBLIC_MAX_TURNS` 지원, 기본값: 30) ✅

**상태**: ✅ 구현 완료 (2026-01-26)

**참고 문서**:
- `docs/구현_상태_요약_2026-01-26.md` - ChatRoom API 연동 및 TTS 통합 구현 상세
- `docs/PHASE5_SETUP.md` - Phase 5.4 구현 가이드

### 6.4 TTS 음성 목록 조회 ✅ **구현 완료**

**API**: `GET /api/tts/voices`

**구현 완료 사항**:
- [x] Backend에서 관리하는 음성 프리셋 목록 반환 (`app/config/voices.json`) ✅
- [x] Frontend UI 추가 (캐릭터 생성 위저드에 통합) ✅

**상태**: ✅ 구현 완료 (2026-01-26)

**참고 문서**:
- `docs/구현_상태_요약_2026-01-26.md` - TTS API 구현 상세

---

## 7. API 사용 현황 요약

### ✅ 구현 완료된 API

**Server B Backend**:
- `POST /api/chat` (기본 기능)
- `GET /api/chat/models`
- `POST /api/tts` (기본 기능)
- `POST /api/generate`
- `GET /api/generate/status/{job_id}`
- `GET /api/auth/google/login`
- `GET /api/auth/google/callback`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/health`
- `GET /`, `GET /docs`, `GET /redoc`

**Server A vLLM**:
- `POST /v1/chat/completions`
- `GET /health`
- `GET /v1/models`

**Server A GPT-SoVITS**:
- `POST /tts`
- `GET /tts`

### ⚠️ 미구현 기능 (API는 구현됨, 기능 추가 필요)

- `POST /api/chat` - 컨텍스트 절약 요약 기능 (Phase 5.2)
- `POST /api/chat` - 동시 접속 제한 (Phase 5.3)
- `GET /api/tts/voices` - 음성 목록 조회

### 📝 Frontend 연동 미구현

- `components/chat-room.tsx` - 턴 제한 제거 (Phase 5.4)
- 세션 관리 로직 추가

---

## 8. 참고 문서

- **전체 프로젝트 명세**: `docs/FINALFINAL.md`
- **Backend 명세**: `docs/Backend_프로젝트_현황_명세서.md`
- **Frontend 명세**: `docs/Front_PROJECT_SPECIFICATION.md`
- **Phase 5 설정 가이드**: `docs/PHASE5_SETUP.md`
- **GPT-SoVITS API 문서**: `docs/GPT-SoVITS WebAPI(api_v2.py).md`
- **vLLM 테스트 가이드**: `docs/VLLM_TEST_GUIDE.md`

---

**문서 버전**: 1.9  
**최종 업데이트**: 2026-01-26

**변경 이력**:
- v1.9 (2026-01-26): 인증 제거 및 프롬프트 전달 수정 반영
  - `/api/chat`, `/api/chat/models` 인증 제거
  - `/api/tts`, `/api/tts/voices` 인증 제거
  - `/api/generate` 인증 제거 (user_id="anonymous")
  - `/api/characters/*` 모든 엔드포인트 인증 제거
  - 프론트엔드에서 persona, scenario, session_id, character_id 전달 확인
  - 백엔드에서 request.persona를 system 메시지로 포맷팅 확인
  - 내부 처리 과정 업데이트 (Character 조회 로직 제거, TTS 통합 임시 비활성화)
- v1.8 (2026-01-26): 캐릭터 API 섹션 추가 및 TTS API 상세화
- v1.6 (2026-01-26): Ollama 기준으로 API 구현 변경 - vLLM 코드 주석 처리, Ollama를 기본 LLM 서비스로 설정 (LLM_SERVICE 기본값: ollama), GPU_SERVER_URL 환경 변수 제거, chat.py Ollama 기준으로 재구현, 케이스 순서 변경 (Ollama 우선)
- v1.5 (2026-01-26): API 경로 통일 완료 - Frontend를 `/api`로 변경 (`lib/api/client.ts`), Backend는 이미 `/api` 사용 중 확인 완료
- v1.4 (2026-01-26): Backend Mock 응답 제거 및 실제 API 호출 구현 완료 - chat.py 수정, vLLM/Ollama 분기 처리, 에러 처리 강화, session_id 지원
- v1.3 (2026-01-26): Server A 연동 상태 업데이트 - vLLM 서버 실행, GPT-SoVITS WebAPI 구동, NPM 설정 완료 반영
- v1.2 (2026-01-26): 문서 정합성 작업 - API 경로 통일 (모든 문서에서 `/api`로 통일), 모델 이름 통일 확인
- v1.1 (2026-01-26): 리버스 프록시 설정 해결 방법 추가 (172.17.0.1:8000), API 문서 엔드포인트 정보 추가
- v1.0 (2026-01-26): 초기 문서 작성
