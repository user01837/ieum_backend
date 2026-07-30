from datetime import datetime, timezone
from typing import Optional, List
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session, aliased
from sqlalchemy import or_, exists, func

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.announcement import Announcement
from app.models.announcement_attachment import AnnouncementAttachment
from app.models.notification import Notification, DeviceToken
from app.models.department import Department
from app.services import fcm_service
from app.services.s3_service import upload_file_to_s3

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
# 유틸
# ----------------------------------------------------------------

def get_department_name(department_code: Optional[str], db: Session) -> str:
    if not department_code:
        return "전체"
    dept = db.query(Department).filter(Department.department_code == department_code).first()
    return dept.name if dept else ""

# ----------------------------------------------------------------
# Pydantic 스키마
# ----------------------------------------------------------------

def get_create_request(request_data: str = Form(...)) -> "AnnouncementCreateRequest":
    """Form-data로 받은 JSON 문자열을 Pydantic 모델로 파싱"""
    return AnnouncementCreateRequest.parse_raw(request_data)

def get_update_request(request_data: str = Form(...)) -> "AnnouncementUpdateRequest":
    """Form-data로 받은 JSON 문자열을 Pydantic 모델로 파싱"""
    return AnnouncementUpdateRequest.parse_raw(request_data)

class AnnouncementCreateRequest(BaseModel):
    title:           str
    content:         str
    is_pinned:       bool = False
    department_code: Optional[str] = None

class AnnouncementUpdateRequest(BaseModel):
    title:           Optional[str] = None
    content:         Optional[str] = None
    is_pinned:       Optional[bool] = None
    department_code: Optional[str] = None

class AnnouncementListItem(BaseModel):
    announcementId: int
    title:          str
    isPinned:       bool
    createdByName:  str
    departmentName:  Optional[str]
    createdAt:      str
    hasAttachment:  bool

class AnnouncementListResponse(BaseModel):
    content:       List[AnnouncementListItem]
    totalElements: int
    totalPages:    int
    page:          int
    size:          int

class AttachmentInfo(BaseModel):
    attachmentId: int
    fileUrl:      str
    fileName:     str

class AnnouncementDetailResponse(BaseModel):
    announcementId: int
    title:          str
    content:        str
    isPinned:       bool
    createdBy:      int
    createdByName:  str
    updatedByName:  Optional[str]
    departmentName:  Optional[str]
    createdAt:      str
    updatedAt:      str
    attachments:    List[AttachmentInfo] = []

# ----------------------------------------------------------------
# 엔드포인트
# ----------------------------------------------------------------

