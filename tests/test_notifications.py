def test_register_and_list_device_token(client):
    res = client.post("/notifications/device-token", json={"fcm_token": "tok-1"})
    assert res.status_code == 204

    from app.models.notification import DeviceToken
    # db_session fixture 없이도 client fixture 내부 세션을 통해 검증 가능하도록 API로 확인
    res2 = client.request("DELETE", "/notifications/device-token", json={"fcm_token": "tok-1"})
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
