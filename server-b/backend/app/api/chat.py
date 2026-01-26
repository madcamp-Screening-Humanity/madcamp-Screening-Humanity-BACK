from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import uuid
import logging
from app.core.config import settings
from app.api.deps import get_db
from app.models.user import User
from app.models.generation import Character
from app.core.llm import call_llm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger(__name__)

def format_persona_for_roleplay(persona: str, character_name: Optional[str] = None, scenario: Optional[Dict[str, str]] = None) -> str:
    """
    페르소나와 시나리오 정보를 결합하여 시스템 프롬프트 생성
    """
    parts = []
    
    # 기본 명령
    parts.append("당신은 지금부터 드라마/영화를 촬영하는 배우이며, 주어진 배역과 상황에 완전히 몰입해야 합니다.")
    
    # 캐릭터 이름 및 성격
    if character_name:
        parts.append(f"이름: {character_name}")
    
    parts.append(f"\n[성격 및 페르소나]\n{persona}")
    
    # 시나리오 정보 (강조)
    if scenario:
        parts.append("\n[현재 촬영 중인 장면 설정]")
        if scenario.get("situation"):
            parts.append(f"- 핵심 줄거리: {scenario['situation']}")
        if scenario.get("opponent"):
            parts.append(f"- 상대방(유저): {scenario['opponent']}")
        if scenario.get("background") and scenario.get("background") != "none":
            parts.append(f"- 장소/배경: {scenario['background']}")
    
    # 역할극 지시사항
    parts.append("\n[연기 지침]")
    parts.append("1. 위 설정된 줄거리와 상황을 완벽하게 이해하고 그 안에서 행동하세요.")
    parts.append("2. 상대방(유저)의 말에 반응하되, 당신의 캐릭터 성격과 현재 상황에서의 목적을 잃지 마세요.")
    parts.append("3. 첫 마디는 현재 설정된 줄거리의 시작점에 어울리는 대사로 시작하세요.")
    parts.append("4. 지문([...])을 사용하여 동작이나 표정, 주변 환경을 묘사할 수 있습니다.")
    parts.append("5. 답변은 반드시 한국어로 작성하세요.")
    
    return "\n".join(parts)


async def get_character_by_id(
    character_id: str,
    user_id: str,
    db: AsyncSession
) -> Optional[Character]:
    """캐릭터 정보 조회 (사전설정 또는 사용자 소유)"""
    try:
        result = await db.execute(
            select(Character).where(Character.id == character_id)
        )
        character = result.scalar_one_or_none()
        
        if character:
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
    scenario: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    model: str = "gemma-3-27b-it"
    session_id: Optional[str] = None
    character_id: Optional[str] = None
    scenario: Optional[Dict[str, str]] = None
    # TTS 관련 필드
    tts_enabled: bool = True
    tts_mode: str = "realtime"
    tts_delay_ms: int = 0
    tts_streaming_mode: int = 0

@router.post("/chat")
async def chat(request: ChatRequest):
    """
<<<<<<< HEAD
    Proxy chat request to Server A (LLM Service).
    Injects persona and scenario into system prompt.
    """
    # System Prompt Injection
    system_content = []
    if request.persona:
        system_content.append(f"당신의 페르소나:\n{request.persona}")
    if request.scenario:
        system_content.append(f"현재 상황/줄거리:\n{request.scenario}")
    
    if system_content:
        full_system_prompt = "\n\n".join(system_content)
        # Check if first message is already system
        if request.messages and request.messages[0].role == "system":
            request.messages[0].content = f"{full_system_prompt}\n\n{request.messages[0].content}"
        else:
            request.messages.insert(0, Message(role="system", content=full_system_prompt))

    # In real deployment, this URL points to Server A
    # In real deployment, this URL points to Server A
    llm_service_url = f"{settings.GPU_SERVER_URL.replace('8001', '8002')}/chat" # Assuming port mapping logic or config
=======
    Ollama 서비스를 사용하여 실제 LLM API를 호출합니다.
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    messages = []
    
    # 시스템 페르소나 설정
    if request.persona:
        formatted_persona = format_persona_for_roleplay(
            persona=request.persona,
            character_name=request.scenario.get("opponent") if request.scenario else None,
            scenario=request.scenario
        )
        messages.append({"role": "system", "content": formatted_persona})
    
    # 대화 기록 추가
    request_messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    # 첫 대화 시작 시 AI가 먼저 말하도록 유도
    if not request_messages:
        request_messages.append({"role": "user", "content": "연극을 시작해줘. 너의 첫 마디로 시작해."})
    
    # 역할 이름 변환 (ai -> assistant)
    for msg in request_messages:
        role = "assistant" if msg["role"] == "ai" else msg["role"]
        messages.append({"role": role, "content": msg["content"]})
>>>>>>> 6fe448cb8225155864a351628994e82378c14e33
    
    try:
        # LLM 호출
        result = await call_llm(
            messages=messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        response_data = {
            "content": result["content"],
            "usage": result["usage"],
            "session_id": session_id,
            "context_summarized": False
        }
        
        return {
            "success": True,
            "data": response_data
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"LLM service error: {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail=f"LLM 서비스 에러: {str(e)}")
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        # 연결 실패 시 Mock 응답 (사용자 요청 반영)
        return {
            "success": True,
            "data": {
                "content": "[테스트 모드] 현재 AI 서버 연결이 원활하지 않아 준비된 대사를 출력합니다. 상황 설정을 확인해 주세요!",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                "session_id": session_id,
                "context_summarized": False
            }
        }
