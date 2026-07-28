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
    for ws in sockets:
        await ws.send_text(json.dumps(payload))


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
                if not room_id or not content:
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
                        await _broadcast(viewing_sockets, message_payload)

                    if elsewhere_sockets or not recipient_sockets:
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
                        # recipient_sockets가 아예 없는 경우(오프라인)의 FCM 발송은 Task 7에서 추가
    except WebSocketDisconnect:
        pass
    finally:
        chat_manager.disconnect(user.user_id, websocket)
