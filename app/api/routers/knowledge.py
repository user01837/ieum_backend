from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import List, Optional

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.task import Task
from app.models.knowledge import Knowledge, KnowledgeLog
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