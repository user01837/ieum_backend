import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.services import chat_service, fcm_service
from app.services.chat_connection_manager import manager as chat_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# WebSocket 연결은 (탭이 열려 있는 동안) 몇 시간까지도 유지되므로 Depends(get_db)로
# 요청 수명 세션을 잡아두면 커넥션 풀(기본 5+10)이 금방 고갈되어 앱 전체가 멈춘다.
# 따라서 인증 시점, 그리고 메시지 1건 처리 시점에만 짧게 세션을 열고 바로 닫는다.
# 테스트에서 인메모리 세션을 주입할 수 있도록 모듈 레벨 팩토리로 노출한다.
session_factory = SessionLocal


async def _broadcast(sockets: set[WebSocket], payload: dict) -> None:
    data = json.dumps(payload)
    for ws in sockets:
        try:
            await ws.send_text(data)
        except Exception:
            # 이미 끊겼지만 아직 정리되지 않은 소켓 하나 때문에 나머지 전송이 중단되지 않도록 한다.
            continue


def _authenticate_ws_user(token: str, db: Session) -> User | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError:
        return None
    if not user_id:
        return None
    return db.query(User).filter(User.user_id == user_id).first()


def _resolve_user_id(token: str) -> str | None:
    """인증에만 짧게 세션을 열고, ORM 객체가 아닌 문자열 user_id만 밖으로 내보낸다."""
    with session_factory() as db:
        user = _authenticate_ws_user(token, db)
        return user.user_id if user is not None else None


async def _handle_send_message(user_id: str, room_id: int, content: str) -> None:
    """메시지 1건을 처리한다. 이 함수 안에서만 DB 세션이 열려 있고, 끝나면 즉시 반납된다.

    DB 오류가 나더라도 연결 전체를 죽이지 않고 "이 메시지만 실패"로 격리한다.
    """
    with session_factory() as db:
        try:
            if not chat_service.is_room_member(db, room_id, user_id):
                return

            message = chat_service.record_message(db, room_id, user_id, content)
            # 세션이 닫힌 뒤 lazy load가 발생하지 않도록 필요한 값은 모두 여기서 읽어둔다.
            message_id = message.message_id
            message_payload = {
                "type": "new_message",
                "room_id": room_id,
                "message": {
                    "message_id": message_id,
                    "room_id": room_id,
                    "sender_id": user_id,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                },
            }

            await _broadcast(chat_manager.connections_for_user(user_id), message_payload)

            for recipient_id in chat_service.other_member_ids(db, room_id, user_id):
                recipient_sockets = chat_manager.connections_for_user(recipient_id)
                viewing_sockets = {
                    s for s in recipient_sockets if chat_manager.is_viewing_room(s, room_id)
                }
                elsewhere_sockets = recipient_sockets - viewing_sockets

                if viewing_sockets:
                    # 보고 있는 탭이 하나라도 있으면 이 방을 보는 중 -> 다른 탭에도 동기화만, 알림 없음
                    await _broadcast(viewing_sockets, message_payload)
                    if elsewhere_sockets:
                        await _broadcast(elsewhere_sockets, message_payload)
                else:
                    notification = chat_service.create_notification(
                        db, recipient_id, room_id, message_id
                    )
                    if elsewhere_sockets:
                        notif_payload = {
                            "type": "notification",
                            "notification": {
                                "notification_id": notification.notification_id,
                                "room_id": room_id,
                                "message_id": message_id,
                                "created_at": notification.created_at.isoformat(),
                            },
                        }
                        await _broadcast(elsewhere_sockets, message_payload)
                        await _broadcast(elsewhere_sockets, notif_payload)
                    else:
                        # elsewhere_sockets가 비어있고 recipient_sockets도 비어있으면(오프라인)
                        # 알림 row만 생성되고 소켓 전송은 없다 - 대신 FCM 푸시를 발송한다.
                        # messaging.send()는 동기 HTTPS 호출(토큰당 100~300ms)이라
                        # 이벤트 루프에서 직접 호출하면 다른 모든 사용자의 트래픽이 멈춘다.
                        await run_in_threadpool(
                            fcm_service.send_new_message_push, db, recipient_id, room_id, message
                        )
        except WebSocketDisconnect:
            raise
        except Exception:
            logger.exception(
                "채팅 메시지 처리 실패 (user_id=%s, room_id=%s)", user_id, room_id
            )
            db.rollback()


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket, token: str = Query(...)):
    user_id = _resolve_user_id(token)
    if user_id is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    chat_manager.connect(user_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                msg_type = data.get("type")
            except (json.JSONDecodeError, AttributeError):
                # 형식이 잘못된 메시지는 무시하고 연결을 유지한다.
                continue

            if msg_type == "active_room":
                chat_manager.set_active_room(websocket, data.get("room_id"))

            elif msg_type == "send_message":
                room_id = data.get("room_id")
                content = (data.get("content") or "").strip()
                if not isinstance(room_id, int) or not content:
                    continue
                try:
                    await _handle_send_message(user_id, room_id, content)
                except WebSocketDisconnect:
                    raise
                except Exception:
                    # 세션 생성 실패 등 _handle_send_message 밖에서 난 오류도
                    # 연결을 끊지 않고 다음 메시지로 넘어간다.
                    logger.exception(
                        "채팅 메시지 처리 중 예기치 못한 오류 (user_id=%s, room_id=%s)",
                        user_id,
                        room_id,
                    )
    except WebSocketDisconnect:
        pass
    finally:
        chat_manager.disconnect(user_id, websocket)
