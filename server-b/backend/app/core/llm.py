import httpx
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

async def call_llm(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 512
) -> Dict[str, Any]:
    """
    공통 LLM 호출 함수 (Ollama 기반)
    """
    if model is None:
        model = "gemma-3-27b-it" # 기본 모델

    api_path = getattr(settings, 'OLLAMA_API_PATH', "/api/chat")
    base_url = settings.OLLAMA_BASE_URL.rstrip('/')
    if not api_path.startswith('/'):
        api_path = '/' + api_path
    api_url = f"{base_url}{api_path}"
    
    request_data = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    
    if temperature != 0.7 or max_tokens != 512:
        request_data["options"] = {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    
    try:
        ssl_verify = getattr(settings, 'OLLAMA_SSL_VERIFY', False)
        
        async with httpx.AsyncClient(
            timeout=120.0,
            verify=ssl_verify
        ) as client:
            response = await client.post(
                api_url,
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            if "message" not in result:
                raise KeyError("Ollama 응답에 'message' 필드가 없습니다.")
            
            message = result["message"]
            content = message.get("content", "(응답이 비어있습니다.)")
            
            return {
                "content": content.strip(),
                "usage": {
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "completion_tokens": result.get("eval_count", 0)
                }
            }
    except Exception as e:
        logger.error(f"LLM 호출 실패: {e}")
        raise
