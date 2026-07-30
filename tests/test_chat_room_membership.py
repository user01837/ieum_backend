def test_add_members_to_group_room(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    m4 = make_user("emp004", "최직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    res = client.post(f"/chat/rooms/{room['room_id']}/members", json={"member_ids": [m4.user_id]})
    assert res.status_code == 200
    assert sorted(res.json()["member_ids"]) == sorted(["emp001", "emp002", "emp003", "emp004"])


def test_add_members_rejects_direct_room(client, make_user):
    other = make_user("emp002", "이직원")
    room = client.post("/chat/rooms", json={"member_ids": [other.user_id]}).json()

    res = client.post(f"/chat/rooms/{room['room_id']}/members", json={"member_ids": ["emp002"]})
    assert res.status_code == 400


def test_add_members_rejects_unknown_user(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    res = client.post(f"/chat/rooms/{room['room_id']}/members", json={"member_ids": ["ghost"]})
    assert res.status_code == 400


def test_add_members_rejects_non_member(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    m4 = make_user("emp004", "최직원")
    m5 = make_user("emp005", "정직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    # emp001(방 생성자)이 아닌 emp004는 실제로 존재하는 이 방의 멤버가 아니므로
    # 403이 반환되어야 한다. current_user_holder를 바꿔치기하여 emp004로
    # 로그인한 상태를 흉내낸다.
    client.current_user_holder["user"] = m4

    res = client.post(f"/chat/rooms/{room['room_id']}/members", json={"member_ids": [m5.user_id]})
    assert res.status_code == 403


def test_leave_room_removes_current_user_only(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    res = client.delete(f"/chat/rooms/{room['room_id']}")
    assert res.status_code == 204

    rooms = client.get("/chat/rooms").json()
    assert rooms == []


def test_leave_room_rejects_non_member(client):
    res = client.delete("/chat/rooms/999999")
    assert res.status_code == 404


def test_rename_room_updates_name(client, make_user):
    m2 = make_user("emp002", "이직원")
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id], "name": None},
    ).json()

    res = client.patch(f"/chat/rooms/{room['room_id']}", json={"name": "우리 팀방"})
    assert res.status_code == 200
    assert res.json()["name"] == "우리 팀방"

    rooms = client.get("/chat/rooms").json()
    assert rooms[0]["name"] == "우리 팀방"


def test_rename_room_rejects_non_member(client, make_user):
    m2 = make_user("emp002", "이직원")
    m3 = make_user("emp003", "박직원")
    room = client.post("/chat/rooms", json={"member_ids": [m2.user_id]}).json()

    client.current_user_holder["user"] = m3
    res = client.patch(f"/chat/rooms/{room['room_id']}", json={"name": "새 이름"})
    assert res.status_code == 403


def test_rename_room_rejects_nonexistent_room(client):
    res = client.patch("/chat/rooms/999999", json={"name": "새 이름"})
    assert res.status_code == 404


def test_rename_room_rejects_empty_name(client, make_user):
    m2 = make_user("emp002", "이직원")
    room = client.post("/chat/rooms", json={"member_ids": [m2.user_id]}).json()

    res = client.patch(f"/chat/rooms/{room['room_id']}", json={"name": ""})
    assert res.status_code == 422


def test_rename_room_rejects_whitespace_only_name(client, make_user):
    m2 = make_user("emp002", "이직원")
    room = client.post("/chat/rooms", json={"member_ids": [m2.user_id]}).json()

    res = client.patch(f"/chat/rooms/{room['room_id']}", json={"name": "   "})
    assert res.status_code == 422
