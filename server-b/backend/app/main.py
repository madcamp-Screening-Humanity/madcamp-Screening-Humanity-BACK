from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, generate
from contextlib import asynccontextmanager
import logging

# Lifecycle for DB creation
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        # Create tables
        # Import models so they are registered
<<<<<<< HEAD
        from app.models import user, generation, character
=======
        from app.models import user, generation, audio
>>>>>>> 6fe448cb8225155864a351628994e82378c14e33
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS 설정 로깅
logger = logging.getLogger(__name__)

# 개발 환경에서 모든 localhost origin 허용 (간단화된 설정)
# allow_credentials=False로 설정하여 모든 origin 허용 가능
# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS] or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

logger.info("CORS 설정: 모든 origin 허용 (개발 환경)")

# Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(generate.router, prefix=f"{settings.API_V1_STR}/generate", tags=["generate"])

from app.api import chat, characters, story
app.include_router(characters.router, prefix=f"{settings.API_V1_STR}/characters", tags=["characters"])
app.include_router(story.router, prefix=f"{settings.API_V1_STR}/story", tags=["story"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}", tags=["chat"])

from app.api import tts
app.include_router(tts.router, prefix=f"{settings.API_V1_STR}", tags=["tts"])

from app.api import ai
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}/ai", tags=["ai"])

from app.api import characters
app.include_router(characters.router, prefix=f"{settings.API_V1_STR}", tags=["characters"])

# 레거시 경로 호환성 추가
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}", tags=["legacy"])

@app.get("/")
async def root():
    return {"success": True, "message": "Avatar Forge Backend Running"}

@app.get(f"{settings.API_V1_STR}/system/health")
@app.get("/api/health") # Legacy/Direct health
async def health():
<<<<<<< HEAD
    return {"success": True, "data": {"status": "healthy"}}

@app.get(f"{settings.API_V1_STR}/system/status")
async def system_status():
    return {
        "success": True,
        "data": {
            "status": "online",
            "version": "1.0.0",
            "gpu_server": "connected"
        }
=======
    return {"status": "healthy"}


@app.get("/api/test")
async def test_connection():
    """연결 테스트 엔드포인트"""
    return {
        "status": "connected",
        "message": "백엔드 서버에 정상적으로 연결되었습니다.",
        "cors_origins": [str(origin) for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else ["*"]
>>>>>>> 6fe448cb8225155864a351628994e82378c14e33
    }
