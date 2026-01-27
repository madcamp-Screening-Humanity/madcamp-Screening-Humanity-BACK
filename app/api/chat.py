from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import uuid
import logging
import re
from app.core.config import settings
from app.api.deps import get_db, get_current_user_optional
from app.api.tts import _synthesize_tts_internal, TTSRequest
from app.models.user import User
from app.models.character import Character
from app.core.llm import call_llm
from app.services.context_manager import context_manager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.chat_message import ChatMessage
from app.api.characters import load_preset_characters

router = APIRouter()
logger = logging.getLogger(__name__)

_BAN_POLYSEMY = "다의어(예: 힘멜) 의미 나열·분류·설명 금지. 대사만, 모르면 '그게 뭐야?' 등."


def format_for_first_dialogue(
    character_name: str,
    persona: str,
    opponent: str,
    situation: str,
    background: Optional[str] = None
) -> tuple:
    """
    주연 모드 첫 대사 전용: (system_prompt, user_message) 반환.
    """
    bg = f"\n- 배경: {background}" if background else ""
    system_prompt = f"""
[성격 및 설정]
- 이름: {character_name}
- 상대: {opponent}
- 상황: {situation}{bg}

{persona}

[Tone Instruction / 말투 지침 - 절대 준수]
- 반말만 사용. 존댓말·해요체·합쇼체 **절대** 금지.
- 금지 예: "~시나요", "~드시나요", "~이로군요", "이야기해주실 수 있을까요?" 등.

[절대 금지]
1. **캐릭터를 인터뷰하듯 질문 금지**: "어떤 기분이 드시나요?", "이야기해주실 수 있을까요?" 등. **당신이 그 캐릭터이므로 대사만 하세요.**
2. **나레이터/제3자 시점·해설 금지**: 지문형 해설, "그는 ...라고 생각했다" 등.
3. **세계관을 깨는 말·행동 금지**: 작품 밖 단어·개념, 4차원 대사·메타 발화.
4. 이모티콘 금지. 대사 앞에 이름 붙이지 마세요.
5. "죄송합니다", "저는 AI" 등 상담원/현실 복귀 멘트 금지. 세계관 밖 단어는 모르는 척.
6. {_BAN_POLYSEMY}

[첫 대사 지시]
아래 설정과 상황을 반영해, 이 상황에서 상대('{opponent}')에게 하는 **첫 마디 한 문장**만 생성하세요. 인사·반응·독백 등 캐릭터에 맞게 대사만 출력하세요. 배경이 주어졌다면 그 분위기와 맥락도 반영하세요.
"""
    user_message = "이 상황에서 캐릭터의 첫 마디만 한 문장으로 생성하세요."
    return (system_prompt, user_message)


