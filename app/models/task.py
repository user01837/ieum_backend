from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, DateTime, func
from app.db.database import Base

class Task(Base):
    __tablename__ = "TASK"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    department_code = Column(String(10), ForeignKey("DEPARTMENT.department_code"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)