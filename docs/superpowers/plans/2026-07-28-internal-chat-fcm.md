# 직원 간 실시간 채팅 + FCM 푸시 알림 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ieum_backend`/`ieum_frontend`에 직원 간 1:1·그룹 실시간 채팅(WebSocket)과, 온라인 상태에 따라 인앱 알림/FCM 웹 푸시를 분기 발송하는 기능을 추가한다.

**Architecture:** 백엔드는 사용자당 전역 WebSocket 연결(`/ws/chat`) 하나로 실시간 송수신을 처리하고, 메모리 커넥션 매니저로 온라인 상태·현재 보고 있는 방을 추적한다. 새 메시지가 오면 수신자 상태(그 방을 보는 중 / 다른 화면 / 오프라인)에 따라 아무것도 안 함 · 인앱 알림(`NOTIFICATION` 테이블 + 실시간 이벤트) · FCM 푸시 중 하나로 분기한다. 프론트엔드는 React Query로 REST 데이터를 캐싱하고, 하나의 공유 WebSocket 연결(Context)로 실시간 이벤트를 캐시에 반영한다.

**Tech Stack:** FastAPI + SQLAlchemy(MySQL) + `websockets`(Starlette WS) + `firebase-admin`(백엔드), React + React Query + Zustand + Firebase JS SDK(프론트엔드). 테스트: 백엔드는 `pytest` + `TestClient`(SQLite 인메모리 DB로 오버라이드), 프론트엔드는 이 저장소에 자동화 테스트 도구가 전혀 없으므로(기존 페이지들도 전부 무테스트) 각 태스크 종료 시 브라우저 수동 확인으로 검증한다.

## Global Constraints

- 기존 테이블 네이밍 컨벤션 준수: `ALL_CAPS` 테이블명, SQLAlchemy declarative `Base`, `relationship()` 미사용(다른 모델들과 동일하게 plain `Column`+`ForeignKey`만 사용).
- `USER.user_id`는 `String(50)`이므로, 새 테이블에서 이를 참조하는 FK 컬럼도 반드시 `String(50)`으로 맞춘다 (기존 `PROJECT_MEMBER.user_id`가 `Integer`로 잘못 되어 있는 것은 알려진 기존 버그이며, 이 작업에서 그대로 답습하지 않는다).
- 새 테이블 4~5개는 alembic이 실사용되지 않는 현재 관례상 `Base.metadata.create_all()` 스크립트로 생성한다. 기존 테이블에는 영향 없음.
- 백엔드 REST 엔드포인트는 전부 기존 관례대로 `Depends(get_current_user)`(`app/api/routers/auth.py`)로 인증한다.
- 프론트엔드 API 클라이언트는 기존 `src/api/axios.js`의 `api` 인스턴스를 그대로 사용한다 (Authorization 헤더 자동 첨부·401 리프레시는 이미 처리됨).
- 프론트엔드에 새 테스트 프레임워크를 도입하지 않는다 (기존 코드베이스 전체가 무테스트 상태이며, 이 기능만을 위해 새 관례를 만드는 것은 범위 밖).
- FCM 관련 실제 자격증명(Firebase 서비스 계정 JSON, VAPID 키)은 사용자가 Firebase 콘솔에서 직접 발급해야 하며, 이 플랜의 코드는 해당 값이 `.env`에 없어도(=`FIREBASE_CREDENTIALS_PATH`가 비어 있어도) 앱이 정상 기동하고 채팅 자체는 동작하도록 만든다 (FCM 발송만 조용히 스킵).

---

## Task 1: 백엔드 테스트 인프라 + 의존성 추가

**Files:**
- Modify: `ieum_backend/requirements.txt`
- Create: `ieum_backend/tests/__init__.py`
- Create: `ieum_backend/tests/conftest.py`
- Create: `ieum_backend/tests/test_smoke.py`

**Interfaces:**
- Produces: `client` fixture (인증된 `TestClient`, 로그인 사용자 `emp001`), `db_session` fixture(SQLite 세션), `make_user(user_id, name=..., department_code=...)` 팩토리 fixture — 이후 모든 백엔드 태스크의 테스트가 이 세 fixture를 사용한다.

- [ ] **Step 1: requirements.txt에 의존성 추가**

`ecdsa==0.19.2` 줄 다음, `fastapi==0.139.0` 줄 다음에 삽입:

```
ecdsa==0.19.2
fastapi==0.139.0
firebase-admin==6.5.0
greenlet==3.5.3
```

`PyMySQL==1.2.0` 다음, `python-dateutil` 앞에 삽입:

```
PyMySQL==1.2.0
pytest==8.3.3
python-dateutil==2.9.0.post0
```

`urllib3==2.7.0` 다음, `wheel` 앞에 삽입:

```
urllib3==2.7.0
websockets==13.1
wheel==0.47.0
```

그 다음 실행 (conda 환경 `ieum_backend` 활성화된 상태):

```bash
pip install firebase-admin==6.5.0 pytest==8.3.3 websockets==13.1
```

- [ ] **Step 2: `tests/__init__.py` 생성 (빈 파일)**

- [ ] **Step 3: `tests/conftest.py` 작성**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base
from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User

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
```

주의: 이 시점(Task 1)에는 `app.models.chat`/`app.models.notification` 모듈이 아직 없으므로 `Base.metadata`에는 기존 테이블만 등록되어 있다. Task 2부터 해당 모델 파일을 만들면 `app/api/routers/chat.py` 등에서 임포트되어 자동으로 `Base.metadata`에 등록되므로 이 conftest는 수정할 필요 없다.

- [ ] **Step 4: 스모크 테스트 작성 (`tests/test_smoke.py`)**

```python
def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Hello IEUM Backend"
```

- [ ] **Step 5: 테스트 실행 및 통과 확인**

```bash
pytest tests/test_smoke.py -v
```

Expected: `1 passed`

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt tests/__init__.py tests/conftest.py tests/test_smoke.py
git commit -m "test: pytest 기반 백엔드 테스트 인프라(SQLite 오버라이드) 추가"
```

---

## Task 2: 채팅방 모델 + 생성/목록 API

**Files:**
- Create: `ieum_backend/app/models/chat.py`
- Create: `ieum_backend/app/services/chat_service.py`
- Create: `ieum_backend/app/api/routers/chat.py`
- Create: `ieum_backend/scripts/__init__.py`
- Create: `ieum_backend/scripts/create_chat_tables.py`
- Test: `ieum_backend/tests/test_chat_rooms.py`

**Interfaces:**
- Consumes: Task 1의 `client`/`db_session`/`make_user` fixture.
- Produces: `ChatRoom`, `ChatRoomMember`, `ChatMessage` 모델(`app/models/chat.py`). `chat_service.create_room(db, creator_id, member_ids, name) -> ChatRoom`, `chat_service.find_existing_direct_room(db, user_id_a, user_id_b) -> ChatRoom | None`, `chat_service.list_rooms_for_user(db, user_id) -> list[dict]` (dict 키: `room_id, name, is_group, member_ids, last_message, last_message_at`) — 이후 Task 3에서 `unread_count` 키가 추가된다. REST: `POST /chat/rooms`, `GET /chat/rooms`.

- [ ] **Step 1: `app/models/chat.py` 작성**

```python
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, func
from app.db.database import Base


class ChatRoom(Base):
    __tablename__ = "CHAT_ROOM"

    room_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=True)
    is_group = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(50), ForeignKey("USER.user_id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ChatRoomMember(Base):
    __tablename__ = "CHAT_ROOM_MEMBER"

    room_id = Column(Integer, ForeignKey("CHAT_ROOM.room_id"), primary_key=True)
    user_id = Column(String(50), ForeignKey("USER.user_id"), primary_key=True)
    joined_at = Column(DateTime, nullable=False, server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "CHAT_MESSAGE"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("CHAT_ROOM.room_id"), nullable=False)
    sender_id = Column(String(50), ForeignKey("USER.user_id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

- [ ] **Step 2: `app/services/chat_service.py` 작성**

```python
from sqlalchemy.orm import Session
from app.models.chat import ChatRoom, ChatRoomMember, ChatMessage


def find_existing_direct_room(db: Session, user_id_a: str, user_id_b: str) -> ChatRoom | None:
    """두 사람 모두를 멤버로 둔 1:1(is_group=False) 방이 이미 있으면 반환."""
    rooms_of_a = db.query(ChatRoomMember.room_id).filter(ChatRoomMember.user_id == user_id_a).subquery()
    return (
        db.query(ChatRoom)
        .join(ChatRoomMember, ChatRoom.room_id == ChatRoomMember.room_id)
        .filter(
            ChatRoom.is_group.is_(False),
            ChatRoom.room_id.in_(rooms_of_a),
            ChatRoomMember.user_id == user_id_b,
        )
        .first()
    )


def create_room(db: Session, creator_id: str, member_ids: list[str], name: str | None) -> ChatRoom:
    all_member_ids = sorted(set(member_ids) | {creator_id})
    is_group = len(all_member_ids) > 2

    if not is_group:
        other_id = next(uid for uid in all_member_ids if uid != creator_id)
        existing = find_existing_direct_room(db, creator_id, other_id)
        if existing:
            return existing

    room = ChatRoom(name=name if is_group else None, is_group=is_group, created_by=creator_id)
    db.add(room)
    db.flush()

    for user_id in all_member_ids:
        db.add(ChatRoomMember(room_id=room.room_id, user_id=user_id))

    db.commit()
    db.refresh(room)
    return room


