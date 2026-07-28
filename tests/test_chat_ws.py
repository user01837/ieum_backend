import json
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.routers.auth import create_token


def _token_for(user):
    return create_token({"sub": user.user_id, "pos": user.position_code}, timedelta(minutes=30))


def test_ws_rejects_invalid_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/chat?token=invalid-token"):
            pass


def test_ws_connect_marks_user_online_and_disconnect_clears_it(client):
    from app.services.chat_connection_manager import manager as chat_manager

    user = client.current_user_holder["user"]
    token = _token_for(user)

    assert chat_manager.is_user_online(user.user_id) is False
    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        ws.send_text(json.dumps({"type": "active_room", "room_id": 1}))
        assert chat_manager.is_user_online(user.user_id) is True
    assert chat_manager.is_user_online(user.user_id) is False


def test_ws_ignores_malformed_message_and_keeps_connection_alive(client):
    from app.services.chat_connection_manager import manager as chat_manager

    user = client.current_user_holder["user"]
    token = _token_for(user)

    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        # 형식이 잘못된 메시지(비-JSON 텍스트)를 보내도 연결이 끊기지 않아야 한다.
        ws.send_text("not json")
        # 뒤이어 정상 메시지를 보내면 계속 처리되어야 한다.
        ws.send_text(json.dumps({"type": "active_room", "room_id": 1}))
        assert chat_manager.is_user_online(user.user_id) is True
    assert chat_manager.is_user_online(user.user_id) is False


def test_ws_message_delivered_when_viewing_creates_no_notification(client, make_user, db_session):
    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    sender_token = _token_for(client.current_user_holder["user"])
    recipient_token = _token_for(other)

    with client.websocket_connect(f"/ws/chat?token={sender_token}") as sender_ws:
        with client.websocket_connect(f"/ws/chat?token={recipient_token}") as recipient_ws:
            recipient_ws.send_text(json.dumps({"type": "active_room", "room_id": room["room_id"]}))

            sender_ws.send_text(
                json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"})
            )

            sender_echo = json.loads(sender_ws.receive_text())
            assert sender_echo["type"] == "new_message"

            recipient_event = json.loads(recipient_ws.receive_text())
            assert recipient_event["type"] == "new_message"
            assert recipient_event["message"]["content"] == "안녕"

    from app.models.notification import Notification
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 0


def test_ws_message_creates_notification_when_elsewhere(client, make_user, db_session):
    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    sender_token = _token_for(client.current_user_holder["user"])
    recipient_token = _token_for(other)

    with client.websocket_connect(f"/ws/chat?token={sender_token}") as sender_ws:
        with client.websocket_connect(f"/ws/chat?token={recipient_token}") as recipient_ws:
            # recipient는 active_room을 보내지 않음 = 다른 화면을 보는 중
            sender_ws.send_text(
                json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"})
            )
            sender_ws.receive_text()  # echo

            events = [json.loads(recipient_ws.receive_text()) for _ in range(2)]
            types = {e["type"] for e in events}
            assert types == {"new_message", "notification"}

    from app.models.notification import Notification
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 1


def test_ws_message_creates_notification_when_recipient_offline(client, make_user, db_session):
    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    sender_token = _token_for(client.current_user_holder["user"])

    with client.websocket_connect(f"/ws/chat?token={sender_token}") as sender_ws:
        sender_ws.send_text(
            json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"})
        )
        sender_ws.receive_text()  # echo

    from app.models.notification import Notification
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 1
