from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class ChatSummary(Base):
    __tablename__ = "chat_summaries"

    session_id = Column(String(100), primary_key=True, index=True)
    summary = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
