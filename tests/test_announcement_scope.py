import json

from app.models.announcement import Announcement
from app.models.department import Department


def test_admin_can_create_company_wide_announcement(client, make_user, db_session):
    admin = make_user("2001", "관리자", department_code="01")
    admin.system_role_code = "02"
    db_session.commit()

    client.current_user_holder["user"] = admin

    res = client.post(
        "/announcements",
        data={"request_data": json.dumps({"title": "전체 공지", "content": "내용", "department_code": None})},
    )
    assert res.status_code == 200

    a = db_session.query(Announcement).filter(
        Announcement.announcement_id == res.json()["announcementId"]
    ).first()
    assert a.department_code is None


def test_admin_can_create_department_scoped_announcement(client, make_user, db_session):
    db_session.add(Department(department_code="02", name="주택건축부"))
    db_session.commit()

    admin = make_user("2002", "관리자", department_code="01")
    admin.system_role_code = "02"
    db_session.commit()

    client.current_user_holder["user"] = admin

    res = client.post(
        "/announcements",
        data={"request_data": json.dumps({"title": "부서 공지", "content": "내용", "department_code": "02"})},
    )
    assert res.status_code == 200

    a = db_session.query(Announcement).filter(
        Announcement.announcement_id == res.json()["announcementId"]
    ).first()
    assert a.department_code == "02"


def test_department_head_cannot_create_company_wide_announcement(client, make_user, db_session):
    head = make_user("2003", "부장", department_code="01")
    head.position_code = "01"
    db_session.commit()

    client.current_user_holder["user"] = head

    # department_code=None을 직접 보내봐도(=전체 공지 시도) 본인 부서로 강제되어야 한다.
    res = client.post(
        "/announcements",
        data={"request_data": json.dumps({"title": "부장이 시도한 전체 공지", "content": "내용", "department_code": None})},
    )
    assert res.status_code == 200

    a = db_session.query(Announcement).filter(
        Announcement.announcement_id == res.json()["announcementId"]
    ).first()
    assert a.department_code == "01"
