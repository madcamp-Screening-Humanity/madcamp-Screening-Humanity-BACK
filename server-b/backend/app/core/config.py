from typing import List, Union, Optional
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
    
    # Frontend URL (OAuth 콜백 리다이렉트용)
    FRONTEND_URL: str = "http://localhost:3000"

    # LLM 서비스 설정
    # "vllm" 또는 "ollama" 중 선택 (동시 실행 불가, VRAM 제약)
    # 현재 기본값: ollama (vLLM 코드는 주석 처리되어 있음)
    LLM_SERVICE: str = "ollama"
    
    # vLLM API 설정 (OpenAI 호환)
    # 엔드포인트: /v1/chat/completions
    # NPM 프록시 예시: https://llm.server-a.local
    # 직접 접근 예시: http://server-a:8002
    VLLM_BASE_URL: str = "http://localhost:8002"  # vLLM 서비스 기본 URL (포트 8002)
    
    # Ollama API 설정
    # 엔드포인트: /api/chat
    # NPM 프록시 예시: https://ollama.server-a.local
    # 직접 접근 예시: http://server-a:11434
    OLLAMA_BASE_URL: str = "http://localhost:11434"  # Ollama 서비스 기본 URL (포트 11434)
    
    # GPT-SoVITS TTS API 설정
    # 엔드포인트: /tts (POST/GET)
    # NPM 프록시 예시: https://tts.server-a.local
    # 직접 접근 예시: http://server-a:9880
    TTS_BASE_URL: str = "http://localhost:9880"  # GPT-SoVITS TTS 서비스 기본 URL (포트 9880, api_v2.py)
    
    # Paths (Configurable for Windows/Ubuntu)
    SHARED_MODELS_DIR: str = "/mnt/shared_models"
    USER_ASSETS_DIR: str = "/mnt/user_assets"

    model_config = SettingsConfigDict(
        env_file=".env", 
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
