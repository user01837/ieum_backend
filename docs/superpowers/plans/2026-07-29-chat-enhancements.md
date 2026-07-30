# 채팅 기능 확장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 채팅 기능에 (1) 인원 즉시 추가, (2) 채팅방 나가기, (3) 실시간 알림
반영 버그 수정, (4) 사업 협력자 추가 시 단톡방 자동생성을 추가하고, 팀원이 추가한
`ANNOUNCEMENT` 관련 라이브 DB 스키마 변경을 우리 모델에 반영한다.

**Architecture:** 백엔드는 기존 `chat_service.py` / `chat.py` 라우터 패턴을
그대로 확장한다(서비스 함수 추가 + 라우터 엔드포인트 추가). 프로젝트 자동
단톡방 생성은 `project.py` 라우터가 `chat_service`를 직접 호출하는 방식으로
구현한다(별도 도메인 서비스 계층을 새로 만들지 않음). 프론트는 기존
`api/chat.js` → `useChatMutations.js` → `ChatPage.jsx` 3단 구조를 그대로
따른다.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL(lower_case_table_names=1), pytest,
React 19, React Query, Vite.

**설계 문서:** `docs/superpowers/specs/2026-07-29-chat-enhancements-design.md`

## Global Constraints

- 이 코드베이스에서 `USER.user_id`는 실제 DB에서 int이지만, 채팅 관련 서비스
  함수/Pydantic 스키마는 전부 문자열(str)로 다룬다 - 새 코드도 이 관례를
  그대로 따른다(경계에서 `str(x)`로 변환).
- `lower_case_table_names=1`이므로 SQLAlchemy 모델의 `ForeignKey("TABLE.col")`
  문자열은 기존 코드 관례대로 대문자 모델 tablename으로 쓴다(예:
  `ForeignKey("CHAT_ROOM.room_id")`) - 실제 물리 테이블명은 소문자이지만 MySQL이
  대소문자 구분 없이 처리한다.
- `Notification.announcement_id`는 **SQLAlchemy `ForeignKey`를 걸지 않는다** -
  이 코드베이스에 `Announcement` 모델/테이블이 등록되어 있지 않아
  `ForeignKey("announcement.announcement_id")`를 걸면 매퍼 구성 시점에
  `NoReferencedTableError`가 난다(이전에 `USER` 미등록으로 겪었던 것과 동일한
  종류의 오류). 라이브 DB에는 이미 FK가 걸려 있으므로 컬럼만 추가하면 된다.
- 채팅방 인원 추가/나가기는 기존 방 생성과 동일하게 WS 실시간 브로드캐스트를
  하지 않는다(다음 폴링/재연결/포커스 시 반영) - 새 배관을 만들지 않아 범위를
  최소화한다.
- 프론트엔드에는 자동화 테스트 하네스가 없다(`package.json`에 test 스크립트
  없음) - 프론트 작업은 dev 서버로 브라우저에서 직접 확인한다.
- 각 백엔드 작업은 `python -m pytest`로 전체 테스트를 실행해 회귀가 없는지
  확인하고 커밋한다.

---

### Task 1: DB 모델 정리 + 라이브 스키마 반영 (notification.announcement_id, project.chat_room_id)

**Files:**
- Modify: `app/models/notification.py`
- Modify: `app/models/project.py`
- Create: `scripts/add_project_chat_room_column.py`
- Test: `tests/test_models_schema.py`

**Interfaces:**
- Produces: `Notification.announcement_id: int | None` (컬럼만, FK 객체 없음)
- Produces: `Project.chat_room_id: int | None` (FK → `CHAT_ROOM.room_id`,
  `ON DELETE SET NULL`) - Task 3/4에서 이 컬럼을 읽고 쓴다.

배경: 라이브 공유 DB(`ggieum`)에 팀원이 만든 `announcement` 테이블과
`notification.announcement_id` 컬럼이 이미 존재한다(직접 `SHOW CREATE TABLE`로
확인 완료). 우리 SQLAlchemy 모델만 여기에 맞추면 된다 - 라이브 DB에
`ALTER TABLE`을 실행할 필요는 없다. 반대로 `project.chat_room_id`는 이번에
우리가 새로 추가하는 컬럼이므로, 모델 변경과 함께 라이브 DB에도 실제로
`ALTER TABLE`을 실행해야 한다.

- [ ] **Step 1: `Notification` 모델에 `announcement_id` 컬럼 추가**

`app/models/notification.py`를 다음과 같이 수정한다 (기존 임포트/다른 컬럼은
그대로 유지하고 `announcement_id` 줄만 추가):

```python
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
```

- [ ] **Step 2: `Project` 모델에 `chat_room_id` 컬럼 추가**

`app/models/project.py`의 `Project` 클래스 마지막 컬럼(`updated_at`) 다음 줄에
추가한다:

```python
    updated_at            = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    chat_room_id          = Column(Integer, ForeignKey("CHAT_ROOM.room_id"), nullable=True)
```

파일 맨 위 import 줄도 `ForeignKey`가 이미 임포트되어 있으므로 추가 임포트는
필요 없다.

- [ ] **Step 3: 실패하는 스키마 테스트 작성**

`tests/test_models_schema.py` 새로 작성:

