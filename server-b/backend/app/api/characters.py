from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import httpx

from app.core.config import settings
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.character import Character

router = APIRouter()

# 설정 파일 경로
CHARACTERS_CONFIG_PATH = Path(__file__).parent.parent / "config" / "characters.json"

# 사전설정 캐릭터 캐시
_preset_characters_cache = None
_cache_file_mtime = None

def load_preset_characters() -> List[Dict[str, Any]]:
    """사전설정 캐릭터 설정 파일 로드 (파일 변경 감지)"""
    global _preset_characters_cache, _cache_file_mtime
    
    if not CHARACTERS_CONFIG_PATH.exists():
        _preset_characters_cache = []
        _cache_file_mtime = None
        return []
    
    current_mtime = CHARACTERS_CONFIG_PATH.stat().st_mtime
    
    if _preset_characters_cache is not None and _cache_file_mtime == current_mtime:
        return _preset_characters_cache
    
    try:
        with open(CHARACTERS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            _preset_characters_cache = data.get("characters", [])
            _cache_file_mtime = current_mtime
            return _preset_characters_cache
    except Exception as e:
        print(f"사전설정 캐릭터 로드 실패: {e}")
        _preset_characters_cache = []
        _cache_file_mtime = None
        return []

# Pydantic 모델
class CharacterBase(BaseModel):
    name: str = Field(..., description="캐릭터 이름")
    description: Optional[str] = Field(None, description="캐릭터 설명")
    persona: Optional[str] = Field(None, description="캐릭터 페르소나")
    voice_id: Optional[str] = Field(None, description="음성 ID")
    category: Optional[str] = Field(None, description="카테고리")
    tags: Optional[List[str]] = Field(None, description="태그 목록")
    sample_dialogue: Optional[str] = Field(None, description="샘플 대화")
    image_url: Optional[str] = Field(None, description="이미지 URL")

class CharacterCreate(CharacterBase):
    pass

class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    persona: Optional[str] = None
    voice_id: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    sample_dialogue: Optional[str] = None
    image_url: Optional[str] = None

class GenerateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    category: Optional[str] = ""

# Endpoints
@router.get("/characters/presets")
async def list_preset_characters():
    """사전설정 캐릭터 목록 조회"""
    try:
        preset_chars = load_preset_characters()
        return {
            "success": True,
            "data": {
                "characters": preset_chars
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"사전설정 캐릭터 조회 실패: {str(e)}"
        )

@router.get("/characters")
async def list_user_characters(
    db: AsyncSession = Depends(get_db)
):
    """개발 환경: 인증 없이 캐릭터 목록 조회"""
    try:
        # 개발 환경: dev-user의 캐릭터만 조회
        result = await db.execute(
            select(Character).where(
                Character.user_id == "dev-user",
                Character.is_preset == False
            ).order_by(Character.created_at.desc())
        )
        characters = result.scalars().all()
        
        character_list = []
        for char in characters:
            tags = json.loads(char.tags) if char.tags else []
            character_list.append({
                "id": char.id,
                "name": char.name,
                "description": char.description,
                "persona": char.persona,
                "voice_id": char.voice_id,
                "category": char.category,
                "tags": tags,
                "sample_dialogue": char.sample_dialogue,
                "image_url": char.image_url,
                "is_preset": char.is_preset,
                "user_id": char.user_id,
                "created_at": char.created_at.isoformat() if char.created_at else None
            })
        
        return {
            "success": True,
            "data": {
                "characters": character_list
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐릭터 조회 실패: {str(e)}"
        )

@router.post("/characters")
async def create_character(
    character: CharacterCreate,
    db: AsyncSession = Depends(get_db)
):
    """개발 환경용: 인증 없이 캐릭터 생성 (임시 user_id 사용)"""
    try:
        tags_json = json.dumps(character.tags) if character.tags else None
        
        db_character = Character(
            user_id="dev-user",  # 개발 환경용 임시 사용자 ID
            name=character.name,
            description=character.description,
            persona=character.persona,
            voice_id=character.voice_id,
            category=character.category,
            tags=tags_json,
            sample_dialogue=character.sample_dialogue,
            image_url=character.image_url,
            is_preset=False
        )
        
        db.add(db_character)
        await db.commit()
        await db.refresh(db_character)
        
        tags = json.loads(db_character.tags) if db_character.tags else []
        return {
            "success": True,
            "data": {
                "id": db_character.id,
                "name": db_character.name,
                "description": db_character.description,
                "persona": db_character.persona,
                "voice_id": db_character.voice_id,
                "category": db_character.category,
                "tags": tags,
                "sample_dialogue": db_character.sample_dialogue,
                "image_url": db_character.image_url,
                "is_preset": db_character.is_preset,
                "user_id": db_character.user_id,
                "created_at": db_character.created_at.isoformat() if db_character.created_at else None
            }
        }
    except Exception as e:
        await db.rollback()
        print(f"Character create error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐릭터 생성 실패: {str(e)}"
        )

@router.get("/characters/{character_id}")
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db)
):
    """특정 캐릭터 상세 조회 (인증 없음)"""
    try:
        preset_chars = load_preset_characters()
        preset_char = next((c for c in preset_chars if c.get("id") == character_id), None)
        
        if preset_char:
            return {
                "success": True,
                "data": {
                    **preset_char,
                    "is_preset": True
                }
            }
        
        result = await db.execute(
            select(Character).where(Character.id == character_id)
        )
        character = result.scalar_one_or_none()
        
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="캐릭터를 찾을 수 없습니다"
            )
        
        tags = json.loads(character.tags) if character.tags else []
        return {
            "success": True,
            "data": {
                "id": character.id,
                "name": character.name,
                "description": character.description,
                "persona": character.persona,
                "voice_id": character.voice_id,
                "category": character.category,
                "tags": tags,
                "sample_dialogue": character.sample_dialogue,
                "image_url": character.image_url,
                "is_preset": character.is_preset,
                "user_id": character.user_id,
                "created_at": character.created_at.isoformat() if character.created_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐릭터 조회 실패: {str(e)}"
        )

@router.put("/characters/{character_id}")
async def update_character(
    character_id: str,
    character_update: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캐릭터 수정 (본인 소유 확인)"""
    try:
        preset_chars = load_preset_characters()
        preset_char = next((c for c in preset_chars if c.get("id") == character_id), None)
        if preset_char:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="사전설정 캐릭터는 수정할 수 없습니다"
            )
        
        result = await db.execute(
            select(Character).where(Character.id == character_id)
        )
        character = result.scalar_one_or_none()
        
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="캐릭터를 찾을 수 없습니다"
            )
            
        if character.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="캐릭터를 수정할 권한이 없습니다"
            )
        
        update_data = character_update.model_dump(exclude_unset=True)
        if "tags" in update_data and update_data["tags"] is not None:
            update_data["tags"] = json.dumps(update_data["tags"])
        
        for field, value in update_data.items():
            setattr(character, field, value)
        
        await db.commit()
        await db.refresh(character)
        
        tags = json.loads(character.tags) if character.tags else []
        return {
            "success": True,
            "data": {
                "id": character.id,
                "name": character.name,
                "description": character.description,
                "persona": character.persona,
                "voice_id": character.voice_id,
                "category": character.category,
                "tags": tags,
                "sample_dialogue": character.sample_dialogue,
                "image_url": character.image_url,
                "is_preset": character.is_preset,
                "user_id": character.user_id,
                "created_at": character.created_at.isoformat() if character.created_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐릭터 수정 실패: {str(e)}"
        )

@router.delete("/characters/{character_id}")
async def delete_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캐릭터 삭제 (본인 소유 확인)"""
    try:
        preset_chars = load_preset_characters()
        preset_char = next((c for c in preset_chars if c.get("id") == character_id), None)
        if preset_char:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="사전설정 캐릭터는 삭제할 수 없습니다"
            )
        
        result = await db.execute(
            select(Character).where(Character.id == character_id)
        )
        character = result.scalar_one_or_none()
        
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="캐릭터를 찾을 수 없습니다"
            )
            
        if character.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="캐릭터를 삭제할 권한이 없습니다"
            )
        
        await db.execute(delete(Character).where(Character.id == character_id))
        await db.commit()
        
        return {
            "success": True,
            "data": {
                "message": "캐릭터가 삭제되었습니다"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐릭터 삭제 실패: {str(e)}"
        )

@router.post("/generate", response_model=dict)
async def generate_character_details(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI를 사용하여 캐릭터의 상세 정보(페르소나, 말투 등)를 생성합니다.
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