def list_rooms_for_user(db: Session, user_id: str) -> list[dict]:
    memberships = db.query(ChatRoomMember).filter(ChatRoomMember.user_id == user_id).all()
    room_ids = [m.room_id for m in memberships]
    if not room_ids:
        return []

    rooms = db.query(ChatRoom).filter(ChatRoom.room_id.in_(room_ids)).all()
    result = []
    for room in rooms:
        member_ids = [
            m.user_id for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
        ]
        last_message = (
            db.query(ChatMessage)
            .filter(ChatMessage.room_id == room.room_id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        result.append({
            "room_id": room.room_id,
            "name": room.name,
            "is_group": room.is_group,
            "member_ids": member_ids,
            "last_message": last_message.content if last_message else None,
            "last_message_at": last_message.created_at.isoformat() if last_message else None,
        })
    result.sort(key=lambda r: r["last_message_at"] or "", reverse=True)
    return result


def is_room_member(db: Session, room_id: int, user_id: str) -> bool:
    return (
        db.query(ChatRoomMember)
        .filter(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user_id)
        .first()
        is not None
    )


def other_member_ids(db: Session, room_id: int, sender_id: str) -> list[str]:
    return [
        m.user_id
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
        if m.user_id != sender_id
    ]
```

- [ ] **Step 3: `app/api/routers/chat.py` 작성 (REST 부분)**

```python
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.chat import ChatRoomMember
from app.services import chat_service

router = APIRouter()


class CreateRoomRequest(BaseModel):
    member_ids: list[str] = Field(..., min_length=1, description="나를 제외한 참여자 사번 목록")
    name: Optional[str] = Field(None, description="그룹방 이름 (그룹일 때만 사용, 1:1이면 무시)")


class RoomResponse(BaseModel):
    room_id: int
    name: Optional[str]
    is_group: bool
    member_ids: list[str]


class RoomListItem(BaseModel):
    room_id: int
    name: Optional[str]
    is_group: bool
    member_ids: list[str]
    last_message: Optional[str]
    last_message_at: Optional[str]


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    req: CreateRoomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invalid_ids = [
        uid for uid in req.member_ids
        if not db.query(User.user_id).filter(User.user_id == uid).first()
    ]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"존재하지 않는 사용자: {invalid_ids}")

    room = chat_service.create_room(db, current_user.user_id, req.member_ids, req.name)
    member_ids = [
        m.user_id for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
    ]
    return RoomResponse(room_id=room.room_id, name=room.name, is_group=room.is_group, member_ids=member_ids)


@router.get("/rooms", response_model=list[RoomListItem])
def list_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rooms = chat_service.list_rooms_for_user(db, current_user.user_id)
    return [RoomListItem(**r) for r in rooms]
```

(`main.py`에 라우터를 등록하는 것은 Task 7에서 WS 라우터와 함께 한 번에 처리한다. 그 전까지는 `TestClient(app)`가 아니라 이 라우터 자체를 직접 앱에 마운트해 테스트할 수 없으므로, 아래 테스트에서는 임시로 `app/main.py`에 한 줄만 먼저 추가한다.)

- [ ] **Step 4: `app/main.py`에 chat 라우터 임시 등록**

`app/main.py`의 `from app.api.routers import ...` 줄에 `chat` 추가:

```python
from app.api.routers import auth, department, user, petition, task, project, upload, admin, ai, dashboard, knowledge, chat
```

`app.include_router(dashboard.router, ...)` 아래에 추가:

```python
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
```

- [ ] **Step 5: `scripts/__init__.py` 생성 (빈 파일) + `scripts/create_chat_tables.py` 작성**

```python
"""신규 채팅 테이블(CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE)을 실제 MySQL DB에 생성하는 1회성 스크립트.
기존 테이블에는 영향을 주지 않는다 (Base.metadata.create_all은 없는 테이블만 생성한다).

실행: python -m scripts.create_chat_tables
"""
from app.db.database import Base, engine
from app.models import chat  # noqa: F401  (Base.metadata 등록을 위한 임포트)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("완료: CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE 테이블 생성/확인")
```

- [ ] **Step 6: 실패하는 테스트부터 작성 (`tests/test_chat_rooms.py`)**

```python
def test_create_direct_room(client, make_user):
    other = make_user("emp002", "이직원")
    res = client.post("/chat/rooms", json={"member_ids": [other.user_id]})
    assert res.status_code == 201
    body = res.json()
    assert body["is_group"] is False
    assert sorted(body["member_ids"]) == sorted(["emp001", "emp002"])


def test_create_direct_room_dedup(client, make_user):
    other = make_user("emp002", "이직원")
    first = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    second = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    assert first["room_id"] == second["room_id"]


def test_create_group_room(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    res = client.post(
        "/chat/rooms",
        json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    )
    body = res.json()
    assert body["is_group"] is True
    assert body["name"] == "기획팀방"
    assert len(body["member_ids"]) == 3


def test_create_room_rejects_unknown_user(client):
    res = client.post("/chat/rooms", json={"member_ids": ["ghost"]})
    assert res.status_code == 400


def test_list_rooms_returns_my_rooms(client, make_user):
    other = make_user("emp002", "이직원")
    client.post("/chat/rooms", json={"member_ids": [other.user_id]})
    res = client.get("/chat/rooms")
    assert res.status_code == 200
    rooms = res.json()
    assert len(rooms) == 1
    assert "emp002" in rooms[0]["member_ids"]
```

- [ ] **Step 7: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_chat_rooms.py -v
```

Expected: `5 passed`

- [ ] **Step 8: 커밋**

```bash
git add app/models/chat.py app/services/chat_service.py app/api/routers/chat.py app/main.py scripts/__init__.py scripts/create_chat_tables.py tests/test_chat_rooms.py
git commit -m "feat: 채팅방 생성/목록 API 추가 (1:1 중복 방지 포함)"
```

---

## Task 3: 알림 모델 + 메시지 히스토리/읽음 처리 API

**Files:**
- Create: `ieum_backend/app/models/notification.py`
- Modify: `ieum_backend/app/services/chat_service.py`
- Modify: `ieum_backend/app/api/routers/chat.py`
- Modify: `ieum_backend/scripts/create_chat_tables.py`
- Test: `ieum_backend/tests/test_chat_messages.py`

**Interfaces:**
- Consumes: Task 2의 `chat_service.is_room_member`, `ChatRoom`/`ChatRoomMember`/`ChatMessage`.
- Produces: `Notification` 모델(`app/models/notification.py`, 이 시점엔 `DEVICE_TOKEN` 없이 `NOTIFICATION`만). `chat_service.get_messages(db, room_id, before_message_id, size) -> list[ChatMessage]`, `chat_service.mark_room_read(db, room_id, user_id) -> int`, `chat_service.unread_count_by_room(db, user_id) -> dict[int, int]`. REST: `GET /chat/rooms/{room_id}/messages`, `POST /chat/rooms/{room_id}/read`. `list_rooms_for_user` 응답에 `unread_count` 키 추가.

- [ ] **Step 1: `app/models/notification.py` 작성**

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from app.db.database import Base


class Notification(Base):
    __tablename__ = "NOTIFICATION"

    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("USER.user_id"), nullable=False)
    type = Column(String(20), nullable=False)
    room_id = Column(Integer, ForeignKey("CHAT_ROOM.room_id"), nullable=True)
    message_id = Column(Integer, ForeignKey("CHAT_MESSAGE.message_id"), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

- [ ] **Step 2: `app/services/chat_service.py`에 함수 추가**

파일 상단 import를 다음으로 교체:

```python
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.chat import ChatRoom, ChatRoomMember, ChatMessage
from app.models.notification import Notification
```

파일 끝에 추가:

```python
def get_messages(db: Session, room_id: int, before_message_id: int | None, size: int) -> list[ChatMessage]:
    query = db.query(ChatMessage).filter(ChatMessage.room_id == room_id)
    if before_message_id is not None:
        query = query.filter(ChatMessage.message_id < before_message_id)
    return query.order_by(ChatMessage.message_id.desc()).limit(size).all()


def mark_room_read(db: Session, room_id: int, user_id: str) -> int:
    updated = (
        db.query(Notification)
        .filter(
            Notification.room_id == room_id,
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return updated


def unread_count_by_room(db: Session, user_id: str) -> dict[int, int]:
    rows = (
        db.query(Notification.room_id, func.count(Notification.notification_id))
        .filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
            Notification.room_id.isnot(None),
        )
        .group_by(Notification.room_id)
        .all()
    )
    return {room_id: count for room_id, count in rows}
```

`list_rooms_for_user` 함수를 아래와 같이 교체 (끝부분에 `unread_count` 추가):

```python
def list_rooms_for_user(db: Session, user_id: str) -> list[dict]:
    memberships = db.query(ChatRoomMember).filter(ChatRoomMember.user_id == user_id).all()
    room_ids = [m.room_id for m in memberships]
    if not room_ids:
        return []

    rooms = db.query(ChatRoom).filter(ChatRoom.room_id.in_(room_ids)).all()
    unread_map = unread_count_by_room(db, user_id)
    result = []
    for room in rooms:
        member_ids = [
            m.user_id for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
        ]
        last_message = (
            db.query(ChatMessage)
            .filter(ChatMessage.room_id == room.room_id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        result.append({
            "room_id": room.room_id,
            "name": room.name,
            "is_group": room.is_group,
            "member_ids": member_ids,
            "last_message": last_message.content if last_message else None,
            "last_message_at": last_message.created_at.isoformat() if last_message else None,
            "unread_count": unread_map.get(room.room_id, 0),
        })
    result.sort(key=lambda r: r["last_message_at"] or "", reverse=True)
    return result
```

- [ ] **Step 3: `app/api/routers/chat.py` 수정**

`RoomListItem`에 필드 추가:

```python
class RoomListItem(BaseModel):
    room_id: int
    name: Optional[str]
    is_group: bool
    member_ids: list[str]
    last_message: Optional[str]
    last_message_at: Optional[str]
    unread_count: int
```

새 엔드포인트 추가 (파일 끝):

```python
class MessageResponse(BaseModel):
    message_id: int
    room_id: int
    sender_id: str
    content: str
    created_at: str


@router.get("/rooms/{room_id}/messages", response_model=list[MessageResponse])
def get_room_messages(
    room_id: int,
    before_message_id: Optional[int] = Query(None),
    size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not chat_service.is_room_member(db, room_id, current_user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 채팅방의 멤버가 아닙니다.")

    messages = chat_service.get_messages(db, room_id, before_message_id, size)
    return [
        MessageResponse(
            message_id=m.message_id,
            room_id=m.room_id,
            sender_id=m.sender_id,
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post("/rooms/{room_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_room_read_endpoint(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not chat_service.is_room_member(db, room_id, current_user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 채팅방의 멤버가 아닙니다.")
    chat_service.mark_room_read(db, room_id, current_user.user_id)
```

- [ ] **Step 4: `scripts/create_chat_tables.py`에 notification 모듈 임포트 추가**

```python
from app.models import chat, notification  # noqa: F401  (Base.metadata 등록을 위한 임포트)
```

print문도 갱신:

```python
    print("완료: CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE, NOTIFICATION 테이블 생성/확인")
```

- [ ] **Step 5: 실패하는 테스트 작성 (`tests/test_chat_messages.py`)**

```python
def test_get_messages_rejects_non_member(client):
    res = client.get("/chat/rooms/99999/messages")
    assert res.status_code == 403


def test_get_messages_pagination(client, make_user, db_session):
    from app.models.chat import ChatMessage

    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    for i in range(5):
        db_session.add(ChatMessage(room_id=room["room_id"], sender_id="emp001", content=f"msg{i}"))
    db_session.commit()

    page1 = client.get(f"/chat/rooms/{room['room_id']}/messages", params={"size": 2}).json()
    assert len(page1) == 2
    assert page1[0]["content"] == "msg4"

    page2 = client.get(
        f"/chat/rooms/{room['room_id']}/messages",
        params={"size": 2, "before_message_id": page1[-1]["message_id"]},
    ).json()
    assert len(page2) == 2
    assert page2[0]["content"] == "msg2"


def test_mark_room_read_clears_notifications(client, make_user, db_session):
    from app.models.notification import Notification

    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    db_session.add(Notification(user_id="emp001", type="CHAT_MESSAGE", room_id=room["room_id"], is_read=False))
    db_session.commit()

    res = client.post(f"/chat/rooms/{room['room_id']}/read")
    assert res.status_code == 204

    remaining = db_session.query(Notification).filter(Notification.is_read.is_(False)).count()
    assert remaining == 0


def test_list_rooms_reports_unread_count(client, make_user, db_session):
    from app.models.notification import Notification

    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    db_session.add(Notification(user_id="emp001", type="CHAT_MESSAGE", room_id=room["room_id"], is_read=False))
    db_session.commit()

    rooms = client.get("/chat/rooms").json()
    assert rooms[0]["unread_count"] == 1
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_chat_messages.py -v
```

Expected: `4 passed`

- [ ] **Step 7: 전체 회귀 확인**

```bash
pytest -v
```

Expected: 지금까지의 모든 테스트 통과 (Task 1~3분)

- [ ] **Step 8: 커밋**

```bash
git add app/models/notification.py app/services/chat_service.py app/api/routers/chat.py scripts/create_chat_tables.py tests/test_chat_messages.py
git commit -m "feat: 채팅 메시지 히스토리 조회 + 방별 읽음 처리/안읽음 카운트 추가"
```

---

## Task 4: 기기 토큰 + 알림 목록 API

**Files:**
- Modify: `ieum_backend/app/models/notification.py`
- Create: `ieum_backend/app/api/routers/notification.py`
- Modify: `ieum_backend/app/main.py`
- Modify: `ieum_backend/scripts/create_chat_tables.py`
- Test: `ieum_backend/tests/test_notifications.py`

**Interfaces:**
- Consumes: Task 3의 `Notification` 모델.
- Produces: `DeviceToken` 모델. REST: `GET /notifications`, `POST /notifications/device-token`, `DELETE /notifications/device-token`.

- [ ] **Step 1: `app/models/notification.py`에 `DeviceToken` 추가**

파일 끝에 추가:

```python
class DeviceToken(Base):
    __tablename__ = "DEVICE_TOKEN"

    token_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("USER.user_id"), nullable=False)
    fcm_token = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

- [ ] **Step 2: `app/api/routers/notification.py` 작성**

```python
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.notification import Notification, DeviceToken

router = APIRouter()


class DeviceTokenRequest(BaseModel):
    fcm_token: str


class NotificationItem(BaseModel):
    notification_id: int
    type: str
    room_id: int | None
    message_id: int | None
    is_read: bool
    created_at: str


@router.get("", response_model=list[NotificationItem])
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.user_id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    return [
        NotificationItem(
            notification_id=n.notification_id,
            type=n.type,
            room_id=n.room_id,
            message_id=n.message_id,
            is_read=n.is_read,
            created_at=n.created_at.isoformat(),
        )
        for n in rows
    ]


@router.post("/device-token", status_code=status.HTTP_204_NO_CONTENT)
def register_device_token(
    req: DeviceTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(DeviceToken).filter(DeviceToken.fcm_token == req.fcm_token).first()
    if existing:
        existing.user_id = current_user.user_id
    else:
        db.add(DeviceToken(user_id=current_user.user_id, fcm_token=req.fcm_token))
    db.commit()


@router.delete("/device-token", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device_token(
    req: DeviceTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(DeviceToken).filter(
        DeviceToken.fcm_token == req.fcm_token,
        DeviceToken.user_id == current_user.user_id,
    ).delete(synchronize_session=False)
    db.commit()
```

- [ ] **Step 3: `app/main.py`에 라우터 등록**

import 줄 수정:

```python
from app.api.routers import auth, department, user, petition, task, project, upload, admin, ai, dashboard, knowledge, chat, notification
```

`app.include_router(chat.router, prefix="/chat", tags=["Chat"])` 아래에 추가:

```python
app.include_router(notification.router, prefix="/notifications", tags=["Notifications"])
```

- [ ] **Step 4: `scripts/create_chat_tables.py` 완료 메시지 갱신**

```python
    print("완료: CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE, NOTIFICATION, DEVICE_TOKEN 테이블 생성/확인")
```

- [ ] **Step 5: 실패하는 테스트 작성 (`tests/test_notifications.py`)**

```python
def test_register_and_list_device_token(client):
    res = client.post("/notifications/device-token", json={"fcm_token": "tok-1"})
    assert res.status_code == 204

    from app.models.notification import DeviceToken
    # db_session fixture 없이도 client fixture 내부 세션을 통해 검증 가능하도록 API로 확인
    res2 = client.delete("/notifications/device-token", json={"fcm_token": "tok-1"})
    assert res2.status_code == 204


def test_register_device_token_upsert_reassigns_owner(client, make_user, db_session):
    from app.models.notification import DeviceToken

    make_user("emp002")
    client.post("/notifications/device-token", json={"fcm_token": "shared-tok"})
    row = db_session.query(DeviceToken).filter(DeviceToken.fcm_token == "shared-tok").first()
    assert row.user_id == "emp001"


def test_list_notifications_returns_my_notifications(client, make_user, db_session):
    from app.models.notification import Notification

    make_user("emp002")
    db_session.add(Notification(user_id="emp001", type="CHAT_MESSAGE", is_read=False))
    db_session.add(Notification(user_id="emp002", type="CHAT_MESSAGE", is_read=False))
    db_session.commit()

    res = client.get("/notifications")
    body = res.json()
    assert len(body) == 1
    assert body[0]["type"] == "CHAT_MESSAGE"
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_notifications.py -v
```

Expected: `3 passed`

- [ ] **Step 7: 커밋**

```bash
git add app/models/notification.py app/api/routers/notification.py app/main.py scripts/create_chat_tables.py tests/test_notifications.py
git commit -m "feat: FCM 기기 토큰 등록/해제 + 알림 목록 조회 API 추가"
```

---

## Task 5: WebSocket 연결 매니저 + 연결/온라인 상태 추적

**Files:**
- Create: `ieum_backend/app/services/chat_connection_manager.py`
- Create: `ieum_backend/app/api/routers/chat_ws.py`
- Modify: `ieum_backend/app/main.py`
- Test: `ieum_backend/tests/test_chat_ws.py`

**Interfaces:**
- Consumes: Task 2의 `User` 조회, `app.core.config.settings.JWT_SECRET`.
- Produces: `chat_manager`(`ChatConnectionManager` 싱글턴, `app/services/chat_connection_manager.py`) — `connect`, `disconnect`, `set_active_room`, `is_user_online`, `connections_for_user`, `is_viewing_room` 메서드. WS 엔드포인트 `/ws/chat?token=<accessToken>` (연결/해제/`active_room` 메시지만 처리, `send_message`는 Task 6에서 구현).

- [ ] **Step 1: `app/services/chat_connection_manager.py` 작성**

```python
from fastapi import WebSocket


class ChatConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}
        self._active_room: dict[WebSocket, int | None] = {}

    def connect(self, user_id: str, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(websocket)
        self._active_room[websocket] = None

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if sockets and websocket in sockets:
            sockets.remove(websocket)
            if not sockets:
                del self._connections[user_id]
        self._active_room.pop(websocket, None)

    def set_active_room(self, websocket: WebSocket, room_id: int | None) -> None:
        self._active_room[websocket] = room_id

    def is_user_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    def connections_for_user(self, user_id: str) -> set[WebSocket]:
        return set(self._connections.get(user_id, set()))

    def is_viewing_room(self, websocket: WebSocket, room_id: int) -> bool:
        return self._active_room.get(websocket) == room_id


manager = ChatConnectionManager()
```

- [ ] **Step 2: `app/api/routers/chat_ws.py` 작성**

```python
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.chat_connection_manager import manager as chat_manager

router = APIRouter()


def _authenticate_ws_user(token: str, db: Session) -> User | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError:
        return None
    if not user_id:
        return None
    return db.query(User).filter(User.user_id == user_id).first()


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket, token: str = Query(...), db: Session = Depends(get_db)):
    user = _authenticate_ws_user(token, db)
    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    chat_manager.connect(user.user_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "active_room":
                chat_manager.set_active_room(websocket, data.get("room_id"))
            # "send_message"는 Task 6에서 구현
    except WebSocketDisconnect:
        chat_manager.disconnect(user.user_id, websocket)
```

- [ ] **Step 3: `app/main.py`에 WS 라우터 등록**

import 줄 수정:

```python
from app.api.routers import auth, department, user, petition, task, project, upload, admin, ai, dashboard, knowledge, chat, notification, chat_ws
```

`app.include_router(notification.router, ...)` 아래에 추가 (prefix 없음 — 경로가 라우터 안에서 `/ws/chat`으로 이미 확정되어 있음):

```python
app.include_router(chat_ws.router, tags=["Chat WebSocket"])
```

- [ ] **Step 4: 실패하는 테스트 작성 (`tests/test_chat_ws.py`)**

```python
import json
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.routers.auth import create_token


def _token_for(user):
    return create_token({"sub": user.user_id, "pos": user.position_code}, timedelta(minutes=30))


def test_ws_rejects_invalid_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/chat?token=invalid-token"):
            pass


def test_ws_connect_marks_user_online_and_disconnect_clears_it(client):
    from app.services.chat_connection_manager import manager as chat_manager

    user = client.current_user_holder["user"]
    token = _token_for(user)

    assert chat_manager.is_user_online(user.user_id) is False
    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        ws.send_text(json.dumps({"type": "active_room", "room_id": 1}))
        assert chat_manager.is_user_online(user.user_id) is True
    assert chat_manager.is_user_online(user.user_id) is False
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_chat_ws.py -v
```

Expected: `2 passed`

- [ ] **Step 6: 커밋**

```bash
git add app/services/chat_connection_manager.py app/api/routers/chat_ws.py app/main.py tests/test_chat_ws.py
git commit -m "feat: 채팅 WebSocket 연결/인증/온라인 상태 추적 추가"
```

---

## Task 6: 실시간 메시지 송수신 + 3단계 알림 분기(온라인/다른방/오프라인)

**Files:**
- Modify: `ieum_backend/app/services/chat_service.py`
- Modify: `ieum_backend/app/api/routers/chat_ws.py`
- Modify: `ieum_backend/tests/test_chat_ws.py`

**Interfaces:**
- Consumes: Task 5의 `chat_manager`, Task 3의 `Notification`.
- Produces: `chat_service.record_message(db, room_id, sender_id, content) -> ChatMessage`, `chat_service.create_notification(db, user_id, room_id, message_id) -> Notification`. WS 클라이언트 → 서버: `{"type": "send_message", "room_id": int, "content": str}`. 서버 → 클라이언트: `{"type": "new_message", "room_id": int, "message": {...}}`, `{"type": "notification", "notification": {...}}`.

- [ ] **Step 1: `app/services/chat_service.py`에 함수 추가 (파일 끝)**

```python
def record_message(db: Session, room_id: int, sender_id: str, content: str) -> ChatMessage:
    message = ChatMessage(room_id=room_id, sender_id=sender_id, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def create_notification(db: Session, user_id: str, room_id: int, message_id: int) -> Notification:
    notification = Notification(
        user_id=user_id, type="CHAT_MESSAGE", room_id=room_id, message_id=message_id, is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification
```

- [ ] **Step 2: `app/api/routers/chat_ws.py` 수정 — `send_message` 처리 추가**

파일 상단 import에 추가:

```python
from app.services import chat_service
```

`chat_ws` 함수 안의 `while True` 루프를 아래로 교체:

```python
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "active_room":
                chat_manager.set_active_room(websocket, data.get("room_id"))

            elif msg_type == "send_message":
                room_id = data.get("room_id")
                content = (data.get("content") or "").strip()
                if not room_id or not content:
                    continue
                if not chat_service.is_room_member(db, room_id, user.user_id):
                    continue

                message = chat_service.record_message(db, room_id, user.user_id, content)
                message_payload = {
                    "type": "new_message",
                    "room_id": room_id,
                    "message": {
                        "message_id": message.message_id,
                        "room_id": room_id,
                        "sender_id": user.user_id,
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                    },
                }

                await _broadcast(chat_manager.connections_for_user(user.user_id), message_payload)

                for recipient_id in chat_service.other_member_ids(db, room_id, user.user_id):
                    recipient_sockets = chat_manager.connections_for_user(recipient_id)
                    viewing_sockets = {
                        s for s in recipient_sockets if chat_manager.is_viewing_room(s, room_id)
                    }
                    elsewhere_sockets = recipient_sockets - viewing_sockets

                    if viewing_sockets:
                        await _broadcast(viewing_sockets, message_payload)

                    if elsewhere_sockets or not recipient_sockets:
                        notification = chat_service.create_notification(
                            db, recipient_id, room_id, message.message_id
                        )
                        if elsewhere_sockets:
                            notif_payload = {
                                "type": "notification",
                                "notification": {
                                    "notification_id": notification.notification_id,
                                    "room_id": room_id,
                                    "message_id": message.message_id,
                                    "created_at": notification.created_at.isoformat(),
                                },
                            }
                            await _broadcast(elsewhere_sockets, message_payload)
                            await _broadcast(elsewhere_sockets, notif_payload)
                        # recipient_sockets가 아예 없는 경우(오프라인)의 FCM 발송은 Task 7에서 추가
    except WebSocketDisconnect:
        chat_manager.disconnect(user.user_id, websocket)
```

같은 파일에 헬퍼 함수 추가 (`chat_ws` 함수 정의 위):

```python
async def _broadcast(sockets: set[WebSocket], payload: dict) -> None:
    for ws in sockets:
        await ws.send_text(json.dumps(payload))
```

- [ ] **Step 3: 실패하는 테스트 추가 (`tests/test_chat_ws.py` 끝에 추가)**

```python
def test_ws_message_delivered_when_viewing_creates_no_notification(client, make_user, db_session):
    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    sender_token = _token_for(client.current_user_holder["user"])
    recipient_token = _token_for(other)

    with client.websocket_connect(f"/ws/chat?token={sender_token}") as sender_ws:
        with client.websocket_connect(f"/ws/chat?token={recipient_token}") as recipient_ws:
            recipient_ws.send_text(json.dumps({"type": "active_room", "room_id": room["room_id"]}))

            sender_ws.send_text(
                json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"})
            )

            sender_echo = json.loads(sender_ws.receive_text())
            assert sender_echo["type"] == "new_message"

            recipient_event = json.loads(recipient_ws.receive_text())
            assert recipient_event["type"] == "new_message"
            assert recipient_event["message"]["content"] == "안녕"

    from app.models.notification import Notification
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 0


def test_ws_message_creates_notification_when_elsewhere(client, make_user, db_session):
    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    sender_token = _token_for(client.current_user_holder["user"])
    recipient_token = _token_for(other)

    with client.websocket_connect(f"/ws/chat?token={sender_token}") as sender_ws:
        with client.websocket_connect(f"/ws/chat?token={recipient_token}") as recipient_ws:
            # recipient는 active_room을 보내지 않음 = 다른 화면을 보는 중
            sender_ws.send_text(
                json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"})
            )
            sender_ws.receive_text()  # echo

            events = [json.loads(recipient_ws.receive_text()) for _ in range(2)]
            types = {e["type"] for e in events}
            assert types == {"new_message", "notification"}

    from app.models.notification import Notification
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 1


def test_ws_message_creates_notification_when_recipient_offline(client, make_user, db_session):
    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    sender_token = _token_for(client.current_user_holder["user"])

    with client.websocket_connect(f"/ws/chat?token={sender_token}") as sender_ws:
        sender_ws.send_text(
            json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"})
        )
        sender_ws.receive_text()  # echo

    from app.models.notification import Notification
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 1
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_chat_ws.py -v
```

Expected: `5 passed`

- [ ] **Step 5: 전체 회귀 확인**

```bash
pytest -v
```

Expected: 지금까지의 모든 테스트 통과

- [ ] **Step 6: 커밋**

```bash
git add app/services/chat_service.py app/api/routers/chat_ws.py tests/test_chat_ws.py
git commit -m "feat: 실시간 메시지 송수신 + 온라인/다른방/오프라인 3단계 알림 분기 구현"
```

---

## Task 7: FCM 푸시 발송 (오프라인 분기 완성)

**Files:**
- Create: `ieum_backend/app/services/fcm_service.py`
- Modify: `ieum_backend/app/api/routers/chat_ws.py`
- Modify: `ieum_backend/app/core/config.py`
- Test: `ieum_backend/tests/test_fcm_service.py`

**Interfaces:**
- Consumes: Task 4의 `DeviceToken`, Task 6의 오프라인 분기 지점.
- Produces: `fcm_service.send_new_message_push(db, recipient_id, room_id, message)`, `fcm_service.init_firebase()`. `settings.FIREBASE_CREDENTIALS_PATH: str | None`.

- [ ] **Step 1: `app/core/config.py`에 설정 추가**

`EXTERNAL_PETITION_API_KEY: str` 줄 다음에 추가:

```python
    EXTERNAL_PETITION_API_KEY: str

    # FCM (선택) - 비어 있으면 채팅은 정상 동작하되 푸시 발송만 스킵된다.
    FIREBASE_CREDENTIALS_PATH: str | None = None
```

- [ ] **Step 2: `app/services/fcm_service.py` 작성**

```python
import logging

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification import DeviceToken

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase() -> None:
    global _initialized
    if _initialized or not settings.FIREBASE_CREDENTIALS_PATH:
        return
    try:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        _initialized = True
    except Exception:
        logger.exception("Firebase 초기화 실패 - FCM 발송이 비활성화됩니다.")


def send_new_message_push(db: Session, recipient_id: str, room_id: int, message) -> None:
    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.info("FIREBASE_CREDENTIALS_PATH 미설정 - FCM 발송을 건너뜁니다.")
        return

    init_firebase()
    if not _initialized:
        return

    tokens = db.query(DeviceToken).filter(DeviceToken.user_id == recipient_id).all()
    for device_token in tokens:
        fcm_message = messaging.Message(
            notification=messaging.Notification(title="새 메시지", body=message.content[:80]),
            data={"room_id": str(room_id), "message_id": str(message.message_id)},
            token=device_token.fcm_token,
        )
        try:
            messaging.send(fcm_message)
        except Exception as exc:
            # firebase_admin의 정확한 예외 계층은 버전마다 달라질 수 있어 클래스 이름으로 판별한다.
            if type(exc).__name__ == "UnregisteredError":
                db.query(DeviceToken).filter(DeviceToken.token_id == device_token.token_id).delete()
                db.commit()
            else:
                logger.exception(
                    "FCM 발송 실패 (user_id=%s, token_id=%s)", recipient_id, device_token.token_id
                )
```

- [ ] **Step 3: `app/api/routers/chat_ws.py`에 FCM 호출 연결**

import 추가:

```python
from app.services import fcm_service
```

Task 6에서 만든 `if elsewhere_sockets or not recipient_sockets:` 블록을 아래로 교체 (오프라인일 때 FCM 호출 추가):

```python
                    if elsewhere_sockets or not recipient_sockets:
                        notification = chat_service.create_notification(
                            db, recipient_id, room_id, message.message_id
                        )
                        if elsewhere_sockets:
                            notif_payload = {
                                "type": "notification",
                                "notification": {
                                    "notification_id": notification.notification_id,
                                    "room_id": room_id,
                                    "message_id": message.message_id,
                                    "created_at": notification.created_at.isoformat(),
                                },
                            }
                            await _broadcast(elsewhere_sockets, message_payload)
                            await _broadcast(elsewhere_sockets, notif_payload)
                        if not recipient_sockets:
                            fcm_service.send_new_message_push(db, recipient_id, room_id, message)
```

- [ ] **Step 4: 실패하는 테스트 작성 (`tests/test_fcm_service.py`)**

```python
from unittest.mock import patch

from app.services import fcm_service
from app.models.notification import DeviceToken
from app.models.chat import ChatMessage


def test_send_new_message_push_skips_without_credentials(db_session, make_user, monkeypatch):
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", None)
    user = make_user("emp002")
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="tok-1"))
    db_session.commit()

    message = ChatMessage(room_id=1, sender_id="emp001", content="hi")
    with patch("app.services.fcm_service.messaging.send") as mock_send:
        fcm_service.send_new_message_push(db_session, user.user_id, 1, message)
        mock_send.assert_not_called()


def test_send_new_message_push_sends_to_all_tokens(db_session, make_user, monkeypatch):
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", "/fake/path.json")
    monkeypatch.setattr(fcm_service, "_initialized", True)
    user = make_user("emp002")
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="tok-1"))
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="tok-2"))
    db_session.commit()

    message = ChatMessage(room_id=1, sender_id="emp001", content="hi")
    with patch("app.services.fcm_service.messaging.send") as mock_send:
        fcm_service.send_new_message_push(db_session, user.user_id, 1, message)
        assert mock_send.call_count == 2


def test_send_new_message_push_removes_unregistered_token(db_session, make_user, monkeypatch):
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", "/fake/path.json")
    monkeypatch.setattr(fcm_service, "_initialized", True)
    user = make_user("emp002")
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="dead-token"))
    db_session.commit()

    class FakeUnregisteredError(Exception):
        pass
    FakeUnregisteredError.__name__ = "UnregisteredError"

    message = ChatMessage(room_id=1, sender_id="emp001", content="hi")
    with patch("app.services.fcm_service.messaging.send", side_effect=FakeUnregisteredError("gone")):
        fcm_service.send_new_message_push(db_session, user.user_id, 1, message)

    assert db_session.query(DeviceToken).filter(DeviceToken.fcm_token == "dead-token").count() == 0
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_fcm_service.py -v
```

Expected: `3 passed`

- [ ] **Step 6: 오프라인 WS 테스트가 FCM을 호출하지 않고도(자격증명 없음) 여전히 통과하는지 회귀 확인**

```bash
pytest -v
```

Expected: 전체 통과 (`FIREBASE_CREDENTIALS_PATH`가 테스트 환경에 없으므로 `test_ws_message_creates_notification_when_recipient_offline`은 FCM을 그냥 스킵하고 통과해야 함)

- [ ] **Step 7: 커밋**

```bash
git add app/services/fcm_service.py app/api/routers/chat_ws.py app/core/config.py tests/test_fcm_service.py
git commit -m "feat: 오프라인 사용자 대상 FCM 웹 푸시 발송 연결"
```

---

## Task 8: `.env` 예시 갱신 + 테이블 생성 스크립트 실행 안내

**Files:**
- Modify: `ieum_backend/.env.example`

**Interfaces:**
- Consumes: 없음 (문서/설정 마무리 작업).

- [ ] **Step 1: `.env.example`에 `FIREBASE_CREDENTIALS_PATH` 추가**

`EXTERNAL_PETITION_API_KEY=` 줄 다음에 추가:

```
EXTERNAL_PETITION_API_KEY=