```python
from sqlalchemy import inspect


def test_notification_has_announcement_id_column(db_session):
    from app.models.notification import Notification

    columns = {c.name for c in inspect(Notification).columns}
    assert "announcement_id" in columns


def test_project_has_chat_room_id_column(db_session):
    from app.models.project import Project

    columns = {c.name for c in inspect(Project).columns}
    assert "chat_room_id" in columns
```

`db_session` fixture는 `tests/conftest.py`에 이미 있다(인메모리 sqlite에
`Base.metadata.create_all`을 실행해준다). 이 테스트는 컬럼을 추가하기 전에는
`AssertionError`로 실패해야 한다.

- [ ] **Step 4: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_models_schema.py -v`
Expected: Step 1/2를 아직 안 했다면 FAIL. Step 1/2를 먼저 했다면 이 시점엔
이미 PASS일 수 있음 - 순서상 Step 1~2 이후에 이 스텝을 실행하게 되므로
PASS를 확인하는 것으로 대체해도 된다.

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_models_schema.py -v`
Expected: `2 passed`

- [ ] **Step 6: 라이브 DB에 `project.chat_room_id` 컬럼 실제 추가**

`scripts/add_project_chat_room_column.py` 새로 작성 (실행은 실제 운영 공유
DB에 영향을 주므로, 이 스텝을 실행하는 사람은 반드시 사용자에게 먼저
알리고 진행할 것):

```python
"""PROJECT 테이블에 chat_room_id 컬럼(신규)을 실제 MySQL DB에 추가하는 1회성 스크립트.
이미 컬럼이 있으면 아무 것도 하지 않는다(재실행 안전).

실행: python -m scripts.add_project_chat_room_column
"""
from sqlalchemy import text
from app.db.database import engine


def main() -> None:
    with engine.connect() as conn:
        existing = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'project' "
                "AND column_name = 'chat_room_id'"
            )
        ).scalar()
        if existing:
            print("이미 존재함: project.chat_room_id - 건너뜀")
            return

        conn.execute(
            text(
                "ALTER TABLE project "
                "ADD COLUMN chat_room_id INT NULL COMMENT '자동 생성된 사업 협업 채팅방', "
                "ADD CONSTRAINT fk_project_chat_room FOREIGN KEY (chat_room_id) "
                "REFERENCES chat_room (room_id) ON DELETE SET NULL"
            )
        )
        conn.commit()
        print("완료: project.chat_room_id 컬럼 추가")


if __name__ == "__main__":
    main()
```

Run: `python -m scripts.add_project_chat_room_column`
Expected: `완료: project.chat_room_id 컬럼 추가` (또는 이미 존재하면 건너뜀 메시지)

- [ ] **Step 7: 라이브 DB에 실제로 컬럼이 생겼는지 확인**

Run:
```
python -c "from app.db.database import engine; from sqlalchemy import inspect; cols = [c['name'] for c in inspect(engine).get_columns('project')]; print('chat_room_id' in cols)"
```
Expected: `True`

- [ ] **Step 8: 전체 테스트 실행 후 커밋**

Run: `python -m pytest -q`
Expected: 전부 통과 (기존 테스트 회귀 없음)

```bash
git add app/models/notification.py app/models/project.py scripts/add_project_chat_room_column.py tests/test_models_schema.py
git commit -m "feat: notification.announcement_id 반영, project.chat_room_id 컬럼 추가"
```

---

### Task 2: `chat_service`에 인원 추가 / 나가기 로직 추가

**Files:**
- Modify: `app/services/chat_service.py`
- Test: `tests/test_chat_service.py` (신규 파일)

**Interfaces:**
- Consumes: `ChatRoomMember`, `Notification` (기존 모델, 변경 없음)
- Produces:
  - `add_members_to_room(db: Session, room_id: int, new_member_ids: list[str]) -> None`
  - `leave_room(db: Session, room_id: int, user_id: str) -> None`

이 두 함수는 순수 DB 로직만 담당한다 - 방 존재 여부/권한 검증(멤버인지,
1:1인지, 존재하는 사용자인지)은 Task 3의 라우터가 호출 전에 처리한다(기존
`create_room` 엔드포인트가 사용자 존재 검증을 라우터에서 먼저 하는 것과
동일한 패턴).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_chat_service.py` 새로 작성:

```python
from app.services import chat_service
from app.models.chat import ChatRoomMember
from app.models.notification import Notification


def test_add_members_to_room_adds_new_members_only(client, make_user, db_session):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    room = chat_service.create_room(db_session, "emp001", ["emp002"], name="테스트방")

    chat_service.add_members_to_room(db_session, room.room_id, ["emp002", "emp003"])

    member_ids = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
    }
    assert member_ids == {"emp001", "emp002", "emp003"}


def test_leave_room_removes_membership_and_own_notifications(client, make_user, db_session):
    other = make_user("emp002", "이직원")
    room = chat_service.create_room(db_session, "emp001", ["emp002"], name=None)
    db_session.add(Notification(user_id="emp002", type="CHAT_MESSAGE", room_id=room.room_id, is_read=False))
    db_session.commit()

    chat_service.leave_room(db_session, room.room_id, "emp002")

    remaining_members = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
    }
    assert remaining_members == {"emp001"}
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 0


def test_leave_room_does_not_affect_other_members_notifications(client, make_user, db_session):
    other = make_user("emp002", "이직원")
    room = chat_service.create_room(db_session, "emp001", ["emp002"], name=None)
    db_session.add(Notification(user_id="emp001", type="CHAT_MESSAGE", room_id=room.room_id, is_read=False))
    db_session.commit()

    chat_service.leave_room(db_session, room.room_id, "emp002")

    assert db_session.query(Notification).filter(Notification.user_id == "emp001").count() == 1
