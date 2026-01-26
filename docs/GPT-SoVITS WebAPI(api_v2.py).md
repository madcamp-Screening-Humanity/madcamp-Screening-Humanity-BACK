# 📘 GPT-SoVITS WebAPI 통합 문서

**작성일**: 2026-01-26  
**프로젝트 사용 현황**: Server A (GPU 서버)에서 실행, Server B Backend가 내부 호출

---

## 📋 프로젝트에서 사용하는 API

### ✅ 사용 중인 API

1. **`POST /tts`** - 텍스트-음성 변환
   - **호출자**: Server B Backend (`POST /api/tts`)
   - **상태**: 사용 중

2. **`GET /tts`** - 텍스트-음성 변환 (GET 방식)
   - **호출자**: 직접 호출 또는 테스트용
   - **상태**: 사용 가능

### ⚠️ 미사용 API (관리용)

3. **`GET /set_gpt_weights`** - GPT 모델 변경
   - **상태**: 관리용, 현재 미사용

4. **`GET /set_sovits_weights`** - SoVITS 모델 변경
   - **상태**: 관리용, 현재 미사용

5. **`GET /control?command=restart`** - 서버 재시작
   - **상태**: 관리용, 현재 미사용

---

## 1. 서버 실행 (Server Startup)

터미널에서 아래 명령어로 서버를 시작합니다.

```bash
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml

```

**실행 파라미터:**

* `-a`: 바인딩 IP 주소 (기본값: `127.0.0.1`)
* `-p`: 바인딩 포트 (기본값: `9880`)
* `-c`: TTS 설정 파일 경로 (기본값: `GPT_SoVITS/configs/tts_infer.yaml`)

**⚠️ 포트 정보 (GPT-SoVITS 서비스 구분)**:

GPT-SoVITS는 여러 서비스가 다른 포트를 사용합니다:

| 포트 | 서비스 | 설명 | 사용 방법 |
|------|--------|------|----------|
| **9880** | **WebAPI (api_v2.py)** | 텍스트-음성 변환 API 서버 | 이 문서에서 설명하는 서비스 |
| 9872 | TTS API (webui.py) | webui.py에서 제공하는 TTS API | webui.py 실행 시 |
| 9873 | 반주 분리 (UVR5) | 오디오에서 반주 분리 서비스 | webui.py 실행 시 |
| 9874 | WebUI | GPT-SoVITS 관리 인터페이스 | webui.py 실행 시 |

**참고**: 이 문서는 `api_v2.py` (포트 9880)에 대한 문서입니다. `webui.py`를 사용하는 경우 포트 9872를 사용하세요.

---

## 2. 텍스트 음성 변환 (Text-to-Speech)

**Endpoint:** `/tts`

**Method:** `GET` / `POST`

### 📤 POST 요청 (권장)

복잡한 설정을 세밀하게 제어하려면 POST 방식을 권장합니다.

**Request Body (JSON):**

