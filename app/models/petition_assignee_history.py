from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from app.db.database import Base

class PetitionAssigneeHistory(Base):
    __tablename__ = "PETITION_ASSIGNEE_HISTORY"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    petition_id = Column(Integer, ForeignKey("PETITION.petition_id"), nullable=False)
    from_user_id = Column(String(50), ForeignKey("USER.user_id"), nullable=True)
    to_user_id = Column(String(50), ForeignKey("USER.user_id"), nullable=True)
    change_type = Column(String(2), nullable=False)
    changed_at = Column(DateTime, nullable=False, server_default=func.now())