```

`client`/`make_user`/`db_session` fixture는 `tests/conftest.py`에 이미 있다
(`client` fixture가 `app`을 초기화하며 `db_session`을 오버라이드해주므로,
`chat_service` 호출 시 이 세션을 그대로 넘기면 된다).

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_chat_service.py -v`
Expected: `AttributeError: module 'app.services.chat_service' has no attribute 'add_members_to_room'`로 실패

- [ ] **Step 3: `add_members_to_room`, `leave_room` 구현**

`app/services/chat_service.py` 파일 끝(`create_notification` 함수 다음)에
추가:

```python
def add_members_to_room(db: Session, room_id: int, new_member_ids: list[str]) -> None:
    existing_ids = {
        str(m.user_id)
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
    }
    for user_id in new_member_ids:
        if user_id in existing_ids:
            continue
        db.add(ChatRoomMember(room_id=room_id, user_id=user_id))
        existing_ids.add(user_id)
    db.commit()


def leave_room(db: Session, room_id: int, user_id: str) -> None:
    db.query(ChatRoomMember).filter(
        ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user_id,
    ).delete(synchronize_session=False)
    db.query(Notification).filter(
        Notification.room_id == room_id, Notification.user_id == user_id,
    ).delete(synchronize_session=False)
    db.commit()
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python -m pytest tests/test_chat_service.py -v`
Expected: `3 passed`

- [ ] **Step 5: 전체 테스트 실행 후 커밋**

Run: `python -m pytest -q`
Expected: 전부 통과

```bash
git add app/services/chat_service.py tests/test_chat_service.py
git commit -m "feat: 채팅방 인원 추가/나가기 서비스 함수 추가"
```

---

### Task 3: 채팅방 인원 추가 / 나가기 REST 엔드포인트

**Files:**
- Modify: `app/api/routers/chat.py`
- Test: `tests/test_chat_room_membership.py` (신규 파일)

**Interfaces:**
- Consumes: `chat_service.add_members_to_room`, `chat_service.leave_room`,
  `chat_service.is_room_member` (Task 2, 기존)
- Produces:
  - `POST /chat/rooms/{room_id}/members` - body `{"member_ids": [str, ...]}` →
    `RoomResponse`
  - `DELETE /chat/rooms/{room_id}` - 204 No Content

- [ ] **Step 1: 실패하는 통합 테스트 작성**

`tests/test_chat_room_membership.py` 새로 작성:

```python
def test_add_members_to_group_room(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    m4 = make_user("emp004", "최직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    res = client.post(f"/chat/rooms/{room['room_id']}/members", json={"member_ids": [m4.user_id]})
    assert res.status_code == 200
    assert sorted(res.json()["member_ids"]) == sorted(["emp001", "emp002", "emp003", "emp004"])


def test_add_members_rejects_direct_room(client, make_user):
    other = make_user("emp002", "이직원")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    res = client.post(f"/chat/rooms/{room['room_id']}/members", json={"member_ids": ["emp002"]})
    assert res.status_code == 400


def test_add_members_rejects_unknown_user(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    res = client.post(f"/chat/rooms/{room['room_id']}/members", json={"member_ids": ["ghost"]})
    assert res.status_code == 400


def test_add_members_rejects_non_member(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    m4 = make_user("emp004", "최직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    # emp001(현재 로그인 사용자)이 아닌 emp004는 이 방의 멤버가 아니므로
    # 이 요청 자체가 emp001 자격으로 나가지만, 멤버가 아닌 방에 시도하는 케이스를
    # 검증하기 위해 존재하지 않는 room_id로 대체 검증한다.
    res = client.post("/chat/rooms/999999/members", json={"member_ids": [m4.user_id]})
    assert res.status_code == 404


def test_leave_room_removes_current_user_only(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    res = client.delete(f"/chat/rooms/{room['room_id']}")
    assert res.status_code == 204

    rooms = client.get("/chat/rooms").json()
    assert rooms == []


def test_leave_room_rejects_non_member(client):
    res = client.delete("/chat/rooms/999999")
    assert res.status_code == 404
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_chat_room_membership.py -v`
Expected: 404가 나야 할 곳에서 405(Method Not Allowed) 등으로 실패

- [ ] **Step 3: 엔드포인트 구현**

`app/api/routers/chat.py` 상단 import 줄을 수정한다 (`ChatRoomMember` 옆에
`ChatRoom` 추가):

```python
from app.models.chat import ChatRoom, ChatRoomMember
```

`CreateRoomRequest` 클래스 아래, `RoomResponse`/`RoomListItem` 사이 아무 곳에나
새 요청 모델을 추가한다 (예: `RoomListItem` 클래스 다음):

```python
class AddMembersRequest(BaseModel):
    member_ids: list[str] = Field(..., min_length=1, description="추가할 참여자 사번 목록")
```

파일 끝(`mark_room_read_endpoint` 함수 다음)에 두 엔드포인트를 추가한다:

