from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.db.database import Base

class ChatMessageAttachment(Base):
    __tablename__ = "CHAT_MESSAGE_ATTACHMENT"

    attachment_id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("CHAT_MESSAGE.message_id"))
    file_url = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())

    message = relationship("ChatMessage", back_populates="attachments")