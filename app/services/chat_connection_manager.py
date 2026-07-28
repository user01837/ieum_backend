from fastapi import WebSocket


class ChatConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}
        self._active_room: dict[WebSocket, int | None] = {}

    def connect(self, user_id: str, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(websocket)
        self._active_room[websocket] = None

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if sockets and websocket in sockets:
            sockets.remove(websocket)
            if not sockets:
                del self._connections[user_id]
        self._active_room.pop(websocket, None)

    def set_active_room(self, websocket: WebSocket, room_id: int | None) -> None:
        self._active_room[websocket] = room_id

    def is_user_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    def connections_for_user(self, user_id: str) -> set[WebSocket]:
        return set(self._connections.get(user_id, set()))

    def is_viewing_room(self, websocket: WebSocket, room_id: int) -> bool:
        return self._active_room.get(websocket) == room_id


manager = ChatConnectionManager()