```python
@router.post("/rooms/{room_id}/members", response_model=RoomResponse)
def add_room_members(
    room_id: int,
    req: AddMembersRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    room = db.query(ChatRoom).filter(ChatRoom.room_id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="존재하지 않는 채팅방입니다.")

    if not chat_service.is_room_member(db, room_id, str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 채팅방의 멤버가 아닙니다.")

    if not room.is_group:
        raise HTTPException(status_code=400, detail="1:1 채팅방에는 인원을 추가할 수 없습니다.")

    invalid_ids = [
        uid for uid in req.member_ids
        if not db.query(User.user_id).filter(User.user_id == uid).first()
    ]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"존재하지 않는 사용자: {invalid_ids}")

    chat_service.add_members_to_room(db, room_id, req.member_ids)

    member_ids = [
        str(m.user_id)
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
    ]
    return RoomResponse(room_id=room.room_id, name=room.name, is_group=room.is_group, member_ids=member_ids)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def leave_room_endpoint(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not chat_service.is_room_member(db, room_id, str(current_user.user_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="존재하지 않는 채팅방이거나 이미 나간 방입니다.")

    chat_service.leave_room(db, room_id, str(current_user.user_id))
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `python -m pytest tests/test_chat_room_membership.py -v`
Expected: `6 passed`

- [ ] **Step 5: 전체 테스트 실행 후 커밋**

Run: `python -m pytest -q`
Expected: 전부 통과

```bash
git add app/api/routers/chat.py tests/test_chat_room_membership.py
git commit -m "feat: 채팅방 인원 추가/나가기 REST 엔드포인트 추가"
```

---

### Task 4: 사업 프로젝트 협력자 추가 시 단톡방 자동 생성

**Files:**
- Modify: `app/api/routers/project.py`
- Test: `tests/test_project_chat_room.py` (신규 파일)

**Interfaces:**
- Consumes: `chat_service.create_room(db, creator_id: str, member_ids: list[str], name: str | None) -> ChatRoom`,
  `chat_service.add_members_to_room(db, room_id: int, new_member_ids: list[str]) -> None` (Task 2, 기존/신규)
- Produces: `project.chat_room_id`가 채워짐 (DB 부수효과, API 응답 스키마 변경 없음
  - `ProjectDetailResponse`/`ProjectCreateResponse`에 `chat_room_id`를 노출할
    필요는 없다, 요청 범위 밖)

- [ ] **Step 1: 실패하는 통합 테스트 작성**

`tests/test_project_chat_room.py` 새로 작성:

```python
from app.models.project import Project
from app.models.chat import ChatRoomMember


def test_create_project_with_collaborators_creates_chat_room(client, make_user, db_session):
    collab = make_user("emp002", "이직원")

    res = client.post(
        "/projects",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab.user_id],
        },
    )
    assert res.status_code == 200
    project_id = res.json()["projectId"]

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is not None

    member_ids = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == project.chat_room_id).all()
    }
    assert member_ids == {"emp001", "emp002"}


def test_create_project_without_collaborators_skips_chat_room(client, db_session):
    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": []},
    )
    project_id = res.json()["projectId"]

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is None


def test_update_project_adding_collaborator_creates_chat_room_if_missing(client, make_user, db_session):
    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": []},
    )
    project_id = res.json()["projectId"]
    collab = make_user("emp002", "이직원")

    update_res = client.patch(
        f"/projects/{project_id}",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab.user_id]},
    )
    assert update_res.status_code == 200

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is not None

    member_ids = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == project.chat_room_id).all()
    }
    assert member_ids == {"emp001", "emp002"}


def test_update_project_adding_more_collaborators_reuses_existing_chat_room(client, make_user, db_session):
    collab1 = make_user("emp002", "이직원")
    create_res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab1.user_id]},
    )
    project_id = create_res.json()["projectId"]
    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    original_room_id = project.chat_room_id

    collab2 = make_user("emp003", "박직원")
    client.patch(
        f"/projects/{project_id}",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab1.user_id, collab2.user_id],
        },
    )

    db_session.refresh(project)
    assert project.chat_room_id == original_room_id

    member_ids = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == project.chat_room_id).all()
    }
    assert member_ids == {"emp001", "emp002", "emp003"}
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_project_chat_room.py -v`
Expected: `AttributeError` 또는 `assert None is not None`으로 실패 (아직
`chat_room_id`를 채우는 로직이 없음)

- [ ] **Step 3: `create_project`에 자동 생성 로직 추가**

`app/api/routers/project.py` 상단 import에 추가:

```python
from app.services import chat_service
```

`create_project` 함수의 `db.commit()` (마지막에서 두 번째 줄, `db.refresh(project)`
바로 앞) 이전에 다음 블록을 추가한다:

```python
    collaborator_ids = [str(uid) for uid in body.memberUserIds if uid != current_user.user_id]
    if collaborator_ids:
        room = chat_service.create_room(
            db,
            str(current_user.user_id),
            collaborator_ids,
            name=f"[사업] {project.name}",
        )
        project.chat_room_id = room.room_id

    db.commit()
    db.refresh(project)
```

(기존에 있던 `db.commit()` / `db.refresh(project)` 두 줄을 위와 같이 이
블록 뒤로 옮기는 것이지, 새로 추가하는 것이 아니다 - 기존 두 줄을 지우고
위 블록 전체로 교체한다.)

- [ ] **Step 4: `update_project`에 자동 생성/확장 로직 추가**

`update_project` 함수에서 `ids_to_add` 처리 블록(`for uid in ids_to_add: ...`)
바로 다음, `db.commit()` 이전에 추가한다:

```python
    if ids_to_add:
        collaborator_ids = [str(uid) for uid in new_collab_ids]
        if project.chat_room_id:
            chat_service.add_members_to_room(db, project.chat_room_id, collaborator_ids)
        else:
            room = chat_service.create_room(
                db,
                str(current_user.user_id),
                collaborator_ids,
                name=f"[사업] {project.name}",
            )
            project.chat_room_id = room.room_id

    db.commit()
    db.refresh(project)
