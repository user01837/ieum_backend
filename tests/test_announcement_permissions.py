import json

from app.models.announcement import Announcement
from app.models.department import Department


def _make_announcement(db_session, created_by, department_code="01"):
    a = Announcement(
        title="원본 제목",
        content="원본 내용",
        created_by=created_by,
        department_code=department_code,
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


def test_update_by_other_department_head_is_rejected(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.add(Department(department_code="02", name="주택건축부"))
    db_session.commit()

    author = make_user("1001", "작성자부장", department_code="01")
    author.position_code = "01"
    db_session.commit()

    other_head = make_user("1002", "다른부장", department_code="02")
    other_head.position_code = "01"
    db_session.commit()

    a = _make_announcement(db_session, created_by=author.user_id, department_code="01")

    client.current_user_holder["user"] = other_head

    res = client.patch(
        f"/announcements/{a.announcement_id}",
        data={"request_data": json.dumps({"title": "해킹된 제목"})},
    )
    assert res.status_code == 403

    db_session.refresh(a)
    assert a.title == "원본 제목"


def test_update_by_admin_who_is_not_author_is_rejected(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.commit()

    author = make_user("1003", "작성자부장", department_code="01")
    author.position_code = "01"
    db_session.commit()

    admin = make_user("1004", "관리자", department_code="01")
    admin.system_role_code = "02"
    db_session.commit()

    a = _make_announcement(db_session, created_by=author.user_id, department_code="01")

    client.current_user_holder["user"] = admin

    res = client.patch(
        f"/announcements/{a.announcement_id}",
        data={"request_data": json.dumps({"title": "관리자가 수정 시도"})},
    )
    assert res.status_code == 403

    db_session.refresh(a)
    assert a.title == "원본 제목"


def test_update_by_author_succeeds(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.commit()

    author = make_user("1005", "작성자부장", department_code="01")
    author.position_code = "01"
    db_session.commit()

    a = _make_announcement(db_session, created_by=author.user_id, department_code="01")

    client.current_user_holder["user"] = author

    res = client.patch(
        f"/announcements/{a.announcement_id}",
        data={"request_data": json.dumps({"title": "본인이 수정"})},
    )
    assert res.status_code == 200

    db_session.refresh(a)
    assert a.title == "본인이 수정"


def test_delete_by_non_author_is_rejected(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.add(Department(department_code="02", name="주택건축부"))
    db_session.commit()

    author = make_user("1006", "작성자부장", department_code="01")
    author.position_code = "01"
    db_session.commit()

    other_head = make_user("1007", "다른부장", department_code="02")
    other_head.position_code = "01"
    db_session.commit()

    a = _make_announcement(db_session, created_by=author.user_id, department_code="01")

    client.current_user_holder["user"] = other_head

    res = client.delete(f"/announcements/{a.announcement_id}")
    assert res.status_code == 403

    db_session.refresh(a)
    assert a.is_deleted is False


def test_delete_by_author_succeeds(client, make_user, db_session):
    db_session.add(Department(department_code="01", name="교통부"))
    db_session.commit()

    author = make_user("1008", "작성자부장", department_code="01")
    author.position_code = "01"
    db_session.commit()

    a = _make_announcement(db_session, created_by=author.user_id, department_code="01")

    client.current_user_holder["user"] = author

    res = client.delete(f"/announcements/{a.announcement_id}")
    assert res.status_code == 200

    db_session.refresh(a)
    assert a.is_deleted is True