# FCM (선택) - 비워두면 채팅은 정상 동작하되 푸시 발송만 비활성화됨
FIREBASE_CREDENTIALS_PATH=
```

- [ ] **Step 2: 로컬에서 실제 테이블 생성 스크립트 실행 (개발 DB에 1회)**

```bash
python -m scripts.create_chat_tables
```

Expected 출력: `완료: CHAT_ROOM, CHAT_ROOM_MEMBER, CHAT_MESSAGE, NOTIFICATION, DEVICE_TOKEN 테이블 생성/확인`

- [ ] **Step 3: 커밋**

```bash
git add .env.example
git commit -m "docs: FIREBASE_CREDENTIALS_PATH 환경변수 예시 추가"
```

---

## Task 9: 프론트엔드 — 채팅 페이지 (REST + WebSocket 실시간 송수신)

**Files:**
- Create: `ieum_frontend/src/api/chat.js`
- Create: `ieum_frontend/src/hooks/queries/useChatQuery.js`
- Create: `ieum_frontend/src/hooks/mutations/useChatMutations.js`
- Create: `ieum_frontend/src/hooks/useChatSocket.js`
- Create: `ieum_frontend/src/store/ChatSocketContext.jsx`
- Modify: `ieum_frontend/src/layouts/MainLayout.jsx`
- Modify: `ieum_frontend/src/components/EmpSearchModal/EmpSearchModal.jsx`
- Create: `ieum_frontend/src/pages/Chat/ChatPage.jsx`
- Create: `ieum_frontend/src/pages/Chat/ChatPage.css`
- Modify: `ieum_frontend/src/components/sidebar/Sidebar.jsx`
- Modify: `ieum_frontend/src/routes/Router.jsx`

**Interfaces:**
- Consumes: 백엔드 Task 2/3/6의 `POST /chat/rooms`, `GET /chat/rooms`, `GET /chat/rooms/{id}/messages`, `POST /chat/rooms/{id}/read`, `/ws/chat`.
- Produces: `ChatSocketProvider`/`useChatSocketContext()` — `{ isConnected, sendMessage(roomId, content), setActiveRoom(roomId) }`. Task 10(알림벨)이 같은 Context를 소비한다. `EmployeeSearchModal`의 `multiSelect`/`onConfirm` prop.

- [ ] **Step 1: `src/api/chat.js` 작성**

```javascript
import api from './axios';

