import asyncio
import json
import httpx
import redis.asyncio as redis
import os
import sys

# 프로젝트 루트를 sys.path에 추가하여 app 모듈을 찾을 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import settings

# Worker 상태 (현재 로드된 모델)
_current_gpt_path: str = None
_current_sovits_path: str = None

async def run_worker():
    """
    TTS Worker 메인 루프
    Redis 큐(BRPOP) -> set_weights -> POST /tts (stream) -> Redis Stream(XADD)
    """
    global _current_gpt_path, _current_sovits_path
    
    print(f"Connecting to Redis: {settings.REDIS_URL}")
    redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=False)
    client = httpx.AsyncClient(timeout=None) # 타임아웃 없음 (스트리밍 위해)
    
    print("TTS Worker started. Waiting for jobs...")
    
    try:
        while True:
            # 1. Job 수신 (Priority: realtime > delayed > on_click)
            keys = [
                "tts:queue:realtime",
                "tts:queue:delayed",
                "tts:queue:on_click"
            ]
            
            # BRPOP: (key, value) 튜플 반환. 타임아웃 0(무한 대기)
            try:
                # redis-py의 brpop은 타임아웃 0이면 무한대기
                # 연결이 끊어지면 예외 발생 -> 아래 catch
                result = await redis_client.brpop(keys, timeout=0)
                if not result:
                    continue
                    
                queue_key, job_data = result
                # job_data는 bytes일 수 있으므로 decode
                if isinstance(job_data, bytes):
                    job_data = job_data.decode('utf-8')
                    
                job = json.loads(job_data)
                
                job_id = job["job_id"]
                gpt_path = job.get("gpt_weights_path")
                sovits_path = job.get("sovits_weights_path")
                request_body = job["request_body"]
                
                stream_key = f"tts:stream:{job_id}"
                
                print(f"Processing job {job_id} from {queue_key}")
                
                # 2. 모델 교체 (필요 시)
                tts_base = settings.TTS_BASE_URL.rstrip('/')
                
                if gpt_path and gpt_path != _current_gpt_path:
                    try:
                        print(f"Setting GPT weights: {gpt_path}")
                        resp = await client.get(f"{tts_base}/set_gpt_weights", params={"weights_path": gpt_path})
                        if resp.status_code == 200:
                            _current_gpt_path = gpt_path
                        else:
                            print(f"Failed to set GPT weights: {resp.text}")
                    except Exception as e:
                        print(f"Error setting GPT weights: {e}")

                if sovits_path and sovits_path != _current_sovits_path:
                    try:
                        print(f"Setting SoVITS weights: {sovits_path}")
                        resp = await client.get(f"{tts_base}/set_sovits_weights", params={"weights_path": sovits_path})
                        if resp.status_code == 200:
                            _current_sovits_path = sovits_path
                        else:
                            print(f"Failed to set SoVITS weights: {resp.text}")
                    except Exception as e:
                        print(f"Error setting SoVITS weights: {e}")

                # 3. TTS 요청 (Streaming)
                # request_body에서 가중치 정보 제거
                request_body.pop("gpt_weights", None)
                request_body.pop("sovits_weights", None)
                
                # streaming_mode 강제 확인 (Worker는 항상 스트림으로 처리하여 Relay)
                # 하지만 Client가 streaming_mode=0을 원할 수도 있음.
                # Server A는 streaming_mode 파라미터에 따라 청크를 다르게 줄 수 있음.
                # 여기서는 Server A가 주는 대로 받아서 Relay 함.
                
                tts_url = f"{tts_base}/{settings.TTS_API_PATH.lstrip('/')}"
                
                try:
                    async with client.stream("POST", tts_url, json=request_body) as response:
                        if response.status_code != 200:
                            # 에러 발생
                            error_text = await response.read()
                            err_msg = f"Server A error: {response.status_code} {error_text.decode('utf-8', errors='ignore')}"
                            print(err_msg)
                            await redis_client.xadd(stream_key, {
                                "type": "error",
                                "message": err_msg
                            })
                        else:
                            # 4. 청크 중계 (Relay)
                            chunk_count = 0
                            async for chunk in response.aiter_bytes():
                                if chunk:
                                    chunk_count += 1
                                    await redis_client.xadd(stream_key, {
                                        "type": "chunk",
                                        "data": chunk
                                    })
                            
                            # 5. 완료 (EOF)
                            await redis_client.xadd(stream_key, {"type": "eof"})
                            print(f"Job {job_id} completed. {chunk_count} chunks relayed.")
                            
                except Exception as e:
                    print(f"TTS Request failed: {e}")
                    await redis_client.xadd(stream_key, {
                        "type": "error",
                        "message": str(e)
                    })
                    
                # 결과 TTL 설정 (스트림 키 자동 만료)
                await redis_client.expire(stream_key, 60) 

            except redis.ConnectionError:
                print("Redis connection lost. Retrying in 1s...")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Worker loop error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(1)
                
    finally:
        await client.aclose()
        await redis_client.close()

if __name__ == "__main__":
    # 윈도우/Python 3.8+ asyncio 정책
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_worker())