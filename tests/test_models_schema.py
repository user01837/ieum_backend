from sqlalchemy import inspect


def test_notification_has_announcement_id_column(db_session):
    from app.models.notification import Notification

    columns = {c.name for c in inspect(Notification).columns}
    assert "announcement_id" in columns


def test_project_has_chat_room_id_column(db_session):
    from app.models.project import Project

    columns = {c.name for c in inspect(Project).columns}
    assert "chat_room_id" in columns
