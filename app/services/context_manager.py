import json
from typing import List, Optional, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import tiktoken
from sqlalchemy import select
from app.core.config import settings
from app.core.llm import call_llm
from app.models.summary import ChatSummary
# Redis는 선택 사항 (ImportError 방지)
try:
    import redis
    redis_available = True
except ImportError:
    redis_available = False

class ContextManager:
    def __init__(self):
        self.is_redis_active = False
        self._memory_store = {} # 1차 캐시 (혹은 최후의 보루)

        # Redis 연결 시도
        if redis_available:
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379")
            try:
                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                self.is_redis_active = True
                print(f"ContextManager: Redis connected at {redis_url}")
            except Exception:
                pass # Redis 실패 시 조용히 넘김

    async def get_summary(self, session_id: str, db: Optional[AsyncSession] = None) -> str:
        """
        요약 조회 우선순위:
        1. Redis (있으면 가장 빠름)
        2. DB (영구 저장소)
        3. Memory (임시)
        """
        summary = ""
        
        # 1. Redis 조회
        if self.is_redis_active:
            try:
                summary = self.redis.get(f"summary:{session_id}")
                if summary: return summary
            except Exception:
                pass

        # 2. DB 조회 (권장)
        if db:
            try:
                stmt = select(ChatSummary).where(ChatSummary.session_id == session_id)
                result = await db.execute(stmt)
                obj = result.scalar_one_or_none()
                if obj and obj.summary:
                    summary = obj.summary
                    # Redis 캐시 갱신 (Write-around 처럼)
                    if self.is_redis_active:
                        self.redis.set(f"summary:{session_id}", summary)
                    return summary
            except Exception as e:
                print(f"DB Load Error: {e}")

        # 3. Memory 조회 (DB 없음 등)
        return self._memory_store.get(f"summary:{session_id}", "")

    async def save_summary(self, session_id: str, summary: str, db: Optional[AsyncSession] = None):
        """
        요약 저장:
        1. DB 저장 (영구)
        2. Redis 저장 (캐시)
        3. Memory 저장 (Fallback)
        """
        # 1. DB 저장
        if db:
            try:
                # Upsert 로직 (있으면 업데이트, 없으면 생성)
                stmt = select(ChatSummary).where(ChatSummary.session_id == session_id)
                result = await db.execute(stmt)
                obj = result.scalar_one_or_none()
                
                if obj:
                    obj.summary = summary
                else:
                    new_obj = ChatSummary(session_id=session_id, summary=summary)
                    db.add(new_obj)
                
                await db.commit()
            except Exception as e:
                print(f"DB Save Error: {e}")
                await db.rollback()

        # 2. Redis 저장
        if self.is_redis_active:
            try:
                self.redis.set(f"summary:{session_id}", summary)
            except Exception:
                pass

        # 3. Memory 저장
        self._memory_store[f"summary:{session_id}"] = summary

    async def manage_context(
        self,
        messages: List[Dict],
        summary: str,
        session_id: str,
        db: Optional[AsyncSession],
        persona: Optional[str],
        max_turns: int,
        max_context: int,
        ratio: float,
    ) -> Tuple[List[Dict], str, bool]:
        """
        턴 기반 슬라이딩 윈도우 + tiktoken 80% 트리거.
        - messages를 {"role":"assistant"|"user", "content"}로 정규화
        - total >= max_context*ratio 이면 K_eff 축소 후 슬라이드·요약·save_summary
        - to_drop이 40개 초과 시 to_drop[-40:]만 요약
        반환: (windowed_messages, summary, did_summarize)
        """
        enc = tiktoken.get_encoding("cl100k_base")
        # 1. 정규화
        normalized = [
            {"role": "assistant" if (m.get("role") == "ai") else m.get("role", "user"), "content": m.get("content", "")}
            for m in messages
        ]
        # 2. 토큰 추정
        sys_est = 600 + len(enc.encode(persona or "")) + len(enc.encode(summary or ""))
        total = sys_est + sum(len(enc.encode(m.get("content", ""))) + 10 for m in normalized)
        # 3. K_eff
        if total >= max_context * ratio:
            k_eff = max(2, max_turns // 2)
        else:
            k_eff = max_turns
        k = 2 * k_eff
        if len(normalized) <= k:
            return (normalized, summary or "", False)
        to_drop = normalized[:-k]
        windowed = normalized[-k:]
        if len(to_drop) > 40:
            to_drop = to_drop[-40:]
        new_summary = await self.summarize_dialogue(to_drop, previous_summary=summary or "")
        await self.save_summary(session_id, new_summary, db)
        return (windowed, new_summary, True)

    async def summarize_dialogue(self, messages: List[Dict[str, str]], previous_summary: str = "") -> str:
        """
        LLM을 사용한 요약 생성 (기존 로직 유지)
        """
        if not messages:
            return previous_summary

        dialogue_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        
        system_prompt = f"""
        당신은 드라마 보조 작가입니다.
        주어진 '이전 줄거리'와 '최근 대화'를 바탕으로, 전체 이야기를 아우르는 **새로운 줄거리 요약본**을 작성하세요.
        
        [규칙]
        1. 현재 상황과 캐릭터 간의 관계 변화를 중심으로 서술하세요.
        2. 분량은 3~5문장으로 요약하세요.
        3. '이전 줄거리'의 내용을 포함하여 흐름이 끊기지 않게 하세요.
        4. 제3자 관점(서술형)으로 작성하세요.
        5. 총 400자 이내로 압축하세요.
        
        [이전 줄거리]
        {previous_summary if previous_summary else "(없음)"}
        """

        messages_payload = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"최근 대화:\n{dialogue_text}"}
        ]

        try:
            result = await call_llm(messages_payload, temperature=0.5, max_tokens=500)
            summary = (result.get("content", "") or "") if isinstance(result, dict) else ""
            return summary.strip()
        except Exception as e:
            print(f"Summarization failed: {e}")
            return previous_summary

context_manager = ContextManager()
