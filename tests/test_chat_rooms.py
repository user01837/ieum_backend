def test_create_direct_room(client, make_user):
    other = make_user("emp002", "이직원")
    res = client.post("/chat/rooms", json={"member_ids": [other.user_id]})
    assert res.status_code == 201
    body = res.json()
    assert body["is_group"] is False
    assert sorted(body["member_ids"]) == sorted(["emp001", "emp002"])


def test_create_direct_room_dedup(client, make_user):
    other = make_user("emp002", "이직원")
    first = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    second = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()
    assert first["room_id"] == second["room_id"]


def test_create_group_room(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    res = client.post(
        "/chat/rooms",
        json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    )
    body = res.json()
    assert body["is_group"] is True
    assert body["name"] == "기획팀방"
    assert len(body["member_ids"]) == 3


def test_create_room_rejects_unknown_user(client):
    res = client.post("/chat/rooms", json={"member_ids": ["ghost"]})
    assert res.status_code == 400


def test_list_rooms_returns_my_rooms(client, make_user):
    other = make_user("emp002", "이직원")
    client.post("/chat/rooms", json={"member_ids": [other.user_id]})
    res = client.get("/chat/rooms")
    assert res.status_code == 200
    rooms = res.json()
    assert len(rooms) == 1
    assert "emp002" in rooms[0]["member_ids"]


def test_create_room_rejects_self_only_member(client):
    res = client.post("/chat/rooms", json={"member_ids": ["emp001"]})
    assert res.status_code == 400


def test_list_rooms_last_message_uses_message_id_order_on_created_at_tie(client, make_user, db_session):
    """created_at(초 단위)이 같은 메시지들 사이에서도 마지막 메시지 미리보기가 흔들리면 안 된다.

    페이지네이션(get_messages)이 message_id 기준이므로 미리보기도 같은 기준이어야 한다.
    """
    from datetime import datetime

    from app.models.chat import ChatMessage

    other = make_user("emp002", "이직원")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    same_second = datetime(2026, 7, 28, 12, 0, 0)
    for content in ["첫 번째", "두 번째", "마지막"]:
        db_session.add(
            ChatMessage(
                room_id=room["room_id"], sender_id="emp001", content=content, created_at=same_second
            )
        )
        db_session.commit()

    rooms = client.get("/chat/rooms").json()
    assert rooms[0]["last_message"] == "마지막"
