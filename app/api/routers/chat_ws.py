import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services import chat_service
from app.services.chat_connection_manager import manager as chat_manager

router = APIRouter()


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


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket, token: str = Query(...), db: Session = Depends(get_db)):
    user = _authenticate_ws_user(token, db)
    if user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    chat_manager.connect(user.user_id, websocket)

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
                if not chat_service.is_room_member(db, room_id, user.user_id):
                    continue

                message = chat_service.record_message(db, room_id, user.user_id, content)
                message_payload = {
                    "type": "new_message",
                    "room_id": room_id,
                    "message": {
                        "message_id": message.message_id,
                        "room_id": room_id,
                        "sender_id": user.user_id,
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                    },
                }

                await _broadcast(chat_manager.connections_for_user(user.user_id), message_payload)

                for recipient_id in chat_service.other_member_ids(db, room_id, user.user_id):
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
                            db, recipient_id, room_id, message.message_id
                        )
                        if elsewhere_sockets:
                            notif_payload = {
                                "type": "notification",
                                "notification": {
                                    "notification_id": notification.notification_id,
                                    "room_id": room_id,
                                    "message_id": message.message_id,
                                    "created_at": notification.created_at.isoformat(),
                                },
                            }
                            await _broadcast(elsewhere_sockets, message_payload)
                            await _broadcast(elsewhere_sockets, notif_payload)
                        # elsewhere_sockets가 비어있고 recipient_sockets도 비어있으면(오프라인) 알림 row만 생성되고
                        # 소켓 전송은 없다(FCM 발송은 Task 7에서 추가).
    except WebSocketDisconnect:
        pass
    finally:
        chat_manager.disconnect(user.user_id, websocket)
