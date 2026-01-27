# 프로젝트 API 사용 현황 정리

**작성일**: 2026-01-26  
**버전**: 1.8

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
  "director_note": "갑자기 화를 내라",  // 선택, 감독 모드 연출 지시 (2026-01-27)
  "current_speaker": "헤르미온느",  // 선택, 감독 모드에서 현재 말할 캐릭터
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
- **⚠️ Frontend client `chat()` body**: `director_note`, `current_speaker`, `tts_enabled`, `tts_mode`, `tts_delay_ms`, `tts_streaming_mode`를 **전달하지 않음** (`lib/api/client.ts`의 `chat()`에서 `JSON.stringify` body에 미포함). Backend `ChatRequest`는 수신·처리 지원. ChatRequest 타입 및 `chat-room` 인자와 불일치.

#### `GET /api/chat/models` ⚠️ **미구현 (Backend 라우트 없음)**
- **용도**: 사용 가능한 LLM 모델 목록 조회
- **상태**: Backend `chat.py`에 해당 라우트 없음. Frontend `chatApi.listModels()`는 호출하나 404 발생.
- **인증**: (미구현이므로 해당 없음)
- **(참고) 구현 시 예상 응답 형식**: `{ "success": true, "data": { "models": [ {"id": "gemma-3-27b-it", "name": "Gemma 3 27B IT (Default)"} ] } }`

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
- **구현 방식**: 
  - **Frontend API Route**: `app/api/characters/route.ts` (신규 생성, 2026-01-26)
  - `public/characters/*.json` 파일을 동적으로 로드
  - 자동 마이그레이션: 파일 로드 시 `persona` 필드가 남아있으면 자동으로 삭제하고 정규화된 스펙으로 덮어쓰기
  - **Backend API**: `GET /api/characters/presets` (백엔드 폴백)
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "characters": [
        {
          "id": "hermione",
          "name": "헤르미온느 그레인저",
          "description": "해리포터 시리즈의 똑똑한 마법사...",
          "gender": "여성",
          "species": "인간",
          "age": "17세",
          "height": "165cm",
          "job": "마법사",
          "personality": "똑똑함, 책임감, 완벽주의, 용기, 충성심, 호기심, 인내심, 배려심, 지식욕, 정의감",
          "appearance": "갈색 곱슬 머리, 갈색 눈, 작은 키, 책을 많이 읽어서 안경을 씀",
          "likes": ["책", "학습", "마법", "규칙", "정의", "친구들"],
          "dislikes": ["불공평함", "무지", "규칙 위반", "게으름"],
          "speech_style": "정중하고 학술적인 말투, 때로는 교사처럼 설명하는 스타일",
          "thoughts": "'규칙을 지켜야 해.', '공부가 가장 중요해.', '친구들을 보호해야 해.'",
          "features": "항상 책을 들고 다니며, 마법에 대한 지식이 풍부함",
          "habits": "'실제로', '정확히 말하면' 같은 표현을 자주 사용",
          "guidelines": "- 항상 정확하고 논리적인 답변을 제공하세요.\n- 마법에 대한 지식을 자랑하듯 설명하세요.\n- 친구들을 보호하려는 마음이 강합니다.",
          "voice_id": "default",
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
- **설정 파일**: 
  - Frontend: `public/characters/*.json` (9종 캐릭터 마이그레이션 완료)
  - Backend: `app/config/characters.json` (백엔드 폴백)
- **⚠️ 중요 변경사항 (2026-01-26)**:
  - `persona` 필드 사용 중단: 런타임 페르소나 빌드 시스템으로 대체
  - 상세 필드 구조 도입: `personality`, `appearance`, `likes`, `dislikes`, `speech_style`, `thoughts`, `features`, `habits`, `guidelines` 등
  - 데이터 중복 제거: 저장 시 무거운 persona 문자열 대신 상세 필드만 저장

#### `GET /api/characters` ✅ **구현됨**
- **용도**: 사용자가 생성한 캐릭터 목록 조회
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **응답**: 위와 동일한 형식 (is_preset=false)

#### `POST /api/characters` ✅ **구현됨**
- **용도**: 새 캐릭터 생성
- **인증**: 불필요 (인증 제거됨, user_id="anonymous"로 설정, 2026-01-26)
- **요청 예시** (상세 필드 구조):
  ```json
  {
    "name": "나만의 캐릭터",
    "description": "캐릭터 설명",
    "gender": "여성",
    "species": "인간",
    "age": "20세",
    "height": "160cm",
    "job": "학생",
    "personality": "밝고 명랑한 성격, 활발함, 친근함, 긍정적, 에너지 넘침",
    "appearance": "검은 머리, 큰 눈, 밝은 표정",
    "likes": ["음악", "춤", "친구들과의 시간"],
    "dislikes": ["외로움", "부정적인 생각"],
    "speech_style": "반말을 사용하며 친근하고 밝은 말투",
    "thoughts": "'오늘도 즐거운 하루가 될 거야!', '모두 행복했으면 좋겠어.'",
    "features": "항상 웃는 얼굴, 에너지가 넘침",
    "habits": "'와!', '대박!' 같은 감탄사를 자주 사용",
    "guidelines": "- 항상 밝고 긍정적인 답변을 제공하세요.\n- 친근하고 편안한 말투를 사용하세요.",
    "voice_id": "default",
    "category": "커스텀",
    "tags": ["태그1", "태그2"],
    "image_url": "/images/characters/custom.jpg"
  }
  ```
- **⚠️ 참고**: `persona` 필드는 선택사항이며, 제공되면 하위 호환성을 위해 사용됨. 하지만 상세 필드 구조를 사용하는 것을 권장함.
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

### 2.6 AI 생성 API ✅ **구현됨**

#### `POST /api/ai/generate/story` ✅ **구현됨**
- **용도**: 상황 분석 및 드라마틱한 줄거리 생성
- **인증**: 불필요 (인증 제거됨, 2026-01-26)
- **요청 예시**:
  ```json
  {
    "situation": "새벽 3시, 프로젝트 마감이 내일인데 팀원이 3시간째 잠만 자고 있다.",
    "opponent_name": "코딩 안 하고 자는 팀원",
    "character_persona": "밝고 명랑한 성격..."
  }
  ```
- **응답 예시**:
  ```json
  {
    "plot": "드라마틱하고 구체적인 줄거리 텍스트..."
  }
  ```
- **내부 처리**: LLM을 통한 상황 분석 및 줄거리 생성

#### `POST /api/ai/generate/character-details` ✅ **구현됨** (2026-01-26)

- **용도**: 캐릭터 상세 설정 자동 생성 (JSON)
- **인증**: 필요 (인증 유지)
- **요청 예시**:
  ```json
  {
    "name": "나루토",
    "category": "애니메이션",
    "source_work": "나루토",
    "description": "호카게를 꿈꾸는 열정적인 닌자",
    "worldview": "나루토 세계관"
  }
  ```
- **응답 예시**:
  ```json
  {
    "success": true,
    "data": {
      "name": "나루토",
      "gender": "남성",
      "species": "인간 (인주력)",
      "age": "16세",
      "height": "166cm",
      "job": "나뭇잎 마을 닌자",
      "worldview": "나루토 세계관 (닌자 세계)",
      "personality": "열정적, 포기를 모름, 긍정적...",
      "appearance": "금발의 삐죽머리, 파란 눈...",
      "description": "호카게를 꿈꾸는 열정적인 닌자...",
      "likes": ["일라쿠 라면", "친구들", "수행"],
      "dislikes": ["야채", "기다리는 것"],
      "speech_style": "끝에 '~니깐(닷테바요)'를 붙이는 독특한 말투...",
      "thoughts": "'나는 호카게가 될 남자다!'...",
      "features": "그림자 분신술이 특기...",
      "habits": "'닷테바요!', '호카게가 될 거야!'",
      "guidelines": "- 에너지가 넘치고 시끄러운 분위기를 조성하세요..."
    }
  }
  ```
- **주요 기능**:
  - **Google Generative AI SDK (`google-generativeai`) 사용**:
    - 공식 Python SDK 사용으로 코드 간소화 및 안정성 향상
    - 비동기 API 호출 (`generate_content_async`)
    - JSON Mode 지원 (`response_mime_type="application/json"`)
    - System Instruction 지원 (`system_instruction` 파라미터)
  - **Safety Settings 적용**:
    - 기본값: `BLOCK_NONE` (무검열)
    - 환경변수로 조절 가능 (`GOOGLE_SAFETY_THRESHOLD`)
    - 지원 값: `BLOCK_NONE`, `BLOCK_ONLY_HIGH`, `BLOCK_MEDIUM_AND_ABOVE`, `BLOCK_LOW_AND_ABOVE`
  - **환경변수 기반 설정**:
    - `GOOGLE_API_KEY`: Gemini API 키 (필수)
    - `GOOGLE_API_MODEL`: 사용할 모델 (기본값: `gemini-1.5-flash`)
    - `GOOGLE_SAFETY_THRESHOLD`: 안전 설정 (기본값: `BLOCK_NONE`)
    - 폴백: `NEXT_PUBLIC_GEMINI_API_KEY` (개발 환경 편의)
  - 성능 모니터링: API 호출 시간 측정 및 로깅
- **상태**: ✅ 구현 완료 (2026-01-26)
- **참고 문서**:
  - [Gemini API 사용해보기](https://velog.io/@dyd1308/Gemini-api-%EC%82%AC%EC%9A%A9%ED%95%B4%EB%B3%B4%EA%B8%B0)
  - [Gemini 모델 버전](https://ai.google.dev/gemini-api/docs/models?hl=ko#model-versions)

---

#### `POST /api/auth/logout` ✅ **구현됨**
- **용도**: 로그아웃 처리 및 쿠키 삭제
- **인증**: 불필요
- **응답**: 쿠키 삭제 후 프론트엔드로 리다이렉트 (`http://localhost:3000/`)

### 2.7 프론트엔드 API Route ✅ **구현됨**

#### `GET /api/characters` ✅ **구현됨** (Next.js API Route)

- **용도**: `public/characters/*.json` 파일 동적 로드
- **인증**: 불필요
- **구현 위치**: `app/api/characters/route.ts`
- **주요 기능**:
  - **비동기 처리 개선** (2026-01-26):
    - 동기식 파일 처리(`fs.readFileSync`) → 비동기식(`fs.promises`) 전환 ✅
    - `Promise.all()`을 사용한 병렬 파일 로드 ✅
    - 예외 처리 강화 (각 파일별 try-catch) ✅
    - 디렉토리 존재 확인 (`fs.promises.access`) ✅
    - 파일 타입 확인 (`stats.isFile()`) ✅
  - 자동 마이그레이션: 파일 로드 시 `persona` 필드 자동 제거
  - 프리셋 우선 정렬
- **응답**: `{ characters: Character[] }`
- **상태**: ✅ 구현 완료 (2026-01-26)

---

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
- **호출자**: Server B Backend `GET /api/chat/models` (**미구현** — 해당 라우트 없음)

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
- **호출자**: Server B Backend `GET /api/chat/models` (**미구현** — 해당 라우트 없음). Frontend `chatApi.listModels()`는 `/api/chat/models`를 호출하나 404.
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

### 6.1 Phase 5.2: 컨텍스트 절약 요약 기능 ✅ **부분 구현 완료** (2026-01-27)

**영향받는 API**: `POST /api/chat`

**구현 완료**:
- `app/services/context_manager.py`: get_summary, save_summary, summarize_dialogue
- Redis(선택) → DB(ChatSummary) → Memory; `chat.py` get_summary 연동; `evaluation.py` 요약 저장

**미구현**: 토큰 계산, 80% 트리거, 슬라이딩 윈도우, `manage_context` in chat

**참고**: `docs/구현_상태_요약_2026-01-26.md` §9.2

### 6.2 Phase 5.4: Frontend 턴 제한 설정화 ✅ **구현 완료**

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

### 6.3 TTS 음성 목록 조회 ✅ **구현 완료**

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
- `GET /api/chat/models` ⚠️ **미구현** (라우트 없음)
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
- `GET /api/tts/voices` - 음성 목록 조회

### ⚠️ Backend 미구현 API (Frontend `lib/api/client.ts`에만 정의)

- **Style Transfer API**: `POST /api/style/transform`, `GET /api/style/status/{job_id}` — Backend 라우트 없음. `styleApi`만 client에 정의.
- **Animation API**: `GET /api/animations` — Backend 라우트 없음. `animationApi`만 client에 정의.
- **`POST /api/characters/generate`** — Backend에 해당 경로 없음. Frontend `characterApi.generateCharacterDetails()`가 이 경로를 호출.
  - **client–Backend 경로 불일치**: 실제 연동 시 `POST /api/ai/generate/character-details`(구현됨, 인증 필요)를 사용하도록 client 수정 필요.

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

**문서 버전**: 2.0  
**최종 업데이트**: 2026-01-27

**변경 이력**:
- v2.0 (2026-01-27): BACK/FRONT 코드 검토 반영 — GET /api/chat/models, /api/style/*, /api/animations, /api/characters/generate 미구현; client chat body director_note/current_speaker/tts_* 미전달; /api/ai/generate/character-details와 client 경로 불일치 명시
- v1.9 (2026-01-27): 감독 모드(director_note, current_speaker), Phase 5.2 부분 완료(ContextManager, Redis, ChatSummary)
- v1.8 (2026-01-26): 서버 에러 해결 및 백엔드 Gemini SDK 도입 반영
  - 프론트엔드 500 에러 해결: `/api/characters` API 비동기 처리 개선
  - 백엔드 Gemini SDK 도입: `google-generativeai` 패키지 추가 및 적용
  - 백엔드 SDK 고도화: Safety Settings, JSON Mode 적용
  - 환경변수 기반 설정: GOOGLE_API_KEY, GOOGLE_API_MODEL, GOOGLE_SAFETY_THRESHOLD
  - AI 생성 API 섹션 추가 (`POST /api/ai/generate/story`, `POST /api/ai/generate/character-details`)
  - 프론트엔드 API Route 섹션 추가 (`GET /api/characters`)
  - 참고 문서 추가: Gemini API 사용 가이드 및 모델 버전 문서
- v1.7 (2026-01-26): 캐릭터 생성 위저드 개편 반영
  - Step 1 간소화 (이름, 카테고리, 작품명 3가지만 입력)
  - '다음' 버튼 클릭 시 AI 자동 생성
  - Step 2 통합 편집 (모든 정보 한 화면에서 수정)
  - AI 재생성 횟수 제한 (총 3회)
  - 작품명 필드 추가 (source_work)
  - worldview 필드 추가 (9종 캐릭터 모두)
  - 캐릭터 API 섹션 상세화 (상세 필드 구조 반영)
- v1.7 (2026-01-26): 캐릭터 시스템 고도화 작업 반영
  - 데이터 구조 세분화 (persona → 10개 이상의 상세 필드)
  - 파일 기반 관리 시스템 (public/characters/*.json API Route)
  - AI 자동 완성 기능 고도화 (generateCharacterSpec)
  - 프론트엔드 UI/UX 혁신 (CharacterCreationWizard 개편)
  - 시스템 최적화 (페르소나 빌더 시스템)
  - 9종 캐릭터 데이터 마이그레이션 완료
  - 캐릭터 API 섹션 상세화 (상세 필드 구조 반영)
- v1.7 (2026-01-26): 인증 제거 및 프롬프트 전달 수정 반영
  - `/api/chat`, `/api/chat/models` 인증 제거
  - `/api/tts`, `/api/tts/voices` 인증 제거
  - `/api/generate` 인증 제거 (user_id="anonymous")
  - `/api/characters/*` 모든 엔드포인트 인증 제거
  - 프론트엔드에서 persona, scenario, session_id, character_id 전달 확인
  - 백엔드에서 request.persona를 system 메시지로 포맷팅 확인
  - 내부 처리 과정 업데이트 (Character 조회 로직 제거, TTS 통합 임시 비활성화)
- v1.6 (2026-01-26): 캐릭터 API 섹션 추가 및 TTS API 상세화
- v1.6 (2026-01-26): Ollama 기준으로 API 구현 변경 - vLLM 코드 주석 처리, Ollama를 기본 LLM 서비스로 설정 (LLM_SERVICE 기본값: ollama), GPU_SERVER_URL 환경 변수 제거, chat.py Ollama 기준으로 재구현, 케이스 순서 변경 (Ollama 우선)
- v1.5 (2026-01-26): API 경로 통일 완료 - Frontend를 `/api`로 변경 (`lib/api/client.ts`), Backend는 이미 `/api` 사용 중 확인 완료
- v1.4 (2026-01-26): Backend Mock 응답 제거 및 실제 API 호출 구현 완료 - chat.py 수정, vLLM/Ollama 분기 처리, 에러 처리 강화, session_id 지원
- v1.3 (2026-01-26): Server A 연동 상태 업데이트 - vLLM 서버 실행, GPT-SoVITS WebAPI 구동, NPM 설정 완료 반영
- v1.2 (2026-01-26): 문서 정합성 작업 - API 경로 통일 (모든 문서에서 `/api`로 통일), 모델 이름 통일 확인
- v1.1 (2026-01-26): 리버스 프록시 설정 해결 방법 추가 (172.17.0.1:8000), API 문서 엔드포인트 정보 추가
- v1.0 (2026-01-26): 초기 문서 작성
