from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base


class Character(Base):
    """
    캐릭터 모델
    사용자가 생성한 캐릭터 정보를 저장합니다.
    """
    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    
    # 페르소나 설정
    persona = Column(Text, nullable=True)
    
    # 음성 설정 (Voice 모델과 연동)
    voice_id = Column(String(36), ForeignKey("voices.id"), nullable=True)
    
    # 카테고리 및 태그
    category = Column(String(50), nullable=True)
    tags = Column(Text, nullable=True)  # JSON 문자열로 저장
    
    # 샘플 대화 및 이미지
    sample_dialogue = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)
    
    # 3D 모델 관련
    model_url = Column(String(255), nullable=True)
    thumbnail_url = Column(String(255), nullable=True)

    is_preset = Column(Boolean, default=False)
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationship
    user = relationship("User", back_populates="characters")
    voice = relationship("Voice", back_populates="characters")
