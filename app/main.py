from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis import init_redis_pool, close_redis_pool
from app.api import auth, users, generate
from contextlib import asynccontextmanager
import logging
import os

# Lifecycle for DB creation
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_redis_pool()
    
    # Ensure USER_ASSETS_DIR exists
    os.makedirs(settings.USER_ASSETS_DIR, exist_ok=True)
    
    async with engine.begin() as conn:
        # Create tables
        from app.models import user, generation, character, audio, summary, voice, scenario, chat_message, user_preference
        await conn.run_sync(Base.metadata.create_all)
        # 기존 DB: voices에 user_id 컬럼 추가 (이미 있으면 무시)
        for col, typ in [("user_id", "VARCHAR(36)"), ("train_input_dir", "VARCHAR(500)"), ("training_model_name", "VARCHAR(200)")]:
            try:
                await conn.execute(text(f"ALTER TABLE voices ADD COLUMN {col} {typ}"))
            except Exception as e:
                if "duplicate column" not in str(e).lower() and "already exists" not in str(e).lower():
                    raise
        # user_ref_sounds 테이블 삭제 (drop_only, 없으면 무시)
        try:
            await conn.execute(text("DROP TABLE IF EXISTS user_ref_sounds"))
        except Exception:
            pass
        # characters.sample_dialogue 컬럼 제거 (SQLite 3.35+)
        try:
            await conn.execute(text("ALTER TABLE characters DROP COLUMN sample_dialogue"))
        except Exception as e:
            logging.getLogger("app.main").info("characters.sample_dialogue DROP COLUMN 생략 또는 실패: %s", e)
    yield
    # Shutdown
    await close_redis_pool()
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

# Static Files Mount
# /assets 경로로 접근 시 USER_ASSETS_DIR의 파일을 서빙
app.mount("/assets", StaticFiles(directory=settings.USER_ASSETS_DIR), name="assets")

# Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(generate.router, prefix=f"{settings.API_V1_STR}/generate", tags=["generate"])

from app.api import chat, characters, story, evaluation
app.include_router(story.router, prefix=f"{settings.API_V1_STR}/story", tags=["story"])
app.include_router(evaluation.router, prefix=f"{settings.API_V1_STR}/evaluation", tags=["evaluation"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}", tags=["chat"])

from app.api import tts
app.include_router(tts.router, prefix=f"{settings.API_V1_STR}", tags=["tts"])

from app.api import voices
app.include_router(voices.router, prefix=f"{settings.API_V1_STR}", tags=["voices"])

from app.api import ai
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}/ai", tags=["ai"])

from app.api import characters
app.include_router(characters.router, prefix=f"{settings.API_V1_STR}", tags=["characters"])

from app.api import system
app.include_router(system.router, prefix=f"{settings.API_V1_STR}/system", tags=["system"])

from app.api import model_make
app.include_router(model_make.router, prefix=f"{settings.API_V1_STR}/model-make", tags=["model-make"])

# 레거시 경로 호환성 추가
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}", tags=["legacy"])

@app.get("/")
async def root():
    return {"success": True, "message": "Avatar Forge Backend Running"}

@app.get(f"{settings.API_V1_STR}/system/health")
@app.get("/api/health") # Legacy/Direct health
async def health():
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
    }

@app.get("/api/test")
async def test_connection():
    """연결 테스트 엔드포인트"""
    return {
        "status": "connected",
        "message": "백엔드 서버에 정상적으로 연결되었습니다.",
        "cors_origins": [str(origin) for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else ["*"]
    }
