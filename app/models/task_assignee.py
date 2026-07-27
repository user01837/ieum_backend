from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from app.db.database import Base

class TaskAssignee(Base):
    __tablename__ = "TASK_ASSIGNEE"

    task_assignee_id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("TASK.task_id"), nullable=False)   # 👈 "task" -> 대문자 "TASK"로 수정
    user_id = Column(String(50), ForeignKey("USER.user_id"), nullable=False) # 👈 "user" -> 대문자 "USER"로 수정
    assigned_at = Column(DateTime, nullable=False, server_default=func.now())