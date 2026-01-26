# LLM 서비스 비교: vLLM vs Ollama

**작성일**: 2026-01-26  
**버전**: 1.3

---

## 📋 목차

1. [개요](#1-개요)
2. [케이스 A: vLLM](#2-케이스-a-vllm)
3. [케이스 B: Ollama](#3-케이스-b-ollama)
4. [API 차이점 비교](#4-api-차이점-비교)
5. [Backend 구현 차이점](#5-backend-구현-차이점)
6. [환경 변수 설정](#6-환경-변수-설정)

---

## 1. 개요

**⚠️ 중요**: vLLM과 Ollama는 동시에 실행할 수 없습니다 (VRAM 제약). 하나만 선택하여 사용하세요.

### 선택 기준

| 항목 | vLLM | Ollama |
|------|------|--------|
| **모델 형식** | BitsAndBytes 4-bit | GGUF (Q4_K_XL) |
| **용량** | ~14GB | ~16.8GB |
| **성능** | 높은 처리량 (동시 접속 10-12명) | 중간 처리량 |
| **API 표준** | OpenAI 호환 | Ollama 자체 API |
| **설정 복잡도** | 중간 | 낮음 |
| **추천 용도** | 프로덕션, 높은 동시 접속 | 개발/테스트, 간단한 설정 |

---

## 2. 케이스 A: vLLM

### 2.1 서버 설정

**포트**: 8002 (외부) → 8000 (내부 컨테이너)  
**기본 URL**: `http://server-a:8002` 또는 `http://localhost:8002`  
**API 표준**: OpenAI 호환 API

### 2.2 Docker Compose 설정

```yaml
# docker-compose.yml (vLLM 사용 시)
services:
  vllm-server:
    image: vllm/vllm-openai:latest
    container_name: vllm-server
    ports:
      - "8002:8000"
    command:
      - unsloth/gemma-3-27b-it-bnb-4bit
      - --tensor-parallel-size 1
      - --dtype auto
      - --quantization bitsandbytes
      - --max-model-len 4096
```

### 2.3 API 엔드포인트

#### `POST /v1/chat/completions`

**요청 형식**:
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

**응답 형식**:
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "unsloth/gemma-3-27b-it-bnb-4bit",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "안녕하세요! 무엇을 도와드릴까요?"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

#### `GET /v1/models`

**응답 형식**:
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

---

## 3. 케이스 B: Ollama

### 3.1 서버 설정

**포트**: 11434  
**기본 URL**: `http://server-a:11434` 또는 `http://localhost:11434`  
**API 표준**: Ollama 자체 API

### 3.2 Docker Compose 설정

```yaml
# docker-compose.yml (Ollama 사용 시)
services:
  ollama-server:
    image: ollama/ollama:latest
    container_name: ollama-server
    ports:
      - "11434:11434"
    volumes:
      - /mnt/shared_models/llm/gemma-3-27b-it-GGUF:/models:ro
      - ollama-data:/root/.ollama
```

### 3.3 모델 등록

```bash
# Ollama 실행 후 모델 등록
docker exec -it ollama-server ollama create gemma-3-27b-it -f /models/gemma-3-27b-it-UD-Q4_K_XL.gguf
```

### 3.4 API 엔드포인트

**⚠️ 중요**: 채팅 기능에는 `/api/chat`를 사용합니다. `/api/generate`는 단순 프롬프트만 지원하므로 채팅에 부적합합니다.

#### `POST /api/chat` ✅ **채팅용 (권장)**

**요청 형식**:
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

**응답 형식**:
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

#### `GET /api/tags`

**응답 형식** (공식 문서 기준):
```json
{
  "models": [
    {
      "name": "gemma-3-27b-it",
      "modified_at": "2026-01-26T12:00:00Z",
      "size": 16800000000,
      "digest": "sha256:abc123...",
      "details": {
        "format": "gguf",
        "family": "gemma",
        "families": ["gemma"],
        "parameter_size": "27B",
        "quantization_level": "Q4_K_XL"
      }
    }
  ]
}
```

#### `POST /api/generate` ⚠️ **참고용 (채팅에는 사용하지 않음)**

**용도**: 단순 프롬프트 기반 텍스트 생성 (메시지 히스토리 미지원)

**요청 형식**:
```json
{
  "model": "gemma-3-27b-it",
  "prompt": "안녕하세요",
  "stream": false,
  "options": {
    "temperature": 0.7,
    "num_predict": 512
  }
}
```

**응답 형식**:
```json
{
  "model": "gemma-3-27b-it",
  "created_at": "2026-01-26T12:00:00Z",
  "response": "안녕하세요! 무엇을 도와드릴까요?",
  "done": true,
  "prompt_eval_count": 10,
  "eval_count": 20
}
```

**⚠️ 주의**: `/api/generate`는 `prompt`만 사용하고 `messages`를 지원하지 않으므로, 채팅 기능에는 `/api/chat`를 사용해야 합니다.

---

## 4. API 차이점 비교

### 4.1 엔드포인트 비교

| 기능 | vLLM | Ollama |
|------|------|--------|
| **채팅 완료** | `POST /v1/chat/completions` | `POST /api/chat` (권장) |
| **텍스트 생성** | `POST /v1/completions` | `POST /api/generate` (단순 프롬프트만) |
| **모델 목록** | `GET /v1/models` | `GET /api/tags` |
| **헬스체크** | `GET /health` | `GET /api/version` |

### 4.2 요청 형식 비교

#### vLLM 요청
```json
{
  "model": "unsloth/gemma-3-27b-it-bnb-4bit",
  "messages": [...],
  "temperature": 0.7,
  "max_tokens": 512
}
```

#### Ollama 요청
```json
{
  "model": "gemma-3-27b-it",
  "messages": [...],
  "stream": false,
  "options": {
    "temperature": 0.7,
    "num_predict": 512
  }
}
```

**주요 차이점**:
- vLLM: `max_tokens` 직접 사용
- Ollama: `options.num_predict` 사용
- Ollama: `stream` 필드 필수

### 4.3 응답 형식 비교

#### vLLM 응답
```json
{
  "choices": [{
    "message": {"role": "assistant", "content": "..."}
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20
  }
}
```

#### Ollama 응답
```json
{
  "message": {"role": "assistant", "content": "..."},
  "prompt_eval_count": 10,
  "eval_count": 20
}
```

**주요 차이점**:
- vLLM: `choices[0].message.content`
- Ollama: `message.content`
- vLLM: `usage.prompt_tokens`, `usage.completion_tokens`
- Ollama: `prompt_eval_count`, `eval_count`

---

## 5. Backend 구현 차이점

### 5.1 Server B Backend 코드 구현 상태

**위치**: `server-b/backend/app/api/chat.py`

**현재 상태**: ✅ Ollama 기준으로 구현 완료 (vLLM 코드는 주석 처리됨)

#### 케이스 B: Ollama 사용 (기본, 현재 구현됨)

```python
# 환경 변수
LLM_SERVICE = os.getenv("LLM_SERVICE", "ollama")  # 기본값: ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://server-a:11434")

# API 호출
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": request.model,
            "messages": messages,
            "stream": False,  # Ollama는 stream 필드 필수
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens  # Ollama는 num_predict 사용
            }
        },
        timeout=60.0
    )
    result = response.json()
    
    # 응답 파싱 (필드명 변환)
    content = result["message"]["content"]
    usage = {
        "prompt_tokens": result.get("prompt_eval_count", 0),
        "completion_tokens": result.get("eval_count", 0)
    }
```

#### 케이스 A: vLLM 사용 (주석 처리됨, 필요 시 주석 해제)

```python
# vLLM 코드는 chat.py에 주석으로 보관되어 있음
# 필요 시 주석을 해제하고 LLM_SERVICE를 "vllm"으로 변경하여 사용

# 환경 변수
# LLM_SERVICE = os.getenv("LLM_SERVICE", "vllm")
# VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://server-a:8002")

# API 호출
# async with httpx.AsyncClient() as client:
#     response = await client.post(
#         f"{VLLM_BASE_URL}/v1/chat/completions",
#         json={
#             "model": request.model,
#             "messages": messages,
#             "temperature": request.temperature,
#             "max_tokens": request.max_tokens
#         },
#         timeout=60.0
#     )
#     result = response.json()
#     
#     # 응답 파싱
#     content = result["choices"][0]["message"]["content"]
#     usage = {
#         "prompt_tokens": result["usage"]["prompt_tokens"],
#         "completion_tokens": result["usage"]["completion_tokens"]
#     }
```

### 5.2 페르소나 포맷팅 및 TTS 통합 ✅

**위치**: `server-b/backend/app/api/chat.py`

**구현 완료된 기능**:
- ✅ `format_persona_for_roleplay()` 함수: 역할극에 적합한 구조화된 페르소나 포맷팅
- ✅ 시나리오 정보 포함: opponent, situation, background
- ✅ Character 조회: character_id로 voice_id 자동 추출
- ✅ TTS 통합: 채팅 응답 후 자동 TTS 호출 (`_synthesize_tts_internal` 사용)
- ✅ 매 요청마다 system 메시지 포함 (Ollama 요구사항)

**페르소나 포맷팅 예시**:
```python
formatted_persona = format_persona_for_roleplay(
    persona=request.persona,
    character_name=character.name if character else None,
    scenario=request.scenario
)
# 결과: "당신은 {character_name}입니다.\n{persona}\n\n현재 상황: {situation}..."
```

### 5.3 현재 구현 상태

**위치**: `server-b/backend/app/api/chat.py`

**현재 구현**: ✅ Ollama 기준으로 구현 완료 (vLLM 코드는 주석 처리됨)

```python
# server-b/backend/app/api/chat.py
# 현재 기본값: ollama
LLM_SERVICE = os.getenv("LLM_SERVICE", "ollama")  # 기본값: ollama

async def call_llm_service(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 512
) -> Dict[str, Any]:
    """LLM 서비스 호출 (Ollama 기준, vLLM 코드는 주석 처리됨)"""
    
    if LLM_SERVICE == "ollama":
        # 케이스 B: Ollama API (기본 사용)
        OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://server-a:11434")
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
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
    
    # vLLM 코드는 주석 처리되어 있음 (필요 시 주석 해제)
    # elif LLM_SERVICE == "vllm":
    #     VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://server-a:8002")
    #     response = await client.post(
    #         f"{VLLM_BASE_URL}/v1/chat/completions",
    #         json={
    #             "model": model,
    #             "messages": messages,
    #             "temperature": temperature,
    #             "max_tokens": max_tokens
    #         },
    #         timeout=60.0
    #     )
    #     result = response.json()
    #     return {
    #         "content": result["choices"][0]["message"]["content"],
    #         "usage": {
    #             "prompt_tokens": result["usage"]["prompt_tokens"],
    #             "completion_tokens": result["usage"]["completion_tokens"]
    #         }
    #     }
```

---

## 6. 환경 변수 설정

### 6.1 Server B Backend 환경 변수

**파일**: `server-b/backend/.env`

#### 케이스 B: Ollama 사용 (기본, 현재 구현됨)

```bash
# LLM 서비스 선택 (기본값: ollama)
LLM_SERVICE=ollama

# Ollama 서버 URL
OLLAMA_BASE_URL=http://gpugpt.duckdns.org  # 또는 직접 IP (예: http://192.168.1.100:11434)
```

#### 케이스 A: vLLM 사용 (주석 처리됨, 필요 시 주석 해제)

```bash
# vLLM 사용 시 chat.py의 vLLM 코드 주석 해제 필요
# LLM_SERVICE=vllm

# vLLM 서버 URL (주석 처리된 코드에서 사용)
# VLLM_BASE_URL=http://server-a:8002
```

### 6.2 Server A Docker Compose

#### 케이스 A: vLLM 실행

```bash
docker-compose --profile vllm up -d vllm-server
```

#### 케이스 B: Ollama 실행

```bash
docker-compose --profile ollama up -d ollama-server
```

---

## 7. 요약

### 주요 차이점

1. **API 엔드포인트**:
   - vLLM: `/v1/chat/completions` (OpenAI 호환)
   - Ollama: `/api/chat` (Ollama 자체)

2. **요청 형식**:
   - vLLM: `max_tokens` 직접 사용
   - Ollama: `options.num_predict` 사용

3. **응답 형식**:
   - vLLM: `choices[0].message.content`
   - Ollama: `message.content`

4. **토큰 사용량**:
   - vLLM: `usage.prompt_tokens`, `usage.completion_tokens`
   - Ollama: `prompt_eval_count`, `eval_count`

5. **포트**:
   - vLLM: 8002
   - Ollama: 11434

### 구현 시 주의사항

1. **환경 변수로 선택**: `LLM_SERVICE=vllm` 또는 `LLM_SERVICE=ollama`
2. **응답 파싱 분기**: 케이스별로 다른 응답 형식 처리
3. **토큰 사용량 변환**: Ollama의 경우 필드명 변환 필요
4. **모델 이름**: vLLM은 Hugging Face 모델 ID, Ollama는 등록된 모델 이름 사용

---

**참고 문서**:
- **Ollama 공식 문서**: https://docs.ollama.com/api/introduction
- `docs/PROJECT_API_SUMMARY.md` - API 명세서
- `docs/FINALFINAL.md` - 통합 명세서
- `docs/Backend_프로젝트_현황_명세서.md` - Backend 구현 명세서

---

## 7. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.3 | 2026-01-26 | 로그인/로그아웃 시스템 통합 완료 반영 - Backend JWT HttpOnly Cookie 설정, Frontend NextAuth.js 제거 |
| 1.2 | 2026-01-26 | Ollama 기준으로 구현 변경 - vLLM 코드 주석 처리, Ollama를 기본 LLM 서비스로 설정 (LLM_SERVICE 기본값: ollama), GPU_SERVER_URL 제거, chat.py Ollama 기준으로 재구현, 모든 문서 업데이트 |
| 1.1 | 2026-01-26 | 문서 정합성 작업 - 정보 일관성 확인 (기준 문서) |
| 1.0 | 2026-01-26 | 초기 문서 작성 |
