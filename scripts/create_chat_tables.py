"""신규 채팅 테이블(CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE)을 실제 MySQL DB에 생성하는 1회성 스크립트.
기존 테이블에는 영향을 주지 않는다 (Base.metadata.create_all은 없는 테이블만 생성한다).

실행: python -m scripts.create_chat_tables
"""
from app.db.database import Base, engine
from app.models import chat, notification  # noqa: F401  (Base.metadata 등록을 위한 임포트)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("완료: CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE, NOTIFICATION 테이블 생성/확인")
