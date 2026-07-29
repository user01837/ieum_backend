from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from app.db.database import Base


class Announcement(Base):
    __tablename__ = "ANNOUNCEMENT"

    announcement_id = Column(Integer, primary_key=True, autoincrement=True)
    title           = Column(String(200), nullable=False)
    content         = Column(Text, nullable=False)
    is_pinned       = Column(Boolean, nullable=False, default=False)
    is_deleted      = Column(Boolean, nullable=False, default=False)
    deleted_at      = Column(DateTime, nullable=True)
    created_by      = Column(Integer, ForeignKey("USER.user_id"), nullable=False)
    updated_by      = Column(Integer, ForeignKey("USER.user_id"), nullable=True)
    created_at      = Column(DateTime, nullable=False, server_default=func.now())
    updated_at      = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())