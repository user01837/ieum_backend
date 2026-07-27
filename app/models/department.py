from sqlalchemy import Column, String, Integer, ForeignKey
from app.db.database import Base

class Department(Base):
    __tablename__ = "DEPARTMENT"

    department_code = Column(String(10), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    parent_department_code = Column(String(10), ForeignKey("DEPARTMENT.department_code"), nullable=True)
    head_user_id = Column(Integer, ForeignKey("USER.user_id"), nullable=True)