export const createChatRoom = async ({ memberIds, name }) => {
  const response = await api.post('/chat/rooms', { member_ids: memberIds, name });
  return response.data;
};

export const getChatRooms = async () => {
  const response = await api.get('/chat/rooms');
  return response.data;
};

export const getChatRoomMessages = async ({ roomId, beforeMessageId, size = 30 }) => {
  const params = { size };
  if (beforeMessageId) params.before_message_id = beforeMessageId;
  const response = await api.get(`/chat/rooms/${roomId}/messages`, { params });
  return response.data;
};

export const markChatRoomRead = async (roomId) => {
  await api.post(`/chat/rooms/${roomId}/read`);
};
```

- [ ] **Step 2: `src/hooks/queries/useChatQuery.js` 작성**

```javascript
import { useQuery } from '@tanstack/react-query';
import { getChatRooms, getChatRoomMessages } from '../../api/chat';

export const useChatRoomsQuery = () => {
  return useQuery({
    queryKey: ['chatRooms'],
    queryFn: getChatRooms,
  });
};

export const useChatRoomMessagesQuery = (roomId) => {
  return useQuery({
    queryKey: ['chatRoomMessages', roomId],
    queryFn: () => getChatRoomMessages({ roomId }),
    enabled: !!roomId,
  });
};
```

- [ ] **Step 3: `src/hooks/mutations/useChatMutations.js` 작성**

```javascript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createChatRoom, markChatRoomRead } from '../../api/chat';

