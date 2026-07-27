from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime, Date, func
from app.db.database import Base

class Petition(Base):
    __tablename__ = "PETITION"

    petition_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    received_at = Column(DateTime, nullable=True)
    status_code = Column(String(10), nullable=True)
    task_id = Column(Integer, ForeignKey("TASK.task_id"), nullable=True)  # 👈 외래키 추가 및 대문자 통일
    department_code = Column(String(10), ForeignKey("DEPARTMENT.department_code"), nullable=True)
    assignee_user_id = Column(String(50), ForeignKey("USER.user_id"), nullable=True)  # 👈 "user"를 대문자 "USER"로 수정
    manual_answer = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())