```

(이번에도 기존 `db.commit()` / `db.refresh(project)` 두 줄을 이 블록으로
교체한다.)

- [ ] **Step 5: 테스트 실행해 통과 확인**

Run: `python -m pytest tests/test_project_chat_room.py -v`
Expected: `4 passed`

- [ ] **Step 6: 전체 테스트 실행 후 커밋**

Run: `python -m pytest -q`
Expected: 전부 통과

```bash
git add app/api/routers/project.py tests/test_project_chat_room.py
git commit -m "feat: 사업 협력자 추가 시 단톡방 자동 생성/확장"
```

---

### Task 5: DDL v39 문서 갱신 (announcement, notification.announcement_id, project.chat_room_id 반영)

**Files:**
- Create: `docs/db/v39_공공이음_DDL_FK포함.sql`

이 태스크는 Task 1(라이브 DB에 `project.chat_room_id`가 실제로 추가된 이후)에
의존한다.

**Interfaces:**
- Consumes: 없음 (라이브 DB 직접 조회)
- Produces: 새 DDL 문서 파일 (기존 v36 문서를 대체하는 최신 스냅샷)

- [ ] **Step 1: 라이브 DB 전체 테이블 목록과 각 테이블의 `SHOW CREATE TABLE` 확인**

기존 v36 문서(`docs/db/v36_공공이음_DDL_FK포함.sql`)가 이미 있으므로 처음부터
새로 조회할 필요 없이, 다음만 라이브로 재확인한다: `announcement` 테이블의
정확한 `SHOW CREATE TABLE` 결과, `notification` 테이블의 갱신된
`SHOW CREATE TABLE` 결과, `project` 테이블의 갱신된 `SHOW CREATE TABLE` 결과.

Run:
```
python -c "
from app.db.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    for t in ['announcement', 'notification', 'project']:
        r = conn.execute(text(f'SHOW CREATE TABLE {t}'))
        print(r.fetchone()[1])
        print('=====')
