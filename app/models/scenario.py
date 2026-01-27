from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base

class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True) # dev-user etc
    
    # Metadata
    user_name = Column(String(100), nullable=True) # 당시 설정한 사용자 이름
    character_name = Column(String(100), nullable=True) # 당시 설정한 캐릭터 이름
    situation = Column(Text, nullable=True) # 입력받은 상황 키워드
    
    # Generated Content
    summary = Column(Text, nullable=True) # 1줄 요약
    background = Column(Text, nullable=True) # 구체적 배경 설정 (AI System Prompt용)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User", back_populates="scenarios")
    # ChatMessages linked manually by session_id or similar logic if needed, 
    # but currently Scenario is just the setup.
