from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(100), index=True, nullable=False) # 채팅 세션 ID (UUID)
    
    role = Column(String(20), nullable=False) # user, assistant, system
    content = Column(Text, nullable=False)
    
    # Optional metadata
    character_name = Column(String(100), nullable=True) # 화자 이름 (AI인 경우)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
