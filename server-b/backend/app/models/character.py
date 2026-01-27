from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base

class Character(Base):
    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True) # Text 처럼 큰건 아니지만 255면 충분한가? generation.py는 Text사용. Text로 변경하는게 안전할듯
    
    # 페르소나 및 음성 설정
    persona = Column(Text, nullable=True)
    voice_id = Column(String(100), nullable=True)
    
    # 카테고리 및 태그
    category = Column(String(50), nullable=True)
    tags = Column(Text, nullable=True)  # JSON 문자열로 저장 (generation.py에서 옴)
    
    # 샘플 대화 및 이미지
    sample_dialogue = Column(Text, nullable=True)  # 샘플 대화 (generation.py에서 옴)
    image_url = Column(String(255), nullable=True)
    
    # 3D 모델 관련 (generation.py에서 옴)
    model_url = Column(String(255), nullable=True)
    thumbnail_url = Column(String(255), nullable=True)

    is_preset = Column(Boolean, default=False)
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationship to user
    user = relationship("User", back_populates="characters")
