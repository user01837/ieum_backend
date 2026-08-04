# 민원 담당자 타부서 이관 허용 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 민원 담당자 변경 시 같은 부서뿐 아니라 다른 부서 직원으로도 재배정할 수 있게 하고, 그 경우 민원의 소속 부서(department_code)를 새 담당자 부서로 갱신하고 기존 task_id를 초기화한다.

**Architecture:** 백엔드는 이미 임의 부서 직원을 담당자로 지정하는 것을 막지 않는다 — `ieum_backend/app/api/routers/petition.py`의 `temp_save_petition`에 새 담당자의 부서가 민원의 현재 부서와 다를 때 `department_code`를 갱신하고 `task_id`를 `None`으로 초기화하는 분기를 추가한다. 프론트엔드는 `ieum_frontend/src/pages/Petition/Detail_petition.jsx`에서 담당자 검색 모달에 걸어둔 `forceDeptScope={true}`를 제거해, 이미 구현되어 있는 모달의 "전체 부서" 검색 기능을 그대로 노출시킨다.

**Tech Stack:** FastAPI + SQLAlchemy (ieum_backend), React 19 + Vite (ieum_frontend), pytest + in-memory SQLite (백엔드 테스트)

## Global Constraints

- 권한 체크는 기존 `is_current_assignee`(현재 담당자만) 그대로 유지 — 타부서 이관에 추가 권한 제한을 두지 않는다.
- 같은 부서 내 담당자 변경 시 `department_code`/`task_id`는 절대 건드리지 않는다 (기존 동작 그대로).
- 담당자 지정 해제(`assigneeUserId=""`)는 `department_code`를 절대 바꾸지 않는다.
- 백엔드 테스트는 `ieum_backend/tests/conftest.py`의 `client`/`make_user`/`db_session` fixture를 그대로 사용한다 (새 fixture 추가 금지). `client` fixture의 기본 로그인 사용자는 `user_id="emp001"`, `department_code="01"`이다.

---

### Task 1: 백엔드 — 담당자 타부서 변경 시 department_code/task_id 동기화

**Files:**
- Modify: `ieum_backend/app/api/routers/petition.py:625-639` (`temp_save_petition` 내 담당자 신규 지정/변경 분기)
- Create: `ieum_backend/tests/test_petition_reassignment.py`

**Interfaces:**
- Consumes: 기존 엔드포인트 `PUT /petitions/{complaintId}/temp-save` (multipart/form-data, `assigneeUserId: Optional[str]`), 기존 모델 `Petition`(`app.models.petition.Petition`, 필드: `petition_id`, `title`, `content`, `department_code`, `task_id`, `assignee_user_id`, `status_code`), `Task`(`app.models.task.Task`, 필드: `task_id`, `name`, `department_code`), `Department`(`app.models.department.Department`, 필드: `department_code`, `name`), `User`(`app.models.user.User`, 필드: `user_id`, `department_code`)
- Produces: 변경 없음 (기존 응답 형식 `{"message": "저장 되었습니다."}` 그대로 유지)

- [ ] **Step 1: 실패하는 테스트 작성**

`ieum_backend/tests/test_petition_reassignment.py` 파일을 새로 만든다:

```python
from app.models.department import Department
from app.models.task import Task
from app.models.petition import Petition


def test_reassign_same_department_keeps_department_and_task(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.commit()

    make_user("emp002", "박직원", department_code="01")

    task = Task(name="도로 보수", department_code="01")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    petition = Petition(
        title="테스트 민원",
        content="내용",
        department_code="01",
        task_id=task.task_id,
        assignee_user_id="emp001",
        status_code="02",
    )
    db_session.add(petition)
    db_session.commit()
    db_session.refresh(petition)

    res = client.put(
        f"/petitions/{petition.petition_id}/temp-save",
        data={"assigneeUserId": "emp002"},
    )
    assert res.status_code == 200

    db_session.refresh(petition)
    assert petition.department_code == "01"
    assert petition.task_id == task.task_id
    assert petition.assignee_user_id == "emp002"


def test_reassign_cross_department_updates_department_and_clears_task(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.add(Department(department_code="02", name="주택건축부"))
    db_session.commit()

    make_user("emp002", "유현서", department_code="02")

    task = Task(name="도로 보수", department_code="01")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    petition = Petition(
        title="인도 블록 파손",
        content="내용",
        department_code="01",
        task_id=task.task_id,
        assignee_user_id="emp001",
        status_code="02",
    )
    db_session.add(petition)
    db_session.commit()
    db_session.refresh(petition)

    res = client.put(
        f"/petitions/{petition.petition_id}/temp-save",
        data={"assigneeUserId": "emp002"},
    )
    assert res.status_code == 200

    db_session.refresh(petition)
    assert petition.department_code == "02"
    assert petition.task_id is None
    assert petition.assignee_user_id == "emp002"


def test_unassign_does_not_change_department(client, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.commit()

    petition = Petition(
        title="테스트 민원",
        content="내용",
        department_code="01",
        task_id=None,
        assignee_user_id="emp001",
        status_code="02",
    )
    db_session.add(petition)
    db_session.commit()
    db_session.refresh(petition)

    res = client.put(
        f"/petitions/{petition.petition_id}/temp-save",
        data={"assigneeUserId": ""},
    )
    assert res.status_code == 200

    db_session.refresh(petition)
    assert petition.department_code == "01"
    assert petition.assignee_user_id is None
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd ieum_backend && pytest tests/test_petition_reassignment.py -v`

