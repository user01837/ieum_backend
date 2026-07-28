import logging

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification import DeviceToken

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase() -> None:
    global _initialized
    if _initialized or not settings.FIREBASE_CREDENTIALS_PATH:
        return
    try:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        _initialized = True
    except Exception:
        logger.exception("Firebase 초기화 실패 - FCM 발송이 비활성화됩니다.")


def send_new_message_push(db: Session, recipient_id: str, room_id: int, message) -> None:
    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.info("FIREBASE_CREDENTIALS_PATH 미설정 - FCM 발송을 건너뜁니다.")
        return

    init_firebase()
    if not _initialized:
        return

    tokens = db.query(DeviceToken).filter(DeviceToken.user_id == recipient_id).all()
    for device_token in tokens:
        fcm_message = messaging.Message(
            notification=messaging.Notification(title="새 메시지", body=message.content[:80]),
            data={"room_id": str(room_id), "message_id": str(message.message_id)},
            token=device_token.fcm_token,
        )
        try:
            messaging.send(fcm_message)
        except Exception as exc:
            # firebase_admin의 정확한 예외 계층은 버전마다 달라질 수 있어 클래스 이름으로 판별한다.
            if type(exc).__name__ == "UnregisteredError":
                db.query(DeviceToken).filter(DeviceToken.token_id == device_token.token_id).delete()
                db.commit()
            else:
                logger.exception(
                    "FCM 발송 실패 (user_id=%s, token_id=%s)", recipient_id, device_token.token_id
                )
