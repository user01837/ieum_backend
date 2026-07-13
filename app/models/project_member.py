# DB - PROJECT_MEMBER 테이블과 연결됨
# SQLAlchemy가 이 클래스를 보고 DB 테이블과 데이터를 주고받음
# - role_code 01: 주관자 (프로젝트 생성자, 기획서 작성 권한)
# - role_code 02: 협력자 (멤버 명단에만 표시)

from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.database import Base

class ProjectMember(Base):
    __tablename__ = "project_member"

    project_member_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id        = Column(Integer, nullable=False)
    user_id           = Column(Integer, nullable=False)
    role_code         = Column(String(10), nullable=True)
    invited_by        = Column(Integer, nullable=True)
    joined_at         = Column(DateTime, nullable=False, server_default=func.now())