from sqlalchemy import Column, String, Integer, Text, Date, DateTime, func
from app.db.database import Base

class Project(Base):
    __tablename__ = "project"

    project_id       = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String(200), nullable=False)
    stage_code       = Column(String(10), nullable=True)
    task_id          = Column(Integer, nullable=True)
    department_code  = Column(String(10), nullable=True)
    deadline         = Column(Date, nullable=True)
    start_date       = Column(Date, nullable=True)
    business_content = Column(Text, nullable=True)
    overview         = Column(Text, nullable=True)
    report_content   = Column(Text, nullable=True)
    approved_at      = Column(DateTime, nullable=True)
    created_at       = Column(DateTime, nullable=False, server_default=func.now())
    updated_at       = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())