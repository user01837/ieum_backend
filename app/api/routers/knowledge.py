from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, or_, and_
from typing import List, Optional

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.task import Task
from app.models.knowledge import Knowledge, KnowledgeLog, KnowledgeLogTag, KnowledgeTag
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
        logs=log_details
    )