```json
{
    // --- 필수 입력 항목 ---
    "text": "안녕하세요, 반갑습니다.",      // 합성할 텍스트
    "text_lang": "ko",                   // 텍스트 언어 (zh, en, ja, ko 등)
    "ref_audio_path": "path/to/ref.wav", // 참조 오디오 파일 경로 (서버 내부 경로)
    "prompt_lang": "ko",                 // 참조 오디오의 언어
    
    // --- 참조 오디오 관련 (선택) ---
    "prompt_text": "",                   // 참조 오디오의 텍스트 (비워두면 자동 인식 시도하지만, 입력 권장)
    "aux_ref_audio_paths": [],           // 다화자 톤 융합을 위한 추가 참조 오디오 경로 리스트

    // --- 추론 및 품질 설정 ---
    "top_k": 5,                          // Top-K 샘플링 (기본값: 5)
    "top_p": 1,                          // Top-P 샘플링 (기본값: 1)
    "temperature": 1,                    // 샘플링 온도 (기본값: 1)
    "repetition_penalty": 1.35,          // 반복 패널티 (T2S 모델, 기본값: 1.35)
    "batch_size": 1,                     // 추론 배치 크기 (기본값: 1)
    "speed_factor": 1.0,                 // 발화 속도 조절 (1.0 = 정속)
    "seed": -1,                          // 랜덤 시드 (-1 = 무작위)
    "parallel_infer": true,              // 병렬 추론 사용 여부 (기본값: true)

    // --- 텍스트 처리 ---
    "text_split_method": "cut5",         // 텍스트 분할 방식 (cut0, cut1, cut2, cut3, cut4, cut5)
    "batch_threshold": 0.75,             // 배치 분할 임계값 (기본값: 0.75)
    "split_bucket": true,                // 배치를 버킷으로 나눌지 여부 (기본값: true)

    // --- 출력 형식 및 스트리밍 ---
    "media_type": "wav",                 // 응답 포맷 ("wav", "ogg", "aac", "raw")
    "streaming_mode": 0,                 // 스트리밍 모드 설정 (아래 상세 설명 참조)
    
    // --- 스트리밍 세부 설정 (streaming_mode 켜짐 시) ---
    "overlap_length": 2,                 // 스트리밍 시맨틱 토큰 중첩 길이 (기본값: 2)
    "min_chunk_length": 16,              // 스트리밍 최소 청크 길이 (기본값: 16)
    "fragment_interval": 0.3,            // 오디오 조각 간격 제어 (기본값: 0.3)

    // --- VITS 모델 고급 설정 ---
    "sample_steps": 32,                  // VITS 모델 샘플링 스텝 수 (기본값: 32)
    "super_sampling": false              // VITS 초해상도(Super Sampling) 사용 여부 (기본값: false)
}

```

#### 💡 `streaming_mode` 상세 옵션

* `0` (False): 비활성화 (전체 생성 후 반환)
* `1` (True): **고품질** 스트리밍 (응답 속도 느림, 구버전 방식)
* `2`: **중간 품질** 스트리밍 (응답 속도 보통)
* `3`: **저품질** 스트리밍 (응답 속도 매우 빠름)

---

### 📥 GET 요청 (간편 테스트용)

```
http://127.0.0.1:9880/tts?text=테스트입니다&text_lang=ko&ref_audio_path=123.wav&prompt_lang=ko&text_split_method=cut5&batch_size=1&media_type=wav&streaming_mode=0

```

---

## 3. 모델 관리 (Model Management)

실행 중인 모델(가중치)을 실시간으로 교체합니다.

### GPT 모델 변경

**Endpoint:** `/set_gpt_weights`

**Method:** `GET`

```
http://127.0.0.1:9880/set_gpt_weights?weights_path=GPT_SoVITS/pretrained_models/s1bert25hz.ckpt

```

### SoVITS 모델 변경

**Endpoint:** `/set_sovits_weights`

**Method:** `GET`

```
http://127.0.0.1:9880/set_sovits_weights?weights_path=GPT_SoVITS/pretrained_models/s2G488k.pth

```

---

## 4. 시스템 제어 (System Control)

**Endpoint:** `/control`

**Method:** `GET` / `POST`

**명령어 (command):**

* `restart`: 서버 재시작 (모델 리로드 등 필요 시)
* `exit`: 서버 프로세스 종료

**GET 예시:**

```
http://127.0.0.1:9880/control?command=restart

```

---

## 5. 응답 (Responses)

* **성공 (Success):**
* `/tts`: 오디오 바이너리 스트림 (wav, ogg, aac 등) 반환 (HTTP 200)
* 그 외: `{"message": "success"}` JSON 반환 (HTTP 200)


* **실패 (Failure):**
* 오류 메시지가 포함된 JSON 반환 (HTTP 400)
* 예: `{"message": "ref_audio_path is required"}`

---

## 6. Backend 통합 방식

### 6.1 Chat API에서 TTS 자동 호출

**파일**: `server-b/backend/app/api/chat.py`

**구현 방식**:
- Chat API 응답 후 자동으로 TTS 생성 (`tts_enabled=True`일 때)
- `_synthesize_tts_internal()` 함수 직접 호출 (내부 함수)
- character.voice_id 사용 (없으면 "default")
- streaming_mode는 요청에서 받은 값 사용
- TTS 실패 시에도 채팅 응답은 정상 반환

