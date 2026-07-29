from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.chat import ChatRoom, ChatRoomMember, ChatMessage
from app.models.notification import Notification


def find_existing_direct_room(db: Session, user_id_a: str, user_id_b: str) -> ChatRoom | None:
    """두 사람 모두를 멤버로 둔 1:1(is_group=False) 방이 이미 있으면 반환."""
    rooms_of_a = db.query(ChatRoomMember.room_id).filter(ChatRoomMember.user_id == user_id_a).scalar_subquery()
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
    unread_map = unread_count_by_room(db, user_id)
    result = []
    for room in rooms:
        member_ids = [
            str(m.user_id)
            for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
        ]
        last_message = (
            db.query(ChatMessage)
            .filter(ChatMessage.room_id == room.room_id)
            # created_at(MySQL DATETIME)은 초 단위라 같은 초에 들어온 메시지끼리 순서가 갈리지 않는다.
            # 페이지네이션(get_messages)과 동일하게 autoincrement PK 기준으로 정렬한다.
            .order_by(ChatMessage.message_id.desc())
            .first()
        )
        result.append({
            "room_id": room.room_id,
            "name": room.name,
            "is_group": room.is_group,
            "member_ids": member_ids,
            "last_message": last_message.content if last_message else None,
            "last_message_at": last_message.created_at.isoformat() if last_message else None,
            "unread_count": unread_map.get(room.room_id, 0),
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
    # ChatRoomMember.user_id는 실제 DB에서 int로 저장되어 있어(USER.user_id가 int) ORM이
    # 읽어올 때 Python int로 돌아온다. sender_id(문자열)와 비교하려면 양쪽을 str로 맞춰야
    # 발신자 본인을 정확히 제외할 수 있다.
    return [
        str(m.user_id)
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
        if str(m.user_id) != str(sender_id)
    ]


def get_messages(db: Session, room_id: int, before_message_id: int | None, size: int) -> list[ChatMessage]:
    query = db.query(ChatMessage).filter(ChatMessage.room_id == room_id)
    if before_message_id is not None:
        query = query.filter(ChatMessage.message_id < before_message_id)
    return query.order_by(ChatMessage.message_id.desc()).limit(size).all()


def mark_room_read(db: Session, room_id: int, user_id: str) -> int:
    updated = (
        db.query(Notification)
        .filter(
            Notification.room_id == room_id,
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return updated


def unread_count_by_room(db: Session, user_id: str) -> dict[int, int]:
    rows = (
        db.query(Notification.room_id, func.count(Notification.notification_id))
        .filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
            Notification.room_id.isnot(None),
        )
        .group_by(Notification.room_id)
        .all()
    )
    return {room_id: count for room_id, count in rows}


def record_message(db: Session, room_id: int, sender_id: str, content: str) -> ChatMessage:
    message = ChatMessage(room_id=room_id, sender_id=sender_id, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def create_notification(db: Session, user_id: str, room_id: int, message_id: int) -> Notification:
    notification = Notification(
        user_id=user_id, type="CHAT_MESSAGE", room_id=room_id, message_id=message_id, is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def add_members_to_room(db: Session, room_id: int, new_member_ids: list[str]) -> None:
    existing_ids = {
        str(m.user_id)
        for m in db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
    }
    for user_id in new_member_ids:
        if user_id in existing_ids:
            continue
        db.add(ChatRoomMember(room_id=room_id, user_id=user_id))
        existing_ids.add(user_id)
    db.commit()


def leave_room(db: Session, room_id: int, user_id: str) -> None:
    db.query(ChatRoomMember).filter(
        ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user_id,
    ).delete(synchronize_session=False)
    db.query(Notification).filter(
        Notification.room_id == room_id, Notification.user_id == user_id,
    ).delete(synchronize_session=False)
    db.commit()