export const useCreateChatRoomMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createChatRoom,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatRooms'] });
    },
  });
};

export const useMarkChatRoomReadMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: markChatRoomRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatRooms'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
};
```

- [ ] **Step 4: `src/hooks/useChatSocket.js` 작성**

```javascript
import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import useAuthStore from '../store/useAuthStore';

const getWsBaseUrl = () => {
  const httpBase = import.meta.env.VITE_API_BASE_URL || '';
  return httpBase.replace(/^http/, 'ws');
};

export const useChatSocket = () => {
  const queryClient = useQueryClient();
  const token = useAuthStore((state) => state.token);
  const wsRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!token) return undefined;

    const ws = new WebSocket(`${getWsBaseUrl()}/ws/chat?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'new_message') {
        const { room_id: roomId, message } = data;
        queryClient.setQueryData(['chatRoomMessages', roomId], (old = []) => [message, ...old]);
        queryClient.invalidateQueries({ queryKey: ['chatRooms'] });
      }

      if (data.type === 'notification') {
        queryClient.invalidateQueries({ queryKey: ['notifications'] });
        queryClient.invalidateQueries({ queryKey: ['chatRooms'] });
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [token, queryClient]);

  const sendMessage = useCallback((roomId, content) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'send_message', room_id: roomId, content }));
    }
  }, []);

  const setActiveRoom = useCallback((roomId) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'active_room', room_id: roomId }));
    }
  }, []);

  return { isConnected, sendMessage, setActiveRoom };
};
```

- [ ] **Step 5: `src/store/ChatSocketContext.jsx` 작성**

```javascript
import React, { createContext, useContext } from 'react';
import { useChatSocket } from '../hooks/useChatSocket';

const ChatSocketContext = createContext(null);

export function ChatSocketProvider({ children }) {
  const socket = useChatSocket();
  return (
    <ChatSocketContext.Provider value={socket}>
      {children}
    </ChatSocketContext.Provider>
  );
}

export function useChatSocketContext() {
  const ctx = useContext(ChatSocketContext);
  if (!ctx) {
    throw new Error('useChatSocketContext는 ChatSocketProvider 내부에서만 사용할 수 있습니다.');
  }
  return ctx;
}
```

- [ ] **Step 6: `src/layouts/MainLayout.jsx`에 Provider 적용**

```javascript
import Sidebar from "../components/sidebar/Sidebar";
import { Outlet, useLocation, useOutlet } from "react-router-dom";
import "../styles/global.css";
import Header from "../components/header/Header";
import { format } from 'date-fns';
import Chatbot from "../components/chatbot/Chatbot.jsx";
import { ChatSocketProvider } from "../store/ChatSocketContext";

function MainLayout() {
  const outlet = useOutlet();
  const location = useLocation();
  const formattedDate = format(new Date(), 'yyyy년 M월 d일 (E)');

  const getTitle = () => {
    const path = location.pathname;
    if (path.startsWith("/petitions")) return "민원 처리";
    if (path.startsWith("/orgchart")) return "조직도";
    if (path.startsWith("/projects")) return "사업/프로젝트 기획";
    if (path.startsWith("/knowl")) return "지식베이스";
    if (path.startsWith("/departments")) return "부서 관리";
    if (path.startsWith("/admin")) return "관리자";
    if (path.startsWith("/chat")) return "채팅";
    return "IEUM";
  };

  const isSplitViewActive =
    location.pathname.startsWith("/petitions/") &&
    outlet?.props?.children?.props?.isCaseDetailOpen === true;

  return (
    <ChatSocketProvider>
      <div className="layout">
        <Sidebar />
        <main className={`content ${isSplitViewActive ? 'no-max-width' : ''}`}>
          <Header title={getTitle()} userName="박주임" currentDate={formattedDate} />
          <Outlet />
          <Chatbot />
        </main>
      </div>
    </ChatSocketProvider>
  );
}

export default MainLayout;
```

- [ ] **Step 7: `EmpSearchModal.jsx`에 다중 선택 모드 추가**

함수 시그니처를 교체:

```javascript
function EmployeeSearchModal({ currentDept, onSelect, onConfirm, onClose, forceDeptScope = false, multiSelect = false }) {
```

`const [deptFilter, setDeptFilter] = useState('all');` 다음 줄에 상태 추가:

```javascript
  const [selectedMap, setSelectedMap] = useState({}); // multiSelect일 때만 사용: { [userId]: emp }
```

결과 행 렌더링 부분(`employees.map((emp) => (...))`)을 교체:

```javascript
              employees.map((emp) => {
                const isSelected = multiSelect && !!selectedMap[emp.userId];
                return (
                  <div
                    key={emp.userId}
                    className={`modal-result-row ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      if (multiSelect) {
                        setSelectedMap((prev) => {
                          const next = { ...prev };
                          if (next[emp.userId]) {
                            delete next[emp.userId];
                          } else {
                            next[emp.userId] = emp;
                          }
                          return next;
                        });
                      } else {
                        onSelect(emp);
                      }
                    }}
                  >
                    <div className="modal-avatar">{getInitials(emp.name)}</div>
                    <div className="modal-result-info">
                      <p className="modal-employee-name">
                        {emp.name}
                        <span className="modal-employee-role">{emp.positionName}</span>
                      </p>
                      <p className="modal-employee-id">{emp.userId}</p>
                    </div>
                    {scope === 'all' && deptFilter === 'all' && (
                      <span className="modal-employee-dept">{emp.departmentName}</span>
                    )}
                    {multiSelect && isSelected && <span className="modal-selected-check">✓</span>}
                  </div>
                );
              })
