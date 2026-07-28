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
