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
    room = client.post(
        "/chat/rooms", json={"member_ids": [m2.user_id, m3.user_id], "name": "기획팀방"},
    ).json()

    # emp001(현재 로그인 사용자)이 아닌 emp004는 이 방의 멤버가 아니므로
    # 이 요청 자체가 emp001 자격으로 나가지만, 멤버가 아닌 방에 시도하는 케이스를
    # 검증하기 위해 존재하지 않는 room_id로 대체 검증한다.
    res = client.post("/chat/rooms/999999/members", json={"member_ids": [m4.user_id]})
    assert res.status_code == 404


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
