from unittest.mock import patch

from app.services import fcm_service
from app.models.notification import DeviceToken
from app.models.chat import ChatMessage


def test_send_new_message_push_skips_without_credentials(db_session, make_user, monkeypatch):
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", None)
    user = make_user("emp002")
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="tok-1"))
    db_session.commit()

    message = ChatMessage(room_id=1, sender_id="emp001", content="hi")
    with patch("app.services.fcm_service.messaging.send") as mock_send:
        fcm_service.send_new_message_push(db_session, user.user_id, 1, message)
        mock_send.assert_not_called()


def test_send_new_message_push_sends_to_all_tokens(db_session, make_user, monkeypatch):
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", "/fake/path.json")
    monkeypatch.setattr(fcm_service, "_initialized", True)
    user = make_user("emp002")
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="tok-1"))
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="tok-2"))
    db_session.commit()

    message = ChatMessage(room_id=1, sender_id="emp001", content="hi")
    with patch("app.services.fcm_service.messaging.send") as mock_send:
        fcm_service.send_new_message_push(db_session, user.user_id, 1, message)
        assert mock_send.call_count == 2


def test_send_new_message_push_removes_unregistered_token(db_session, make_user, monkeypatch):
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", "/fake/path.json")
    monkeypatch.setattr(fcm_service, "_initialized", True)
    user = make_user("emp002")
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="dead-token"))
    db_session.commit()

    class FakeUnregisteredError(Exception):
        pass
    FakeUnregisteredError.__name__ = "UnregisteredError"

    message = ChatMessage(room_id=1, sender_id="emp001", content="hi")
    with patch("app.services.fcm_service.messaging.send", side_effect=FakeUnregisteredError("gone")):
        fcm_service.send_new_message_push(db_session, user.user_id, 1, message)

    assert db_session.query(DeviceToken).filter(DeviceToken.fcm_token == "dead-token").count() == 0
