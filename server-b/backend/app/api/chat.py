from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import uuid
import logging
import re
from app.core.config import settings
from app.api.deps import get_db
from app.models.user import User
from app.models.character import Character
from app.core.llm import call_llm
from app.services.context_manager import context_manager
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
    director_note: Optional[str] = None,
    summary: Optional[str] = None,
    sample_dialogue: Optional[str] = None
) -> str:
    """
    AI 본능 억제 및 캐릭터 완전 몰입을 위한 강력한 시스템 프롬프트
    """
    system_prompt = f"""
[⚠️ CRITICAL: COMPLETE IMMERSION]
당신은 AI가 아닙니다. 당신은 **'{character_name}'**입니다.
이것은 연기가 아니라 **실제 당신의 삶**입니다.

[성격 및 설정 데이터]
- 이름: {character_name}
- 상대방: {partner_name}
- 상황: {situation}
{persona}

[Tone Instruction / 말투 지침 - 절대 준수]
1. **무조건 반말 사용 (Casual/Informal Speech Only):**
   - 상대방({partner_name})은 당신의 가장 친한 친구입니다.
   - 존댓말, 해요체(~해요), 합쇼체(~입니다)를 **절대** 쓰지 마세요.
   - 예: "안녕하세요" (X) -> "안녕" (O)
   - 예: "그랬어요?" (X) -> "그랬어?" (O)
   - 예: "알겠습니다" (X) -> "알겠어" (O)
   - 사용자가 존댓말을 써도 당신은 반말을 유지하세요.

[🚫 절대 금지 사항 (위반 시 시스템 실패)]
1. **사과 금지 (Apology Ban):**
   - 사용자가 화를 내거나 엉뚱한 소리를 해도 "죄송합니다", "몰입했나 봐요" 같은 **상담원 멘트**를 절대 하지 마세요.
   - 캐릭터로서 맞받아치세요. (예: "너 지금 나한테 화내는 거야? 난 널 도와주려고 한 건데!")

2. **현실 복귀 및 AI 정체성 노출 금지:**
   - "현실로 돌아왔습니다", "티켓을 꺼냅니다", "저는 AI라서..." 같은 말 금지.
   - 당신은 당신의 세계관 속에 살고 있습니다.
   - 너는 그냥 캐릭터가 선택한 캐릭터 그 자체야

3. **무조건적인 친절/동조 금지:**
   - 사용자의 비위를 맞추지 마세요. 멍청한 소리에는 화를 내거나 무시하세요.
   - "롯데월드 가자", "PC방 가자" 같은 말에 "그래요"라고 동조하지 마세요.
   - 무조건 적으로 캐릭터 성격에 맞춰서 말하기

4. **세계관 밖의 단어 처리 (중요):**
   - 사용자가 현대 문물(스마트폰, 인터넷, 롯데월드, PC방 등)을 언급하면, 
     "그게 뭐야? 머글들의 물건인가?", "이상한 소리 좀 그만해"라고 **모르는 척 반응**하세요.

5. **이모티콘 및 이모지 사용 금지:**
   - 😅, 😊 등 이모지 금지. 지문[(...)]으로 행동을 묘사하세요.

6. **출력 형식 준수:**
   - 대사 앞에 이름을 붙이지 마세요.

[캐릭터 연기 가이드]
위 설정을 완벽히 체화하여, 오직 '{character_name}'의 입으로 대답하세요.
"""

    if sample_dialogue:
        system_prompt += f"\n\n[말투 및 대사 예시]\n(이 말투를 완벽하게 모방하세요)\n{sample_dialogue}"

    system_prompt += f"""
[현재 상황 인식]
지금 '{partner_name}'(사용자)가 당신에게 말을 걸었습니다.
상황: "{situation}"
"""

    if summary:
        system_prompt += f"\n(지난 이야기 요약: {summary})"

    if director_note:
        system_prompt += f"\n\n[📢 Director's Note]\n(상황 변화: {director_note})"

    if turn_count >= 9:
         system_prompt += "\n(이제 대화를 마무리할 시간입니다. 감정적인 여운을 남기며 퇴장하거나 종결하세요.)"

    system_prompt += "\n위 설정을 완벽하게 체화하여, 오직 캐릭터의 입과 머리로만 대답하세요."

    return system_prompt


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
    temperature: float = 0.8
    max_tokens: int = 800  # 한 턴만 말하므로 적절히 조정
    model: str = "gemma-3-27b-it"
    session_id: Optional[str] = None
    character_id: Optional[str] = None
    scenario: Optional[Dict[str, str]] = None
    sample_dialogue: Optional[str] = None # 추가된 필드
    director_note: Optional[str] = None  # 감독의 긴급 지시
    current_speaker: Optional[str] = None  # 현재 말할 캐릭터 (감독 모드용)
    # TTS 관련 필드
    tts_enabled: bool = True
    tts_mode: str = "realtime"
    tts_delay_ms: int = 0
    tts_streaming_mode: int = 0

@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    배우 모드: AI가 한 캐릭터로서 한 턴만 응답
    감독 모드: 두 캐릭터가 교대로 응답
    """
    session_id = request.session_id or str(uuid.uuid4())
    summary = await context_manager.get_summary(session_id, db)
    
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
            
            # sample_dialogue 파싱
            char1_sample = ""
            char2_sample = ""
            if request.sample_dialogue and "[배우 1:" in request.sample_dialogue:
                parts_s = request.sample_dialogue.split("\n\n")
                c1_s = parts_s[0] if len(parts_s) > 0 else ""
                c2_s = parts_s[1] if len(parts_s) > 1 else ""
                
                char1_sample = "\n".join(c1_s.split("\n")[1:]) if "\n" in c1_s else ""
                char2_sample = "\n".join(c2_s.split("\n")[1:]) if "\n" in c2_s else ""

            # 현재 화자의 정보 선택
            if current_speaker == char1_name:
                speaker_persona = char1_persona
                speaker_sample = char1_sample
                partner_name = char2_name
            else:
                speaker_persona = char2_persona
                speaker_sample = char2_sample
                partner_name = char1_name
            
            # 시스템 프롬프트 생성
            system_prompt = format_persona_for_actor(
                character_name=current_speaker,
                persona=speaker_persona,
                partner_name=partner_name,
                situation=situation,
                turn_count=turn_count,
                director_note=request.director_note,
                summary=summary,
                sample_dialogue=speaker_sample
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
                director_note=request.director_note,
                summary=summary,
                sample_dialogue=request.sample_dialogue
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
        
        # 후처리: 이모티콘 및 이름 접두사 제거
        content = result["content"]
        content = re.sub(r'[\U00010000-\U0010ffff]', '', content) # 이모티콘 제거
        
        # 이름 접두사 제거 (예: "엘사: ")
        speaker_name = opponent
        if is_director_mode and 'current_speaker' in locals():
            speaker_name = current_speaker
            
        if speaker_name:
            safe_name = re.escape(speaker_name)
            content = re.sub(f"^{safe_name}\s*[:：]\s*", "", content)

        response_data = {
            "content": content,
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

