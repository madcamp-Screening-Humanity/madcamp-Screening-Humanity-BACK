from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_sso.sso.google import GoogleSSO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
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
    
    # Ideally, redirection to frontend would happen here with token in params
    # For now, we return the token directly (REST API style)
    # return {
    #     "access_token": access_token, 
    #     "token_type": "bearer",
    #     "user": {
    #         "email": user.email,
    #         "name": user.username,
    #         "picture": user.picture
    #     }
    # }
    
    # Or Redirect to Frontend (assuming localhost:3000 for React)
    # This is safer for browser flows.
    frontend_url = "http://localhost:3000/auth/callback"
    return RedirectResponse(url=f"{frontend_url}?token={access_token}")
