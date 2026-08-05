from app.models.department import Department
from app.models.petition import Petition
from app.models.petition_assignee_history import PetitionAssigneeHistory
from app.models.task_assignee import TaskAssignee  # noqa: F401  (admin.py의 TASK_ASSIGNEE 삭제 쿼리가 테이블 등록을 요구함)
from app.models.project import Project  # noqa: F401
from app.models.project_member import ProjectMember  # noqa: F401
from app.models.project_member_history import ProjectMemberHistory  # noqa: F401


def test_temp_assigned_petition_is_clawed_back_to_successor_after_department_move(
    client, make_user, db_session
):
    """
    재현 시나리오:
    1. 전임자가 부서이동(01 -> 02)하면서, 미완료 민원이 이전 부서(01)의 부장에게 임시 배정된다.
    2. 후임자가 뒤늦게 전임자를 지정하면, 그 임시 배정된 민원이 후임자에게 승계되어야 한다.

    버그: 클로백 로직이 '전임자의 현재 부서'(부서이동 후엔 새 부서인 02)를 기준으로
    부장을 찾는데, 실제로 민원을 임시 배정받은 사람은 이전 부서(01)의 부장이라
    영영 못 찾고 승계가 안 된다.
    """
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.add(Department(department_code="02", name="주택건축부"))
    db_session.commit()

    admin = make_user("9001", "관리자", department_code="01")
    admin.system_role_code = "02"
    db_session.commit()

    old_dept_head = make_user("9002", "교통부장", department_code="01")
    old_dept_head.position_code = "01"

    new_dept_head = make_user("9003", "주택건축부장", department_code="02")
    new_dept_head.position_code = "01"

    predecessor = make_user("9004", "전임자", department_code="01")
    db_session.commit()

    petition = Petition(
        title="테스트 민원",
        content="내용",
        department_code="01",
        assignee_user_id=predecessor.user_id,
        status_code="01",
    )
    db_session.add(petition)
    db_session.commit()
    db_session.refresh(petition)

    client.current_user_holder["user"] = admin

    # 1. 전임자를 01 -> 02로 부서이동 -> 미완료 민원은 '이전' 부서(01)의 부장에게 임시 배정되어야 함
    res = client.patch(f"/admin/users/{predecessor.user_id}", json={"departmentCode": "02"})
    assert res.status_code == 200

    db_session.refresh(petition)
    assert petition.assignee_user_id == old_dept_head.user_id

    history_after_move = (
        db_session.query(PetitionAssigneeHistory)
        .filter(PetitionAssigneeHistory.petition_id == petition.petition_id)
        .order_by(PetitionAssigneeHistory.history_id.desc())
        .first()
    )
    assert history_after_move.from_user_id == predecessor.user_id
    assert history_after_move.to_user_id == old_dept_head.user_id
    assert history_after_move.change_type == "02"

    # 2. 후임자 생성 후, 뒤늦게 전임자를 predecessorUserId로 지정
    successor = make_user("9005", "후임자", department_code="02")
    db_session.commit()

    res2 = client.patch(
        f"/admin/users/{successor.user_id}",
        json={"predecessorUserId": predecessor.user_id},
    )
    assert res2.status_code == 200

    # 3. 임시 배정됐던 민원이 후임자에게 승계되어야 한다
    db_session.refresh(petition)
    assert petition.assignee_user_id == successor.user_id


def test_temp_assigned_petition_is_clawed_back_to_successor_after_retirement(
    client, make_user, db_session
):
    """퇴직(부서 변경 없음) 시에도 임시 배정 -> 후임자 클로백이 정상 동작해야 한다 (회귀 확인)."""
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.commit()

    admin = make_user("9101", "관리자", department_code="01")
    admin.system_role_code = "02"
    db_session.commit()

    dept_head = make_user("9102", "교통부장", department_code="01")
    dept_head.position_code = "01"

    predecessor = make_user("9104", "전임자", department_code="01")
    db_session.commit()

    petition = Petition(
        title="테스트 민원",
        content="내용",
        department_code="01",
        assignee_user_id=predecessor.user_id,
        status_code="01",
    )
    db_session.add(petition)
    db_session.commit()
    db_session.refresh(petition)

    client.current_user_holder["user"] = admin

    # 1. 전임자 퇴직 처리 -> 부서 변경 없이, 미완료 민원은 같은 부서 부장에게 임시 배정
    res = client.patch(f"/admin/users/{predecessor.user_id}", json={"statusCode": "03"})
    assert res.status_code == 200

    db_session.refresh(petition)
    assert petition.assignee_user_id == dept_head.user_id

    # 2. 후임자가 뒤늦게 전임자를 지정
    successor = make_user("9105", "후임자", department_code="01")
    db_session.commit()

    res2 = client.patch(
        f"/admin/users/{successor.user_id}",
        json={"predecessorUserId": predecessor.user_id},
    )
    assert res2.status_code == 200

    db_session.refresh(petition)
    assert petition.assignee_user_id == successor.user_id
