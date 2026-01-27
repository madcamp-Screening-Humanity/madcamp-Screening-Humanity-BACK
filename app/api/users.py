# GET /api/users/me/settings, PUT /api/users/me/settings
from fastapi import APIRouter, Depends
from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.user_preference import UserPreference

router = APIRouter()

# 설정에 허용할 키 (부분 업데이트 시 이 키만 반영)
ALLOWED_SETTINGS_KEYS = {"tts_mode", "tts_delay_ms", "tts_streaming_mode", "tts_enabled", "tts_speed"}


@router.get("/me/settings")
async def get_my_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로그인 사용자의 settings JSON 반환. 없으면 {}."""
    r = await db.execute(select(UserPreference).where(UserPreference.user_id == current_user.id))
    row = r.scalar_one_or_none()
    if not row:
        return {"success": True, "data": {}}
    out = row.settings if isinstance(row.settings, dict) else {}
    return {"success": True, "data": out}


@router.put("/me/settings")
async def put_my_settings(
    body: Dict[str, Any],  # {"tts_speed": 1.2, ...} 부분 업데이트
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """body에 포함된 키만 기존 settings에 병합. 허용 키: tts_mode, tts_delay_ms, tts_streaming_mode, tts_enabled, tts_speed."""
    to_merge = {k: v for k, v in body.items() if k in ALLOWED_SETTINGS_KEYS}
    if not to_merge:
        r = await db.execute(select(UserPreference).where(UserPreference.user_id == current_user.id))
        row = r.scalar_one_or_none()
        cur = (row.settings if row and isinstance(row.settings, dict) else {}) or {}
        return {"success": True, "data": cur}

    r = await db.execute(select(UserPreference).where(UserPreference.user_id == current_user.id))
    row = r.scalar_one_or_none()
    if not row:
        pref = UserPreference(user_id=current_user.id, settings=dict(to_merge))
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
        return {"success": True, "data": pref.settings or to_merge}
    cur = (row.settings if isinstance(row.settings, dict) else {}) or {}
    cur.update(to_merge)
    row.settings = cur
    await db.commit()
    await db.refresh(row)
    return {"success": True, "data": row.settings or cur}
