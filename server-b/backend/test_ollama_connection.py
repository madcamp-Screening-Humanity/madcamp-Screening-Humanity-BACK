"""
Ollama API 연결 테스트 스크립트

사용법:
    python test_ollama_connection.py

환경 변수 설정:
    OLLAMA_BASE_URL=http://localhost:11434  (기본값)
    또는
    OLLAMA_BASE_URL=http://gpugpt.duckdns.org
"""

import os
import sys
import asyncio
import httpx
from typing import Optional

# Ollama API URL (환경 변수 또는 기본값)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


async def test_ollama_version() -> bool:
    """Ollama 버전 정보 확인"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/version")
            response.raise_for_status()
            version_info = response.json()
            print(f"✅ Ollama 버전 확인 성공: {version_info}")
            return True
    except httpx.ConnectError:
        print(f"❌ Ollama 서버에 연결할 수 없습니다: {OLLAMA_BASE_URL}")
        print("   서버가 실행 중인지 확인하세요.")
        return False
    except Exception as e:
        print(f"❌ 버전 확인 실패: {e}")
        return False


async def test_ollama_models() -> Optional[list]:
    """사용 가능한 모델 목록 조회"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            models_data = response.json()
            models = [model["name"] for model in models_data.get("models", [])]
            print(f"✅ 사용 가능한 모델 목록:")
            for model in models:
                print(f"   - {model}")
            return models
    except Exception as e:
        print(f"❌ 모델 목록 조회 실패: {e}")
        return None


async def test_ollama_chat(model: str = "gemma-3-27b-it") -> bool:
    """Ollama 채팅 API 테스트"""
    try:
        api_url = f"{OLLAMA_BASE_URL}/api/chat"
        print(f"\n📤 채팅 API 테스트 중... (모델: {model})")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                api_url,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "당신은 친절한 AI 어시스턴트입니다."},
                        {"role": "user", "content": "안녕하세요! 간단히 인사만 해주세요."}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 50
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ 채팅 API 테스트 성공!")
            print(f"   응답: {result.get('message', {}).get('content', 'N/A')}")
            print(f"   프롬프트 토큰: {result.get('prompt_eval_count', 0)}")
            print(f"   생성 토큰: {result.get('eval_count', 0)}")
            return True
    except httpx.ConnectError:
        print(f"❌ Ollama 서버에 연결할 수 없습니다: {OLLAMA_BASE_URL}")
        return False
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"❌ 모델 '{model}'을 찾을 수 없습니다.")
            print("   모델이 등록되어 있는지 확인하세요.")
        else:
            print(f"❌ HTTP 오류: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ 채팅 API 테스트 실패: {e}")
        return False


async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("Ollama API 연결 테스트")
    print("=" * 60)
    print(f"Ollama URL: {OLLAMA_BASE_URL}\n")
    
    # 1. 버전 확인
    print("1️⃣  Ollama 버전 확인...")
    version_ok = await test_ollama_version()
    if not version_ok:
        print("\n❌ Ollama 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        sys.exit(1)
    
    # 2. 모델 목록 조회
    print("\n2️⃣  사용 가능한 모델 목록 조회...")
    models = await test_ollama_models()
    
    # 3. 채팅 API 테스트
    if models:
        # 첫 번째 모델로 테스트 (또는 gemma-3-27b-it)
        test_model = "gemma-3-27b-it" if "gemma-3-27b-it" in models else models[0]
        print(f"\n3️⃣  채팅 API 테스트 (모델: {test_model})...")
        chat_ok = await test_ollama_chat(test_model)
        
        if chat_ok:
            print("\n" + "=" * 60)
            print("✅ 모든 테스트 통과! Ollama API가 정상적으로 작동합니다.")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("❌ 채팅 API 테스트 실패")
            print("=" * 60)
            sys.exit(1)
    else:
        print("\n⚠️  모델 목록을 가져올 수 없어 채팅 테스트를 건너뜁니다.")


if __name__ == "__main__":
    asyncio.run(main())
