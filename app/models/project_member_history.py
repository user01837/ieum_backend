from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.database import Base

class ProjectMemberHistory(Base):
    __tablename__ = "PROJECT_MEMBER_HISTORY"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False)
    from_user_id = Column(Integer, nullable=True)
    to_user_id = Column(Integer, nullable=True)
    change_type = Column(String(2), nullable=False, default="01")
    changed_at = Column(DateTime, nullable=False, server_default=func.now())