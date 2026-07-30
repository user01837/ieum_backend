from app.models.project import Project
from app.models.chat import ChatRoom, ChatRoomMember
from app.models.project_member import ProjectMember
from app.models import department, task, project_member  # noqa: F401  (register PROJECT's FK targets with Base)


def _room_member_ids(db_session, room_id):
    return {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
    }


def test_create_project_with_collaborators_creates_chat_room(client, make_user, db_session):
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner
    collab = make_user("20260002", "이직원")

    res = client.post(
        "/projects",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab.user_id],
        },
    )
    assert res.status_code == 200
    project_id = res.json()["projectId"]

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is not None

    member_ids = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == project.chat_room_id).all()
    }
    assert member_ids == {"20260001", "20260002"}


def test_create_project_without_collaborators_skips_chat_room(client, db_session):
    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": []},
    )
    project_id = res.json()["projectId"]

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is None


def test_update_project_adding_collaborator_creates_chat_room_if_missing(client, make_user, db_session):
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner

    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": []},
    )
    project_id = res.json()["projectId"]
    collab = make_user("20260002", "이직원")

    update_res = client.patch(
        f"/projects/{project_id}",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab.user_id]},
    )
    assert update_res.status_code == 200

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is not None

    member_ids = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == project.chat_room_id).all()
    }
    assert member_ids == {"20260001", "20260002"}


def test_update_project_adding_more_collaborators_reuses_existing_chat_room(client, make_user, db_session):
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner

    collab1 = make_user("20260002", "이직원")
    create_res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab1.user_id]},
    )
    project_id = create_res.json()["projectId"]
    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    original_room_id = project.chat_room_id

    collab2 = make_user("20260003", "박직원")
    client.patch(
        f"/projects/{project_id}",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab1.user_id, collab2.user_id],
        },
    )

    db_session.refresh(project)
    assert project.chat_room_id == original_room_id

    member_ids = {
        str(m.user_id)
        for m in db_session.query(ChatRoomMember).filter(ChatRoomMember.room_id == project.chat_room_id).all()
    }
    assert member_ids == {"20260001", "20260002", "20260003"}


def test_project_room_with_single_collaborator_is_group_room(client, make_user, db_session):
    """협력자가 1명이어도 사업 채팅방은 그룹방이어야 한다(인원 추가 가능)."""
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner
    collab = make_user("20260002", "이직원")

    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab.user_id]},
    )
    project_id = res.json()["projectId"]

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    room = db_session.query(ChatRoom).filter(ChatRoom.room_id == project.chat_room_id).first()
    assert room.is_group is True
    assert room.name == "[사업] 테스트 사업"


def test_project_room_does_not_hijack_existing_direct_room(client, make_user, db_session):
    """소유자-협력자 간 기존 1:1 DM이 있어도 사업 채팅방은 별도의 그룹방으로 생성된다."""
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner
    collab = make_user("20260002", "이직원")

    dm_res = client.post("/chat/rooms", json={"member_ids": [str(collab.user_id)]})
    assert dm_res.status_code == 201
    dm_room_id = dm_res.json()["room_id"]
    assert dm_res.json()["is_group"] is False

    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab.user_id]},
    )
    project_id = res.json()["projectId"]

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is not None
    # 기존 1:1 DM을 사업 채팅방으로 물려받으면 안 된다.
    assert project.chat_room_id != dm_room_id

    room = db_session.query(ChatRoom).filter(ChatRoom.room_id == project.chat_room_id).first()
    assert room.is_group is True
    assert _room_member_ids(db_session, project.chat_room_id) == {"20260001", "20260002"}
    # 원래의 1:1 DM은 그대로 남아 있어야 한다.
    assert _room_member_ids(db_session, dm_room_id) == {"20260001", "20260002"}


def test_project_room_can_add_members_after_single_collaborator_creation(client, make_user, db_session):
    """협력자 1명으로 만든 사업 채팅방에도 인원 추가 API가 통해야 한다."""
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner
    collab = make_user("20260002", "이직원")
    newcomer = make_user("20260003", "박직원")

    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab.user_id]},
    )
    project = db_session.query(Project).filter(
        Project.project_id == res.json()["projectId"]
    ).first()

    add_res = client.post(
        f"/chat/rooms/{project.chat_room_id}/members",
        json={"member_ids": [str(newcomer.user_id)]},
    )
    assert add_res.status_code == 200
    assert set(add_res.json()["member_ids"]) == {"20260001", "20260002", "20260003"}


