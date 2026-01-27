from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.core.llm import call_llm
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

class StoryGenerationRequest(BaseModel):
    situation: str = Field(..., description="사용자가 입력한 짧은 상황")
    user_name: Optional[str] = Field(None, description="사용자 이름")
    character_name: Optional[str] = Field(None, description="상대 캐릭터 이름")

class StoryGenerationResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

@router.post("/generate/story")
async def generate_story(
    request: StoryGenerationRequest,
    # current_user: User = Depends(get_current_user) # 필요시 인증 추가
):
    """
    사용자의 상황 입력을 바탕으로 드라마틱한 줄거리 생성
    """
    user_n = request.user_name or "사용자"
    char_n = request.character_name or "상대방"
    
    system_prompt = (
        "당신은 드라마와 영화의 전문 시나리오 작가입니다. "
        "사용자가 제공한 상황과 인물 정보를 바탕으로, 매우 드라마틱하고 구체적인 한 문단의 줄거리를 작성해주세요.\n\n"
        "[지침]\n"
        f"1. 반드시 주어진 인물 이름인 '{user_n}'(나/주인공)와 '{char_n}'(상대역)만 사용하세요. 절대 다른 이름을 지어내지 마세요.\n"
        "2. 전체적인 분위기는 선택한 상황에 맞추되, 인물들 간의 갈등이나 감정이 잘 드러나도록 풍부하게 묘사하세요.\n"
        "2. 입력되지 않은 제3의 인물을 절대 창조하거나 언급하지 마세요.\n"
        "3. 사용자가 입력한 상황 설정을 바탕으로 이야기를 구체화하되, 내용을 왜곡하지 마세요.\n"
        "4. 문체는 소설처럼 몰입감 있게 서술하고, 한국어로 작성하세요.\n"
        "5. 마지막 문장은 두 사람이 대화를 시작하기 직전의 긴장감 있는 상황 묘사로 끝내세요."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"상황: {request.situation}"}
    ]
    
    try:
        result = await call_llm(messages, temperature=0.8, max_tokens=1000)
        return {
            "success": True,
            "data": {
                "story": result["content"]
            }
        }
    except Exception as e:
        # 에러 발생 시 Mock 응답 제공 (연결 실패 대비)
        import logging
        logging.error(f"Story generation failed, using mock: {e}")
        
        mock_story = (
            f"운명의 장난처럼 {request.situation} 상황이 펼쳐집니다. "
            "서로의 오해와 감정이 얽히며 예상치 못한 전개가 시작되려 합니다. "
            "이 긴장감 넘치는 순간, 당신의 선택이 모든 것을 결정할 것입니다."
        )
        return {
            "success": True,
            "data": {
                "story": mock_story
            }
        }

@router.post("/story/analyze")
async def analyze_story_legacy(request: StoryGenerationRequest):
    """구형 엔드포인트 호환용 (/api/story/analyze)"""
    return await generate_story(request)

class CharacterGenerationRequest(BaseModel):
    name: str = Field(..., description="캐릭터 이름")
    description: str = Field(..., description="캐릭터 기본 설명/배경")

class CharacterGenerationResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

@router.post("/generate/character-details", response_model=CharacterGenerationResponse)
async def generate_character_details(
    request: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    이름과 기본 설명을 바탕으로 캐릭터의 페르소나, 성격, 말투 등을 자동 생성
    """
    system_prompt = (
        "당신은 캐릭터 디자이너이자 작가입니다. "
        "사용자가 제공한 이름과 기본 배경을 바탕으로, 대화형 AI 캐릭터를 위한 상세 설정을 만들어주세요. "
        "결과는 반드시 다음 JSON 형식을 따라야 합니다:\n"
        "{\n"
        "  \"persona\": \"성격, 가치관, 과거 트라우마 등 깊이 있는 내면 묘사\",\n"
        "  \"speech_style\": \"말투의 특징 (예: 존댓말을 쓰지만 차가움, 사투리를 씀, 장난스러움 등)\",\n"
        "  \"goal\": \"이 캐릭터의 현재 목표 또는 대화의 목적\",\n"
        "  \"tags\": [\"태그1\", \"태그2\"]\n"
        "}\n"
        "답변은 반드시 유효한 JSON 형식이어야 하며, 다른 설명은 하지 마세요."
    )
    
    user_input = f"이름: {request.name}\n배경: {request.description}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    
    try:
        result = await call_llm(messages, temperature=0.7, max_tokens=1000)
        import json
        
        # JSON 파싱 시도 (코드 블록 등이 포함될 수 있으므로 정제 필요할 수 있음)
        content = result["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        details = json.loads(content.strip())
        
        return {
            "success": True,
            "data": details
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐릭터 정보 생성 실패: {str(e)}"
        )
