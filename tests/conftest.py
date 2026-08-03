import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base
from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models import chat, notification, announcement, department  # noqa: F401  (to register chat/notification/announcement/department models with Base)

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    # SQLite's "insertmanyvalues" batching correlates inserted rows back via a
    # RETURNING sentinel. When a batch inserts a numeric-looking string into an
    # Integer-typed column (e.g. CHAT_ROOM_MEMBER.user_id, which stores string
    # employee ids), SQLite's dynamic type affinity silently coerces that value
    # to an int on the way back out, and SQLAlchemy can't match it to the
    # original string it sent — raising
    # "Can't match sentinel values in result set to parameter sets".
    # This is purely a SQLite/test-harness artifact of multi-row batch inserts
    # with RETURNING; it does not reflect production DB behavior. Disabling
    # insertmanyvalues avoids it without touching any application code.
    use_insertmanyvalues=False,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def make_user(db_session):
    def _make(user_id: str, name: str = "테스트유저", department_code: str = "01"):
        user = User(
            user_id=user_id,
            name=name,
            password="x",
            department_code=department_code,
            position_code="03",
            system_role_code="01",
            status_code="01",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    return _make


@pytest.fixture()
def client(db_session, make_user):
    from app.main import app
    from app.api.routers import chat_ws

    holder = {"user": make_user("emp001", "김직원")}

    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return holder["user"]

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    # WebSocket 핸들러는 Depends(get_db)가 아니라 모듈 레벨 세션 팩토리로
    # 짧은 수명 세션을 직접 열기 때문에(커넥션 풀 고갈 방지), 테스트에서는
    # 그 팩토리를 인메모리 테스트 엔진 기반 세션메이커로 바꿔 끼운다.
    original_session_factory = chat_ws.session_factory
    chat_ws.session_factory = TestingSessionLocal

    with TestClient(app) as test_client:
        test_client.current_user_holder = holder
        yield test_client

    chat_ws.session_factory = original_session_factory
    app.dependency_overrides.clear()
