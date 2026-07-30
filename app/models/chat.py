from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, func
from app.db.database import Base
from sqlalchemy.orm import Session, relationship

class ChatRoom(Base):
    __tablename__ = "CHAT_ROOM"

    room_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=True)
    is_group = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, ForeignKey("USER.user_id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ChatRoomMember(Base):
    __tablename__ = "CHAT_ROOM_MEMBER"

    room_id = Column(Integer, ForeignKey("CHAT_ROOM.room_id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("USER.user_id"), primary_key=True)
    joined_at = Column(DateTime, nullable=False, server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "CHAT_MESSAGE"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("CHAT_ROOM.room_id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("USER.user_id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    attachments = relationship("ChatMessageAttachment", back_populates="message")
