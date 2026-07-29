from app.services import chat_service
from app.models.chat import ChatRoomMember
from app.models.notification import Notification


def test_add_members_to_room_adds_new_members_only(client, make_user, db_session):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    room = chat_service.create_room(db_session, "emp001", ["emp002"], name="테스트방")

    chat_service.add_members_to_room(db_session, room.room_id, ["emp002", "emp003"])

    member_ids = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
    }
    assert member_ids == {"emp001", "emp002", "emp003"}


def test_leave_room_removes_membership_and_own_notifications(client, make_user, db_session):
    other = make_user("emp002", "이직원")
    room = chat_service.create_room(db_session, "emp001", ["emp002"], name=None)
    db_session.add(Notification(user_id="emp002", type="CHAT_MESSAGE", room_id=room.room_id, is_read=False))
    db_session.commit()

    chat_service.leave_room(db_session, room.room_id, "emp002")

    remaining_members = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == room.room_id).all()
    }
    assert remaining_members == {"emp001"}
    assert db_session.query(Notification).filter(Notification.user_id == "emp002").count() == 0


def test_leave_room_does_not_affect_other_members_notifications(client, make_user, db_session):
    other = make_user("emp002", "이직원")
    room = chat_service.create_room(db_session, "emp001", ["emp002"], name=None)
    db_session.add(Notification(user_id="emp001", type="CHAT_MESSAGE", room_id=room.room_id, is_read=False))
    db_session.commit()

    chat_service.leave_room(db_session, room.room_id, "emp002")

    assert db_session.query(Notification).filter(Notification.user_id == "emp001").count() == 1


def test_leave_room_scoped_to_room_id(client, make_user, db_session):
    """Verify that leave_room only deletes notifications in the specific room, not all for the user."""
    emp002 = make_user("emp002", "이직원")
    emp003 = make_user("emp003", "박직원")
    # Create first room with emp001 and emp002 (1:1 room)
    room1 = chat_service.create_room(db_session, "emp001", ["emp002"], name=None)
    # Create second room with emp001, emp002, and emp003 (group room)
    room2 = chat_service.create_room(db_session, "emp001", ["emp002", "emp003"], name="room2")

    # Add notification for emp002 in the second room
    db_session.add(Notification(user_id="emp002", type="CHAT_MESSAGE", room_id=room2.room_id, is_read=False))
    db_session.commit()

    # emp002 leaves the first room only
    chat_service.leave_room(db_session, room1.room_id, "emp002")

    # emp002 should still be a member of room2
    room2_members = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == room2.room_id).all()
    }
    assert "emp002" in room2_members

    # emp002's notification in room2 should still exist
    room2_notifications = db_session.query(Notification).filter(
        Notification.user_id == "emp002",
        Notification.room_id == room2.room_id,
    ).count()
    assert room2_notifications == 1

    # emp002 should not be a member of room1
    room1_members = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == room1.room_id).all()
    }
    assert "emp002" not in room1_members