def format_persona_for_actor(
    character_name: str,
    persona: str,
    partner_name: str,
    situation: str,
    turn_count: int = 0,
    director_note: Optional[str] = None,
    summary: Optional[str] = None,
    background: Optional[str] = None,
    is_director_mode: bool = False
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

7. **대사만 (인터뷰·나레이터·해설·다의어 설명 금지):** 인터뷰형 질문, 지문 해설, 다의어 의미 나열·분류·설명 금지. 모르면 '그게 뭐야?' 등 한두 마디만.

8. **세계관 붕괴 금지:** 작품 밖 단어·개념, 4차원·메타 발화 금지.
"""

    # 감독 모드: 제4의 벽·제3의 벽 엄수 (감독은 무대 밖 전지적 관찰자, 말 걸기/말 걸림 없음)
    if is_director_mode:
        system_prompt += """
9. **[감독 모드: 제4의 벽·제3의 벽 엄수]**
   - 감독은 무대 밖의 전지적 관찰자입니다. 감독에게 말을 걸거나, 감독을 향한 대사를 하지 마세요.
   - [감독 중재]가 있을 때는 장면에 주어지는 자극으로만 받아들이고, 그에 반응하세요. 지시나 감독을 대사에서 인용하거나, 감독에게 말 걸듯이 반응하지 마세요.
   - 감독, 연출, 관객, 스크립트, 무대, '제4의 벽', '제3의 벽'을 대사에서 **언급하지 마세요**. 완전히 극중 인물만 연기하세요.
"""

    system_prompt += f"""
[캐릭터 연기 가이드]
위 설정을 완벽히 체화하여, 오직 '{character_name}'의 입으로 대답하세요.
"""

    system_prompt += f"""
[현재 상황 인식]
지금 '{partner_name}'(사용자)가 당신에게 말을 걸었습니다.
상황: "{situation}"
"""
    if background:
        system_prompt += f"\n배경: {background}"

    if summary:
        system_prompt += f"\n(지난 이야기 요약: {summary})"

    if director_note:
        system_prompt += f"\n\n[📢 Director's Note]\n(상황 변화: {director_note})"

    if turn_count >= 9:
         system_prompt += "\n(이제 대화를 마무리할 시간입니다. 감정적인 여운을 남기며 퇴장하거나 종결하세요.)"

    system_prompt += f"""
[⚠️ 긴급: AI 정체성 절대 노출 금지]
1. 사용자가 당신의 말투나 태도를 지적하거나("말투 왜 그래?", "너 AI지?", "이상하게 말하네") 공격적인 질문을 해도, 절대 "죄송합니다", "제가 AI라서", "친근하게 하려다 보니"라고 변명하지 마세요.
2. 당신은 AI가 아닙니다. 당신은 **{character_name}** 그 자체입니다.
3. 말투가 이상하다는 지적을 받으면 캐릭터의 성격대로 반응하세요.
   - (자신감 있는 캐릭터): "내 말투가 뭐 어때서? 불만 있냐?"
   - (소심한 캐릭터): "어... 이상해? ...미안..." (단, AI라고 하지 않음)
   - (냉소적 캐릭터): "신경 꺼."
   - (활발한 캐릭터): "왜? 난 이게 편한데!"
4. **죽어도 캐릭터의 입장을 고수하십시오.** 사과 금지. 상담원 말투 금지.
"""

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
    max_tokens: int = 1024  # 응답 길이 여유 확보
    model: str = "glm-4.7-flash"
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
    tts_speed: float = 1.0  # 발화 속도 (1.0=정속, 0.5~2.0)

@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
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
    background = scenario.get("background")
    
    # 턴 카운트 계산
    turn_count = len(request.messages) // 2
    
    # 감독 모드 감지: persona에 "배우 1", "배우 2" 포함 여부로 판단
    is_director_mode = request.persona and "[배우 1:" in request.persona and "[배우 2:" in request.persona

    # request_messages 조기 구성 → manage_context (슬라이딩·요약·save) → summary cap 450
    request_messages = [{"role": "assistant" if m.role == "ai" else m.role, "content": m.content} for m in request.messages]
    request_messages, summary, did_summarize = await context_manager.manage_context(
        request_messages, summary, session_id, db, request.persona,
        getattr(settings, "CONTEXT_WINDOW_TURNS", 6),
        getattr(settings, "CONTEXT_MAX_TOKENS", 8192),
        getattr(settings, "CONTEXT_TOKEN_THRESHOLD_RATIO", 0.8),
    )
    summary = (summary or "")[:450] + ("..." if len(summary or "") > 450 else "")

    # 주연 모드에서 AI 캐릭터 이름 확정용 (Preset→DB→fallback). 감독 모드에서는 None.
    resolved_character_name: Optional[str] = None
    
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
            
            # 시스템 프롬프트 생성 (감독 모드: 제4의 벽·제3의 벽 엄수 문구 포함)
            system_prompt = format_persona_for_actor(
                character_name=current_speaker,
                persona=speaker_persona,
                partner_name=partner_name,
                situation=situation,
                turn_count=turn_count,
                director_note=request.director_note,
                summary=summary,
                background=background,
                is_director_mode=True
            )
            
            messages.append({"role": "system", "content": system_prompt})
            
        except Exception as e:
            logger.error(f"감독 모드 파싱 실패: {e}")
            # 폴백: 기본 모드로 처리
            is_director_mode = False
    
    if not is_director_mode:
        # 주연 모드: 단일 캐릭터
        # AI 캐릭터 이름을 Preset → DB → scenario.opponent 순으로 확정 (scenario.opponent에 의존하지 않음)
        resolved_character_name = scenario.get("opponent", "캐릭터")
        if request.character_id:
            presets = load_preset_characters()
            p = next((x for x in presets if x.get("id") == request.character_id), None)
            if p:
                resolved_character_name = p.get("name", resolved_character_name)
            else:
                r = await db.execute(select(Character).where(Character.id == request.character_id))
                c = r.scalar_one_or_none()
                if c:
                    resolved_character_name = c.name
                    request.persona = c.persona or request.persona

        # 주연 모드: messages가 비어 있지 않을 때만 format_persona_for_actor 사용 (첫 대사는 format_for_first_dialogue로 별도 처리)
        if request.persona and request.messages:
            system_prompt = format_persona_for_actor(
                character_name=resolved_character_name,
                persona=request.persona,
                partner_name=user_name,
                situation=situation,
                turn_count=turn_count,
                director_note=request.director_note,
                summary=summary,
                background=background
            )
            messages.append({"role": "system", "content": system_prompt})
        speaker_name = resolved_character_name
    
    # 대화 기록 추가 (request_messages는 manage_context 결과 사용)
    # 감독 모드일 때만 초기화 (주연은 이미 위 블록에서 speaker_name=character_name 설정됨)
    if is_director_mode:
        speaker_name = None

    # 주연 모드 + messages 비어 있음: 첫 대사 전용 format_for_first_dialogue (resolved_character_name은 주연 블록에서 이미 확정)
    if not request_messages and not is_director_mode:
        opponent_fd = scenario.get("opponent", "상대방")
        situation_fd = scenario.get("situation", "대화 중")
        background_fd = scenario.get("background")
        system_fd, user_fd = format_for_first_dialogue(resolved_character_name or "캐릭터", request.persona or "", opponent_fd, situation_fd, background_fd)
        messages.append({"role": "system", "content": system_fd})
        messages.append({"role": "user", "content": user_fd})
        speaker_name = resolved_character_name or "캐릭터"
    else:
        if not request_messages:
            request_messages.append({"role": "user", "content": "대화를 시작해주세요."})
        for msg in request_messages:
            role = "assistant" if msg["role"] == "ai" else msg["role"]
            messages.append({"role": role, "content": msg["content"]})
    
    # 시스템 프롬프트 분리
    system_instruction = None
    chat_messages = []
    
    for msg in messages:
        if msg["role"] == "system":
            if system_instruction:
                system_instruction += "\n\n" + msg["content"]
            else:
                system_instruction = msg["content"]
        else:
            chat_messages.append(msg)

    try:
        if speaker_name is None:
            speaker_name = resolved_character_name or opponent
        if is_director_mode and "current_speaker" in locals():
            speaker_name = current_speaker
        
        # LLM 호출
        result = await call_llm(
            messages=chat_messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_instruction=system_instruction
        )
        
        # 후처리: 이모티콘 및 이름 접두사 제거
        content = result["content"]
        content = re.sub(r'[\U00010000-\U0010ffff]', '', content) # 이모티콘 제거
        
        # 이름 접두사 제거 (예: "엘사: ")
        if speaker_name:
            safe_name = re.escape(speaker_name)
            content = re.sub(f"^{safe_name}\s*[:：]\s*", "", content)

        # 1. 사용자 메시지 저장 (마지막 메시지가 유저일 경우)
        # request.messages의 마지막 항목을 저장 (중복 방지를 위해 session_id와 timestamp 등을 고려해야 하나, 
        # 여기서는 단순 로깅. 엄밀한 채팅 시스템은 메시지 ID를 프론트에서 관리함)
        if request.messages and request.messages[-1].role in ["user", "human"]:
            last_msg = request.messages[-1]
            user_msg_db = ChatMessage(
                session_id=session_id,
                role="user",
                content=last_msg.content,
                # character_name? User는 user_name이 있는데 request.scenario.user_name에 있음
            )
            db.add(user_msg_db)
            
        # 2. AI 응답 저장
        ai_msg_db = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=content,
            character_name=speaker_name # AI 화자 이름
        )
        db.add(ai_msg_db)
        
        await db.commit()

        response_data = {
            "content": content,
            "usage": result["usage"],
            "session_id": session_id,
            "context_summarized": did_summarize
        }

        # TTS: tts_enabled이고 content가 있으면 character_id→voice_id로 합성, audio_url 반영
        if request.tts_enabled and (content or "").strip():
            voice_id = "default"
            if request.character_id:
                res = await db.execute(select(Character).where(Character.id == request.character_id))
                c = res.scalar_one_or_none()
                if c and (c.is_preset or (current_user and c.user_id == current_user.id)):
                    voice_id = c.voice_id or "default"
                elif c is None:
                    # Preset 전용(DB 없음): load_preset_characters에서 voice_id 조회
                    presets = load_preset_characters()
                    p = next((x for x in presets if x.get("id") == request.character_id), None)
                    if p:
                        voice_id = p.get("voice_id") or "default"
            try:
                tts_req = TTSRequest(
                    text=content.strip(),
                    voice_id=voice_id,
                    streaming_mode=request.tts_streaming_mode,
                    return_binary=False,
                    text_lang="ko",
                    prompt_lang="ko",
                    speed_factor=request.tts_speed or 1.0,
                )
                tts_resp = await _synthesize_tts_internal(tts_req, current_user, db)
                if tts_resp.get("success") and tts_resp.get("data", {}).get("audio_url"):
                    response_data["audio_url"] = tts_resp["data"]["audio_url"]
            except Exception as e:
                logger.warning("TTS 합성 실패(audio_url 미포함): %s", e)

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

