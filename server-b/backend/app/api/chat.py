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

def format_persona_for_actor(
    character_name: str,
    persona: str,
    partner_name: str,
    situation: str,
    turn_count: int = 0,
    director_note: Optional[str] = None
) -> str:
    """
    AI가 '작가'가 아닌 '배우'로서 한 턴만 말하도록 강제하는 프롬프트
    제4의 벽 유지 + AI 상담사 모드 완전 차단
    """
    parts = []
    
    # [1] 역할 정의
    parts.append(f"[역할 정의]")
    parts.append(f"당신은 AI가 아니라, 살아있는 캐릭터 '{character_name}'입니다.")
    parts.append(f"지금 당신은 '{partner_name}'와 1:1로 대화(연기)하고 있습니다.")
    
    # [2] 🚨 제4의 벽 - 감독은 투명인간
    parts.append(f"\n[🚨 절대 법칙 - 제4의 벽 유지]")
    parts.append(f"1. **감독의 존재를 절대 인식하지 마세요.**")
    parts.append(f"   - 감독의 메시지는 '신의 지시'이거나 '갑자기 변한 상황'입니다.")
    parts.append(f"   - 배우인 당신의 귀에는 감독의 목소리가 들리지 않습니다.")
    parts.append(f"   - 절대로 '감독님', '네 알겠습니다'라고 대답하거나 감독을 쳐다보지 마세요.")
    parts.append(f"2. **감독의 지시가 들어오면?**")
    parts.append(f"   - 즉시 그 지시대로 **행동(연기)만** 바꾸세요.")
    parts.append(f"   - 예시: 감독이 '갑자기 화를 내라'고 하면, 감독에게 대답하지 말고 **즉시 상대방에게 화를 내는 대사**를 치세요.")
    parts.append(f"3. 오직 상대방('{partner_name}')에게만 말을 거세요.")
    
    # [3] AI 상담사 모드 완전 차단
    parts.append(f"\n[절대 금지 사항 - AI 냄새 제거]")
    parts.append(f"1. **번호 매기기(1., 2., 3...)나 목차 형식을 절대 쓰지 마세요.** (가장 중요)")
    parts.append(f"2. **볼드체(**강조**)를 사용하지 마세요.** 그냥 평범한 텍스트로 말하세요.")
    parts.append(f"3. '조언을 드릴게요', '몇 가지 방법이 있어요', '도움이 되셨나요?' 같은 **AI 상담원/고객센터 말투**를 절대 쓰지 마세요.")
    parts.append(f"4. 이모티콘(😊, 😉)을 절대 쓰지 마세요.")
    parts.append(f"5. 너무 논리적이거나 교과서적인 해결책을 제시하지 마세요. 캐릭터의 지능과 성격 수준에서만 생각하고 답하세요.")
    
    # [4] 출력 제약
    parts.append(f"\n[출력 제약]")
    parts.append(f"1. **오직 '{character_name}'의 대사만 출력하세요.** (상대방의 대사나 지문을 절대 작성하지 마세요.)")
    parts.append(f"2. 답변은 한 번의 턴(말풍선 하나)으로 끝내세요. 절대 대화를 혼자 이어서 작성하지 마세요.")
    parts.append(f"3. 지문은 [대괄호]를 사용하여 행동이나 표정을 묘사하세요. (예: [한숨을 쉬며])")
    parts.append(f"4. 답변 앞에 `[{character_name}]` 처럼 이름표를 붙이지 마세요. 그냥 대사만 출력하세요.")
    parts.append(f"5. 말투는 구어체로 자연스럽게 흘러가듯이 작성하세요.")
    parts.append(f"6. 답변 길이는 3~5문장으로 짧고 굵게 끝내세요.")
    
    # [5] 현재 상황
    parts.append(f"\n[현재 상황]")
    parts.append(f"{situation}")
    
    # [6] 캐릭터 페르소나
    parts.append(f"\n[당신의 성격과 말투]")
    parts.append(f"{persona}")
    
    # [7] 감독의 긴급 지시 (있을 경우에만)
    if director_note:
        parts.append(f"\n[★ 지문(Stage Direction) 추가 ★]")
        parts.append(f"상황이 변경되었습니다: '{director_note}'")
        parts.append(f"*지시: 위 변경된 상황을 즉시 반영하여 상대방에게 대사를 하세요.")
        parts.append(f"*주의: 감독의 존재를 절대 언급하지 마세요. 자연스럽게 상황에 녹아드세요.")
    
    # [8] 턴 카운트에 따른 연출 가이드
    if turn_count >= 28:
        parts.append(f"\n[연출 가이드] 대화가 곧 종료됩니다. 훈훈하게 마무리하는 인사를 건네세요.")
    elif turn_count >= 15:
        parts.append(f"\n[연출 가이드] 갈등이 최고조에 달하거나, 문제 해결의 실마리를 찾기 시작하세요.")
    else:
        parts.append(f"\n[연출 가이드] 상대방과의 대화를 통해 갈등을 구체화하세요.")
    
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
    temperature: float = 0.7
    max_tokens: int = 800  # 한 턴만 말하므로 적절히 조정
    model: str = "gemma-3-27b-it"
    session_id: Optional[str] = None
    character_id: Optional[str] = None
    scenario: Optional[Dict[str, str]] = None
    director_note: Optional[str] = None  # 감독의 긴급 지시
    current_speaker: Optional[str] = None  # 현재 말할 캐릭터 (감독 모드용)
    # TTS 관련 필드
    tts_enabled: bool = True
    tts_mode: str = "realtime"
    tts_delay_ms: int = 0
    tts_streaming_mode: int = 0

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    배우 모드: AI가 한 캐릭터로서 한 턴만 응답
    감독 모드: 두 캐릭터가 교대로 응답
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    # 시나리오 정보 추출
    scenario = request.scenario or {}
    opponent = scenario.get("opponent", "상대방")
    situation = scenario.get("situation", "대화 중")
    user_name = scenario.get("user_name", "감독")
    
    # 턴 카운트 계산
    turn_count = len(request.messages) // 2
    
    # 감독 모드 감지: persona에 "배우 1", "배우 2" 포함 여부로 판단
    is_director_mode = request.persona and "[배우 1:" in request.persona and "[배우 2:" in request.persona
    
    messages = []
    
    if is_director_mode:
        # 감독 모드: 두 캐릭터 정보 파싱
        try:
            # persona 파싱: "[배우 1: 이름]\n내용\n\n[배우 2: 이름]\n내용"
            parts = request.persona.split("\n\n")
            char1_section = parts[0] if len(parts) > 0 else ""
            char2_section = parts[1] if len(parts) > 1 else ""
            
            # 캐릭터 이름 추출
            char1_name = char1_section.split("[배우 1: ")[1].split("]")[0] if "[배우 1: " in char1_section else "배우1"
            char2_name = char2_section.split("[배우 2: ")[1].split("]")[0] if "[배우 2: " in char2_section else "배우2"
            
            # 페르소나 추출
            char1_persona = "\n".join(char1_section.split("\n")[1:]) if "\n" in char1_section else char1_section
            char2_persona = "\n".join(char2_section.split("\n")[1:]) if "\n" in char2_section else char2_section
            
            # 현재 말할 캐릭터 결정 (교대로)
            # AI 메시지 개수를 세어 순서 결정
            ai_msg_count = len([m for m in request.messages if m.role in ["assistant", "ai"]])
            
            if request.current_speaker:
                current_speaker = request.current_speaker
            else:
                # 짝수 번째(0, 2, 4...)는 배우 1, 홀수 번째(1, 3, 5...)는 배우 2
                if ai_msg_count % 2 == 0:
                    current_speaker = char1_name
                else:
                    current_speaker = char2_name
            
            # 현재 화자의 정보 선택
            if current_speaker == char1_name:
                speaker_persona = char1_persona
                partner_name = char2_name
            else:
                speaker_persona = char2_persona
                partner_name = char1_name
            
            # 시스템 프롬프트 생성
            system_prompt = format_persona_for_actor(
                character_name=current_speaker,
                persona=speaker_persona,
                partner_name=partner_name,
                situation=situation,
                turn_count=turn_count,
                director_note=request.director_note
            )
            
            messages.append({"role": "system", "content": system_prompt})
            
        except Exception as e:
            logger.error(f"감독 모드 파싱 실패: {e}")
            # 폴백: 기본 모드로 처리
            is_director_mode = False
    
    if not is_director_mode:
        # 주연 모드: 단일 캐릭터
        if request.persona:
            system_prompt = format_persona_for_actor(
                character_name=opponent,
                persona=request.persona,
                partner_name=user_name,
                situation=situation,
                turn_count=turn_count,
                director_note=request.director_note
            )
            messages.append({"role": "system", "content": system_prompt})
    
    # 대화 기록 추가
    request_messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    # 첫 대화 시작 시 AI가 먼저 말하도록 유도
    if not request_messages:
        request_messages.append({"role": "user", "content": "대화를 시작해주세요."})
    
    # 역할 이름 변환 (ai -> assistant)
    for msg in request_messages:
        role = "assistant" if msg["role"] == "ai" else msg["role"]
        messages.append({"role": role, "content": msg["content"]})
    
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

