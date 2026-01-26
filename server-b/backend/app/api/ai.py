from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.core.llm import call_llm
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

class StoryGenerationRequest(BaseModel):
    situation: str = Field(..., description="사용자가 입력한 짧은 상황")
    opponent_name: str = Field(None, description="상대방 캐릭터 이름")
    character_persona: str = Field(None, description="캐릭터 페르소나 설정")

class StoryGenerationResponse(BaseModel):
    plot: str

@router.post("/generate/story", response_model=StoryGenerationResponse)
async def generate_story(
    request: StoryGenerationRequest,
):
    """
    사용자의 상황 입력을 바탕으로 드라마틱한 줄거리 생성
    """
    
    # 페르소나 정보가 있으면 활용, 없으면 기본값
    persona_context = ""
    if request.character_persona:
        persona_context = f"\n\n[주인공 캐릭터 설정]\n{request.character_persona}"
    
    opponent_context = ""
    if request.opponent_name:
        opponent_context = f"\n\n[상대방 캐릭터]\n이름: {request.opponent_name}"

    system_prompt = (
        "당신은 드라마와 영화의 전문 시나리오 작가입니다. "
        "사용자가 제공한 상황과 캐릭터 설정을 바탕으로, 매우 드라마틱하고 구체적인 한 문단의 줄거리를 작성해주세요. "
        "전체적인 분위기는 선택한 상황에 맞추되, 인물들 간의 갈등이나 감정이 잘 드러나도록 풍부하게 묘사하세요. "
        "답변은 한국어로, 줄거리 내용만 제공하세요. 다른 서론이나 부연 설명은 하지 마세요."
    )
    
    user_content = f"상황: {request.situation}{opponent_context}{persona_context}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    try:
        result = await call_llm(messages, temperature=0.8, max_tokens=1000)
        return {
            "plot": result["content"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"줄거리 생성 실패: {str(e)}"
        )

class CharacterGenerationRequest(BaseModel):
    name: str = Field(..., description="캐릭터 이름")
    category: Optional[str] = Field(None, description="카테고리")
    source_work: Optional[str] = Field(None, description="작품명 (출처)")
    description: str = Field("", description="캐릭터 컨셉/설명")
    worldview: Optional[str] = Field(None, description="세계관")

class CharacterGenerationResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

@router.post("/generate/character-details", response_model=CharacterGenerationResponse)
async def generate_character_details(
    request: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    이름, 카테고리, 작품명을 바탕으로 캐릭터의 상세 설정을 자동 생성 (JSON)
    Google Generative AI SDK (Gemini) 사용
    """
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    import os
    import json
    import time
    
    # 백엔드 환경변수에서 API Key 로드
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # 개발 환경 편의를 위해 프론트엔드 키도 확인해봄 (권장되지는 않음)
        api_key = os.getenv("NEXT_PUBLIC_GEMINI_API_KEY")
        
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버에 GOOGLE_API_KEY가 설정되지 않았습니다."
        )

    try:
        genai.configure(api_key=api_key)
        
        system_instruction = (
            "당신은 창의적인 캐릭터 설정 전문가입니다. "
            "사용자가 제공한 정보를 바탕으로 캐릭터의 상세 설정을 한국어로 작성하여 JSON 형식으로 응답해주세요. "
            "특히 '작품명'이 제공되면 해당 작품의 '이름'을 가진 캐릭터 정보를 정확하게 찾아서 채워주세요. (없는 작품이면 창작해주세요)\n\n"
            "## 요구사항\n"
            "다음 JSON 스키마를 정확히 따라주세요. 모든 필드는 필수입니다.\n"
            "빈칸이 없도록 내용을 풍부하게 채워주세요. 작품의 고증을 철저히 지켜주세요.\n"
            "{\n"
            "  \"name\": \"캐릭터 이름\",\n"
            "  \"gender\": \"성별\",\n"
            "  \"species\": \"종족\",\n"
            "  \"age\": \"나이 (예: 14세)\",\n"
            "  \"height\": \"키 (예: 148cm)\",\n"
            "  \"job\": \"직업\",\n"
            "  \"worldview\": \"세계관 (예: 해리포터 세계관)\",\n"
            "  \"personality\": \"성격 (콤마로 구분된 특성들 10개 이상 나열)\",\n"
            "  \"appearance\": \"외모 (머리, 눈, 체형, 복장 등 상세 묘사)\",\n"
            "  \"description\": \"설명 (캐릭터의 배경 스토리와 현재 상황 3-5문장)\",\n"
            "  \"likes\": [\"좋아하는 것 1\", \"좋아하는 것 2\", ...],\n"
            "  \"dislikes\": [\"싫어하는 것 1\", \"싫어하는 것 2\", ...],\n"
            "  \"speech_style\": \"말투 (구체적인 어조, 어미, 특징 상세 설명)\",\n"
            "  \"thoughts\": \"생각 (속마음 대사 3개 이상)\",\n"
            "  \"features\": \"특징 (행동 패턴, 독특한 습관 등)\",\n"
            "  \"habits\": \"말버릇 (자주 쓰는 감탄사 등)\",\n"
            "  \"guidelines\": \"가이드라인 (롤플레이 시 주의할 점 3-5항목)\"\n"
            "}\n"
            "응답은 오직 JSON 형식이어야 합니다."
        )

        # 모델 초기화
        model_name = os.getenv("GOOGLE_API_MODEL", "gemini-1.5-flash")
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        
        # 안전 설정 (기본값: 무검열 BLOCK_NONE)
        # 환경변수로 조절 가능: BLOCK_NONE, BLOCK_ONLY_HIGH, BLOCK_MEDIUM_AND_ABOVE, BLOCK_LOW_AND_ABOVE
        safety_threshold = os.getenv("GOOGLE_SAFETY_THRESHOLD", "BLOCK_NONE")
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": safety_threshold},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": safety_threshold},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": safety_threshold},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": safety_threshold},
        ]

        user_input = f"이름: {request.name}\n카테고리: {request.category or '기타'}\n작품명: {request.source_work or '창작'}\n컨셉: {request.description}"
        if request.worldview:
            user_input += f"\n세계관: {request.worldview}"
            
        start_time = time.time()
        
        # SDK 비동기 호출
        response = await model.generate_content_async(
            user_input,
            generation_config={
                "temperature": 0.8,
                "max_output_tokens": 4000,
                "response_mime_type": "application/json", # JSON 강제
            },
            safety_settings=safety_settings
        )
        
        elapsed = time.time() - start_time
        print(f"[Gemini API] 생성 완료 ({elapsed:.2f}s)")

        # JSON 파싱
        # response_mime_type="application/json"을 썼으므로 response.text는 JSON 문자열임
        try:
            details = json.loads(response.text)
        except json.JSONDecodeError:
            # 혹시 모를 마크다운 처리 백업
            content = response.text
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            elif content.startswith("```"):
                content = content.replace("```", "")
            details = json.loads(content.strip())
        
        return {
            "success": True,
            "data": details
        }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gemini SDK 캐릭터 생성 실패: {str(e)}"
        )
