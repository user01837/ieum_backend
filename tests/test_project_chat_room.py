from app.models.project import Project
from app.models.chat import ChatRoomMember
from app.models import department, task, project_member  # noqa: F401  (register PROJECT's FK targets with Base)


def test_create_project_with_collaborators_creates_chat_room(client, make_user, db_session):
    collab = make_user("emp002", "이직원")

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
    assert member_ids == {"emp001", "emp002"}


def test_create_project_without_collaborators_skips_chat_room(client, db_session):
    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": []},
    )
    project_id = res.json()["projectId"]

    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    assert project.chat_room_id is None


def test_update_project_adding_collaborator_creates_chat_room_if_missing(client, make_user, db_session):
    res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": []},
    )
    project_id = res.json()["projectId"]
    collab = make_user("emp002", "이직원")

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
    assert member_ids == {"emp001", "emp002"}


def test_update_project_adding_more_collaborators_reuses_existing_chat_room(client, make_user, db_session):
    collab1 = make_user("emp002", "이직원")
    create_res = client.post(
        "/projects",
        json={"name": "테스트 사업", "businessContent": "내용", "memberUserIds": [collab1.user_id]},
    )
    project_id = create_res.json()["projectId"]
    project = db_session.query(Project).filter(Project.project_id == project_id).first()
    original_room_id = project.chat_room_id

    collab2 = make_user("emp003", "박직원")
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
    assert member_ids == {"emp001", "emp002", "emp003"}
