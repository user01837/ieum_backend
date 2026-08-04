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


def test_unassign_currently_returns_400_pre_existing_bug(client, db_session):
    """
    담당자 해제(assigneeUserId="")는 FastAPI Form(None) 파싱에서 빈 문자열이
    기본값(None)으로 뭉개지는 이 프로젝트의 FastAPI 버전(0.139.0)의 기존 버그로 인해
    현재 400을 반환한다. 이 버그는 department_code 동기화 로직 도달 이전
    Step 0 검증에서 걸리므로, 이번 타부서 이관 기능과는 무관한 별도 이슈이며
    이 태스크의 범위 밖이다. 이 테스트는 그 사실을 문서화한다 — 향후 그 버그가
    고쳐지면 이 테스트는 실패하게 되고, 그때 이 테스트를 진짜 "해제 시 department_code
    불변" 검증으로 교체하면 된다.
    """
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
    assert res.status_code == 400

    db_session.refresh(petition)
    assert petition.department_code == "01"
    assert petition.assignee_user_id == "emp001"
