import json
import logging
import queue
import threading
from datetime import timedelta

import pytest
from sqlalchemy.exc import OperationalError
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


def test_ws_fcm_push_receives_message_with_attributes_already_loaded(client, make_user, monkeypatch):
    """스레드풀로 넘어가는 message는 lazy load가 필요 없는 상태여야 한다.

    바로 앞의 create_notification 커밋이 (sessionmaker 기본값 expire_on_commit=True)
    message를 만료시키므로, 그대로 넘기면 워커 스레드에서 SELECT가 나간다. 이는 세션을
    소유하지 않은 스레드에서 Session을 쓰는 것이 된다(Session은 스레드 안전하지 않다).
    """
    import time

    from sqlalchemy import inspect as sa_inspect

    from app.services import fcm_service

    other = make_user("emp002")  # 소켓을 열지 않으므로 오프라인 -> FCM 경로
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    token = _token_for(client.current_user_holder["user"])

    recorded = {}

    def _fake_push(db, recipient_id, room_id, message):
        state = sa_inspect(message)
        # 속성을 읽으면 그 순간 다시 적재되므로, 만료 여부를 먼저 캡처한다.
        recorded["expired"] = state.expired
        recorded["unloaded"] = set(state.unloaded)
        recorded["content"] = message.content
        recorded["message_id"] = message.message_id

    monkeypatch.setattr(fcm_service, "send_new_message_push", _fake_push)

    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        ws.send_text(json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"}))
        ws.receive_text()  # echo

    for _ in range(100):
        if "expired" in recorded:
            break
        time.sleep(0.02)

    assert "expired" in recorded, "FCM 발송이 호출되지 않았다"
    assert recorded["expired"] is False
    assert "content" not in recorded["unloaded"]
    assert "message_id" not in recorded["unloaded"]
    assert recorded["content"] == "안녕"
    assert isinstance(recorded["message_id"], int)


def test_ws_fcm_push_runs_off_the_event_loop_thread(client, make_user, monkeypatch):
    """동기 HTTPS 호출인 FCM 발송이 이벤트 루프를 막지 않고 스레드풀에서 실행되어야 한다."""
    import time

    from app.services import chat_service, fcm_service

    other = make_user("emp002")  # 소켓을 열지 않으므로 오프라인 -> FCM 경로
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    token = _token_for(client.current_user_holder["user"])

    recorded = {}
    real_record_message = chat_service.record_message

    def _record_message(db, room_id, sender_id, content):
        # 이 호출은 WS 핸들러 코루틴(=이벤트 루프 스레드) 안에서 일어난다.
        recorded["loop_thread"] = threading.get_ident()
        return real_record_message(db, room_id, sender_id, content)

    def _fake_push(db, recipient_id, room_id, message):
        recorded["fcm_thread"] = threading.get_ident()

    monkeypatch.setattr(chat_service, "record_message", _record_message)
    monkeypatch.setattr(fcm_service, "send_new_message_push", _fake_push)

    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        ws.send_text(json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "안녕"}))
        ws.receive_text()  # echo

    for _ in range(100):
        if "fcm_thread" in recorded:
            break
        time.sleep(0.02)

    assert "fcm_thread" in recorded, "FCM 발송이 호출되지 않았다"
    assert recorded["fcm_thread"] != recorded["loop_thread"]


def test_ws_db_error_during_message_does_not_kill_connection(client, make_user, db_session, caplog):
    """메시지 처리 중 DB 오류가 나도 연결이 유지되고, 서버 로그에 흔적이 남아야 한다.

    실패한 메시지는 "그 메시지만 실패"로 끝나고, 뒤이은 정상 메시지는 계속 처리되어야 한다.
    """
    from app.services import chat_service
    from app.services.chat_connection_manager import manager as chat_manager

    other = make_user("emp002")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    user = client.current_user_holder["user"]
    token = _token_for(user)

    real_record_message = chat_service.record_message
    calls = {"n": 0}

    def _flaky_record_message(db, room_id, sender_id, content):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("INSERT INTO CHAT_MESSAGE", {}, Exception("server has gone away"))
        return real_record_message(db, room_id, sender_id, content)

    chat_service.record_message = _flaky_record_message
    try:
        with caplog.at_level(logging.ERROR, logger="app.api.routers.chat_ws"):
            with client.websocket_connect(f"/ws/chat?token={token}") as ws:
                ws.send_text(
                    json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "실패할 메시지"})
                )
                # 연결이 살아있고, 뒤이은 정상 메시지는 계속 처리된다.
                ws.send_text(
                    json.dumps({"type": "send_message", "room_id": room["room_id"], "content": "정상 메시지"})
                )

                # 실패한 메시지는 브로드캐스트되지 않으므로 첫 수신 이벤트가 곧 두 번째 메시지여야 한다.
                echo = json.loads(ws.receive_text())
                assert echo["type"] == "new_message"
                assert echo["message"]["content"] == "정상 메시지"
                assert chat_manager.is_user_online(user.user_id) is True
    finally:
        chat_service.record_message = real_record_message

    assert any("채팅 메시지 처리 실패" in r.message for r in caplog.records)

    from app.models.chat import ChatMessage
    contents = [m.content for m in db_session.query(ChatMessage).all()]
    assert contents == ["정상 메시지"]


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
