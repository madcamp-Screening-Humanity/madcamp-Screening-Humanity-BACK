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
        from app.models import user, generation
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
app.include_router(generate.router, prefix=f"{settings.API_V1_STR}", tags=["generate"])

from app.api import chat
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}", tags=["chat"])

@app.get("/")
async def root():
    return {"message": "Avatar Forge Backend Running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}
