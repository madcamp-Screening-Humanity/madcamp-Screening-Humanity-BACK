# Redis Queue 사용 중단에 따른 주석 처리
# import json
# import uuid
# import asyncio
# import time
# from typing import AsyncGenerator, Dict, Any, Optional
# from app.core.redis import get_redis_client
# from app.core.config import settings
# 
# async def submit_tts_job(
#     request_body: Dict[str, Any],
#     gpt_weights_path: Optional[str] = None,
#     sovits_weights_path: Optional[str] = None,
#     priority: str = "realtime"
# ) -> str:
#     """
#     TTS 작업을 Redis Queue에 등록하고 job_id 반환
#     priority: 'realtime' | 'delayed' | 'on_click'
#     """
#     redis = get_redis_client()
#     job_id = str(uuid.uuid4())
#     
#     # 작업 명세
#     job_payload = {
#         "job_id": job_id,
#         "gpt_weights_path": gpt_weights_path,
#         "sovits_weights_path": sovits_weights_path,
#         "request_body": request_body,
#         "timestamp": time.time()
#     }
#     
#     # 큐 키 (우선순위별)
#     # priority 검증
#     if priority not in ["realtime", "delayed", "on_click"]:
#         priority = "realtime"
#         
#     queue_key = f"tts:queue:{priority}"
#     
#     # 작업 등록 (LPUSH)
#     await redis.lpush(queue_key, json.dumps(job_payload))
#     
#     # 큐 크기 제한 체크 (옵션)
#     # q_len = await redis.llen(queue_key)
#     
#     return job_id
# 
# async def tts_stream_generator(job_id: str) -> AsyncGenerator[bytes, None]:
#     """
#     Redis Stream을 구독하여 실시간 오디오 청크를 yield
#     """
#     redis = get_redis_client()
#     stream_key = f"tts:stream:{job_id}"
#     last_id = "0-0"
#     
#     start_time = time.time()
#     timeout = settings.TTS_QUEUE_JOB_TIMEOUT
#     
#     try:
#         while True:
#             # 전체 타임아웃 체크 (너무 오래 걸리면 중단)
#             if time.time() - start_time > timeout:
#                 print(f"Stream timeout for job {job_id}")
#                 yield b"" 
#                 break
#             
#             # XREAD (Blocking 1초)
#             # streams={key: last_id}
#             try:
#                 response = await redis.xread({stream_key: last_id}, count=None, block=1000)
#             except Exception as e:
#                 print(f"Redis XREAD error: {e}")
#                 break
#             
#             if not response:
#                 continue
#                 
#             # response format: [[key, [(id, fields), ...]], ...]
#             _, messages = response[0]
#             
#             for msg_id, fields in messages:
#                 last_id = msg_id
#                 
#                 # fields는 binary dict {b'data': b'...', b'type': b'...'}
#                 # 데이터 타입 확인
#                 msg_type = fields.get(b'type', b'chunk').decode('utf-8')
#                 
#                 if msg_type == 'eof':
#                     return
#                 
#                 if msg_type == 'error':
#                     error_msg = fields.get(b'message', b'Unknown error').decode('utf-8')
#                     print(f"TTS Worker Error for job {job_id}: {error_msg}")
#                     # 에러 발생 시 스트림 종료 (클라이언트에는 끊긴 오디오 전송됨)
#                     return
#                 
#                 data = fields.get(b'data')
#                 if data:
#                     yield data
#                     
#     finally:
#         # 스트림 키 삭제 (Cleanup) 및 만료 설정
#         # Worker가 expire를 걸지만, 확실히 하기 위해 여기서도 삭제 시도 가능
#         # 하지만 XREAD 도중 끊길 수 있으므로 expire에 의존하는 것이 안전함.
#         # 여기서는 명시적 삭제보다는 안전하게 놔둠 (Worker가 expire 검)
#         pass