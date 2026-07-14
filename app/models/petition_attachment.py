from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.db.database import Base

class PetitionAttachment(Base):
    __tablename__ = "petition_attachment"

    attachment_id = Column(Integer, primary_key=True, index=True)
    petition_id = Column(Integer, ForeignKey("PETITION.petition_id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    is_staff_upload = Column(Boolean, nullable=False, default=False)