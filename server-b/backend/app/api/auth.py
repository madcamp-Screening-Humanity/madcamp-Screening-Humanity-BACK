from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_sso.sso.google import GoogleSSO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.api.deps import get_current_user
import uuid

router = APIRouter()

sso = GoogleSSO(
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    redirect_uri=settings.GOOGLE_REDIRECT_URI,
    allow_insecure_http=True
)

@router.get("/google/login")
async def google_login():
    """Redirect user to Google Login"""
    return await sso.get_login_redirect()

@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Process login response from Google and return JWT"""
    try:
        user_info = await sso.verify_and_process(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")
        
    # Check if user exists
    user_email = user_info.email
    result = await db.execute(select(User).where(User.email == user_email))
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            email=user_email,
            username=user_info.display_name,
            picture=user_info.picture,
            provider="google"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
    # Create JWT
    access_token = create_access_token(subject=user.id)
    
    # Redirect to Frontend with JWT in HttpOnly Cookie
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
    redirect_url = f"{frontend_url}/auth/callback"
    
    response = RedirectResponse(url=redirect_url)
    # Set HttpOnly Cookie for JWT token
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # HTTPS 환경에서는 True로 변경
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    return response

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """현재 로그인한 사용자 정보 조회"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "picture": current_user.picture,
        "provider": current_user.provider,
    }

@router.post("/logout")
async def logout():
    """로그아웃 - 쿠키에서 토큰 삭제"""
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
    redirect_url = f"{frontend_url}/"
    
    response = RedirectResponse(url=redirect_url)
    # 쿠키 삭제
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="lax"
    )
    return response