def test_leaving_project_room_is_not_undone_by_new_collaborator(client, make_user, db_session):
    """채팅방을 나간 협력자는 새 협력자가 추가돼도 다시 초대되지 않는다."""
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner
    collab1 = make_user("20260002", "이직원")
    collab2 = make_user("20260003", "박직원")

    res = client.post(
        "/projects",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab1.user_id, collab2.user_id],
        },
    )
    project_id = res.json()["projectId"]
    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    room_id = project.chat_room_id
    assert _room_member_ids(db_session, room_id) == {"20260001", "20260002", "20260003"}

    # collab1이 스스로 채팅방을 나간다 (사업 협력자 자격은 유지).
    client.current_user_holder["user"] = collab1
    leave_res = client.delete(f"/chat/rooms/{room_id}")
    assert leave_res.status_code == 204
    assert "20260002" not in _room_member_ids(db_session, room_id)

    # 주관자가 새 협력자를 추가한다.
    client.current_user_holder["user"] = owner
    collab3 = make_user("20260004", "최직원")
    patch_res = client.patch(
        f"/projects/{project_id}",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab1.user_id, collab2.user_id, collab3.user_id],
        },
    )
    assert patch_res.status_code == 200

    member_ids = _room_member_ids(db_session, room_id)
    assert "20260002" not in member_ids  # 나간 사람은 재초대되지 않는다
    assert "20260004" in member_ids      # 새로 추가된 사람은 들어온다
    assert member_ids == {"20260001", "20260003", "20260004"}
    # 사업 협력자 자격 자체는 유지된다.
    collab_ids = {
        str(m.user_id)
        for m in db_session.query(ProjectMember).filter(
            ProjectMember.project_id == project_id, ProjectMember.role_code == "02"
        ).all()
    }
    assert collab_ids == {"20260002", "20260003", "20260004"}


def test_create_project_with_collaborators_but_createChatRoom_false_skips_room(client, make_user, db_session):
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner
    collab = make_user("20260002", "이직원")

    res = client.post(
        "/projects",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab.user_id],
            "createChatRoom": False,
        },
    )
    assert res.status_code == 200
    project_id = res.json()["projectId"]

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is None


def test_update_project_adding_collaborator_with_createChatRoom_false_skips_room(client, make_user, db_session):
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner

    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": []},
    )
    project_id = res.json()["projectId"]
    collab = make_user("20260002", "이직원")

    update_res = client.patch(
        f"/projects/{project_id}",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab.user_id],
            "createChatRoom": False,
        },
    )
    assert update_res.status_code == 200

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is None
    # 사업 협력자 자격 자체는 정상적으로 부여되어야 한다 (단톡방만 생략).
    collab_ids = {
        str(m.user_id)
        for m in db_session.query(ProjectMember).filter(
            ProjectMember.project_id == project_id, ProjectMember.role_code == "02"
        ).all()
    }
    assert collab_ids == {"20260002"}


def test_update_project_with_existing_room_and_createChatRoom_false_skips_adding_new_member(
    client, make_user, db_session
):
    """이미 방이 있어도 createChatRoom=false면 새 협력자를 그 방에 초대하지 않는다."""
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner
    collab1 = make_user("20260002", "이직원")

    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab1.user_id]},
    )
    project_id = res.json()["projectId"]
    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    room_id = project.chat_room_id
    assert room_id is not None

    collab2 = make_user("20260003", "박직원")
    client.patch(
        f"/projects/{project_id}",
        json={
            "name": "테스트 사업",
            "businessContent": "내용",
            "memberUserIds": [collab1.user_id, collab2.user_id],
            "createChatRoom": False,
        },
    )

    assert "20260003" not in _room_member_ids(db_session, room_id)


def test_lazy_room_creation_by_non_owner_includes_real_owner(client, make_user, db_session):
    """주관자가 아닌 사람이 수정해 방이 뒤늦게 만들어져도 실제 주관자가 포함된다."""
    owner = make_user("20260001", "김직원")
    client.current_user_holder["user"] = owner

    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": []},
    )
    project_id = res.json()["projectId"]
    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is None

    outsider = make_user("20260009", "정직원")
    collab = make_user("20260002", "이직원")
    client.current_user_holder["user"] = outsider

    patch_res = client.patch(
        f"/projects/{project_id}",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab.user_id]},
    )
    assert patch_res.status_code == 200

    db_session.refresh(project)
    assert project.chat_room_id is not None
    room = db_session.query(ChatRoom).filter(ChatRoom.room_id == project.chat_room_id).first()
    assert room.is_group is True

    member_ids = _room_member_ids(db_session, project.chat_room_id)
    assert "20260001" in member_ids  # 실제 주관자가 빠지지 않는다
    assert member_ids == {"20260001", "20260002", "20260009"}
