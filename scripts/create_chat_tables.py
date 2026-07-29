"""신규 채팅 테이블(CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE)을 실제 MySQL DB에 생성하는 1회성 스크립트.
기존 테이블에는 영향을 주지 않는다 (Base.metadata.create_all은 없는 테이블만 생성한다).

실행: python -m scripts.create_chat_tables
"""
from app.db.database import Base, engine

# USER는 신규 테이블들의 ForeignKey 대상이므로 반드시 함께 임포트해야 한다.
# (app/models/__init__.py가 비어 있어 하위 모듈을 명시적으로 임포트하지 않으면
#  Base.metadata에 USER가 등록되지 않아 create_all이 NoReferencedTableError로 실패한다.)
from app.models import user, chat, notification  # noqa: F401  (Base.metadata 등록을 위한 임포트)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("완료: CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE, NOTIFICATION, DEVICE_TOKEN 테이블 생성/확인")
