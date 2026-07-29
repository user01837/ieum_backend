from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from app.db.database import Base


class Notification(Base):
    __tablename__ = "NOTIFICATION"

    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("USER.user_id"), nullable=False)
    type = Column(String(20), nullable=False)
    room_id = Column(Integer, ForeignKey("CHAT_ROOM.room_id"), nullable=True)
    message_id = Column(Integer, ForeignKey("CHAT_MESSAGE.message_id"), nullable=True)
    # ANNOUNCEMENT 테이블은 팀원이 별도 브랜치에서 관리 중이라 이 코드베이스에
    # 모델이 없다. ForeignKey를 걸면 매퍼 구성 시 NoReferencedTableError가 나므로
    # 라이브 DB의 실제 FK와 별개로 컬럼만 등록한다.
    announcement_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class DeviceToken(Base):
    __tablename__ = "DEVICE_TOKEN"

    token_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("USER.user_id"), nullable=False)
    fcm_token = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
