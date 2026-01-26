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
        from app.models import user, generation, audio
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 origin 허용 (개발 환경)
    allow_credentials=False,  # credentials 비활성화 (모든 origin 허용을 위해)
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 헤더 허용
    expose_headers=["*"],
    max_age=3600,
)

logger.info("CORS 설정: 모든 origin 허용 (개발 환경)")

# Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(generate.router, prefix=f"{settings.API_V1_STR}", tags=["generate"])

from app.api import chat
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}", tags=["chat"])

from app.api import tts
app.include_router(tts.router, prefix=f"{settings.API_V1_STR}", tags=["tts"])

from app.api import characters
app.include_router(characters.router, prefix=f"{settings.API_V1_STR}", tags=["characters"])

@app.get("/")
async def root():
    return {"message": "Avatar Forge Backend Running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/test")
async def test_connection():
    """연결 테스트 엔드포인트"""
    return {
        "status": "connected",
        "message": "백엔드 서버에 정상적으로 연결되었습니다.",
        "cors_origins": [str(origin) for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else ["*"]
    }