Expected: `test_reassign_cross_department_updates_department_and_clears_task`만 FAIL (department_code가 "01"에 머물러 있고 task_id가 null이 아님을 보여줌). 나머지 두 테스트(`test_reassign_same_department_keeps_department_and_task`, `test_unassign_does_not_change_department`)는 기존 코드가 department_code를 아예 건드리지 않으므로 이미 PASS — 회귀 방지용 테스트로 계속 통과해야 한다.

- [ ] **Step 3: 최소 구현**

`ieum_backend/app/api/routers/petition.py`에서 아래 블록을 찾는다 (`temp_save_petition` 함수 안, "담당자 신규 지정 또는 변경" 주석 부분):

```python
            else: # 담당자 신규 지정 또는 변경
                new_assignee = db.query(User).filter(User.user_id == new_assignee_id_str).first()
                if not new_assignee:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="새로 지정할 담당자를 찾을 수 없습니다."
                    )
                petition.assignee_user_id = new_assignee_id_str
                to_user_id = new_assignee_id_str
```

다음으로 교체한다:

```python
            else: # 담당자 신규 지정 또는 변경
                new_assignee = db.query(User).filter(User.user_id == new_assignee_id_str).first()
                if not new_assignee:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="새로 지정할 담당자를 찾을 수 없습니다."
                    )

                # 타 부서 직원으로 재배정되는 경우, 민원의 소속 부서도 함께 이동시키고
                # 예전 부서 기준으로 분류되어 있던 task_id는 새 부서에서 의미가 없으므로 초기화한다.
                if new_assignee.department_code != petition.department_code:
                    petition.department_code = new_assignee.department_code
                    petition.task_id = None

                petition.assignee_user_id = new_assignee_id_str
                to_user_id = new_assignee_id_str
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd ieum_backend && pytest tests/test_petition_reassignment.py -v`

Expected: 3개 테스트 모두 PASS

- [ ] **Step 5: 회귀 확인 — 기존 petition 관련 테스트가 깨지지 않았는지 확인**

Run: `cd ieum_backend && pytest tests/ -v`

Expected: 모든 기존 테스트 PASS (기존 채팅/알림 테스트 포함, 이번 변경은 `petition.py`의 한 분기만 건드리므로 영향 없어야 함)

- [ ] **Step 6: 커밋**

```bash
cd ieum_backend
git add app/api/routers/petition.py tests/test_petition_reassignment.py
git commit -m "feat: 민원 담당자 타부서 변경 시 소속 부서·업무분류 동기화"
```

---

### Task 2: 프론트엔드 — 담당자 변경 모달에서 전체 부서 검색 허용

**Files:**
- Modify: `ieum_frontend/src/pages/Petition/Detail_petition.jsx:788-792`

**Interfaces:**
- Consumes: 기존 컴포넌트 `EmployeeSearchModal`(`ieum_frontend/src/components/EmpSearchModal/EmpSearchModal.jsx`)의 `forceDeptScope` prop (boolean, 기본값 `false`) — 이 컴포넌트는 Task 1과 무관하게 이미 "범위: 같은 과"/"범위: 전체 부서" 토글과 부서 드롭다운을 구현하고 있으므로 신규 코드 불필요
- Produces: 변경 없음 (기존 `onSelect(emp)` 콜백 시그니처 그대로, `emp.userId`가 Task 1의 백엔드 엔드포인트로 그대로 전달됨)

- [ ] **Step 1: forceDeptScope 제거**

`ieum_frontend/src/pages/Petition/Detail_petition.jsx`에서 아래 블록을 찾는다:

```jsx
          currentDept={complaint.departmentName}
          onSelect={handleSelectEmployee}
          onClose={handleCloseModal}
          forceDeptScope={true}
        />
```

`forceDeptScope={true}` 줄을 삭제한다:

```jsx
          currentDept={complaint.departmentName}
          onSelect={handleSelectEmployee}
          onClose={handleCloseModal}
        />
```

- [ ] **Step 2: 린트 실행**

Run: `cd ieum_frontend && npm run lint`

Expected: 에러 없음 (사용하지 않는 import/변수 경고가 없어야 함 — `forceDeptScope`는 prop 삭제일 뿐 다른 코드 삭제가 아니므로 발생하지 않아야 함)

- [ ] **Step 3: 개발 서버로 수동 확인**

Run: `cd ieum_frontend && npm run dev`

브라우저에서:
1. 아무 민원 상세 페이지로 이동 (자신이 담당자로 지정된, 완료되지 않은 민원)
2. "담당자 변경" 버튼 클릭
3. 모달 하단에 "범위: 같은 과" / "범위: 전체 부서" 토글 버튼이 보이는지 확인
4. "범위: 전체 부서" 클릭 → 부서 드롭다운이 나타나는지 확인
5. 다른 부서를 선택하고 그 부서 직원을 선택 → 저장 확인 다이얼로그가 뜨고 저장되는지 확인
6. 저장 후 민원 상세 페이지의 부서 표시가 새 담당자의 부서로 바뀌었는지 확인 (Task 1의 백엔드 동작 결과)

Expected: 위 6단계 모두 정상 동작

- [ ] **Step 4: 커밋**

```bash
cd ieum_frontend
git add src/pages/Petition/Detail_petition.jsx
git commit -m "feat: 민원 담당자 변경 시 전체 부서에서 검색 가능하도록 변경"
```
