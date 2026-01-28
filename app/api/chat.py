from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import uuid
import logging
import re
import json
from app.core.config import settings
from app.api.deps import get_db, get_current_user_optional
from app.api.tts import _synthesize_tts_internal, TTSRequest
from app.models.user import User
from app.models.character import Character
from app.core.llm import call_llm, call_llm_stream
from app.services.context_manager import context_manager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.chat_message import ChatMessage
from app.api.characters import load_preset_characters

router = APIRouter()
logger = logging.getLogger(__name__)

_BAN_POLYSEMY = "다의어(예: 힘멜) 의미 나열·분류·설명 금지. 대사만, 모르면 '그게 뭐야?' 등."

def truncate_to_sentence(text: str, max_len: int) -> str:
    """
    문장 종결형으로 깔끔하게 자르는 유틸 함수.
    max_len 이내에서 가장 마지막 문장 종결 위치까지만 반환.
    종결 패턴: . ? ! 。및 한국어 종결 어미(다, 요, 음, 죠, 네, 나, 까, 지, 아, 야)
    """
    if not text or len(text) <= max_len:
        return text
    
    # max_len까지 자른 뒤, 마지막 종결 위치 탐색
    truncated = text[:max_len]
    
    # 종결 문자/어미 패턴 (뒤에서부터 탐색)
    ending_chars = '.?!。'
    korean_endings = ('다.', '요.', '음.', '죠.', '네.', '나.', '까.', '지.', '아.', '야.',
                      '다', '요', '음', '죠', '네', '까', '지')
    
    # 1. 마지막 마침표/물음표/느낌표 찾기
    last_punct = -1
    for i in range(len(truncated) - 1, -1, -1):
        if truncated[i] in ending_chars:
            last_punct = i
            break
    
    # 2. 한국어 종결 어미 찾기 (마침표 없이 끝나는 경우)
    if last_punct == -1:
        for ending in korean_endings:
            pos = truncated.rfind(ending)
            if pos > last_punct:
                last_punct = pos + len(ending) - 1
    
    # 종결 위치가 있으면 거기까지, 없으면 원래 max_len에서 적당히 자름
    if last_punct > max_len // 3:  # 너무 짧아지면 그냥 자르기
        return truncated[:last_punct + 1]
    else:
        # 공백에서 자르기 (단어 중간 끊김 방지)
        last_space = truncated.rfind(' ')
        if last_space > max_len // 2:
            return truncated[:last_space] + "..."
        return truncated + "..."


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
    4k 컨텍스트 최적화: 압축된 시스템 프롬프트 (~1.2k 토큰 목표)
    핵심 페르소나 보존, 중복 제거, 짧은 규칙 사용
    """
    # 기본 규칙 (압축)
    system_prompt = f"""[캐릭터] 당신={character_name}. AI 아님. 이 삶이 현실.
[상대] {partner_name} [상황] {situation}
{persona}

[말투] 반말만. 존댓말/해요체 절대 금지. (안녕하세요→안녕, 그랬어요?→그랬어?)

[금지]
• 사과/상담원 멘트 ("죄송","몰입했나봐요") → 캐릭터로 맞받아치기
• AI 정체 노출 ("저는 AI","현실로") → 세계관 속 인물로 반응
• 무조건 동조 금지. 멍청한 소리엔 화/무시. 성격대로 반응
• 세계관 밖 단어(스마트폰,PC방 등) → "그게 뭐야?" 모르는 척
• 이모지 금지. 이름 접두사 금지. 인터뷰/해설/다의어 설명 금지"""

    if is_director_mode:
        system_prompt += """
• [감독모드] 감독에게 말걸기/언급 금지. 극중 인물만 연기"""

    # 상황 정보 추가 (간결하게)
    if background:
        system_prompt += f"\n[배경] {background}"
    if summary:
        system_prompt += f"\n[이전] {summary}"
    if director_note:
        system_prompt += f"\n[감독지시] {director_note}"
    if turn_count >= 9:
        system_prompt += "\n(대화 마무리 시간. 여운 남기며 종결.)"

    system_prompt += f"\n\n→ 오직 {character_name}의 입으로만 대답."

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
    model: str = "gemma-3-27b"
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
    summary = truncate_to_sentence(summary or "", 250)  # 4k 컨텍스트: 요약은 250자 이내로 문장 종결

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


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    SSE 스트리밍 채팅 엔드포인트.
    Gemini 응답을 실시간으로 청크 단위로 전송하여 체감 응답 속도 향상.
    Content-Type: text/event-stream
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    # 시나리오 정보 추출 (기존 /chat 로직과 동일)
    scenario = request.scenario or {}
    opponent = scenario.get("opponent", "상대방")
    situation = scenario.get("situation", "대화 중")
    user_name = scenario.get("user_name", "사용자")
    background = scenario.get("background")
    
    # 턴 카운트
    turn_count = len(request.messages) // 2
    
    # 메시지 구성
    messages = []
    
    # 시스템 프롬프트 생성 (간소화 버전)
    if request.persona:
        # resolved_character_name 추출
        resolved_character_name = opponent
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

        system_prompt = format_persona_for_actor(
            character_name=resolved_character_name,
            persona=request.persona,
            partner_name=user_name,
            situation=situation,
            turn_count=turn_count,
            director_note=request.director_note,
            summary=None,
            background=background
        )
        messages.append({"role": "system", "content": system_prompt})
    
    # 대화 기록 추가
    for msg in request.messages:
        role = "assistant" if msg.role == "ai" else msg.role
        messages.append({"role": role, "content": msg.content})
    
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

    async def generate_sse():
        """
        SSE 이벤트 생성기.
        각 청크를 data: {...} 형식으로 전송.
        """
        full_content = ""
        try:
            async for chunk in call_llm_stream(
                messages=chat_messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                system_instruction=system_instruction
            ):
                full_content += chunk
                # SSE 형식: data: {...}\n\n
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
            
            # 완료 신호 전송
            yield f"data: {json.dumps({'content': '', 'done': True, 'full_content': full_content, 'session_id': session_id})}\n\n"
            
            # DB에 메시지 저장 (비동기 컨텍스트 외부에서 처리 필요 → 로그만 남김)
            logger.info(f"스트리밍 완료: session={session_id}, length={len(full_content)}")
            
        except Exception as e:
            logger.error(f"스트리밍 오류: {e}")
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
        }
    )