```

`modal-footer` 안, `취소` 버튼 앞에 확인 버튼 추가:

```javascript
          {multiSelect && (
            <button
              className="modal-footer-btn active"
              onClick={() => onConfirm(Object.values(selectedMap))}
              disabled={Object.keys(selectedMap).length === 0}
            >
              선택 완료 ({Object.keys(selectedMap).length})
            </button>
          )}
```

- [ ] **Step 8: `src/pages/Chat/ChatPage.jsx` 작성**

```javascript
import React, { useState, useEffect } from 'react';
import './ChatPage.css';
import { useChatRoomsQuery, useChatRoomMessagesQuery } from '../../hooks/queries/useChatQuery';
import { useCreateChatRoomMutation, useMarkChatRoomReadMutation } from '../../hooks/mutations/useChatMutations';
import { useChatSocketContext } from '../../store/ChatSocketContext';
import useAuthStore from '../../store/useAuthStore';
import EmployeeSearchModal from '../../components/EmpSearchModal/EmpSearchModal';

function ChatPage() {
  const currentUser = useAuthStore((state) => state.user);
  const { data: rooms = [] } = useChatRoomsQuery();
  const [selectedRoomId, setSelectedRoomId] = useState(null);
  const [draft, setDraft] = useState('');
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  const { data: messages = [] } = useChatRoomMessagesQuery(selectedRoomId);
  const { sendMessage, setActiveRoom } = useChatSocketContext();
  const createRoomMutation = useCreateChatRoomMutation();
  const markReadMutation = useMarkChatRoomReadMutation();

  useEffect(() => {
    setActiveRoom(selectedRoomId);
    if (selectedRoomId) {
      markReadMutation.mutate(selectedRoomId);
    }
    return () => setActiveRoom(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRoomId]);

  const handleSend = () => {
    if (!draft.trim() || !selectedRoomId) return;
    sendMessage(selectedRoomId, draft.trim());
    setDraft('');
  };

  const handlePickEmployees = (selectedEmployees) => {
    setIsPickerOpen(false);
    if (selectedEmployees.length === 0) return;
    createRoomMutation.mutate(
      {
        memberIds: selectedEmployees.map((e) => e.userId),
        name: selectedEmployees.length > 1 ? selectedEmployees.map((e) => e.name).join(', ') : null,
      },
      { onSuccess: (room) => setSelectedRoomId(room.room_id) }
    );
  };

  const roomLabel = (room) => {
    if (room.name) return room.name;
    const others = room.member_ids.filter((id) => id !== currentUser?.userId);
    return others.join(', ') || '(참여자 없음)';
  };

  return (
    <div className="chat-page">
      <aside className="chat-room-list">
        <button className="chat-new-room-btn" onClick={() => setIsPickerOpen(true)}>+ 새 채팅</button>
        {rooms.map((room) => (
          <div
            key={room.room_id}
            className={`chat-room-item ${selectedRoomId === room.room_id ? 'active' : ''}`}
            onClick={() => setSelectedRoomId(room.room_id)}
          >
            <div className="chat-room-name">{roomLabel(room)}</div>
            <div className="chat-room-preview">{room.last_message || '대화를 시작해보세요'}</div>
            {room.unread_count > 0 && <span className="chat-unread-badge">{room.unread_count}</span>}
          </div>
        ))}
      </aside>

      <section className="chat-thread">
        {selectedRoomId ? (
          <>
            <div className="chat-message-list">
              {[...messages].reverse().map((m) => (
                <div key={m.message_id} className={`chat-message ${m.sender_id === currentUser?.userId ? 'mine' : ''}`}>
                  <span className="chat-message-sender">{m.sender_id}</span>
                  <p>{m.content}</p>
                </div>
              ))}
            </div>
            <div className="chat-input-area">
              <input
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="메시지를 입력하세요"
              />
              <button onClick={handleSend}>전송</button>
            </div>
          </>
        ) : (
          <div className="chat-empty-state">채팅방을 선택하거나 새 채팅을 시작하세요.</div>
        )}
      </section>

      {isPickerOpen && (
        <EmployeeSearchModal multiSelect onConfirm={handlePickEmployees} onClose={() => setIsPickerOpen(false)} />
      )}
    </div>
  );
}

export default ChatPage;
```

- [ ] **Step 9: `src/pages/Chat/ChatPage.css` 작성**

```css
.chat-page {
  display: flex;
  height: calc(100vh - 120px);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.chat-room-list {
  width: 280px;
  border-right: 1px solid #e5e7eb;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.chat-new-room-btn {
  margin: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}

.chat-room-item {
  position: relative;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f3f4f6;
}

.chat-room-item.active {
  background: #eef2ff;
}

.chat-room-name {
  font-weight: 600;
}

.chat-room-preview {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-unread-badge {
  position: absolute;
  right: 16px;
  top: 12px;
  background: #ef4444;
  color: #fff;
  border-radius: 999px;
  font-size: 11px;
  padding: 1px 7px;
}

.chat-thread {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chat-message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-message {
  max-width: 60%;
  background: #f3f4f6;
  border-radius: 8px;
  padding: 8px 12px;
}

.chat-message.mine {
  align-self: flex-end;
  background: #4f46e5;
  color: #fff;
}

.chat-message-sender {
  font-size: 11px;
  opacity: 0.7;
}

.chat-input-area {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid #e5e7eb;
}

.chat-input-area input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
}

.chat-empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
}
```

- [ ] **Step 10: `Sidebar.jsx`에 채팅 메뉴 추가**

`지식 베이스` `NavLink` 블록 다음에 추가:

```javascript
        <NavLink to="/chat" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
          <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
          채팅
        </NavLink>
```

- [ ] **Step 11: `Router.jsx`에 `/chat` 라우트 추가**

import 추가:

```javascript
import ChatPage from "../pages/Chat/ChatPage";
```

`children` 배열에서 `knowledge` 관련 라우트들 다음에 추가:

```javascript
      {
        path: "chat",
        element: <ChatPage />,
      },
```

- [ ] **Step 12: 수동 브라우저 검증**

```bash
cd ieum_frontend
npm run dev
```

두 개의 서로 다른 브라우저(또는 시크릿 창)에서 각각 다른 사번으로 로그인 후:
1. 사이드바 "채팅" 메뉴 진입, "+ 새 채팅"으로 상대 직원 검색 후 선택 → 1:1 방 생성 확인.
2. 한쪽에서 메시지 전송 → 다른 쪽 창에서 새로고침 없이 즉시 메시지가 뜨는지 확인.
3. "+ 새 채팅"에서 직원 2명 이상 선택 후 "선택 완료" → 그룹방 생성 확인 (참여자 이름이 방 이름으로 표시).
4. 채팅방 목록에서 안읽음 배지가 새 메시지 수신 시 올라가고, 방을 열면 사라지는지 확인.

Expected: 위 4가지가 모두 새로고침 없이 정상 동작.

- [ ] **Step 13: 커밋**

```bash
git add src/api/chat.js src/hooks/queries/useChatQuery.js src/hooks/mutations/useChatMutations.js src/hooks/useChatSocket.js src/store/ChatSocketContext.jsx src/layouts/MainLayout.jsx src/components/EmpSearchModal/EmpSearchModal.jsx src/pages/Chat/ChatPage.jsx src/pages/Chat/ChatPage.css src/components/sidebar/Sidebar.jsx src/routes/Router.jsx
git commit -m "feat: 실시간 채팅 페이지(1:1/그룹) 추가 - REST + WebSocket 연동"
```

---

## Task 10: 프론트엔드 — 헤더 알림벨

**Files:**
- Create: `ieum_frontend/src/api/notification.js`
- Create: `ieum_frontend/src/hooks/queries/useNotificationQuery.js`
- Create: `ieum_frontend/src/components/header/NotificationBell.jsx`
- Create: `ieum_frontend/src/components/header/NotificationBell.css`
- Modify: `ieum_frontend/src/components/header/Header.jsx`

**Interfaces:**
- Consumes: Task 9의 `useChatSocketContext`(실시간 갱신용, 직접 이벤트 구독은 안 하고 React Query invalidate로 이미 반영됨), Task 4의 `GET /notifications`. `useMarkChatRoomReadMutation`(Task 9).
- Produces: `<NotificationBell />` 컴포넌트, `useNotificationsQuery()`.

- [ ] **Step 1: `src/api/notification.js` 작성**

```javascript
import api from './axios';

export const getNotifications = async () => {
  const response = await api.get('/notifications');
  return response.data;
};

export const registerDeviceToken = async (fcmToken) => {
  await api.post('/notifications/device-token', { fcm_token: fcmToken });
};

export const unregisterDeviceToken = async (fcmToken) => {
  await api.delete('/notifications/device-token', { data: { fcm_token: fcmToken } });
};
```

- [ ] **Step 2: `src/hooks/queries/useNotificationQuery.js` 작성**

```javascript
import { useQuery } from '@tanstack/react-query';
import { getNotifications } from '../../api/notification';

export const useNotificationsQuery = () => {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: getNotifications,
    refetchInterval: 30000,
  });
};
```

- [ ] **Step 3: `src/components/header/NotificationBell.jsx` 작성**

```javascript
import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './NotificationBell.css';
import { useNotificationsQuery } from '../../hooks/queries/useNotificationQuery';
import { useMarkChatRoomReadMutation } from '../../hooks/mutations/useChatMutations';

