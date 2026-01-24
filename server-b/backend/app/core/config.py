from typing import List, Union
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Avatar Forge Backend"
    API_V1_STR: str = "/api"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    # Default to sqlite for dev if postgres not provided
    DATABASE_URL: str = "sqlite+aiosqlite:///./avatar_forge.db" 

    # JWT
    SECRET_KEY: str = "YOUR_SECRET_KEY_HERE_CHANGE_IN_PROD"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # External Services (Server A)
    GPU_SERVER_URL: str = "http://localhost:8001" 
    
    # Paths (Configurable for Windows/Ubuntu)
    SHARED_MODELS_DIR: str = "/mnt/shared_models"
    USER_ASSETS_DIR: str = "/mnt/user_assets"

    model_config = SettingsConfigDict(
        env_file=".env", 
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
