from datetime import datetime, timezone
from typing import Optional, List
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.announcement import Announcement
from app.models.notification import Notification, DeviceToken
from app.services import fcm_service

router = APIRouter()

# ----------------------------------------------------------------
# 권한 체크
# ----------------------------------------------------------------

def check_write_permission(user: User):
    is_admin = user.system_role_code == "02"
    is_head  = user.position_code == "01"
    if not (is_admin or is_head):
        raise HTTPException(status_code=403, detail="작성 권한이 없습니다. 관리자 또는 부서장만 가능합니다.")

# ----------------------------------------------------------------
# Pydantic 스키마
# ----------------------------------------------------------------

class AnnouncementCreateRequest(BaseModel):
    title:     str
    content:   str
    is_pinned: bool = False

class AnnouncementUpdateRequest(BaseModel):
    title:     Optional[str] = None
    content:   Optional[str] = None
    is_pinned: Optional[bool] = None

class AnnouncementListItem(BaseModel):
    announcementId: int
    title:          str
    isPinned:       bool
    createdByName:  str
    createdAt:      str

class AnnouncementListResponse(BaseModel):
    content:       List[AnnouncementListItem]
    totalElements: int
    totalPages:    int
    page:          int
    size:          int

class AnnouncementDetailResponse(BaseModel):
    announcementId: int
    title:          str
    content:        str
    isPinned:       bool
    createdByName:  str
    updatedByName:  Optional[str]
    createdAt:      str
    updatedAt:      str

# ----------------------------------------------------------------
# 엔드포인트
# ----------------------------------------------------------------

# 1. 목록 조회
@router.get("", response_model=AnnouncementListResponse, summary="공지사항 목록 조회")
def get_announcement_list(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Announcement).filter(Announcement.is_deleted == False)
    query = query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())

    total_elements = query.count()
    total_pages = math.ceil(total_elements / size)
    items = query.offset(page * size).limit(size).all()

    content = []
    for a in items:
        creator = db.query(User).filter(User.user_id == a.created_by).first()
        content.append(AnnouncementListItem(
            announcementId=a.announcement_id,
            title=a.title,
            isPinned=a.is_pinned,
            createdByName=creator.name if creator else "",
            createdAt=a.created_at.isoformat(),
        ))

    return AnnouncementListResponse(
        content=content,
        totalElements=total_elements,
        totalPages=total_pages,
        page=page,
        size=size,
    )

# 2. 상세 조회
@router.get("/{announcementId}", response_model=AnnouncementDetailResponse, summary="공지사항 상세 조회")
def get_announcement_detail(
    announcementId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = db.query(Announcement).filter(
        Announcement.announcement_id == announcementId,
        Announcement.is_deleted == False,
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="존재하지 않는 공지사항입니다.")

    creator = db.query(User).filter(User.user_id == a.created_by).first()
    updater = db.query(User).filter(User.user_id == a.updated_by).first() if a.updated_by else None

    return AnnouncementDetailResponse(
        announcementId=a.announcement_id,
        title=a.title,
        content=a.content,
        isPinned=a.is_pinned,
        createdByName=creator.name if creator else "",
        updatedByName=updater.name if updater else None,
        createdAt=a.created_at.isoformat(),
        updatedAt=a.updated_at.isoformat(),
    )

# 3. 작성
@router.post("", status_code=status.HTTP_200_OK, summary="공지사항 작성")
def create_announcement(
    body: AnnouncementCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_write_permission(current_user)

    a = Announcement(
        title=body.title,
        content=body.content,
        is_pinned=body.is_pinned,
        created_by=current_user.user_id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)

    # 전체 일반 사용자에게 NOTIFICATION row 생성
    all_users = db.query(User).filter(
        User.system_role_code == "01",
        User.status_code == "01",
    ).all()
    for u in all_users:
        db.add(Notification(
            user_id=u.user_id,
            type="ANNOUNCEMENT",
            announcement_id=a.announcement_id,
            is_read=False,
        ))
    db.commit()

    # FCM 푸시 백그라운드
    background_tasks.add_task(fcm_service.send_notice_push, db, a.announcement_id, a.title)

    return {"announcementId": a.announcement_id}

# 4. 수정
@router.patch("/{announcementId}", status_code=status.HTTP_200_OK, summary="공지사항 수정")
def update_announcement(
    announcementId: int,
    body: AnnouncementUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_write_permission(current_user)

    a = db.query(Announcement).filter(
        Announcement.announcement_id == announcementId,
        Announcement.is_deleted == False,
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="존재하지 않는 공지사항입니다.")

    if body.title is not None:
        a.title = body.title
    if body.content is not None:
        a.content = body.content
    if body.is_pinned is not None:
        a.is_pinned = body.is_pinned
    a.updated_by = current_user.user_id

    db.commit()
    return {"announcementId": a.announcement_id}

# 5. 삭제
@router.delete("/{announcementId}", status_code=status.HTTP_200_OK, summary="공지사항 삭제")
def delete_announcement(
    announcementId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_write_permission(current_user)

    a = db.query(Announcement).filter(
        Announcement.announcement_id == announcementId,
        Announcement.is_deleted == False,
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="존재하지 않는 공지사항입니다.")

    a.is_deleted = True
    a.deleted_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "삭제되었습니다."}