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
