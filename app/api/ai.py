from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.core.llm import call_llm
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

def _extract_json(content: str) -> Dict[str, Any]:
    """LLM 응답에서 JSON 객체를 추출합니다."""
    import json
    import re
    
    content = content.strip()
    
    # 1. 마크다운 코드 블록 제거
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    # 2. JSON 파싱 시도
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
        
    # 3. 중괄호로 감싸진 부분만 추출하여 재시도 (설명 텍스트 제거)
    try:
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = content[start_idx : end_idx + 1]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
        
    # 4. 실패 시 빈 딕셔너리 또는 에러
    raise ValueError("Failed to extract JSON from response")

# ============ 스토리 생성 API ============
class StoryGenerationRequest(BaseModel):
    """스토리 생성 요청 모델"""
    situation: str = Field(..., description="사용자가 입력한 짧은 상황")
    opponent_name: str = Field(None, description="상대방 캐릭터 이름")
    character_persona: str = Field(None, description="캐릭터 페르소나 설정")

class StoryGenerationResponse(BaseModel):
    """스토리 생성 응답 모델"""
    plot: str

@router.post("/generate/story")
async def generate_story(
    request: StoryGenerationRequest,
):
    """
    사용자의 상황 입력을 바탕으로 드라마틱한 줄거리 생성
    """
    
    # ... (이전 코드 생략) ...
    user_n = "나"
    char_n = request.opponent_name or "상대방"
    
    system_prompt = (
        "당신은 드라마와 영화의 전문 시나리오 작가입니다. "
        "사용자가 제공한 상황과 인물 정보를 바탕으로, 몰입감 있고 드라마틱한 줄거리(Plot)와 배경(Background)을 작성해주세요.\n\n"
        "[중요: 정보 검색 및 반영]\n"
        "- 제공된 캐릭터나 작품 이름이 실존하거나 유명한 IP라면, **반드시 검색 도구를 사용하여 정확한 최신 세계관 설정과 배경 지식을 찾아 반영**하세요.\n"
        "- 나무위키나 공식 위키 수준의 디테일한 설정(고유 명사, 지명, 사건 등)을 자연스럽게 녹여내세요.\n\n"
        "[지침]\n"
        f"1. 반드시 주어진 인물 이름인 '{user_n}'(나/주인공)와 '{char_n}'(상대역)만 사용하세요.\n"
        "2. 전체적인 분위기는 선택한 상황에 맞추되, 인물들 간의 갈등이나 감정이 잘 드러나도록 풍부하게 묘사하세요.\n"
        "3. 문체는 소설처럼 몰입감 있게 서술하고, 최대 5줄의 한국어로 작성하세요.\n"
        "4. 줄거리의 마지막 문장은 두 사람이 대화를 시작하기 직전의 긴장감 있는 상황 묘사로 끝내세요.\n"
        "5. **JSON 형식을 사용하지 마세요.** 아래 형식을 지켜 줄글로 작성하세요.\n\n"
        "[출력 형식]\n"
        "[줄거리]\n"
        "(여기에 줄거리 내용을 작성하세요)\n\n"
        "[배경]\n"
        "(여기에 장소, 시간, 분위기 등을 묘사한 배경 설명을 작성하세요)"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"상황: {request.situation}"}
    ]
    
    try:
        import json as _json
        from app.core.config import settings
        
        # 시나리오 생성은 무조건 Gemini-2.5-flash 사용
        model_to_use = "gemini-2.5-flash"
        
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini API Key가 설정되지 않았습니다. .env 파일의 GOOGLE_API_KEY를 확인해주세요."
            )

        result = await call_llm(
            messages, 
            model=model_to_use, 
            temperature=0.8, 
            max_tokens=4000,
            json_mode=False
        )
        
        content = result if isinstance(result, str) else result.get("content", "")
        
        # 태그 기반 파싱 ([줄거리] ... [배경] ...)
        plot = ""
        background = ""
        
        try:
            # 1. [줄거리]와 [배경] 태그 위치 찾기
            plot_idx = content.find("[줄거리]")
            bg_idx = content.find("[배경]")
            
            if plot_idx != -1 and bg_idx != -1:
                if plot_idx < bg_idx:
                    plot = content[plot_idx + 5 : bg_idx].strip()
                    background = content[bg_idx + 4 :].strip()
                else:
                    # 배경이 먼저 나온 경우 (혹시나)
                    background = content[bg_idx + 4 : plot_idx].strip()
                    plot = content[plot_idx + 5 :].strip()
            elif plot_idx != -1:
                # 줄거리만 있는 경우
                plot = content[plot_idx + 5 :].strip()
            elif bg_idx != -1:
                # 배경만 있는 경우 (특이케이스)
                background = content[:bg_idx].strip()
                plot = content[bg_idx + 4 :].strip()
            else:
                # 태그가 없는 경우 -> 전체를 줄거리로 간주
                plot = content.strip()
                
        except Exception as e:
            # 파싱 에러 시 전체를 plot으로
            import logging
            logging.warning(f"Parsing scenario failed: {e}")
            plot = content.strip()

        return {
            "success": True,
            "data": {
                "plot": plot,
                "background": background
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
                "plot": mock_story,
                "background": ""
            }
        }

@router.post("/story/analyze")
async def analyze_story_legacy(request: StoryGenerationRequest):
    """구형 엔드포인트 호환용 (/api/story/analyze)"""
    return await generate_story(request)

class CharacterGenerationRequest(BaseModel):
    """캐릭터 생성 요청 모델 - 상세 필드 지원"""
    name: str = Field(..., description="캐릭터 이름")
    category: Optional[str] = Field(None, description="카테고리")
    source_work: Optional[str] = Field(None, description="작품명 (출처)")
    description: str = Field("", description="캐릭터 컨셉/설명")
    worldview: Optional[str] = Field(None, description="세계관")

class CharacterGenerationResponse(BaseModel):
    """캐릭터 생성 응답 모델"""
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
        "결과는 반드시 다음 JSON 형식을 따라야 합니다. 마크다운이나 기타 설명 없이 오직 JSON만 출력하세요:\n"
        "{\n"
        "  \"persona\": \"성격, 가치관, 과거 트라우마 등 깊이 있는 내면 묘사\",\n"
        "  \"speech_style\": \"말투의 특징 (예: 존댓말을 쓰지만 차가움, 사투리를 씀, 장난스러움 등)\",\n"
        "  \"goal\": \"이 캐릭터의 현재 목표 또는 대화의 목적\",\n"
        "  \"tags\": [\"태그1\", \"태그2\"]\n"
        "}\n"
    )
    
    user_input = f"이름: {request.name}\n배경: {request.description}"
    
    messages = [
        {"role": "user", "content": user_input}
    ]
    
    try:
        # Gemini 사용 가능 시 우선 사용
        from app.core.config import settings
        
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini API Key가 설정되지 않았습니다. .env 파일의 GOOGLE_API_KEY를 확인해주세요."
            )
            
        model_to_use = "gemini-2.5-flash-preview"

        result = await call_llm(
            messages, 
            model=model_to_use, 
            temperature=0.7, 
            max_tokens=1000,
            json_mode=True,
            system_instruction=system_prompt
        )
        
        content = result if isinstance(result, str) else result.get("content", "")
        details = _extract_json(content)
        
        return {
            "success": True,
            "data": details
        }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐릭터 정보 생성 실패: {str(e)}"
        )
