from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from app.db.database import Base

class ProjectMember(Base):
    __tablename__ = "PROJECT_MEMBER"

    project_member_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id        = Column(Integer, ForeignKey("PROJECT.project_id"), nullable=False)  # 👈 외래키 추가
    user_id           = Column(Integer, ForeignKey("USER.user_id"), nullable=False)     # 👈 외래키 추가
    role_code         = Column(String(10), nullable=True)
    invited_by        = Column(Integer, ForeignKey("USER.user_id"), nullable=True)      # 👈 외래키 추가
    joined_at         = Column(DateTime, nullable=False, server_default=func.now())