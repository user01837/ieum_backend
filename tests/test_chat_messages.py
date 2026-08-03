import json
from datetime import timedelta

from app.api.routers.auth import create_token


def _token_for(user):
    return create_token({"sub": user.user_id, "pos": user.position_code}, timedelta(minutes=30))


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


def test_rest_send_message_creates_notification_when_recipient_offline(client, make_user, db_session):
    """REST 첨부파일 전송 엔드포인트(POST /rooms/{room_id}/messages)로 보낸 메시지도
    웹소켓 send_message와 동일하게 수신자에게 알림을 만들어야 한다.
    (버그: 예전엔 이 경로가 메시지만 저장하고 알림/브로드캐스트를 전혀 하지 않았다)"""
    from app.models.notification import Notification

    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    res = client.post(f"/chat/rooms/{room['room_id']}/messages", data={"content": "안녕"})
    assert res.status_code == 200

    notif = db_session.query(Notification).filter(Notification.user_id == "emp002").one()
    assert notif.type == "CHAT_MESSAGE"
    assert notif.room_id == room["room_id"]
    assert notif.is_read is False


def test_rest_send_message_pushes_over_websocket_when_recipient_elsewhere(client, make_user, db_session):
    from app.models.notification import Notification

    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    recipient_token = _token_for(other)

    with client.websocket_connect(f"/ws/chat?token={recipient_token}") as recipient_ws:
        # 수신자는 이 방을 보는 중이 아님(active_room 안 보냄) = 다른 화면
        res = client.post(f"/chat/rooms/{room['room_id']}/messages", data={"content": "안녕"})
        assert res.status_code == 200

        events = [json.loads(recipient_ws.receive_text()) for _ in range(2)]
        types = {e["type"] for e in events}
        assert types == {"new_message", "notification"}

    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 1


def test_rest_send_message_no_notification_when_recipient_viewing(client, make_user, db_session):
    from app.models.notification import Notification

    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    recipient_token = _token_for(other)

    with client.websocket_connect(f"/ws/chat?token={recipient_token}") as recipient_ws:
        recipient_ws.send_text(json.dumps({"type": "active_room", "room_id": room["room_id"]}))

        res = client.post(f"/chat/rooms/{room['room_id']}/messages", data={"content": "안녕"})
        assert res.status_code == 200

        event = json.loads(recipient_ws.receive_text())
        assert event["type"] == "new_message"
        assert event["message"]["content"] == "안녕"

    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 0
