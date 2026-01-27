from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.core.llm import call_llm
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.scenario import Scenario

router = APIRouter()

class StoryGenerationRequest(BaseModel):
    user_name: str
    character_name: str
    situation: str

@router.post("/generate/story")
async def generate_story(
    request: StoryGenerationRequest,
    db: AsyncSession = Depends(get_db), # DB 세션 주입
    current_user: User = Depends(get_current_user) # 사용자 정보 주입
):
    """
    [기능] 
    1. 상황 키워드를 바탕으로 'UI 표시용 1줄 요약' 생성
    2. AI가 연기할 '구체적인 상황 배경' 생성
    3. 생성된 시나리오를 DB에 저장
    """
    
    system_prompt = f"""
    당신은 드라마 시나리오 작가입니다. 
    사용자가 입력한 [상황 키워드]를 바탕으로 두 가지를 출력하세요.

    [입력 정보]
    - 주인공: {request.user_name}
    - 상대역: {request.character_name}
    - 키워드: {request.situation}

    [출력 요구사항 (JSON 포맷)]
    1. "summary": 대화방 상단에 띄울 **1줄 로그라인**. (문학적이고 감성적으로, 50자 이내)
    2. "background": AI 캐릭터에게 주입할 **구체적인 상황 설명**. (현재 분위기, 두 사람의 관계, 직전 사건 포함)
    
    [중요] 오직 JSON 포맷으로만 응답하세요. 마크다운 코드 블록(```json)이나 사족을 붙이지 마세요.

    [예시]
    키워드: 이별 통보
    출력: {{
        "summary": "떨어지는 벚꽃 아래, 되돌릴 수 없는 이별의 순간.",
        "background": "늦은 오후, 벚꽃이 휘날리는 공원 벤치. {request.character_name}은(는) 한참을 망설이다가 이별을 결심했습니다. 분위기는 무겁고 슬프며, 상대방을 쳐다보지 못하고 있습니다."
    }}
    """

    messages = [{"role": "system", "content": system_prompt}]

    try:
        # JSON 모드로 응답 받기 (프롬프트로 강제)
        result = await call_llm(messages, temperature=0.7)
        
        content = result if isinstance(result, str) else result.get("content", "")
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        data = json.loads(content)
        
        summary_text = data.get("summary", request.situation)
        background_text = data.get("background", request.situation)

        # DB 저장
        new_scenario = Scenario(
            user_id=current_user.id,
            user_name=request.user_name,
            character_name=request.character_name,
            situation=request.situation,
            summary=summary_text,
            background=background_text
        )
        db.add(new_scenario)
        await db.commit()
        await db.refresh(new_scenario)

        return {
            "success": True,
            "data": {
                "scenario_id": new_scenario.id, # ID 반환 추가
                "summary": summary_text,
                "background": background_text
            }
        }

    except Exception as e:
        print(f"Story Gen Error: {e}")
        # 실패 시에도 기본값으로라도 저장 시도? 아니면 저장 안함.
        # 에러 발생 시 저장을 못하므로 그냥 리턴
        return {
            "success": True,
            "data": {
                "summary": f"{request.situation} - 이야기가 시작됩니다.",
                "background": f"현재 상황은 {request.situation}입니다."
            }
        }
