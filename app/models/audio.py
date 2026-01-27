from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class AudioFile(Base):
    """오디오 파일 메타데이터 모델"""
    __tablename__ = "audio_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # 파일 정보
    file_path = Column(String(500), nullable=False)  # 저장 경로
    file_url = Column(String(500), nullable=False)  # 접근 URL
    file_size = Column(Integer, nullable=False)  # 파일 크기 (바이트)
    duration = Column(Float, nullable=True)  # 재생 시간 (초)
    format = Column(String(10), nullable=False)  # wav, ogg, aac, raw
    
    # TTS 정보
    voice_id = Column(String(50), nullable=True)  # 사용된 voice_id
    text_hash = Column(String(64), nullable=True, index=True)  # 텍스트 해시 (SHA256, 캐싱용)
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
