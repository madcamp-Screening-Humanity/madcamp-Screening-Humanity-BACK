from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from app.api.deps import get_current_user, get_current_user_optional, get_db
from app.models.user import User
from app.models.character import Character
import httpx
from app.core.config import settings
import json

router = APIRouter()

class CharacterBase(BaseModel):
    name: str
    description: Optional[str] = None
    persona: Optional[str] = None
    voice_id: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None

class CharacterCreate(CharacterBase):
    pass

class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    persona: Optional[str] = None
    voice_id: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None

class CharacterResponse(CharacterBase):
    id: str
    user_id: Optional[str]
    is_preset: bool

    class Config:
        from_attributes = True

@router.get("/presets", response_model=dict)
async def list_presets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Character).where(Character.is_preset == True))
    presets = result.scalars().all()
    return {"success": True, "data": {"characters": presets}}

@router.get("/", response_model=dict)
async def list_characters(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    if not current_user:
        return {"success": True, "data": {"characters": []}}
    result = await db.execute(select(Character).where(Character.user_id == current_user.id))
    characters = result.scalars().all()
    return {"success": True, "data": {"characters": characters}}

@router.post("/", response_model=dict)
async def create_character(
    character_in: CharacterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    user_id = current_user.id if current_user else "anonymous"
    character = Character(
        **character_in.model_dump(),
        user_id=user_id,
        is_preset=False
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return {"success": True, "data": character}

@router.get("/{character_id}", response_model=dict)
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Character).where(
            (Character.id == character_id) & 
            ((Character.user_id == current_user.id) | (Character.is_preset == True))
        )
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"success": True, "data": character}

@router.put("/{character_id}", response_model=dict)
async def update_character(
    character_id: str,
    character_in: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Character).where(
            (Character.id == character_id) & (Character.user_id == current_user.id)
        )
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    
    update_data = character_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(character, field, value)
    
    await db.commit()
    await db.refresh(character)
    return {"success": True, "data": character}

@router.delete("/{character_id}", response_model=dict)
async def delete_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Character).where(
            (Character.id == character_id) & (Character.user_id == current_user.id)
        )
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    
    await db.delete(character)
    await db.commit()
    return {"success": True, "message": "Character deleted"}

class GenerateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    category: Optional[str] = ""

@router.post("/generate", response_model=dict)
async def generate_character_details(
    request: GenerateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    AI를 사용하여 캐릭터의 상세 정보(페르소나, 말투 등)를 생성합니다.
    (Requirement 5 대응)
    """
    if not settings.GEMINI_API_KEY:
        # Mocking if no API key
        return {
            "success": True,
            "data": {
                "persona": f"성격: {request.name}은 매우 성실하고 계획적입니다.\n말투: 정중하고 차분한 말투를 사용합니다.\n배경: 평범한 학생이었으나 사건을 겪으며 변화했습니다.\n목표: 진실을 밝히는 것이 최종 목표입니다.",
                "description": f"{request.name} 캐릭터의 상세 설정입니다.",
                "category": request.category or "일반",
                "tags": ["성실", "정중", "목표의식"],
                "sample_dialogue": "안녕하십니까, 제가 도와드릴 일이 있을까요?"
            }
        }

    # Actual Gemini call
    prompt = f"{request.name} 캐릭터에 대한 상세한 정보를 JSON 형식으로 생성해주세요. 배경설명: {request.description}\n카테고리: {request.category}\n\n" \
             f"다음 필드들을 포함해야 합니다:\n" \
             f"- persona: 캐릭터의 성격, 말투, 행동 패턴을 상세히 설명 (200자 이상). 다음 형식 포함: 성격, 말투, 배경, 목표\n" \
             f"- description: 캐릭터 요약 설명\n" \
             f"- tags: 관련 태그 3-5개 배열\n" \
             f"- sample_dialogue: 대표 대화\n\n" \
             f"JSON 형식으로만 응답하세요."

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
        print(f"Gemini generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
