from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base

class Character(Base):
    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    persona = Column(Text, nullable=True)
    voice_id = Column(String(100), nullable=True)
    category = Column(String(50), nullable=True)
    image_url = Column(String(255), nullable=True)
    is_preset = Column(Boolean, default=False)
    
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationship to user
    user = relationship("User", back_populates="characters")
