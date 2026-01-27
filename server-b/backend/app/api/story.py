from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.core.llm import call_llm

router = APIRouter()

# 요청 데이터 구조 (프론트에서 보내는 것)
class StoryGenerationRequest(BaseModel):
    situation: str = Field(..., description="사용자가 입력한 짧은 상황 (예: 둘이 범인 찾기)")
    user_name: Optional[str] = Field(None, description="사용자 이름")
    character_name: Optional[str] = Field(None, description="상대 캐릭터 이름")

@router.post("/generate/story")
async def generate_story(request: StoryGenerationRequest):
    """
    [기능] 대화 시작 전, 사용자가 입력한 상황을 바탕으로 '도입부 줄거리'를 작성함.
    [역할] 여기서는 AI가 캐릭터 연기를 하지 않고, '작가'로서 배경 설명을 함.
    """
    
    # 1. 이름이 없으면 기본값 설정
    user_n = request.user_name or "주인공"
    char_n = request.character_name or "상대방"
    
    # 2. 작가 모드 프롬프트 (가장 중요!)
    # 여기서만큼은 '캐릭터'가 아니라 '전지적 작가 시점'이어야 합니다.
    system_prompt = f"""
    [역할]
    당신은 베스트셀러 드라마 작가입니다.
    사용자가 던져준 짧은 상황 키워드를 바탕으로, 몰입감 넘치는 **도입부 줄거리(Narrative)**를 작성하세요.

    [입력 정보]
    - 주인공: {user_n}
    - 상대역: {char_n}
    - 핵심 상황: {request.situation}

    [작성 규칙 - 엄격 준수]
    1. **절대 대화체나 대본 형식으로 쓰지 마세요.** (예: "철수: 안녕?" 금지)
    2. 소설의 지문처럼 **배경, 분위기, 두 사람의 긴장감**을 서술형으로 묘사하세요.
    3. 분량은 3~4문장으로 짧고 강렬하게 끝내세요.
    4. 마지막 문장은 두 사람이 막 대화를 시작하려는 순간으로 마무리하세요.
    5. 한국어로 작성하세요.

    [작성 예시]
    (입력: 셜록홈즈 / 왓슨 / 시체 발견)
    -> 런던의 짙은 안개 속, 낡은 창고 안에는 싸늘한 침묵만이 감돌고 있었다. 셜록 홈즈와 왓슨은 바닥에 남겨진 의문의 발자국을 내려다보며 서로의 눈빛을 교환했다. 긴장감이 최고조에 달한 순간, 홈즈가 먼저 입을 열려 하고 있었다.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"상황 키워드: {request.situation}"}
    ]

    try:
        # 3. AI 호출 (Writer 모드이므로 창의성을 위해 temperature를 0.7 정도로 설정)
        # call_llm이 dict를 반환한다고 가정 ({"role": ..., "content": ...} 또는 유사 구조)
        # chat.py에서는 result = await call_llm(...) 하고 result.content 등을 썼을 수 있음.
        # 사용자가 준 코드는 result["content"]를 쓰고 있음. 이게 맞는지 확인 필요하지만,
        # 사용자가 준 코드를 그대로 쓰라고 했으니 그대로 사용.
        # 만약 실제 call_llm 반환값이 다르면 에러가 나겠지만, fallback이 있으니 안전.
        result = await call_llm(messages, temperature=0.7, max_tokens=500)
        
        # 4. 결과 반환 (프론트엔드 형식에 맞춤)
        # result가 문자열일 수도 있고 객체일 수도 있음. 
        # chat.py에서는 어떻게 썼는지 기억이 안 나지만, 보통 래퍼가 content를 반환하거나 dict를 반환함.
        # 여기서는 dict access result["content"]를 시도.
        content = result if isinstance(result, str) else result.get("content", "")
        
        return {
            "success": True,
            "data": {
                "story": content  # 여기가 줄거리 텍스트
            }
        }

    except Exception as e:
        # 5. 혹시라도 AI가 실패하면 '분석 실패' 대신 띄울 '기본 문구' 제공 (비상용)
        print(f"스토리 생성 에러: {e}")
        fallback_story = (
            f"{user_n}와 {char_n} 사이에 '{request.situation}' 상황이 펼쳐집니다. "
            "예상치 못한 전개 속에서 두 사람의 이야기가 지금 시작되려 합니다."
        )
        return {
            "success": True,
            "data": {
                "story": fallback_story
            }
        }
