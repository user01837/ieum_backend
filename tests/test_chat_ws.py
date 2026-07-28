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
