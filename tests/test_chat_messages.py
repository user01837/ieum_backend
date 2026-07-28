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
