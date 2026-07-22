from fastapi import APIRouter, Depends, Query, HTTPException, status, Form, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, or_, and_
from typing import List, Optional

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.task import Task
from app.models.knowledge import Knowledge, KnowledgeAttachment, KnowledgeLog, KnowledgeLogTag, KnowledgeTag
from app.services.s3_service import upload_file_to_s3
from app.models.department import Department

# --- 상수 ---
CATEGORY_NAME_MAP = {
    "01": "민원처리",
    "02": "사업추진",
    "03": "예산",
    "04": "인허가",
    "05": "실패사례",
    "99": "기타",
}

SCOPE_NAME_MAP = {
    "01": "내 부서",
    "02": "전체 부서",
}

# --- Pydantic 스키마 ---
class KnowledgeListItem(BaseModel):
    knowledge_id: int
    task_id: Optional[int]
    task_name: Optional[str]
    title: str
    category_code: Optional[str]
    category_name: Optional[str]
    scope_code: Optional[str]
    scope_name: Optional[str]
    department_name: Optional[str]
    log_count: int
    created_by_name: Optional[str]
    updated_at: Optional[str]

class KnowledgeListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[KnowledgeListItem]

class TagDetail(BaseModel):
    tag_id: int
    name: str

class LogDetail(BaseModel):
    log_id: int
    user_id: Optional[str]
    user_name: Optional[str]
    content: Optional[str]
    tags: List[TagDetail]
    is_deleted: bool
    created_at: Optional[str]
    updated_at: Optional[str]

class KnowledgeAttachmentDetail(BaseModel):
    attachment_id: int
    file_name: Optional[str]
    file_url: str

class KnowledgeDetailResponse(BaseModel):
    knowledge_id: int
    task_id: Optional[int]
    task_name: Optional[str]
    department_code: Optional[str]
    title: str
    category_code: Optional[str]
    category_name: Optional[str]
    summary: Optional[str]
    warning_note: Optional[str]
    scope_code: Optional[str]
    scope_name: Optional[str]
    created_by: Optional[str]
    created_by_name: Optional[str]
    updated_by_name: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    logs: List[LogDetail]
    attachments: List[KnowledgeAttachmentDetail]

class KnowledgeCreateResponse(BaseModel):
    knowledge_id: int
    title: str
    created_at: str

class KnowledgeUpdateResponse(BaseModel):
    knowledge_id: int
    message: str

class TagResponse(BaseModel):
    tag_id: int
    name: str

class TagCreateRequest(BaseModel):
    name: str = Field(..., description="새로 생성할 태그 이름")
    department_code: str = Field(..., description="태그가 속할 부서 코드")

class LogCreateRequest(BaseModel):
    content: str = Field(..., description="노하우 내용")
    tag_ids: List[int] = Field([], description="연결할 태그 ID 목록")

class LogResponse(BaseModel):
    log_id: int
    message: str

class LogUpdateRequest(BaseModel):
    content: Optional[str] = Field(None, description="수정할 노하우 내용")
    tag_ids: Optional[List[int]] = Field(None, description="새롭게 연결할 태그 ID 목록 (기존 연결은 모두 대체됨)")


# --- 라우터 ---
router = APIRouter()

