from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import uuid
import logging
from app.core.config import settings
from app.api.deps import get_db
from app.models.user import User
from app.models.generation import Character
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger(__name__)

# OPTIONS 요청은 CORSMiddleware가 자동으로 처리하므로 명시적 엔드포인트 불필요
# FastAPI의 CORSMiddleware가 preflight 요청을 자동으로 처리합니다


def format_persona_for_roleplay(
    persona: str,
    character_name: Optional[str] = None,
    scenario: Optional[Dict[str, str]] = None
) -> str:
    """
    페르소나를 역할극에 적합한 형식으로 포맷팅
    
    Args:
        persona: 캐릭터 페르소나 설명
        character_name: 캐릭터 이름 (선택적)
        scenario: 시나리오 정보 (opponent, situation, background)
    
    Returns:
        포맷팅된 페르소나 문자열
    """
    parts = []
    
    # 캐릭터 이름
    if character_name:
        parts.append(f"당신은 {character_name}입니다.")
    
    # 페르소나 설명
    parts.append(f"\n{persona}")
    
    # 시나리오 정보
    if scenario:
        if scenario.get("situation"):
            parts.append(f"\n\n현재 상황: {scenario['situation']}")
        if scenario.get("background"):
            parts.append(f"배경: {scenario['background']}")
        if scenario.get("opponent"):
            parts.append(f"상대방: {scenario['opponent']}")
    
    # 역할극 지시사항
    parts.append("\n\n중요 지침:")
    parts.append("- 캐릭터의 성격과 말투를 일관되게 유지하세요.")
    parts.append("- 사용자와 자연스럽게 대화하세요.")
    parts.append("- 캐릭터의 특성을 반영한 응답을 생성하세요.")
    parts.append("- 이전 대화의 맥락을 고려하여 응답하세요.")
    
    return "\n".join(parts)


async def get_character_by_id(
    character_id: str,
    user_id: str,
    db: AsyncSession
) -> Optional[Character]:
    """
    캐릭터 ID로 캐릭터 조회
    
    Args:
        character_id: 캐릭터 ID
        user_id: 사용자 ID (권한 확인용)
        db: 데이터베이스 세션
    
    Returns:
        Character 객체 또는 None
    """
    try:
        result = await db.execute(
            select(Character).where(Character.id == character_id)
        )
        character = result.scalar_one_or_none()
        
        if character:
            # 사전설정 캐릭터이거나 사용자 소유 캐릭터인지 확인
            if character.is_preset or character.user_id == user_id:
                return character
        
        return None
    except Exception as e:
        logger.warning(f"캐릭터 조회 실패: {e}")
        return None