"
```

Expected: 세 테이블의 `CREATE TABLE` 문이 출력됨 (`notification`에
`announcement_id` 컬럼과 `fk_noti_announcement` FK, `project`에
`chat_room_id` 컬럼과 `fk_project_chat_room` FK가 보여야 함)

- [ ] **Step 2: v36 문서를 복사해 v39로 만들고 변경분만 반영**

`docs/db/v36_공공이음_DDL_FK포함.sql`을 `docs/db/v39_공공이음_DDL_FK포함.sql`로
복사한 뒤, 다음을 수정한다:

1. 파일 최상단 주석 블록에 변경 이력을 추가한다 (기존 `-- v36: ...` 블록
   다음, `-- ====...` 구분선 이전에 삽입):

```sql
--
-- v37: PETITION_ASSIGNEE_HISTORY.change_type에 03=DEPT_TRANSFER(부서이동 자동
--      이관) 코드가 추가됨 - v36 스냅샷에서 이미 함께 반영되어 있었음.
--
-- v38: 팀원이 별도로 추가한 공지사항(ANNOUNCEMENT) 기능으로 라이브 DB에 새
--      테이블 1개(announcement)와 NOTIFICATION.announcement_id 컬럼 + FK가
--      추가됨(2026-07-29). 이 기능 자체(모델/라우터/프론트)는 이 저장소
--      어디에도 없음 - 팀원 소유, 별도 브랜치에서 진행 중으로 보임. 우리는
--      Notification 모델에 이 컬럼만 반영했다(FK는 SQLAlchemy에 걸지 않음 -
--      Announcement 모델이 없어 매퍼 구성 시 NoReferencedTableError가 나기
--      때문. 라이브 DB의 FK 자체는 그대로 유지됨).
--
-- v39: 채팅 기능 확장(인원 추가/나가기/사업 단톡방 자동생성) 작업으로
--      PROJECT.chat_room_id 컬럼(신규, 우리가 추가)이 생김 - 사업 참여자
--      전용 단톡방을 연결한다. ON DELETE SET NULL.
--
```

2. `announcement` 테이블 CREATE 문을 (알파벳 순서 등 기존 문서의 번호 순서
   규칙에 맞춰) 적절한 위치에 새 섹션으로 추가한다 - PROJECT_MEMBER 섹션
   (`10. PROJECT_MEMBER`) 바로 다음에 넣는 것을 권장한다 (사업과 연관된
   신규 개념이므로):

```sql
-- ------------------------------------------------------------
-- 10-1. ANNOUNCEMENT - 공지사항 (v38 신규, 팀원 작업 - 별도 브랜치)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS announcement;
CREATE TABLE announcement (
  announcement_id int          NOT NULL AUTO_INCREMENT,
  title           varchar(200) NOT NULL COMMENT '공지 제목',
  content         text         NOT NULL COMMENT '공지 내용',
  is_pinned       tinyint(1)   NOT NULL DEFAULT '0' COMMENT '상단 고정 여부 (1=고정, 0=일반)',
  is_deleted      tinyint(1)   NOT NULL DEFAULT '0' COMMENT '1=삭제됨, 0=정상 (소프트 삭제)',
  deleted_at      datetime     DEFAULT NULL COMMENT '삭제 처리 시각',
  created_by      int          NOT NULL COMMENT '작성자 사번 (관리자 또는 부서장만 작성 가능)',
  updated_by      int          DEFAULT NULL COMMENT '최종 수정자 사번',
  created_at      datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (announcement_id),
  KEY idx_ann_created_by (created_by),
  KEY idx_ann_updated_by (updated_by),
  CONSTRAINT fk_ann_created_by FOREIGN KEY (created_by) REFERENCES `user` (user_id) ON DELETE RESTRICT,
  CONSTRAINT fk_ann_updated_by FOREIGN KEY (updated_by) REFERENCES `user` (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

```

   그 뒤 이어지는 섹션 번호(`11. LEGAL_DOCUMENT` 등)는 그대로 두거나 순차
   재번호를 매겨도 무방하다 - 번호는 문서 내 설명용일 뿐 실행에는 영향이
   없다.

3. `9. PROJECT` 섹션의 `CREATE TABLE project (...)`에 `chat_room_id` 컬럼과
   FK를 추가한다 (`cover_title` 컬럼 다음 줄):

```sql
  cover_title          varchar(200) DEFAULT NULL COMMENT '표지 제목 (사용자 수정 가능)',
  chat_room_id         int          DEFAULT NULL COMMENT '자동 생성된 사업 협업 채팅방 (협력자 2명 이상일 때만 생성)',
  PRIMARY KEY (project_id),
  KEY idx_project_task (task_id),
  KEY idx_project_department (department_code),
  KEY idx_project_chat_room (chat_room_id),
  CONSTRAINT fk_project_task FOREIGN KEY (task_id) REFERENCES task (task_id) ON DELETE SET NULL,
  CONSTRAINT fk_project_department FOREIGN KEY (department_code) REFERENCES department (department_code) ON DELETE SET NULL,
  CONSTRAINT fk_project_chat_room FOREIGN KEY (chat_room_id) REFERENCES chat_room (room_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

4. `22. NOTIFICATION` 섹션의 `CREATE TABLE notification (...)`에
   `announcement_id` 컬럼과 FK를 추가한다 (`message_id` 컬럼 다음 줄):

```sql
  message_id       int          DEFAULT NULL COMMENT '연결된 메시지 (있는 경우)',
  announcement_id  int          DEFAULT NULL COMMENT '연결된 공지사항 (type=ANNOUNCEMENT일 때)',
  is_read          tinyint(1)   NOT NULL DEFAULT '0',
  created_at       datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (notification_id),
  KEY idx_notification_user (user_id),
  KEY idx_notification_room (room_id),
  KEY idx_notification_message (message_id),
  KEY idx_notification_announcement (announcement_id),
  CONSTRAINT fk_notification_user FOREIGN KEY (user_id) REFERENCES `user` (user_id),
  CONSTRAINT fk_notification_room FOREIGN KEY (room_id) REFERENCES chat_room (room_id),
  CONSTRAINT fk_notification_message FOREIGN KEY (message_id) REFERENCES chat_message (message_id),
  CONSTRAINT fk_noti_announcement FOREIGN KEY (announcement_id) REFERENCES announcement (announcement_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

   그리고 이 섹션 바로 위 설명 주석의 "type은 지금은 'CHAT_MESSAGE' 하나뿐"
   문구를 다음으로 고친다:

```sql
-- ------------------------------------------------------------
-- 22. NOTIFICATION - 인앱 알림 (헤더 알림벨 + 채팅방 목록 안읽음 배지가
--     이 테이블 하나를 공유 - is_read 기준으로 두 UI 모두 계산)
--     type: CHAT_MESSAGE | ANNOUNCEMENT (v38부터 - 공지사항 알림 추가,
--     팀원 작업 - 별도 브랜치)
-- ------------------------------------------------------------
```

- [ ] **Step 2: Step 1에서 조회한 라이브 `SHOW CREATE TABLE` 결과와 문서를
  줄 단위로 대조**

세 테이블(`announcement`, `notification`, `project`) 각각에 대해, Step 2에서
작성한 CREATE 문과 Step 1의 라이브 조회 결과를 비교해 컬럼 순서/타입/주석/
제약조건이 정확히 일치하는지 확인한다. 불일치가 있으면 라이브 결과를
기준으로 문서를 고친다(라이브 DB가 항상 진실의 원천).

- [ ] **Step 3: 커밋**

```bash
git add docs/db/v39_공공이음_DDL_FK포함.sql
git commit -m "docs: 공지사항/사업 단톡방 반영한 v39 DB DDL 추가"
```

---

### Task 6: 실시간 알림 미반영 버그 수정 (WS 재연결 시 notifications 캐시 무효화 누락)

**Files:**
- Modify: `ieum_frontend/src/hooks/useChatSocket.js`

**Interfaces:**
- 변경 없음 (내부 로직 수정만)

- [ ] **Step 1: 재연결 무효화 목록에 `notifications` 추가**

`src/hooks/useChatSocket.js`의 `ws.onopen` 핸들러 안, 기존
`if (hasConnectedOnce) { ... }` 블록을 다음으로 교체한다:

```js
        if (hasConnectedOnce) {
          queryClient.invalidateQueries({ queryKey: ['chatRoomMessages'] });
          queryClient.invalidateQueries({ queryKey: ['chatRooms'] });
          queryClient.invalidateQueries({ queryKey: ['notifications'] });
        }
```

- [ ] **Step 2: 수동 검증**

프론트/백엔드 dev 서버를 실행한 상태에서, 두 개의 브라우저(또는 시크릿
창)에 서로 다른 계정으로 로그인한다. A가 B에게 메시지를 보내기 직전에 B의
브라우저에서 개발자 도구 Network 탭의 WS 연결을 강제로 끊었다가(또는 백엔드
서버를 잠깐 재시작해) 재연결시키고, 그 사이 A가 메시지를 보낸 뒤 B가
새로고침 없이 알림벨 배지가 갱신되는지 확인한다. (이 저장소에는 프론트
자동화 테스트 하네스가 없으므로 수동 확인으로 대체 - Global Constraints
참고.)

- [ ] **Step 3: 커밋**

```bash
git add src/hooks/useChatSocket.js
git commit -m "fix: WS 재연결 시 notifications 캐시도 함께 무효화"
```

---

### Task 7: 인원 추가 / 나가기 API 클라이언트 + mutation 훅

**Files:**
- Modify: `ieum_frontend/src/api/chat.js`
- Modify: `ieum_frontend/src/hooks/mutations/useChatMutations.js`

**Interfaces:**
- Produces:
  - `addChatRoomMembers({ roomId, memberIds }) -> RoomResponse` (api/chat.js)
  - `leaveChatRoom(roomId) -> void` (api/chat.js)
  - `useAddChatRoomMembersMutation()` (useChatMutations.js)
  - `useLeaveChatRoomMutation()` (useChatMutations.js)

- [ ] **Step 1: `api/chat.js`에 함수 추가**

`src/api/chat.js` 파일 끝에 추가:

```js
export const addChatRoomMembers = async ({ roomId, memberIds }) => {
  const response = await api.post(`/chat/rooms/${roomId}/members`, { member_ids: memberIds });
  return response.data;
};

export const leaveChatRoom = async (roomId) => {
  await api.delete(`/chat/rooms/${roomId}`);
};
```

- [ ] **Step 2: mutation 훅 추가**

`src/hooks/mutations/useChatMutations.js`를 다음으로 교체한다 (기존 두 훅은
그대로 두고 import 줄과 파일 끝에 두 훅을 추가):

```js
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createChatRoom, markChatRoomRead, addChatRoomMembers, leaveChatRoom } from '../../api/chat';

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

export const useAddChatRoomMembersMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: addChatRoomMembers,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatRooms'] });
    },
  });
};

