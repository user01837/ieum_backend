from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.notification import Notification, DeviceToken

router = APIRouter()


class DeviceTokenRequest(BaseModel):
    fcm_token: str


class NotificationItem(BaseModel):
    notification_id: int
    type: str
    room_id: int | None
    message_id: int | None
    is_read: bool
    created_at: str


@router.get("", response_model=list[NotificationItem])
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.user_id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    return [
        NotificationItem(
            notification_id=n.notification_id,
            type=n.type,
            room_id=n.room_id,
            message_id=n.message_id,
            is_read=n.is_read,
            created_at=n.created_at.isoformat(),
        )
        for n in rows
    ]


@router.post("/device-token", status_code=status.HTTP_204_NO_CONTENT)
def register_device_token(
    req: DeviceTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(DeviceToken).filter(DeviceToken.fcm_token == req.fcm_token).first()
    if existing:
        existing.user_id = current_user.user_id
    else:
        db.add(DeviceToken(user_id=current_user.user_id, fcm_token=req.fcm_token))
    db.commit()


@router.delete("/device-token", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device_token(
    req: DeviceTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(DeviceToken).filter(
        DeviceToken.fcm_token == req.fcm_token,
        DeviceToken.user_id == current_user.user_id,
    ).delete(synchronize_session=False)
    db.commit()
