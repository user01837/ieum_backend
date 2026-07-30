from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base

class AnnouncementAttachment(Base):
    __tablename__ = "ANNOUNCEMENT_ATTACHMENT"

    attachment_id = Column(Integer, primary_key=True, autoincrement=True)
    announcement_id = Column(Integer, ForeignKey("ANNOUNCEMENT.announcement_id"))
    file_url = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    announcement = relationship("Announcement", back_populates="attachments")