@router.get(
    "",
    response_model=KnowledgeListResponse,
    summary="지식베이스 목록 조회 (페이지네이션)",
)
def get_knowledge_list(
    task_id: Optional[int] = Query(None),
    category_code: Optional[str] = Query(None),
    scope_code: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(0, description="페이지 번호 (0부터 시작)", ge=0),
    size: int = Query(10, description="페이지당 건수", ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 각 지식 항목의 로그 수를 계산하는 서브쿼리
    log_count_subquery = db.query(
        KnowledgeLog.knowledge_id,
        func.count(KnowledgeLog.log_id).label("log_count")
    ).filter(KnowledgeLog.is_deleted == 0).group_by(KnowledgeLog.knowledge_id).subquery()

    # 기본 쿼리
    query = db.query(
        Knowledge,
        Task.name.label("task_name"),
        User.name.label("created_by_name"),
        func.coalesce(log_count_subquery.c.log_count, 0).label("log_count"),
        Department.name.label("department_name")
    ).outerjoin(
        Task, Knowledge.task_id == Task.task_id
    ).outerjoin( # User 테이블과 outerjoin을 유지합니다.
        User, Knowledge.created_by == User.user_id
    ).outerjoin(
        log_count_subquery, Knowledge.knowledge_id == log_count_subquery.c.knowledge_id
    ).outerjoin(
        Department, Knowledge.department_code == Department.department_code
    )

    # --- 필터링 ---
    # 1. 공개 범위 필터
    if scope_code == "01":  # '내 부서' 필터
        query = query.filter(
            Knowledge.department_code == current_user.department_code
        )
    elif scope_code == "02":  # '전체 공개' 필터
        query = query.filter(Knowledge.scope_code == "02")
    else:  # 기본 조회 (필터 미선택 시)
        # 사용자는 '전체 부서' 공개 항목과 자신의 부서에 '내 부서'로 공개된 항목을 모두 볼 수 있습니다.
        query = query.filter(
            or_(
                Knowledge.scope_code == '02',  # 전체 부서
                and_(
                    Knowledge.scope_code == '01',  # 내 부서
                    Knowledge.department_code == current_user.department_code
                ),
            )
        )

    # 2. 쿼리 파라미터를 이용한 추가 필터
    if task_id:
        query = query.filter(Knowledge.task_id == task_id)
    if category_code:
        query = query.filter(Knowledge.category_code == category_code)
    if keyword:
        query = query.filter(Knowledge.title.contains(keyword))

    # --- 페이지네이션 ---
    total = query.count()
    results = query.order_by(Knowledge.updated_at.desc()).offset(page * size).limit(size).all()

    # --- 응답 데이터 구성 ---
    items = []
    for k, task_name, created_by_name, log_count, department_name in results:
        items.append(KnowledgeListItem(
            knowledge_id=k.knowledge_id,
            task_id=k.task_id,
            task_name=task_name,
            title=k.title,
            category_code=k.category_code,
            category_name=CATEGORY_NAME_MAP.get(k.category_code),
            scope_code=k.scope_code,
            scope_name=SCOPE_NAME_MAP.get(k.scope_code),
            department_name=department_name,
            log_count=log_count,
            created_by_name=created_by_name,
            updated_at=k.updated_at.isoformat() if k.updated_at else None,
        ))

    return KnowledgeListResponse(
        total=total,
        page=page,
        size=size,
        items=items,
    )

@router.get(
    "/tags",
    response_model=List[TagResponse],
    summary="부서별 태그 목록 조회"
)
def get_tags_by_department(
    department_code: str = Query(..., description="태그를 조회할 부서 코드"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """특정 부서에 속한 모든 태그 목록을 조회합니다."""
    tags = db.query(KnowledgeTag).filter(KnowledgeTag.department_code == department_code).order_by(KnowledgeTag.name).all()
    return tags

@router.post(
    "/tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="새 태그 생성"
)
def create_tag(
    request: TagCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """특정 부서에 새로운 태그를 생성합니다. 동일한 이름의 태그가 이미 존재하면 오류가 발생합니다."""
    existing_tag = db.query(KnowledgeTag).filter(
        KnowledgeTag.department_code == request.department_code,
        KnowledgeTag.name == request.name
    ).first()
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="해당 부서에 이미 동일한 이름의 태그가 존재합니다."
        )

    new_tag = KnowledgeTag(
        name=request.name,
        department_code=request.department_code,
        created_by=current_user.user_id
    )
    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)
    return new_tag

@router.get(
    "/{knowledge_id}",
    response_model=KnowledgeDetailResponse,
    summary="지식 카드 상세 조회",
)
def get_knowledge_detail(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. 작성자, 수정자 이름 조회를 위해 User 모델에 별칭 부여
    Creator = aliased(User, name='creator')
    Updater = aliased(User, name='updater')

    # 2. 지식 기본 정보 조회
    knowledge_query_result = db.query(
        Knowledge,
        Task.name.label("task_name"),
        Creator.name.label("created_by_name"),
        Updater.name.label("updated_by_name")
    ).outerjoin(
        Task, Knowledge.task_id == Task.task_id
    ).outerjoin(
        Creator, Knowledge.created_by == Creator.user_id
    ).outerjoin(
        Updater, Knowledge.updated_by == Updater.user_id
    ).filter(Knowledge.knowledge_id == knowledge_id).first()

    if not knowledge_query_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="존재하지 않는 지식 카드입니다.")

    knowledge, task_name, created_by_name, updated_by_name = knowledge_query_result

    # 3. 접근 권한 확인
    is_public = knowledge.scope_code == '02'
    is_in_my_dept = (knowledge.scope_code == '01' and knowledge.department_code == current_user.department_code)

    if not (is_public or is_in_my_dept):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이 지식 카드에 접근할 권한이 없습니다.")

    # 4. 첨부파일 목록 조회
    attachments_from_db = db.query(KnowledgeAttachment).filter(
        KnowledgeAttachment.knowledge_id == knowledge_id,
        KnowledgeAttachment.is_deleted == 0
    ).all()
    attachment_details = [
        KnowledgeAttachmentDetail(
            attachment_id=att.attachment_id,
            file_name=att.file_name,
            file_url=att.file_url
        ) for att in attachments_from_db
    ]

    # 4. 로그 및 관련 정보 조회 (N+1 방지)
    logs_from_db = db.query(KnowledgeLog).filter(
        KnowledgeLog.knowledge_id == knowledge_id,
        KnowledgeLog.is_deleted == 0
    ).order_by(KnowledgeLog.created_at.asc()).all()

    log_ids = [log.log_id for log in logs_from_db]
    user_ids_from_logs = {log.user_id for log in logs_from_db if log.user_id}

    # 4-1. 로그에 연결된 태그 일괄 조회
    tags_map = {}
    if log_ids:
        tag_results = db.query(
            KnowledgeLogTag.log_id,
            KnowledgeTag.tag_id,
            KnowledgeTag.name
        ).join(
            KnowledgeTag, KnowledgeLogTag.tag_id == KnowledgeTag.tag_id
        ).filter(KnowledgeLogTag.log_id.in_(log_ids)).all()

        for log_id, tag_id, tag_name in tag_results:
            if log_id not in tags_map:
                tags_map[log_id] = []
            tags_map[log_id].append(TagDetail(tag_id=tag_id, name=tag_name))

    # 4-2. 로그 작성자 이름 일괄 조회
    log_user_name_map = {}
    if user_ids_from_logs:
        users_from_logs = db.query(User.user_id, User.name).filter(User.user_id.in_(list(user_ids_from_logs))).all()
        log_user_name_map = {user_id: name for user_id, name in users_from_logs}

    # 5. 최종 응답 데이터 구성
    log_details = []
    for log in logs_from_db:
        log_details.append(LogDetail(
            log_id=log.log_id,
            user_id=str(log.user_id) if log.user_id is not None else None,
            user_name=log_user_name_map.get(str(log.user_id)) if log.user_id is not None else None,
            content=log.content,
            tags=tags_map.get(log.log_id, []),
            is_deleted=bool(log.is_deleted),
            created_at=log.created_at.isoformat() if log.created_at else None,
            updated_at=log.updated_at.isoformat() if log.updated_at else None,
        ))

    return KnowledgeDetailResponse(
        knowledge_id=knowledge.knowledge_id,
        task_id=knowledge.task_id,
        task_name=task_name,
        department_code=knowledge.department_code,
        title=knowledge.title,
        category_code=knowledge.category_code,
        category_name=CATEGORY_NAME_MAP.get(knowledge.category_code),
        summary=knowledge.summary,
        warning_note=knowledge.warning_note,
        scope_code=knowledge.scope_code,
        scope_name=SCOPE_NAME_MAP.get(knowledge.scope_code),
        created_by=str(knowledge.created_by) if knowledge.created_by is not None else None,
        created_by_name=created_by_name,
        updated_by_name=updated_by_name,
        created_at=knowledge.created_at.isoformat() if knowledge.created_at else None,
        updated_at=knowledge.updated_at.isoformat() if knowledge.updated_at else None,
        logs=log_details,
        attachments=attachment_details
    )

@router.post(
    "",
    response_model=KnowledgeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="지식 베이스 항목 생성",
)
def create_knowledge(
    # Form data
    title: str = Form(..., description="지식 제목"),
    category_code: str = Form(..., description="카테고리 코드"),
    scope_code: str = Form(..., description="공개 범위 코드 ('01' 또는 '02')"),
    summary: Optional[str] = Form(None, description="개요"),
    warning_note: Optional[str] = Form(None, description="주의사항"),
    task_id: Optional[int] = Form(None, description="연관된 Task ID"),
    # Files
    files: List[UploadFile] = File([], description="업로드할 첨부파일 목록"),
    # Dependencies
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    새로운 지식 베이스 항목을 생성합니다. 텍스트 정보와 함께 파일을 업로드할 수 있습니다.
    - **multipart/form-data** 형식으로 요청해야 합니다.
    """
    # 1. Knowledge 객체 생성
    new_knowledge = Knowledge(
        title=title,
        category_code=category_code,
        scope_code=scope_code,
        summary=summary,
        warning_note=warning_note,
        task_id=task_id,
        department_code=current_user.department_code,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(new_knowledge)
    db.flush()  # knowledge_id를 할당받기 위해 flush

    # 2. 파일 업로드 처리
    if files:
        for file in files:
            if file.filename:  # 실제 파일이 업로드되었는지 확인
                file_url = upload_file_to_s3(file, path_prefix="knowledge")
                new_attachment = KnowledgeAttachment(
                    knowledge_id=new_knowledge.knowledge_id,
                    file_name=file.filename,
                    file_url=file_url,
                    uploaded_by=current_user.user_id,
                )
                db.add(new_attachment)

    # 3. DB에 최종 커밋 및 응답 반환
    db.commit()
    db.refresh(new_knowledge)

    return KnowledgeCreateResponse(
        knowledge_id=new_knowledge.knowledge_id,
        title=new_knowledge.title,
        created_at=new_knowledge.created_at.isoformat()
    )

@router.post(
    "/{knowledge_id}/logs",
    response_model=LogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="노하우(로그) 생성"
)
def create_knowledge_log(
    knowledge_id: int,
    request: LogCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """특정 지식 카드에 새로운 노하우(로그)를 작성하고 태그를 연결합니다."""
    knowledge = db.query(Knowledge).filter(Knowledge.knowledge_id == knowledge_id).first()
    if not knowledge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="지식 카드를 찾을 수 없습니다.")

    # 노하우를 추가할 수 있는 권한 확인 (해당 지식카드를 볼 수 있는 사용자)
    is_public = knowledge.scope_code == '02'
    is_in_my_dept = (knowledge.scope_code == '01' and knowledge.department_code == current_user.department_code)
    if not (is_public or is_in_my_dept):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이 지식 카드에 노하우를 추가할 권한이 없습니다.")

    new_log = KnowledgeLog(
        knowledge_id=knowledge_id,
        content=request.content,
        user_id=current_user.user_id,
        updated_by=current_user.user_id
    )
    db.add(new_log)
    db.flush()

    if request.tag_ids:
        tags = db.query(KnowledgeTag.tag_id).filter(
            KnowledgeTag.tag_id.in_(request.tag_ids),
            KnowledgeTag.department_code == knowledge.department_code
        ).all()
        
        if len(tags) != len(set(request.tag_ids)):
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않거나 다른 부서의 태그가 포함되어 있습니다."
            )

        for tag_id in request.tag_ids:
            db.add(KnowledgeLogTag(log_id=new_log.log_id, tag_id=tag_id))

    db.commit()
    return LogResponse(log_id=new_log.log_id, message="노하우가 성공적으로 등록되었습니다.")

@router.patch(
    "/logs/{log_id}",
    response_model=LogResponse,
    summary="노하우(로그) 수정"
)
def update_knowledge_log(
    log_id: int,
    request: LogUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """기존 노하우의 내용이나 연결된 태그를 수정합니다. 해당 지식 카드를 열람할 수 있는 사용자는 누구나 수정할 수 있습니다."""
    log_to_update = db.query(KnowledgeLog).filter(KnowledgeLog.log_id == log_id, KnowledgeLog.is_deleted == 0).with_for_update().first()
    if not log_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수정할 노하우를 찾을 수 없습니다.")

    # 권한 확인: 해당 지식 카드를 볼 수 있는 사용자는 누구나 수정 가능
    knowledge = db.query(Knowledge).filter(Knowledge.knowledge_id == log_to_update.knowledge_id).first()
    if not knowledge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="노하우에 연결된 지식 카드를 찾을 수 없습니다.")
    is_public = knowledge.scope_code == '02'
    is_in_my_dept = (knowledge.scope_code == '01' and knowledge.department_code == current_user.department_code)
    if not (is_public or is_in_my_dept):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이 노하우를 수정할 권한이 없습니다.")

    if request.content is not None:
        log_to_update.content = request.content
    
    if request.tag_ids is not None:
        db.query(KnowledgeLogTag).filter(KnowledgeLogTag.log_id == log_id).delete(synchronize_session=False)
        if request.tag_ids:
            for tag_id in request.tag_ids:
                db.add(KnowledgeLogTag(log_id=log_id, tag_id=tag_id))

    log_to_update.updated_by = current_user.user_id
    db.commit()
    return LogResponse(log_id=log_id, message="노하우가 성공적으로 수정되었습니다.")

@router.delete(
    "/logs/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="노하우(로그) 삭제"
)
def delete_knowledge_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """기존 노하우를 삭제(소프트 삭제)합니다. 해당 지식 카드를 열람할 수 있는 사용자는 누구나 삭제할 수 있습니다."""
    log_to_delete = db.query(KnowledgeLog).filter(KnowledgeLog.log_id == log_id, KnowledgeLog.is_deleted == 0).with_for_update().first()
    if not log_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 노하우를 찾을 수 없습니다.")

    # 권한 확인: 해당 지식 카드를 볼 수 있는 사용자는 누구나 삭제 가능
    knowledge = db.query(Knowledge).filter(Knowledge.knowledge_id == log_to_delete.knowledge_id).first()
    if not knowledge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="노하우에 연결된 지식 카드를 찾을 수 없습니다.")
    is_public = knowledge.scope_code == '02'
    is_in_my_dept = (knowledge.scope_code == '01' and knowledge.department_code == current_user.department_code)
    if not (is_public or is_in_my_dept):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이 노하우를 삭제할 권한이 없습니다.")

    log_to_delete.is_deleted = True
    log_to_delete.deleted_at = func.now()
    db.commit()

@router.patch(
    "/{knowledge_id}",
    response_model=KnowledgeUpdateResponse,
    summary="지식 베이스 항목 수정",
)
def update_knowledge(
    knowledge_id: int,
    # Form data for updates
    title: Optional[str] = Form(None, description="새 제목"),
    category_code: Optional[str] = Form(None, description="새 카테고리 코드"),
    scope_code: Optional[str] = Form(None, description="새 공개 범위 코드"),
    summary: Optional[str] = Form(None, description="새 개요"),
    warning_note: Optional[str] = Form(None, description="새 주의사항"),
    # Form data for attachment management
    deleted_attachment_ids: List[int] = Form([], description="삭제할 첨부파일 ID 목록"),
    # New files
    files: List[UploadFile] = File([], description="새로 추가할 첨부파일 목록"),
    # Dependencies
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    기존 지식 베이스 항목을 수정합니다.
    - 텍스트 정보 (제목, 카테고리 등)를 수정할 수 있습니다.
    - 기존 첨부파일을 삭제하거나 새로운 파일을 추가할 수 있습니다.
    - **multipart/form-data** 형식으로 요청해야 합니다.
    """
    # 1. 수정할 지식 카드 조회 (동시 수정을 방지하기 위해 비관적 잠금 사용)
    knowledge_to_update = db.query(Knowledge).filter(Knowledge.knowledge_id == knowledge_id).with_for_update().first()
    if not knowledge_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수정할 지식 카드를 찾을 수 없습니다.")

    # 2. 수정 권한 확인 (작성자 또는 관리자만 가능)
    is_admin = current_user.system_role_code == '02'
    is_creator = str(knowledge_to_update.created_by) == str(current_user.user_id)
    if not (is_admin or is_creator):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이 지식 카드를 수정할 권한이 없습니다.")

    # 3. 텍스트 필드 업데이트
    update_data = {
        "title": title, "category_code": category_code, "scope_code": scope_code,
        "summary": summary, "warning_note": warning_note,
    }
    for key, value in update_data.items():
        if value is not None:
            setattr(knowledge_to_update, key, value)

    # 4. 첨부파일 삭제 처리 (소프트 삭제)
    if deleted_attachment_ids:
        db.query(KnowledgeAttachment).filter(
            KnowledgeAttachment.knowledge_id == knowledge_id,
            KnowledgeAttachment.attachment_id.in_(deleted_attachment_ids)
        ).update({"is_deleted": True, "deleted_at": func.now()}, synchronize_session=False)

    # 5. 새 파일 업로드 처리
    if files:
        for file in files:
            if file.filename:
                file_url = upload_file_to_s3(file, path_prefix="knowledge")
                new_attachment = KnowledgeAttachment(
                    knowledge_id=knowledge_id, file_name=file.filename, file_url=file_url, uploaded_by=current_user.user_id,
                )
                db.add(new_attachment)

    # 6. DB에 최종 커밋 및 응답 반환
    knowledge_to_update.updated_by = current_user.user_id
    db.commit()

    return KnowledgeUpdateResponse(knowledge_id=knowledge_id, message="지식 카드가 성공적으로 수정되었습니다.")