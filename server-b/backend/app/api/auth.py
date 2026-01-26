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
    """
    Process login response from Google and return JWT
    
    성능 최적화:
    - Google SSO 타임아웃: 30초 (느린 네트워크 대응)
    - 데이터베이스 쿼리 최적화 (인덱스 활용)
    - 에러 처리 개선
    """
    import asyncio
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Google SSO 검증 (타임아웃 30초로 증가 - 느린 네트워크 대응)
        try:
            user_info = await asyncio.wait_for(
                sso.verify_and_process(request),
                timeout=30.0  # 10초 → 30초로 증가
            )
        except asyncio.TimeoutError:
            logger.warning("Google 인증 타임아웃 (30초 초과)")
            raise HTTPException(
                status_code=408,
                detail="Google 인증 응답 시간이 초과되었습니다. 네트워크 연결을 확인하고 다시 시도해주세요."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google 인증 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400, 
            detail=f"Google 인증 실패: {str(e)}"
        )
    
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")
        
    # Check if user exists (인덱스 활용 - email 컬럼에 인덱스 필요)
    user_email = user_info.email
    try:
        result = await db.execute(select(User).where(User.email == user_email))
        user = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"사용자 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="사용자 정보 조회 중 오류가 발생했습니다."
        )
    
    if not user:
        # Create new user (최소한의 필드만 설정하여 성능 최적화)
        try:
            user = User(
                id=str(uuid.uuid4()),
                email=user_email,
                username=user_info.display_name or user_email.split("@")[0],  # display_name이 없으면 이메일 앞부분 사용
                picture=user_info.picture,
                provider="google"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"새 사용자 생성: {user_email}")
        except Exception as e:
            logger.error(f"사용자 생성 실패: {str(e)}", exc_info=True)
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="사용자 생성 중 오류가 발생했습니다."
            )
        
    # Create JWT
    try:
        access_token = create_access_token(subject=user.id)
    except Exception as e:
        logger.error(f"JWT 생성 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="인증 토큰 생성 중 오류가 발생했습니다."
        )
    
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
    # 빠른 응답을 위해 최소한의 데이터만 반환
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
