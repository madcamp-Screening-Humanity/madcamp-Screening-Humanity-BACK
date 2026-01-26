from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import json
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.config import settings
from app.api.deps import get_db
from app.models.user import User
from app.models.generation import Character

router = APIRouter()

# 설정 파일 경로
CHARACTERS_CONFIG_PATH = Path(__file__).parent.parent / "config" / "characters.json"

# 사전설정 캐릭터 캐시
_preset_characters_cache = None
_cache_file_mtime = None

def load_preset_characters() -> List[Dict[str, Any]]:
    """사전설정 캐릭터 설정 파일 로드 (파일 변경 감지)"""
    global _preset_characters_cache, _cache_file_mtime
    
    # 파일이 존재하지 않으면 빈 리스트 반환
    if not CHARACTERS_CONFIG_PATH.exists():
        _preset_characters_cache = []
        _cache_file_mtime = None
        return []
    
    # 파일 수정 시간 확인
    current_mtime = CHARACTERS_CONFIG_PATH.stat().st_mtime
    
    # 캐시가 있고 파일이 변경되지 않았으면 캐시 반환
    if _preset_characters_cache is not None and _cache_file_mtime == current_mtime:
        return _preset_characters_cache
    
    # 파일 로드 및 캐시 업데이트
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

class CharacterResponse(CharacterBase):
    id: str
    is_preset: bool
    user_id: Optional[str] = None
    created_at: Optional[str] = None
    
    class Config:
        from_attributes = True

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
    """사용자가 생성한 캐릭터 목록 조회 (인증 없음)"""
    try:
        result = await db.execute(
            select(Character).where(
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
    """나만의 캐릭터 생성 (인증 없음)"""
    try:
        # 태그를 JSON 문자열로 변환
        tags_json = json.dumps(character.tags) if character.tags else None
        
        # Character 모델 생성 (익명 사용자)
        db_character = Character(
            user_id="anonymous",
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
        
        # 응답 생성
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
        # 사전설정 캐릭터인지 확인
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
        
        # DB에서 조회
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
    db: AsyncSession = Depends(get_db)
):
    """캐릭터 수정 (인증 없음)"""
    try:
        # 사전설정 캐릭터는 수정 불가
        preset_chars = load_preset_characters()
        preset_char = next((c for c in preset_chars if c.get("id") == character_id), None)
        if preset_char:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="사전설정 캐릭터는 수정할 수 없습니다"
            )
        
        # DB에서 조회
        result = await db.execute(
            select(Character).where(Character.id == character_id)
        )
        character = result.scalar_one_or_none()
        
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="캐릭터를 찾을 수 없습니다"
            )
        
        # 필드 업데이트
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
    db: AsyncSession = Depends(get_db)
):
    """캐릭터 삭제 (인증 없음)"""
    try:
        # 사전설정 캐릭터는 삭제 불가
        preset_chars = load_preset_characters()
        preset_char = next((c for c in preset_chars if c.get("id") == character_id), None)
        if preset_char:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="사전설정 캐릭터는 삭제할 수 없습니다"
            )
        
        # DB에서 조회
        result = await db.execute(
            select(Character).where(Character.id == character_id)
        )
        character = result.scalar_one_or_none()
        
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="캐릭터를 찾을 수 없습니다"
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
