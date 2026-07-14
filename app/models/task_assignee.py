from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from app.db.database import Base

class TaskAssignee(Base):
    __tablename__ = "task_assignee"

    task_assignee_id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task.task_id"), nullable=False)
    # user.user_id가 String이므로, DB 스키마와 일관성을 위해 String으로 정의합니다.
    user_id = Column(String(50), ForeignKey("user.user_id"), nullable=False)
    assigned_at = Column(DateTime, nullable=False, server_default=func.now())