**코드 예시**:
```python
# chat.py 내부
if request.tts_enabled and result.get("content"):
    try:
        from app.api.tts import _synthesize_tts_internal, TTSRequest
        
        voice_id = "default"
        if character and character.voice_id:
            voice_id = character.voice_id
        
        tts_request = TTSRequest(
            text=result["content"],
            voice_id=voice_id,
            streaming_mode=request.tts_streaming_mode,
            return_binary=False,
            text_lang="ko",
            prompt_lang="ko"
        )
        
        tts_response = await _synthesize_tts_internal(tts_request, current_user, db)
        
        if tts_response and tts_response.get("success") and tts_response.get("data"):
            response_data["audio_url"] = tts_response["data"]["audio_url"]
    except Exception as e:
        # TTS 실패해도 채팅은 정상 반환
        logger.warning(f"TTS generation failed: {e}")
```

### 6.2 _synthesize_tts_internal 함수

**파일**: `server-b/backend/app/api/tts.py`

**용도**: 다른 모듈에서 직접 호출 가능한 내부 TTS 합성 함수

**특징**:
- 항상 JSON 딕셔너리 반환 (Response 객체 반환 안 함)
- `return_binary=True`를 받으면 ValueError 발생 (HTTP 엔드포인트 사용 필요)
- 캐싱 시스템 활용 (데이터베이스 기반)
- 오디오 파일 메타데이터 분석 (mutagen 사용)

**사용 예시**:
```python
from app.api.tts import _synthesize_tts_internal, TTSRequest

tts_request = TTSRequest(
    text="안녕하세요",
    voice_id="default",
    streaming_mode=0,
    return_binary=False  # 내부 함수에서는 False만 지원
)

result = await _synthesize_tts_internal(tts_request, current_user, db)
# result: {"success": True, "data": {"audio_url": "...", ...}}
```

### 6.3 캐싱 시스템 활용

**구현 방식**:
- 동일한 텍스트+voice_id+format 조합은 데이터베이스에서 재사용
- `audio_files` 테이블에 메타데이터 저장
- 캐시 히트 시 GPT-SoVITS API 호출 생략

**장점**:
- 동일한 텍스트의 중복 생성 방지
- 응답 시간 단축
- 서버 부하 감소

---

## 7. 관련 AI 서비스 (Gemini SDK)

### 7.1 개요

**⚠️ 참고**: Gemini SDK는 GPT-SoVITS와는 별도로, **AI 생성 API** (캐릭터 상세 설정 자동 생성)에 사용됩니다.

**구현 위치**: `server-b/backend/app/api/ai.py`

**주요 기능**:
- Google Generative AI SDK (`google-generativeai`) 사용
- 비동기 API 호출 (`generate_content_async`)
- JSON Mode 지원 (`response_mime_type="application/json"`)
- Safety Settings 적용 (기본값: `BLOCK_NONE`)

**환경변수 설정**:
```bash
# server-b/backend/.env
GOOGLE_API_KEY=your-gemini-api-key-here  # 필수: Gemini API 키
GOOGLE_API_MODEL=gemini-1.5-flash  # 선택: 사용할 모델 (기본값: gemini-1.5-flash)
GOOGLE_SAFETY_THRESHOLD=BLOCK_NONE  # 선택: 안전 설정 (기본값: BLOCK_NONE)
```

**참고 문서** (⚠️ **필수 참고**):
- [Gemini API 사용해보기](https://velog.io/@dyd1308/Gemini-api-%EC%82%AC%EC%9A%A9%ED%95%B4%EB%B3%B4%EA%B8%B0) - Gemini API 사용 시 반드시 참고
- [Gemini 모델 버전](https://ai.google.dev/gemini-api/docs/models?hl=ko#model-versions) - 모델 선택 시 반드시 참고

---

## 8. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.3 | 2026-01-26 | 서버 에러 해결 및 백엔드 Gemini SDK 도입 반영 - 프론트엔드 500 에러 해결 (/api/characters API 비동기 처리 개선), 백엔드 Gemini SDK 도입 (google-generativeai 패키지 추가 및 적용), 관련 AI 서비스 섹션 추가 (Gemini SDK) |
| 1.2 | 2026-01-26 | 로그인/로그아웃 시스템 통합 완료 반영 - Backend JWT HttpOnly Cookie 설정, Frontend NextAuth.js 제거 |
| 1.1 | 2026-01-26 | 문서 정합성 작업: 포트 정보 명시 (api_v2.py는 포트 9880, webui.py와 구분) |
| 1.0 | 2026-01-26 | 초기 문서 작성 |