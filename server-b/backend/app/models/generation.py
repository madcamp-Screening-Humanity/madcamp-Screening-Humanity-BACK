from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float, Integer
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
    user_id = Column(String(36), ForeignKey("users.id"))
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    model_url = Column(String(255), nullable=True) # GLB path
    thumbnail_url = Column(String(255), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