function NotificationBell() {
  const { data: notifications = [] } = useNotificationsQuery();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  const markReadMutation = useMarkChatRoomReadMutation();

  useEffect(() => {
    if (!isOpen) return undefined;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const handleClick = (notification) => {
    setIsOpen(false);
    if (notification.room_id) {
      markReadMutation.mutate(notification.room_id);
      navigate(`/chat?room=${notification.room_id}`);
    }
  };

  return (
    <div className="notification-bell" ref={ref}>
      <button className="bell-btn" onClick={() => setIsOpen((v) => !v)} aria-label="알림">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && <span className="bell-badge">{unreadCount}</span>}
      </button>
      {isOpen && (
        <div className="bell-dropdown">
          {notifications.length === 0 ? (
            <div className="bell-empty">알림이 없습니다.</div>
          ) : (
            notifications.map((n) => (
              <div
                key={n.notification_id}
                className={`bell-item ${n.is_read ? '' : 'unread'}`}
                onClick={() => handleClick(n)}
              >
                새 채팅 메시지가 도착했습니다.
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default NotificationBell;
```

- [ ] **Step 4: `src/components/header/NotificationBell.css` 작성**

```css
.notification-bell {
  position: relative;
}

.bell-btn {
  position: relative;
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px;
  color: #374151;
}

.bell-badge {
  position: absolute;
  top: 0;
  right: 0;
  background: #ef4444;
  color: #fff;
  border-radius: 999px;
  font-size: 10px;
  padding: 1px 5px;
}

.bell-dropdown {
  position: absolute;
  right: 0;
  top: 32px;
  width: 280px;
  max-height: 320px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 50;
}

.bell-item {
  padding: 10px 14px;
  font-size: 13px;
  cursor: pointer;
  border-bottom: 1px solid #f3f4f6;
}

.bell-item.unread {
  background: #eef2ff;
  font-weight: 600;
}

.bell-empty {
  padding: 16px;
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
}
```

- [ ] **Step 5: `Header.jsx`에 알림벨 삽입**

```javascript
import React from 'react';
import './Header.css';
import { useLogoutMutation } from "../../hooks/mutations/useAuthMutation";
import { useNavigate } from 'react-router-dom';
import useAuthStore from '../../store/useAuthStore';
import NotificationBell from './NotificationBell';

function Header({ title, currentDate }) {
  const { mutate: logoutMutate } = useLogoutMutation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const authLogout = useAuthStore((state) => state.logout);

  const handleLogout = () => {
    if (!refreshToken) {
      console.error("Logout impossible: No refresh token found.");
      authLogout();
      navigate('/login');
      return;
    }
    logoutMutate(refreshToken, {
      onSettled: () => {
        authLogout();
        navigate('/login');
      },
    });
  };

  return (
    <div className="topbar">
      <h1>{title}</h1>
      <div className="topbar-right">
        <NotificationBell />
        <span>안녕하세요, <b>{user?.name || '사용자'}</b>님</span>
        <span>|</span>
        <span>{currentDate}</span>
        <button className="logout-pill" onClick={handleLogout}>로그아웃</button>
      </div>
    </div>
  );
}

export default Header;
```

- [ ] **Step 6: 수동 브라우저 검증**

두 계정으로 로그인한 상태에서, 한쪽이 다른 화면(채팅방 밖)에 있을 때 상대가 메시지를 보내면:
1. 헤더 벨 아이콘에 빨간 배지 숫자가 뜨는지 확인 (최대 30초 이내, `refetchInterval` 또는 WS `notification` 이벤트로 인한 즉시 반영).
2. 벨을 클릭해 드롭다운에서 항목 클릭 → `/chat`으로 이동하고 배지가 사라지는지 확인.

- [ ] **Step 7: 커밋**

```bash
git add src/api/notification.js src/hooks/queries/useNotificationQuery.js src/components/header/NotificationBell.jsx src/components/header/NotificationBell.css src/components/header/Header.jsx
git commit -m "feat: 헤더 알림벨(새 채팅 메시지) 추가"
```

---

## Task 11: 프론트엔드 — FCM 웹 푸시 연동

**Files:**
- Modify: `ieum_frontend/package.json` (via `npm install`)
- Create: `ieum_frontend/src/firebase/firebaseConfig.js`
- Create: `ieum_frontend/public/firebase-messaging-sw.js`
- Create: `ieum_frontend/src/hooks/useFcmToken.js`
- Modify: `ieum_frontend/src/layouts/MainLayout.jsx`
- Modify: `ieum_frontend/.env.sample`

**Interfaces:**
- Consumes: Task 10의 `registerDeviceToken`/`unregisterDeviceToken`.
- Produces: `useFcmToken()` — 부수효과 훅(반환값 없음), 로그인 시 토큰 등록, 언마운트(로그아웃 경로 이동)시 해제.

- [ ] **Step 1: Firebase SDK 설치**

```bash
cd ieum_frontend
npm install firebase
```

- [ ] **Step 2: `.env.sample`에 Firebase 변수 추가**

```
VITE_API_BASE_URL=http://localhost:8000
VITE_EXTERNAL_PETITION_API_KEY=your-api-key-here

# Firebase Cloud Messaging (웹 푸시) - Firebase 콘솔 > 프로젝트 설정에서 발급
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
VITE_FIREBASE_VAPID_KEY=
```

- [ ] **Step 3: `src/firebase/firebaseConfig.js` 작성**

Vite는 `public/`의 정적 파일(서비스워커)에 `import.meta.env` 값을 주입하지 않으므로, 서비스워커 등록 URL에 설정값을 쿼리 파라미터로 실어 전달한다.

```javascript
import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

let messagingInstance = null;

function getFirebaseMessaging() {
  if (!firebaseConfig.apiKey) return null;
  if (!messagingInstance) {
    const app = initializeApp(firebaseConfig);
    messagingInstance = getMessaging(app);
  }
  return messagingInstance;
}

async function ensureServiceWorkerRegistration() {
  const params = new URLSearchParams(firebaseConfig).toString();
  return navigator.serviceWorker.register(`/firebase-messaging-sw.js?${params}`);
}

export async function requestFcmToken() {
  if (!firebaseConfig.apiKey || !('serviceWorker' in navigator) || !('Notification' in window)) {
    return null;
  }

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return null;

  const messaging = getFirebaseMessaging();
  if (!messaging) return null;

  try {
    const registration = await ensureServiceWorkerRegistration();
    return await getToken(messaging, {
      vapidKey: import.meta.env.VITE_FIREBASE_VAPID_KEY,
      serviceWorkerRegistration: registration,
    });
  } catch (error) {
    console.error('FCM 토큰 발급 실패:', error);
    return null;
  }
}

export function listenForForegroundMessages(onMessageReceived) {
  const messaging = getFirebaseMessaging();
  if (!messaging) return () => {};
  return onMessage(messaging, onMessageReceived);
}
```

- [ ] **Step 4: `public/firebase-messaging-sw.js` 작성**

```javascript
importScripts('https://www.gstatic.com/firebasejs/10.13.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.13.0/firebase-messaging-compat.js');

const params = new URL(location.href).searchParams;

firebase.initializeApp({
  apiKey: params.get('apiKey'),
  authDomain: params.get('authDomain'),
  projectId: params.get('projectId'),
  messagingSenderId: params.get('messagingSenderId'),
  appId: params.get('appId'),
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const { title, body } = payload.notification || {};
  self.registration.showNotification(title || '새 메시지', {
    body: body || '',
    icon: '/icon.png',
  });
});
```

- [ ] **Step 5: `src/hooks/useFcmToken.js` 작성**

```javascript
import { useEffect } from 'react';
import { requestFcmToken, listenForForegroundMessages } from '../firebase/firebaseConfig';
import { registerDeviceToken, unregisterDeviceToken } from '../api/notification';
import useAuthStore from '../store/useAuthStore';

export function useFcmToken() {
  const token = useAuthStore((state) => state.token);

  useEffect(() => {
    if (!token) return undefined;

    let currentFcmToken = null;

    (async () => {
      currentFcmToken = await requestFcmToken();
      if (currentFcmToken) {
        try {
          await registerDeviceToken(currentFcmToken);
        } catch (error) {
          console.error('FCM 토큰 등록 실패:', error);
        }
      }
    })();

    const unsubscribe = listenForForegroundMessages((payload) => {
      console.log('포그라운드 메시지 수신:', payload);
    });

    return () => {
      unsubscribe();
      if (currentFcmToken) {
        unregisterDeviceToken(currentFcmToken).catch(() => {});
      }
    };
  }, [token]);
}
```

- [ ] **Step 6: `MainLayout.jsx`에서 훅 호출**

import 추가:

```javascript
import { useFcmToken } from "../hooks/useFcmToken";
```

`MainLayout` 함수 본문 맨 위(`const outlet = useOutlet();` 다음 줄)에 추가:

```javascript
  useFcmToken();
```

- [ ] **Step 7: 수동 브라우저 검증 (Firebase 프로젝트 및 `.env`에 실제 값이 채워져 있어야 함)**

1. 로그인 후 브라우저 알림 권한 요청 팝업이 뜨는지 확인, 허용.
2. 개발자 도구 Application 탭에서 `firebase-messaging-sw.js`가 등록되어 있는지 확인.
3. 채팅 탭을 백그라운드로 두거나(다른 탭으로 이동) 브라우저 자체를 최소화한 상태에서, 다른 계정으로 메시지 전송.
4. OS 알림 센터에 푸시 알림이 뜨는지 확인.
5. `.env`에 Firebase 값이 비어 있는 환경에서는 위 과정이 조용히 스킵되고(에러 없이) 채팅/알림벨 기능 자체는 정상 동작하는지 확인.

- [ ] **Step 8: 커밋**

```bash
git add package.json package-lock.json src/firebase/firebaseConfig.js public/firebase-messaging-sw.js src/hooks/useFcmToken.js src/layouts/MainLayout.jsx .env.sample
git commit -m "feat: Firebase 웹 푸시(FCM) 토큰 발급/등록 및 서비스워커 연동"
```

---

## 완료 후 남는 것 (범위 밖, 참고용)

- Firebase 프로젝트 생성 + 서비스 계정 JSON + VAPID 키 발급은 사용자가 Firebase 콘솔에서 직접 진행해야 하며, 이 플랜의 코드는 해당 값이 없어도 채팅 자체는 정상 동작한다.
- 배포 환경이 다중 인스턴스로 바뀌면 `chat_connection_manager`를 Redis pub/sub 등으로 교체해야 한다 (설계 문서에 명시된 범위 밖 사항).
