import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.chat_connection_manager import manager as chat_manager

router = APIRouter()


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
            # "send_message"는 Task 6에서 구현
    except WebSocketDisconnect:
        pass
    finally:
        chat_manager.disconnect(user.user_id, websocket)
