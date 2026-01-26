from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, generate
from contextlib import asynccontextmanager

# Lifecycle for DB creation
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        # Create tables
        # Import models so they are registered
        from app.models import user, generation, character
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(generate.router, prefix=f"{settings.API_V1_STR}/generate", tags=["generate"])

from app.api import chat, characters, story
app.include_router(characters.router, prefix=f"{settings.API_V1_STR}/characters", tags=["characters"])
app.include_router(story.router, prefix=f"{settings.API_V1_STR}/story", tags=["story"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}", tags=["chat"])

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