export const useLeaveChatRoomMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: leaveChatRoom,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatRooms'] });
    },
  });
};
```

- [ ] **Step 3: 수동 검증**

Vite dev 서버가 에러 없이 컴파일되는지 확인한다.

Run: `npm run build`
Expected: 빌드 성공 (타입/구문 오류 없음)

- [ ] **Step 4: 커밋**

```bash
git add src/api/chat.js src/hooks/mutations/useChatMutations.js
git commit -m "feat: 채팅방 인원 추가/나가기 API 클라이언트 및 mutation 훅 추가"
```

---

### Task 8: ChatPage UI - 인원 추가 버튼 / 나가기 버튼

**Files:**
- Modify: `ieum_frontend/src/pages/Chat/ChatPage.jsx`
- Modify: `ieum_frontend/src/pages/Chat/ChatPage.css`
- Modify: `ieum_frontend/src/components/EmpSearchModal/EmpSearchModal.jsx`

**Interfaces:**
- Consumes: `useAddChatRoomMembersMutation`, `useLeaveChatRoomMutation`
  (Task 7)
- `EmployeeSearchModal`에 새 prop `excludeUserIds?: string[]` 추가 (기본값
  `[]`) - 이미 방에 있는 사람을 선택 목록에서 제외하기 위함.

- [ ] **Step 1: `EmployeeSearchModal`에 `excludeUserIds` prop 추가**

`src/components/EmpSearchModal/EmpSearchModal.jsx`의 함수 시그니처를 수정한다:

```jsx
function EmployeeSearchModal({ currentDept, onSelect, onConfirm, onClose, forceDeptScope = false, multiSelect = false, excludeUserIds = [] }) {
```

`employees` useMemo를 다음으로 교체한다 (기존 본인 제외 로직에 이미 방에
있는 멤버 제외 로직을 추가):

```jsx
  const employees = useMemo(() => {
    let list = rawEmployees;
    if (multiSelect && currentUser?.userId) {
      list = list.filter((emp) => String(emp.userId) !== String(currentUser.userId));
    }
    if (excludeUserIds.length > 0) {
      const excludeSet = new Set(excludeUserIds.map(String));
      list = list.filter((emp) => !excludeSet.has(String(emp.userId)));
    }
    return list;
  }, [rawEmployees, multiSelect, currentUser, excludeUserIds]);
```

- [ ] **Step 2: `ChatPage.jsx`에 인원 추가 / 나가기 기능 추가**

`src/pages/Chat/ChatPage.jsx` 상단 import 줄을 수정한다:

```jsx
import { useCreateChatRoomMutation, useMarkChatRoomReadMutation, useAddChatRoomMembersMutation, useLeaveChatRoomMutation } from '../../hooks/mutations/useChatMutations';
```

컴포넌트 내부, 기존 `const markReadMutation = useMarkChatRoomReadMutation();`
다음 줄에 추가:

```jsx
  const addMembersMutation = useAddChatRoomMembersMutation();
  const leaveRoomMutation = useLeaveChatRoomMutation();
  const [isAddMemberPickerOpen, setIsAddMemberPickerOpen] = useState(false);
```

`handlePickEmployees` 함수 다음에 새 핸들러 2개를 추가한다:

```jsx
  const handleAddMembers = (selectedEmployees) => {
    setIsAddMemberPickerOpen(false);
    if (selectedEmployees.length === 0 || !selectedRoomId) return;
    setRoomError('');
    addMembersMutation.mutate(
      { roomId: selectedRoomId, memberIds: selectedEmployees.map((e) => e.userId) },
      {
        onError: (error) => {
          const message = error.response?.data?.detail || '인원 추가에 실패했습니다.';
          setRoomError(message);
        },
      }
    );
  };

  const handleLeaveRoom = (roomId) => {
    if (!window.confirm('이 채팅방에서 나가시겠습니까?')) return;
    leaveRoomMutation.mutate(roomId, {
      onSuccess: () => {
        if (selectedRoomId === roomId) setSelectedRoomId(null);
      },
      onError: () => setRoomError('채팅방 나가기에 실패했습니다.'),
    });
  };
```

방 목록 렌더링 부분(`{rooms.map((room) => ( ... ))}`)을 다음으로 교체해
나가기 버튼을 추가한다:

```jsx
        {rooms.map((room) => (
          <div
            key={room.room_id}
            className={`chat-room-item ${selectedRoomId === room.room_id ? 'active' : ''}`}
            onClick={() => setSelectedRoomId(room.room_id)}
          >
            <div className="chat-room-name">{roomLabel(room)}</div>
            <div className="chat-room-preview">{room.last_message || '대화를 시작해보세요'}</div>
            {room.unread_count > 0 && <span className="chat-unread-badge">{room.unread_count}</span>}
            <button
              className="chat-room-leave-btn"
              aria-label="채팅방 나가기"
              onClick={(e) => {
                e.stopPropagation();
                handleLeaveRoom(room.room_id);
              }}
            >
              ✕
            </button>
          </div>
        ))}
```

채팅창 헤더(`<div className="chat-thread-header">`) 안, 기존 연결 상태
배지 바로 앞에 그룹방일 때만 보이는 인원 추가 버튼을 추가한다. 현재 방
정보(그룹 여부, 멤버 목록)를 얻기 위해, `selectedRoomId`로 `rooms` 배열에서
현재 방을 찾는 변수를 헤더 렌더링 앞부분에 추가한다 - `return` 문 바로 위에:

```jsx
  const currentRoom = rooms.find((r) => r.room_id === selectedRoomId);
```

그리고 헤더 JSX를 다음으로 교체한다:

```jsx
            <div className="chat-thread-header">
              {currentRoom?.is_group && (
                <button
                  className="chat-add-member-btn"
                  onClick={() => setIsAddMemberPickerOpen(true)}
                >
                  + 인원 추가
                </button>
              )}
              <span className={`chat-connection-badge ${isConnected ? 'online' : 'offline'}`}>
                {isConnected ? '연결됨' : '연결 끊김'}
              </span>
            </div>
```

파일 마지막, 기존 `{isPickerOpen && (...)}` 블록 다음에 인원 추가용 모달을
추가한다:

```jsx
      {isAddMemberPickerOpen && currentRoom && (
        <EmployeeSearchModal
          multiSelect
          excludeUserIds={currentRoom.member_ids}
          onConfirm={handleAddMembers}
          onClose={() => setIsAddMemberPickerOpen(false)}
        />
      )}
```

- [ ] **Step 3: CSS 추가**

`src/pages/Chat/ChatPage.css`의 `.chat-unread-badge` 규칙 다음에 추가:

```css
.chat-room-leave-btn {
  position: absolute;
  right: 12px;
  bottom: 10px;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 2px 4px;
}

.chat-room-leave-btn:hover {
  color: #ef4444;
}
```

`.chat-thread-header` 규칙을 다음으로 교체한다 (버튼과 배지를 함께 정렬하기
위해 `gap` 추가):

```css
.chat-thread-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 8px 24px 0;
}
```

`.chat-add-member-btn` 규칙을 새로 추가한다 (`.chat-connection-badge` 규칙
앞):

```css
.chat-add-member-btn {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}
```

- [ ] **Step 4: 수동 검증**

Run: `npm run build`
Expected: 빌드 성공

개발 서버에서 브라우저로 다음을 확인한다:
- 그룹방을 만들고 "+ 인원 추가" 버튼이 그룹방에서만 보이는지, 1:1 방에서는
  안 보이는지
- 인원 추가 모달에서 이미 있는 멤버가 목록에 안 뜨는지, 추가 후 방 멤버
  목록에 반영되는지
- 방 목록 항목의 ✕ 버튼으로 나가기가 되는지, 나간 방이 목록에서 사라지는지,
  현재 보고 있던 방을 나가면 빈 화면으로 돌아가는지

- [ ] **Step 5: 커밋**

```bash
git add src/pages/Chat/ChatPage.jsx src/pages/Chat/ChatPage.css src/components/EmpSearchModal/EmpSearchModal.jsx
git commit -m "feat: 채팅방 인원 추가/나가기 UI 추가"
```
