from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.api.deps import get_current_user, get_current_user_optional
from app.models.user import User
from app.core.config import settings
import httpx
import json

router = APIRouter()

class StoryAnalyzeRequest(BaseModel):
    mode: Literal["director", "actor"] = Field(..., description="모드: director(감독 모드, 2명) 또는 actor(주연 모드, 1명)")
    situation: str
    # 주연 모드용 필드
    opponent_name: Optional[str] = Field(None, description="주연 모드: 상대역 이름")
    character_persona: Optional[str] = Field("", description="주연 모드: 상대역 페르소나")
    # 감독 모드용 필드
    character1_name: Optional[str] = Field(None, description="감독 모드: 첫 번째 캐릭터 이름")
    character1_persona: Optional[str] = Field("", description="감독 모드: 첫 번째 캐릭터 페르소나")
    character2_name: Optional[str] = Field(None, description="감독 모드: 두 번째 캐릭터 이름")
    character2_persona: Optional[str] = Field("", description="감독 모드: 두 번째 캐릭터 페르소나")

@router.post("/analyze", response_model=dict)
async def analyze_situation(
    request: StoryAnalyzeRequest,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    사용자가 입력한 상황을 분석하여 드라마틱한 줄거리로 변환합니다.
    - 감독 모드(director): 2명의 캐릭터가 서로 대화
    - 주연 모드(actor): 1명의 상대역과 대화
    """
    user_id = current_user.id if current_user else "anonymous"
    
    # 모드별 검증
    if request.mode == "director":
        if not request.character1_name or not request.character2_name:
            raise HTTPException(status_code=400, detail="감독 모드에서는 character1_name과 character2_name이 필요합니다.")
    elif request.mode == "actor":
        if not request.opponent_name:
            raise HTTPException(status_code=400, detail="주연 모드에서는 opponent_name이 필요합니다.")
    
    if not settings.GEMINI_API_KEY:
        # Mocking
        if request.mode == "director":
            return {
                "success": True,
                "data": {
                    "plot": f"{request.character1_name}와 {request.character2_name}의 갈등이 최고조에 달합니다. {request.situation} 상황에서 두 사람은 선택의 기로에 섭니다. 긴장감 넘치는 대화가 이어지는 가운데, 서로의 진심이 드러나기 시작합니다."
                }
            }
        else:
            return {
                "success": True,
                "data": {
                    "plot": f"{request.opponent_name}와의 갈등이 최고조에 달합니다. {request.situation} 상황에서 당신은 선택의 기로에 섭니다. 긴장감 넘치는 대화가 이어지는 가운데, 서로의 진심이 드러나기 시작합니다."
                }
            }

    # 모드별 프롬프트 생성
    if request.mode == "director":
        prompt = f"다음 상황 설정을 바탕으로 드라마틱하고 구체적인 드라마 줄거리(Plot)를 작성해주세요.\n\n" \
                 f"첫 번째 캐릭터 이름: {request.character1_name}\n" \
                 f"첫 번째 캐릭터 페르소나: {request.character1_persona}\n" \
                 f"두 번째 캐릭터 이름: {request.character2_name}\n" \
                 f"두 번째 캐릭터 페르소나: {request.character2_persona}\n" \
                 f"현재 상황: {request.situation}\n\n" \
                 f"결과물은 'plot' 필드를 가진 JSON 객체로 반환해주세요. 줄거리는 200자 내외로 흥미진진하게 작성해주세요."
    else:
        prompt = f"다음 상황 설정을 바탕으로 드라마틱하고 구체적인 드라마 줄거리(Plot)를 작성해주세요.\n\n" \
                 f"상대역 이름: {request.opponent_name}\n" \
                 f"상대역 페르소나: {request.character_persona}\n" \
                 f"현재 상황: {request.situation}\n\n" \
                 f"결과물은 'plot' 필드를 가진 JSON 객체로 반환해주세요. 줄거리는 200자 내외로 흥미진진하게 작성해주세요."

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}]
                },
                timeout=30.0
            )
            resp.raise_for_status()
            result = resp.json()
            text = result['candidates'][0]['content']['parts'][0]['text']
            
            # Clean JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(text)
            return {"success": True, "data": data}
    except Exception as e:
        print(f"Story analyze error: {e}")
        if request.mode == "director":
            fallback_plot = f"{request.character1_name}와 {request.character2_name}의 대화가 시작됩니다. {request.situation} (분석 실패로 원본 상황 사용)"
        else:
            fallback_plot = f"{request.opponent_name}와의 대화가 시작됩니다. {request.situation} (분석 실패로 원본 상황 사용)"
        return {
            "success": True,
            "data": {
                "plot": fallback_plot
            }
        }