# 1. 목록 조회
@router.get("", response_model=AnnouncementListResponse, summary="공지사항 목록 조회")
def get_announcement_list(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1),
    keyword: Optional[str] = Query(None),
    department_code: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 별칭(alias) 및 서브쿼리 생성
    Creator = aliased(User, name="creator")
    attachment_exists_subquery = exists().where(
        AnnouncementAttachment.announcement_id == Announcement.announcement_id,
        AnnouncementAttachment.is_deleted == False
    ).label("has_attachment")

    # 기본 쿼리 구성 (N+1 문제 해결을 위해 JOIN 사용)
    query = db.query(
        Announcement,
        Creator.name.label("creator_name"),
        Department.name.label("department_name"),
        attachment_exists_subquery
    ).outerjoin(
        Creator, Announcement.created_by == Creator.user_id
    ).outerjoin(
        Department, Announcement.department_code == Department.department_code
    ).filter(Announcement.is_deleted == False)

    # 권한에 따른 필터링
    if current_user.system_role_code == "02":
        if department_code:
            query = query.filter(Announcement.department_code == department_code)
    else:
        if department_code:
            query = query.filter(Announcement.department_code == department_code)
        else:
            query = query.filter(
                or_(
                    Announcement.department_code == None, # 전체 공지
                    Announcement.department_code == current_user.department_code,
                )
            )
    # 키워드 검색
    if keyword:
        query = query.filter(Announcement.title.like(f"%{keyword}%"))

    # 전체 개수 조회 (페이지네이션)
    total_elements = query.with_entities(func.count(Announcement.announcement_id)).scalar()
    total_pages = math.ceil(total_elements / size)
    
    # 정렬 및 페이징 적용하여 데이터 조회
    results = query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).offset(page * size).limit(size).all()

    # 응답 데이터 구성
    content = []
    for a, creator_name, dept_name, has_attachment in results:
        content.append(AnnouncementListItem(
            announcementId=a.announcement_id,
            title=a.title,
            isPinned=a.is_pinned,
            createdByName=creator_name or "",
            departmentName=dept_name if a.department_code else "전체",
            createdAt=a.created_at.isoformat(),
            hasAttachment=has_attachment,
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

    # 첨부파일 조회
    attachments = db.query(AnnouncementAttachment).filter(
        AnnouncementAttachment.announcement_id == announcementId,
        AnnouncementAttachment.is_deleted == False
    ).all()
    attachment_infos = [AttachmentInfo(
        attachmentId=att.attachment_id,
        fileUrl=att.file_url,
        fileName=att.file_name
    ) for att in attachments]

    return AnnouncementDetailResponse(
        announcementId=a.announcement_id,
        title=a.title,
        content=a.content,
        isPinned=a.is_pinned,
        createdBy=a.created_by,
        createdByName=creator.name if creator else "",
        updatedByName=updater.name if updater else None,
        departmentName=get_department_name(a.department_code, db),
        createdAt=a.created_at.isoformat(),
        updatedAt=a.updated_at.isoformat(),
        attachments=attachment_infos,
    )

# 3. 작성
@router.post("", status_code=status.HTTP_200_OK, summary="공지사항 작성")
async def create_announcement(
    background_tasks: BackgroundTasks,
    body: AnnouncementCreateRequest = Depends(get_create_request),
    files: List[UploadFile] = File(None, description="첨부파일 목록"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_write_permission(current_user)

    a = Announcement(
        title=body.title,
        content=body.content,
        is_pinned=body.is_pinned,
        created_by=current_user.user_id,
        department_code=body.department_code if current_user.system_role_code == "02" else current_user.department_code,
    )
    db.add(a)
    db.flush()  # announcement_id를 할당받기 위해 flush

    # 첨부파일 처리
    if files:
        for file in files:
            file_url = upload_file_to_s3(file, path_prefix="announcements")
            attachment = AnnouncementAttachment(
                announcement_id=a.announcement_id,
                file_url=file_url,
                file_name=file.filename,
            )
            db.add(attachment)

    db.commit()  # 모든 DB 작업을 한번에 커밋
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
async def update_announcement(
    announcementId: int,
    body: AnnouncementUpdateRequest = Depends(get_update_request),
    new_files: List[UploadFile] = File(None, description="새로 추가할 첨부파일 목록"),
    deleted_file_ids: Optional[str] = Form(None, description="삭제할 첨부파일 ID 목록 (쉼표로 구분)"),
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

    # 텍스트 필드 업데이트
    if body.title is not None:
        a.title = body.title
    if body.content is not None:
        a.content = body.content
    if body.is_pinned is not None:
        a.is_pinned = body.is_pinned
    if body.department_code is not None:
        a.department_code = body.department_code
    
    # 기존 첨부파일 삭제 처리
    if deleted_file_ids:
        ids_to_delete = [int(id_str) for id_str in deleted_file_ids.split(',') if id_str.isdigit()]
        if ids_to_delete:
            db.query(AnnouncementAttachment).filter(
                AnnouncementAttachment.announcement_id == announcementId,
                AnnouncementAttachment.attachment_id.in_(ids_to_delete)
            ).update({"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}, synchronize_session=False)

    # 새 첨부파일 추가 처리
    if new_files:
        for file in new_files:
            file_url = upload_file_to_s3(file, path_prefix="announcements")
            attachment = AnnouncementAttachment(
                announcement_id=announcementId,
                file_url=file_url,
                file_name=file.filename,
            )
            db.add(attachment)


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

# 6. 공지 알림 읽음 처리
@router.post("/read-notifications", status_code=status.HTTP_200_OK)
def read_announcement_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.type == "ANNOUNCEMENT",
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "읽음 처리 완료"}