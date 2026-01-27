# 사용자별 설정 (TTS 등) 저장
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy import JSON
from app.core.database import Base


class UserPreference(Base):
    """사용자별 앱 설정 (tts_mode, tts_delay_ms, tts_streaming_mode, tts_enabled, tts_speed 등)"""
    __tablename__ = "user_preferences"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    settings = Column(JSON, nullable=False, default=lambda: {})
