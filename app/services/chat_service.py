from sqlalchemy.orm import Session
from app.models.chat import ChatRoom, ChatRoomMember, ChatMessage


def find_existing_direct_room(db: Session, user_id_a: str, user_id_b: str) -> ChatRoom | None:
    """두 사람 모두를 멤버로 둔 1:1(is_group=False) 방이 이미 있으면 반환."""
    rooms_of_a = db.query(ChatRoomMember.room_id).filter(ChatRoomMember.user_id == user_id_a).subquery()
    return (
        db.query(ChatRoom)
        .join(ChatRoomMember, ChatRoom.room_id == ChatRoomMember.room_id)
        .filter(
            ChatRoom.is_group.is_(False),
            ChatRoom.room_id.in_(rooms_of_a),
            ChatRoomMember.user_id == user_id_b,
        )
        .first()
    )


def create_room(db: Session, creator_id: str, member_ids: list[str], name: str | None) -> ChatRoom:
    all_member_ids = sorted(set(member_ids) | {creator_id})
    is_group = len(all_member_ids) > 2

    if not is_group:
        other_id = next(uid for uid in all_member_ids if uid != creator_id)
        existing = find_existing_direct_room(db, creator_id, other_id)
        if existing:
            return existing

    room = ChatRoom(name=name if is_group else None, is_group=is_group, created_by=creator_id)
    db.add(room)
    db.flush()

    for user_id in all_member_ids:
        db.add(ChatRoomMember(room_id=room.room_id, user_id=user_id))

    db.commit()
    db.refresh(room)
    return room


def list_rooms_for_user(db: Session, user_id: str) -> list[dict]:
    memberships = db.query(ChatRoomMember).filter(ChatRoomMember.user_id == user_id).all()
    room_ids = [m.room_id for m in memberships]
    if not room_ids:
        return []

    rooms = db.query(ChatRoom).filter(ChatRoom.room_id.in_(room_ids)).all()
    result = []
    for room in rooms:
        member_ids = [
            m.user_id for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
        ]
        last_message = (
            db.query(ChatMessage)
            .filter(ChatMessage.room_id == room.room_id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        result.append({
            "room_id": room.room_id,
            "name": room.name,
            "is_group": room.is_group,
            "member_ids": member_ids,
            "last_message": last_message.content if last_message else None,
            "last_message_at": last_message.created_at.isoformat() if last_message else None,
        })
    result.sort(key=lambda r: r["last_message_at"] or "", reverse=True)
    return result


def is_room_member(db: Session, room_id: int, user_id: str) -> bool:
    return (
        db.query(ChatRoomMember)
        .filter(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user_id)
        .first()
        is not None
    )


def other_member_ids(db: Session, room_id: int, sender_id: str) -> list[str]:
    return [
        m.user_id
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
        if m.user_id != sender_id
    ]
