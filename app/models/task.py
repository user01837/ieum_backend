from sqlalchemy import Column, String, Integer, ForeignKey
from app.db.database import Base

class Task(Base):
    __tablename__ = "TASK"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    department_code = Column(String(10), ForeignKey("DEPARTMENT.department_code"), nullable=True)