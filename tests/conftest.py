import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base
from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models import chat, notification  # noqa: F401  (to register chat and notification models with Base)

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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

    holder = {"user": make_user("emp001", "김직원")}

    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return holder["user"]

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with TestClient(app) as test_client:
        test_client.current_user_holder = holder
        yield test_client

    app.dependency_overrides.clear()
