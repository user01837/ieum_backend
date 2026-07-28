import json
import queue
import threading
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.routers.auth import create_token


def _token_for(user):
    return create_token({"sub": user.user_id, "pos": user.position_code}, timedelta(minutes=30))


def _try_receive(ws, timeout: float = 0.3):
    """제한 시간 안에 메시지가 오면 파싱해서 반환하고, 안 오면 None을 반환한다.

    `WebSocketTestSession.receive_text()`는 타임아웃 없이 무한정 블로킹하므로,
    "이 소켓으로는 아무 것도 더 오지 않아야 한다"를 검증하려면 별도 스레드에서
    수신을 시도하고 짧은 시간만 기다린 뒤 포기하는 방식으로 우회한다.
    """
    result: "queue.Queue" = queue.Queue()

    def _worker():
        try:
            result.put(ws.receive_text())
        except Exception:
            pass

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        return None
    try:
        return json.loads(result.get_nowait())
    except queue.Empty:
        return None


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


def test_ws_multi_tab_recipient_viewing_in_one_tab_gets_no_phantom_notification(client, make_user, db_session):
    """수신자가 탭 두 개(하나는 이 방을 보는 중, 하나는 다른 화면)를 열어둔 경우:
    보는 중인 탭이 하나라도 있으면 두 탭 모두 new_message만 받아야 하고,
    notification 이벤트도 Notification row도 생성되면 안 된다.
    """
    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    sender_token = _token_for(client.current_user_holder["user"])
    recipient_token = _token_for(other)

    with client.websocket_connect(f"/ws/chat?token={sender_token}") as sender_ws:
        with client.websocket_connect(f"/ws/chat?token={recipient_token}") as viewing_ws:
            with client.websocket_connect(f"/ws/chat?token={recipient_token}") as elsewhere_ws:
                # 탭 1: 이 방을 보는 중
                viewing_ws.send_text(json.dumps({"type": "active_room", "room_id": room["room_id"]}))
                # 탭 2: active_room을 보내지 않음 = 다른 화면을 보는 중

                sender_ws.send_text(
                    json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"})
                )

                sender_echo = json.loads(sender_ws.receive_text())
                assert sender_echo["type"] == "new_message"

                viewing_event = json.loads(viewing_ws.receive_text())
                assert viewing_event["type"] == "new_message"

                elsewhere_event = json.loads(elsewhere_ws.receive_text())
                assert elsewhere_event["type"] == "new_message"

                # 두 탭 모두 이후에 추가로 오는 이벤트(예: notification)가 없어야 한다.
                assert _try_receive(viewing_ws) is None
                assert _try_receive(elsewhere_ws) is None

    from app.models.notification import Notification
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 0


def test_ws_send_message_ignores_non_int_room_id_and_keeps_connection_alive(client):
    from app.services.chat_connection_manager import manager as chat_manager

    user = client.current_user_holder["user"]
    token = _token_for(user)

    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        # room_id가 int가 아닌 경우(dict) 무시하고 연결을 유지해야 한다.
        ws.send_text(json.dumps({"type": "send_message", "room_id": {"a": 1}, "content": "hi"}))
        # 뒤이어 정상 메시지를 보내면 계속 처리되어야 한다.
        ws.send_text(json.dumps({"type": "active_room", "room_id": 1}))
        assert chat_manager.is_user_online(user.user_id) is True
    assert chat_manager.is_user_online(user.user_id) is False
