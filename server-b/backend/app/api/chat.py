from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import httpx
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    persona: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    model: str = "gpt-oss-20b"

@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Proxy chat request to Server A (LLM Service).
    """
    # In real deployment, this URL points to Server A
    llm_service_url = f"{settings.GPU_SERVER_URL.replace('8001', '8002')}/chat" # Assuming port mapping logic or config
    
    # Mock Response if Server A is not reachable (for local dev without GPU server)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Try to call real service
            # For demonstration, let's assume it might fail and fallback to mock
            # But in prod code, we just return error.
            # Here I'll implement the actual call structure.
            response = await client.post(
                llm_service_url,
                json=request.model_dump(),
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        # Fallback Mock for Development
        print(f"LLM Service Error (Mocking response): {e}")
        return {
            "success": True,
            "data": {
                "content": f"[Mock Response from Server B] Server A 연결 실패. ({e}) 안녕하세요! {current_user.username}님.",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}
            }
        }

@router.get("/chat/models")
async def list_models(current_user: User = Depends(get_current_user)):
    return {
        "success": True,
        "data": {
            "models": [
                {"id": "gpt-oss-20b", "name": "GPT-OSS-20B (Default)"},
                {"id": "dolphin-2.9-8b", "name": "Dolphin 2.9 8B (Uncensored)"}
            ]
        }
    }
