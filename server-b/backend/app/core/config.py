from typing import List, Union, Optional
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Avatar Forge Backend"
    API_V1_STR: str = "/api"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000"]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            # JSON 배열 형식 파싱: ["http://localhost:3000","http://localhost:8000"]
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    # JSON 파싱 실패 시 쉼표로 분리
                    return [i.strip().strip('"').strip("'") for i in v.strip("[]").split(",") if i.strip()]
            # 쉼표로 구분된 문자열: http://localhost:3000,http://localhost:8000
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(origin) for origin in v]
        return []

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
    
    # AI API Keys
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    
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
    # VLLM_BASE_URL: str = "http://localhost:8002"  # vLLM 서비스 기본 URL (포트 8002)
    
    # Ollama API 설정
    # 엔드포인트: /api/chat
    # NPM 프록시 예시: https://ollama.server-a.local 또는 http://gpugpt.duckdns.org
    # 직접 접근 예시: http://server-a:11434
    OLLAMA_BASE_URL: str = "http://gpugpt.duckdns.org"  # Ollama 서비스 기본 URL (리버스 프록시 사용)
    OLLAMA_API_PATH: str = "/api/chat"  # Ollama API 경로 (리버스 프록시 경로 포함 가능, 예: "/ollama/api/chat")
    OLLAMA_SSL_VERIFY: bool = False  # SSL 인증서 검증 (개발 환경: False, 프로덕션: True)
    
    # GPT-SoVITS TTS API 설정
    # 엔드포인트: /tts (POST/GET)
    # NPM 프록시 예시: https://tts.server-a.local
    # 직접 접근 예시: http://server-a:9880
    TTS_BASE_URL: str = "http://gpusovitsapi.duckdns.org"  # GPT-SoVITS TTS 서비스 기본 URL (포트 9880, api_v2.py)
    TTS_API_PATH: str = "tts"  # TTS API 경로 (프록시 경로 포함 가능, 예: "tts/tts")
    TTS_TIMEOUT: float = 120.0  # TTS API 호출 타임아웃 (초)
    TTS_MAX_TEXT_LENGTH: int = 10000  # 텍스트 길이 제한 (자)
    TTS_MAX_FILE_SIZE: int = 52428800  # 생성된 오디오 파일 크기 제한 (바이트, 기본 50MB)
    TTS_SSL_VERIFY: bool = False  # SSL 인증서 검증 (개발 환경: False, 프로덕션: True)
    
    # 관리자 설정
    # 관리자 권한이 있는 이메일 목록 (쉼표로 구분)
    # 예: "admin@example.com,manager@example.com"
    ADMIN_EMAILS: str = ""
    
    def is_admin(self, email: str) -> bool:
        """이메일이 관리자 목록에 있는지 확인"""
        if not self.ADMIN_EMAILS:
            return False
        admin_list = [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]
        return email.lower() in admin_list
    
    # Server A 파일 스캔 API (GPT-SoVITS 모델/음성 파일 조회용)
    SERVER_A_FILES_API_URL: str = "http://gpusovitsapi.duckdns.org:10001"
    
    # Paths (Configurable for Windows/Ubuntu)
    SHARED_MODELS_DIR: str = "/mnt/shared_models"
    USER_ASSETS_DIR: str = "/mnt/user_assets"

    model_config = SettingsConfigDict(
        env_file=".env", 
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
