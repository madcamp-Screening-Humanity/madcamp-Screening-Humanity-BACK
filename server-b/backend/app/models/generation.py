from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float, Integer, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base

class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True) # Nullable for anonymous if needed
    
    job_type = Column(String(20), nullable=False) # '3d', 'style', 'tts'
    status = Column(String(20), default="pending") # 'pending', 'processing', 'completed', 'failed'
    
    input_payload = Column(Text, nullable=True) # JSON string of inputs or path to input file
    
    result_url = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    
    progress = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class Character(Base):
    __tablename__ = "characters"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # 사전설정 캐릭터는 user_id가 None
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # 페르소나 및 음성 설정
    persona = Column(Text, nullable=True)  # 캐릭터 성격 설명
    voice_id = Column(String(50), nullable=True)  # TTS 음성 ID
    
    # 사전설정 캐릭터 여부
    is_preset = Column(Boolean, default=False, nullable=False)
    
    # 카테고리 및 태그
    category = Column(String(50), nullable=True)  # 애니메이션, 소설, 영화 등
    tags = Column(Text, nullable=True)  # JSON 문자열로 저장
    
    # 샘플 대화 및 이미지
    sample_dialogue = Column(Text, nullable=True)  # 샘플 대화 텍스트
    image_url = Column(String(255), nullable=True)  # 로컬 assets 경로
    
    # 기존 필드
    model_url = Column(String(255), nullable=True) # GLB path
    thumbnail_url = Column(String(255), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
