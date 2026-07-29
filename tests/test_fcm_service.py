from unittest.mock import patch

from app.services import fcm_service
from app.models.notification import DeviceToken
from app.models.chat import ChatMessage


def test_init_firebase_does_not_retry_after_failure(monkeypatch):
    """초기화가 한 번 실패하면 이후 호출에서 다시 시도하지 않아야 한다(로그 폭주 방지)."""
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", "/fake/path.json")
    monkeypatch.setattr(fcm_service, "_initialized", False)
    monkeypatch.setattr(fcm_service, "_init_failed", False)

    calls = {"n": 0}

    def _boom(path):
        calls["n"] += 1
        raise IOError("credentials file not found")

    monkeypatch.setattr(fcm_service.credentials, "Certificate", _boom)

    fcm_service.init_firebase()
    fcm_service.init_firebase()
    fcm_service.init_firebase()

    assert calls["n"] == 1
    assert fcm_service._init_failed is True
    assert fcm_service._initialized is False


def test_send_new_message_push_does_not_retry_failed_init(db_session, make_user, monkeypatch):
    """초기화 실패가 고정된 뒤에는 오프라인 푸시마다 재시도하지 않고 조용히 건너뛴다."""
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", "/fake/path.json")
    monkeypatch.setattr(fcm_service, "_initialized", False)
    monkeypatch.setattr(fcm_service, "_init_failed", True)

    user = make_user("emp002")
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="tok-1"))
    db_session.commit()

    calls = {"n": 0}

    def _boom(path):
        calls["n"] += 1
        raise IOError("credentials file not found")

    monkeypatch.setattr(fcm_service.credentials, "Certificate", _boom)

    message = ChatMessage(room_id=1, sender_id="emp001", content="hi")
    with patch("app.services.fcm_service.messaging.send") as mock_send:
        fcm_service.send_new_message_push(db_session, user.user_id, 1, message)
        mock_send.assert_not_called()
    assert calls["n"] == 0


def test_init_firebase_treats_already_initialized_as_success(monkeypatch):
    """기본 앱이 이미 존재해서 나는 ValueError는 실패가 아니라 정상 상태로 취급한다."""
    monkeypatch.setattr(fcm_service.settings, "FIREBASE_CREDENTIALS_PATH", "/fake/path.json")
    monkeypatch.setattr(fcm_service, "_initialized", False)
    monkeypatch.setattr(fcm_service, "_init_failed", False)
    monkeypatch.setattr(fcm_service.credentials, "Certificate", lambda path: object())

    def _already_exists(cred):
        raise ValueError("The default Firebase app already exists.")

    monkeypatch.setattr(fcm_service.firebase_admin, "initialize_app", _already_exists)
    monkeypatch.setattr(fcm_service.firebase_admin, "get_app", lambda: object())

    fcm_service.init_firebase()

    assert fcm_service._initialized is True
    assert fcm_service._init_failed is False


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
    db_session.add(DeviceToken(user_id=user.user_id, fcm_token="alive-token"))
    db_session.commit()

    class FakeUnregisteredError(Exception):
        pass
    FakeUnregisteredError.__name__ = "UnregisteredError"

    def _fake_send(fcm_message):
        if fcm_message.token == "dead-token":
            raise FakeUnregisteredError("gone")
        return "fake-message-id"

    message = ChatMessage(room_id=1, sender_id="emp001", content="hi")
    with patch("app.services.fcm_service.messaging.send", side_effect=_fake_send):
        fcm_service.send_new_message_push(db_session, user.user_id, 1, message)

    assert db_session.query(DeviceToken).filter(DeviceToken.fcm_token == "dead-token").count() == 0
    assert db_session.query(DeviceToken).filter(DeviceToken.fcm_token == "alive-token").count() == 1
