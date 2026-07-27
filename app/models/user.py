from sqlalchemy import Column, String, Boolean, Integer, DateTime, func, ForeignKey
from app.db.database import Base

class User(Base):
    __tablename__ = "USER"

    # user_id가 사번(로그인 ID) 역할을 하며, Primary Key 입니다.
    # API 요청(userId: str)에 맞춰 String으로 정의합니다.
    user_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    password = Column(String(255), nullable=False)
    position_code = Column(String(10), nullable=True)
    department_code = Column(String(10), nullable=True)
    system_role_code = Column(String(10), nullable=True)
    status_code = Column(String(10), nullable=True)
    predecessor_user_id = Column(String(50), ForeignKey("USER.user_id"), nullable=True)  # 👈 "user" -> 대문자 "USER"로 수정
    refresh_token = Column(String(512), nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    must_change_password = Column(Boolean, nullable=False, server_default='0')