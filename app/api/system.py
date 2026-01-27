from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.config import settings
import httpx
import time
import asyncio

router = APIRouter()

def _health_message(status_code: int, is_ok: bool) -> str:
    """HTTP 응답 시 사용자 친화 메시지. 4xx·5xx도 '연결됨'으로 안내 (연결 가능 여부 기준)."""
    if not is_ok:  # 5xx
        return "연결됨 (5xx 서버 오류)"
    if status_code == 404:
        return "연결됨 (해당 경로 GET 미지원)"
    if status_code == 405:
        return "연결됨 (POST 전용 엔드포인트)"
    if status_code in (400, 422):
        return "연결됨 (파라미터 필요)"
    return f"Status: {status_code}"


async def check_http_service(url: str, timeout: float = 2.0) -> dict:
    """HTTP 서비스 상태 체크 (GET). 루트(/)가 없으면 404 → '연결됨'으로 안내."""
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            latency = (time.time() - start_time) * 1000
            is_ok = response.status_code < 500  # 4xx 정상, 5xx는 메시지만 구분
            # HTTP 응답이 오면 전부 online (연결 가능). 5xx는 메시지로 "서버 오류" 안내
            return {
                "status": "online",
                "latency": round(latency),
                "message": _health_message(response.status_code, is_ok),
            }
    except Exception as e:
        return {
            "status": "offline",
            "latency": 0,
            "message": str(e),
        }

@router.get("/health/detailed")
async def check_system_health(db: AsyncSession = Depends(get_db)):
    """
    모든 연결된 서비스의 상태를 상세하게 반환
    """
    results = {}

    # 1. Database
    db_start = time.time()
    try:
        await db.execute(text("SELECT 1"))
        db_latency = (time.time() - db_start) * 1000
        results["database"] = {
            "name": "PostgreSQL DB",
            "status": "online",
            "latency": round(db_latency),
            "url": "Internal"
        }
    except Exception as e:
        results["database"] = {
            "name": "PostgreSQL DB",
            "status": "offline",
            "latency": 0,
            "message": str(e),
            "url": "Internal"
        }

    # 2. External Services to check
    # (Service Name, URL, Display Name, Timeout 초). TTS/Train은 응답 지연 가능해 5초
    # TTS: /tts GET (파라미터 없으면 422 → 연결 성공 처리)
    tts_health_url = f"{settings.TTS_BASE_URL.rstrip('/')}/{settings.TTS_API_PATH.lstrip('/')}"
    # Server A Files: 프록시 base + /api/health
    files_health_url = f"{settings.SERVER_A_FILES_API_URL.rstrip('/')}/api/health"
    # Server A Train: /api/health GET (200 정상). base는 gpuvoicetrain.duckdns.org
    train_health_url = f"{settings.SERVER_A_TRAINING_API_URL.rstrip('/')}/api/health"
    services = [
        ("ollama", f"{settings.OLLAMA_BASE_URL}", "Ollama (LLM)", 2.0),
        ("tts", tts_health_url, "GPT-SoVITS (TTS)", 5.0),
        ("server_a_files", files_health_url, "Server A (Files)", 2.0),
        ("server_a_train", train_health_url, "Server A (Train)", 5.0),
    ]

    # Run checks in parallel (서비스별 timeout 적용)
    tasks = [check_http_service(url, t) for (_, url, _, t) in services]
    checks = await asyncio.gather(*tasks)

    for i, (key, url, name, _) in enumerate(services):
        res = checks[i]
        res["name"] = name
        # Server A (Files/Train)는 표시용으로 base만
        if key == "server_a_files":
            res["url"] = settings.SERVER_A_FILES_API_URL.rstrip("/")
        elif key == "server_a_train":
            res["url"] = settings.SERVER_A_TRAINING_API_URL.rstrip("/")
        else:
            res["url"] = url
        results[key] = res

    return {
        "success": True,
        "timestamp": time.time(),
        "services": results
    }
