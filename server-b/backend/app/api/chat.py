from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import uuid
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

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

@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Proxy chat request to Server A (LLM Service).
    Ollama 서비스를 사용하여 실제 LLM API를 호출합니다.
    (vLLM 코드는 주석 처리되어 있으며, 필요 시 주석을 해제하여 사용할 수 있습니다)
    """
    # 세션 ID 생성 (없는 경우)
    session_id = request.session_id or str(uuid.uuid4())
    
    # 메시지 준비 (persona가 있으면 system 메시지로 추가)
    messages = []
    if request.persona:
        messages.append(Message(role="system", content=request.persona))
    messages.extend(request.messages)
    
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
        
        # 성공 응답 반환
        return {
            "success": True,
            "data": {
                "content": result["content"],
                "usage": result["usage"],
                "session_id": session_id,
                "context_summarized": False  # Phase 5.2에서 구현 예정
            }
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
            detail="LLM 서비스 응답 시간 초과 (60초)"
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
    - 엔드포인트: /api/chat
    - 요청 형식: {"model": str, "messages": List[Dict], "stream": bool, "options": Dict}
    - 응답 형식: {"message": Dict, "prompt_eval_count": int, "eval_count": int}
    """
    api_url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            api_url,
            json={
                "model": model,
                "messages": messages,
                "stream": False,  # Ollama는 stream 필드 필수
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens  # Ollama는 num_predict 사용
                }
            }
        )
        response.raise_for_status()
        result = response.json()
        
        # Ollama 응답 파싱 (필드명 변환)
        # Ollama는 prompt_eval_count/eval_count를 사용하므로 표준 형식으로 변환
        return {
            "content": result["message"]["content"],
            "usage": {
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0)
            }
        }


@router.get("/chat/models")
async def list_models(current_user: User = Depends(get_current_user)):
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
