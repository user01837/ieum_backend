from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from app.db.database import Base


class Notification(Base):
    __tablename__ = "NOTIFICATION"

    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("USER.user_id"), nullable=False)
    type = Column(String(20), nullable=False)
    room_id = Column(Integer, ForeignKey("CHAT_ROOM.room_id"), nullable=True)
    message_id = Column(Integer, ForeignKey("CHAT_MESSAGE.message_id"), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