class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    persona: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    model: str = "gemma-3-27b-it"  # 기본 모델 이름 통일
    session_id: Optional[str] = None  # 세션 ID (선택적, 자동 생성)
    character_id: Optional[str] = None  # 캐릭터 ID (voice_id 조회용)
    scenario: Optional[Dict[str, str]] = None  # 시나리오 정보 (opponent, situation, background)
    # TTS 관련 필드
    tts_enabled: bool = True  # TTS 활성화 여부
    tts_mode: str = "realtime"  # "realtime" | "delayed" | "on_click"
    tts_delay_ms: int = 0  # 지연 시간 (밀리초)
    tts_streaming_mode: int = 0  # GPT-SoVITS streaming_mode (0-3)

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Proxy chat request to Server A (LLM Service).
    Ollama 서비스를 사용하여 실제 LLM API를 호출합니다.
    인증 없이 사용 가능합니다.
    """
    # 세션 ID 생성 (없는 경우)
    session_id = request.session_id or str(uuid.uuid4())
    
    # 캐릭터 조회 제거 (인증 없이 사용하기 위해)
    character = None
    
    # 메시지 준비 (persona가 있으면 system 메시지로 추가)
    messages = []
    if request.persona:
        # 페르소나 포맷팅
        formatted_persona = format_persona_for_roleplay(
            persona=request.persona,
            character_name=character.name if character else None,
            scenario=request.scenario
        )
        
        # 개발 환경에서 로깅 (환경 변수 확인)
        import os
        if os.getenv("DEBUG", "false").lower() == "true":
            logger.debug(f"페르소나 포맷팅 결과 (길이: {len(formatted_persona)}):\n{formatted_persona[:200]}...")
        
        messages.append(Message(role="system", content=formatted_persona))
    
    # 대화 메시지 추가 (항상 전체 대화 포함)
    messages.extend(request.messages)
    
    # 개발 환경에서 로깅
    import os
    if os.getenv("DEBUG", "false").lower() == "true":
        logger.debug(f"전송할 메시지 수: {len(messages)} (system: {1 if request.persona else 0}, 대화: {len(request.messages)})")
    
    # 메시지를 딕셔너리 리스트로 변환
    messages_dict = [{"role": msg.role, "content": msg.content} for msg in messages]
    
    try:
        # LLM 서비스에 따라 분기 처리
        # 현재 기본값: ollama (vLLM 코드는 주석 처리되어 있음)
        if settings.LLM_SERVICE == "ollama":
            # 케이스 B: Ollama API (기본 사용)
            result = await _call_ollama_api(
                messages=messages_dict,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
        # elif settings.LLM_SERVICE == "vllm":
        #     # 케이스 A: vLLM OpenAI 호환 API (주석 처리됨)
        #     result = await _call_vllm_api(
        #         messages=messages_dict,
        #         model=request.model,
        #         temperature=request.temperature,
        #         max_tokens=request.max_tokens
        #     )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Unknown LLM_SERVICE: {settings.LLM_SERVICE}. Must be 'ollama' (vllm은 현재 주석 처리됨)."
            )
        
        # 성공 응답 데이터 준비
        response_data = {
            "content": result["content"],
            "usage": result["usage"],
            "session_id": session_id,
            "context_summarized": False  # Phase 5.2에서 구현 예정
        }
        
        # TTS 통합 비활성화 (인증 제거로 인해 임시 비활성화)
        # TTS 기능이 필요하면 별도로 /api/tts 엔드포인트 사용
        # if request.tts_enabled and result.get("content"):
        #     ... (TTS 코드 생략)
        
        # 성공 응답 반환
        return {
            "success": True,
            "data": response_data
        }
        
    except httpx.HTTPStatusError as e:
        # HTTP 에러 처리
        error_detail = f"LLM 서비스 HTTP 에러: {e.response.status_code}"
        if e.response.status_code == 503:
            error_detail += " (서비스 일시 중지 또는 과부하)"
        elif e.response.status_code == 404:
            error_detail += " (엔드포인트를 찾을 수 없음)"
        elif e.response.status_code == 500:
            error_detail += " (서버 내부 오류)"
        
        raise HTTPException(
            status_code=e.response.status_code,
            detail=error_detail
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="LLM 서비스 응답 시간 초과 (120초). Ollama API 응답이 느릴 수 있습니다."
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"LLM 서비스에 연결할 수 없습니다. 서비스가 실행 중인지 확인하세요. (URL: {settings.OLLAMA_BASE_URL})"
        )
    except KeyError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM 서비스 응답 형식 오류: 필수 필드 누락 ({str(e)})"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM 서비스 호출 중 오류 발생: {str(e)}"
        )


# vLLM API 호출 함수 (주석 처리됨 - 현재 Ollama 사용)
# async def _call_vllm_api(
#     messages: List[Dict[str, str]],
#     model: str,
#     temperature: float,
#     max_tokens: int
# ) -> Dict[str, Any]:
#     """vLLM OpenAI 호환 API 호출"""
#     api_url = f"{settings.VLLM_BASE_URL}/v1/chat/completions"
#     
#     async with httpx.AsyncClient(timeout=60.0) as client:
#         response = await client.post(
#             api_url,
#             json={
#                 "model": model,
#                 "messages": messages,
#                 "temperature": temperature,
#                 "max_tokens": max_tokens
#             }
#         )
#         response.raise_for_status()
#         result = response.json()
#         
#         # vLLM 응답 파싱
#         return {
#             "content": result["choices"][0]["message"]["content"],
#             "usage": {
#                 "prompt_tokens": result["usage"]["prompt_tokens"],
#                 "completion_tokens": result["usage"]["completion_tokens"]
#             }
#         }


async def _call_ollama_api(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int
) -> Dict[str, Any]:
    """
    Ollama API 호출 (기본 LLM 서비스)
    
    Ollama API 형식:
    - 엔드포인트: /api/chat (또는 리버스 프록시 경로)
    - 요청 형식: {"model": str, "messages": List[Dict], "stream": bool, "options": Dict}
    - 응답 형식: {"message": Dict, "prompt_eval_count": int, "eval_count": int}
    
    리버스 프록시 지원:
    - OLLAMA_BASE_URL에 도메인 설정 (예: http://gpugpt.duckdns.org)
    - OLLAMA_API_PATH에 경로 설정 (기본: /api/chat, 프록시 경로 포함 가능)
    - OLLAMA_SSL_VERIFY로 SSL 검증 설정
    """
    # 리버스 프록시 경로 지원
    # curl 명령어와 동일하게: http://gpugpt.duckdns.org/api/chat
    api_path = getattr(settings, 'OLLAMA_API_PATH', "/api/chat")
    # BASE_URL 끝에 슬래시가 있으면 제거
    base_url = settings.OLLAMA_BASE_URL.rstrip('/')
    # API 경로가 /로 시작하지 않으면 추가
    if not api_path.startswith('/'):
        api_path = '/' + api_path
    api_url = f"{base_url}{api_path}"
    
    # curl 명령어와 동일한 형식으로 요청 데이터 준비
    # curl: {"model": "gemma-3-27b-it", "messages": [...], "stream": false}
    request_data = {
        "model": model,
        "messages": messages,
        "stream": False,  # Ollama는 stream 필드 필수
    }
    
    # options는 선택적이지만, temperature와 max_tokens가 기본값이 아니면 추가
    if temperature != 0.7 or max_tokens != 512:
        request_data["options"] = {
            "temperature": temperature,
            "num_predict": max_tokens  # Ollama는 num_predict 사용
        }
    
    # 개발 환경에서 로깅
    import os
    if os.getenv("DEBUG", "false").lower() == "true":
        logger.debug(f"Ollama API 호출: {api_url}")
        logger.debug(f"요청 모델: {model}, 메시지 수: {len(messages)}")
    
    try:
        # SSL 검증 설정 (리버스 프록시 사용 시)
        ssl_verify = getattr(settings, 'OLLAMA_SSL_VERIFY', False)
        
        # curl 명령어와 동일하게 POST 요청 전송
        async with httpx.AsyncClient(
            timeout=120.0,  # 타임아웃 120초로 증가
            verify=ssl_verify  # SSL 인증서 검증 설정
        ) as client:
            # curl -d와 동일하게 JSON body로 POST 요청
            response = await client.post(
                api_url,
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            # 개발 환경에서 로깅
            if os.getenv("DEBUG", "false").lower() == "true":
                logger.debug(f"Ollama API 응답 수신: {list(result.keys())}")
                logger.debug(f"Ollama API 응답 내용 (일부): {str(result)[:500]}")
            
            # Ollama API 응답 형식 검증 및 파싱
            # 응답 형식: {
            #   "model": "gemma-3-27b-it",
            #   "message": {"role": "assistant", "content": "..."},
            #   "prompt_eval_count": 11,
            #   "eval_count": 26,
            #   "done": true,
            #   ...
            # }
            
            if "message" not in result:
                logger.error(f"Ollama 응답에 'message' 필드가 없습니다. 응답 키: {list(result.keys())}")
                raise KeyError("Ollama 응답에 'message' 필드가 없습니다.")
            
            message = result["message"]
            if not isinstance(message, dict):
                logger.error(f"Ollama 응답의 'message' 필드가 딕셔너리가 아닙니다: {type(message)}, 값: {message}")
                raise ValueError(f"Ollama 응답의 'message' 필드가 딕셔너리가 아닙니다: {type(message)}")
            
            if "content" not in message:
                logger.error(f"Ollama 응답의 'message'에 'content' 필드가 없습니다. message 키: {list(message.keys()) if isinstance(message, dict) else 'N/A'}")
                raise KeyError("Ollama 응답의 'message'에 'content' 필드가 없습니다.")
            
            content = message["content"]
            if not isinstance(content, str):
                logger.error(f"Ollama 응답의 'content'가 문자열이 아닙니다: {type(content)}, 값: {content}")
                raise ValueError(f"Ollama 응답의 'content'가 문자열이 아닙니다: {type(content)}")
            
            # content가 비어있으면 에러
            if not content.strip():
                logger.warning("Ollama 응답의 'content'가 비어있습니다.")
                content = "(응답이 비어있습니다.)"
            
            # Ollama 응답 파싱 (필드명 변환)
            # Ollama는 prompt_eval_count/eval_count를 사용하므로 표준 형식으로 변환
            parsed_result = {
                "content": content.strip(),  # 앞뒤 공백 제거
                "usage": {
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "completion_tokens": result.get("eval_count", 0)
                }
            }
            
            # 개발 환경에서 로깅
            if os.getenv("DEBUG", "false").lower() == "true":
                logger.debug(f"Ollama API 응답 파싱 완료: content 길이={len(parsed_result['content'])}, tokens={parsed_result['usage']}")
            
            return parsed_result
    except httpx.TimeoutException as e:
        logger.error(f"Ollama API 타임아웃: {api_url}")
        raise
    except httpx.HTTPStatusError as e:
        error_detail = f"Ollama API HTTP 에러: {e.response.status_code}"
        try:
            error_body = e.response.json()
            if "error" in error_body:
                error_detail += f" - {error_body['error']}"
        except:
            error_detail += f" - {e.response.text[:200]}"
        logger.error(f"{error_detail} (URL: {api_url})")
        raise
    except KeyError as e:
        logger.error(f"Ollama API 응답 파싱 오류: {e} (응답: {result if 'result' in locals() else 'N/A'})")
        raise
    except Exception as e:
        logger.error(f"Ollama API 호출 중 예상치 못한 오류: {e}", exc_info=True)
        raise


class SimpleChatRequest(BaseModel):
    """인증 없는 테스트용 단순 채팅 요청"""
    messages: List[Message]
    model: str = "gemma-3-27b-it"
    temperature: float = 0.7
    max_tokens: int = 512


@router.post("/chat/test")
async def chat_test(request: SimpleChatRequest):
    """
    인증 없이 AI 응답을 테스트하는 엔드포인트.
    사용자 인증, TTS, 캐릭터 조회 등 복잡한 로직을 제외하고
    Ollama API 직접 호출만 수행합니다.
    
    테스트용으로만 사용하세요. 프로덕션에서는 /chat 엔드포인트를 사용하세요.
    """
    # 메시지를 딕셔너리 리스트로 변환
    messages_dict = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    try:
        # Ollama API 호출
        result = await _call_ollama_api(
            messages=messages_dict,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return {
            "success": True,
            "data": {
                "content": result["content"],
                "usage": result["usage"]
            }
        }
        
    except httpx.HTTPStatusError as e:
        error_detail = f"LLM 서비스 HTTP 에러: {e.response.status_code}"
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM 서비스 응답 시간 초과")
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"LLM 서비스에 연결할 수 없습니다. (URL: {settings.OLLAMA_BASE_URL})"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 서비스 호출 중 오류: {str(e)}")


@router.get("/chat/models")
async def list_models():
    """
    사용 가능한 LLM 모델 목록 조회
    """
    # 기본 모델 목록 반환 (실제 서비스에서 조회하는 기능은 Phase 5.1 이후 구현 예정)
    return {
        "success": True,
        "data": {
            "models": [
                {"id": "gemma-3-27b-it", "name": "Gemma 3 27B IT (Default)"},
            ]
        }
    }
