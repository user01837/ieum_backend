from app.models.department import Department


def test_search_excludes_retired_employees_by_default(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.commit()

    retired = make_user("3001", "김퇴직", department_code="01")
    retired.status_code = "03"
    db_session.commit()

    res = client.get("/users/search", params={"scope": "all", "keyword": "김퇴직"})
    assert res.status_code == 200
    assert res.json() == []


def test_search_includes_retired_employees_when_requested(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.commit()

    retired = make_user("3002", "이퇴직", department_code="01")
    retired.status_code = "03"
    db_session.commit()

    res = client.get(
        "/users/search",
        params={"scope": "all", "keyword": "이퇴직", "includeInactive": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["userId"] == "3002"
    assert body[0]["name"] == "이퇴직"


def test_search_still_excludes_active_department_mismatch(client, make_user, db_session):
    """회귀 확인: includeInactive와 무관하게 다른 필터(부서 scope)는 그대로 작동해야 한다."""
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.add(Department(department_code="02", name="주택건축부"))
    db_session.commit()

    make_user("3003", "박대상", department_code="02")

    res = client.get(
        "/users/search",
        params={"scope": "all", "departmentCode": "01", "keyword": "박대상", "includeInactive": True},
    )
    assert res.status_code == 200
    assert res.json() == []
