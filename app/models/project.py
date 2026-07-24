from sqlalchemy import Column, String, Integer, Text, Date, DateTime, ForeignKey, func
from app.db.database import Base

class Project(Base):
    __tablename__ = "PROJECT"

    project_id            = Column(Integer, primary_key=True, autoincrement=True)
    name                  = Column(String(200), nullable=False)
    stage_code            = Column(String(10), nullable=True)
    task_id               = Column(Integer, ForeignKey("TASK.task_id"), nullable=True)             # 👈 외래키 추가
    department_code       = Column(String(10), ForeignKey("DEPARTMENT.department_code"), nullable=True) # 👈 외래키 추가
    deadline              = Column(Date, nullable=True)
    start_date            = Column(Date, nullable=True)
    business_content      = Column(Text, nullable=True)
    overview              = Column(Text, nullable=True)
    report_content        = Column(Text, nullable=True)
    sec_overview          = Column(Text, nullable=True)
    sec_background        = Column(Text, nullable=True)
    sec_goals             = Column(Text, nullable=True)
    sec_detailed_plan     = Column(Text, nullable=True)
    sec_schedule          = Column(Text, nullable=True)
    sec_execution_system  = Column(Text, nullable=True)
    sec_budget            = Column(Text, nullable=True)
    sec_expected_effect   = Column(Text, nullable=True)
    sec_post_management   = Column(Text, nullable=True)
    cover_title           = Column(String(200), nullable=True)
    approved_at           = Column(DateTime, nullable=True)
    created_at            = Column(DateTime, nullable=False, server_default=func.now())
    updated_at            = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())