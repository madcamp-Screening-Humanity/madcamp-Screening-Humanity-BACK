from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(100), unique=True, index=True, nullable=False)
    username = Column(String(50), nullable=True) # From Google Name
    picture = Column(String(255), nullable=True) # Profile Picture
    
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    provider = Column(String(20), default="google") # 'google'
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
