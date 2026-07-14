import math
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, case
from pydantic import BaseModel
from typing import List, Optional

from app.db.session import get_db
from app.models.petition import Petition
from app.models.user import User
from app.models.task import Task
from app.models.department import Department
from app.models.task_assignee import TaskAssignee
from app.api.routers.auth import get_current_user

# --- 상수 및 맵 ---

STATUS_MAP = {
    "01": "대기중",
    "02": "처리중",
    "03": "완료",
}

# --- Pydantic 스키마 ---

class PetitionContent(BaseModel):
    complaintId: int
    title: str
    statusName: str | None
    taskName: str | None
    assigneeName: str | None
    receivedAt: str | None
    dueDate: str | None
    answeredAt: str | None
    departmentCode: str | None
    departmentName: str | None

class PaginatedPetitionResponse(BaseModel):
    content: List[PetitionContent]
    totalElements: int
    totalPages: int
    page: int
    size: int

# --- 라우터 ---

router = APIRouter()

@router.get(
    "/",
    response_model=PaginatedPetitionResponse,
    summary="민원 목록 조회 (페이지네이션)",
    dependencies=[Depends(get_current_user)]
)
def get_petitions(
    scope: str = Query(..., description="조회 범위: ALL(부서전체) | MY(내 민원) | TASK(업무별) | PREDECESSOR(전임자)"),
    petition_status: str = Query(..., alias="status", description="민원 상태 필터: ALL | 01(대기중) | 02(임시저장) | 03(완료)"),
    page: int = Query(..., description="페이지 번호 (0부터 시작)"),
    size: int = Query(10, description="페이지 크기, 기본값 10"),
    sort: Optional[str] = Query(None, description="정렬 옵션: incomplete_first (미완료 우선) | due_date_impending (처리기한 임박순)"),
    taskId: Optional[int] = Query(None, description="Task 필터 (scope=TASK일 때)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    다양한 조건과 페이지네이션을 통해 민원 목록을 조회합니다.
    """
    # 1. 기본 쿼리 생성 (Petition, Task, User 테이블 조인)
    query = db.query(
        Petition,
        Task.name.label("task_name"),
        User.name.label("assignee_name"),
        Department.name.label("department_name")
    ).outerjoin(
        Task, Petition.task_id == Task.task_id
    ).outerjoin(
        User, Petition.assignee_user_id == User.user_id
    ).outerjoin(
        Department, Petition.department_code == Department.department_code
    )

    # 2. Scope에 따른 필터링
    if scope.upper() == "MY":
        query = query.filter(Petition.assignee_user_id == current_user.user_id)
    elif scope.upper() == "TASK":
        # taskId가 제공된 경우, 해당 업무로 추가 필터링
        if taskId is not None:
            query = query.filter(Petition.task_id == taskId)
        # taskId가 없는 경우, 현재 사용자가 담당하는 모든 업무의 민원을 조회
        else:
            # 1. task_assignee 테이블에서 현재 사용자의 모든 task_id를 조회
            user_task_ids_query = db.query(TaskAssignee.task_id).filter(TaskAssignee.user_id == current_user.user_id)
            # 2. 해당 task_id 목록에 포함되는 민원들만 필터링
            query = query.filter(Petition.task_id.in_(user_task_ids_query))
    elif scope.upper() == "PREDECESSOR":
        if not current_user.predecessor_user_id:
            # 전임자가 없는 경우 빈 목록을 반환
            return PaginatedPetitionResponse(content=[], totalElements=0, totalPages=0, page=page, size=size)
        query = query.filter(Petition.assignee_user_id == current_user.predecessor_user_id)
    # scope == "ALL"은 별도 필터링 없음

    # 보안/개인정보 보호 규칙 적용:
    # 사용자는 기본적으로 (1) 자신에게 할당된 모든 민원 또는 (2) 상태가 '완료'인 모든 민원만 볼 수 있습니다.
    # 이 필터는 사용자가 다른 사람의 '처리중' 또는 '대기중'인 민원을 볼 수 없도록 보장합니다.
    # 이 로직은 scope와 무관하게 모든 민원 조회에 일관되게 적용됩니다.
    query = query.filter(
        or_(
            Petition.assignee_user_id == current_user.user_id, Petition.status_code == "03"
        )
    )
    
    # 3. 상태(status)에 따른 필터링
    if petition_status != "ALL":
        query = query.filter(Petition.status_code == petition_status)

    # 4. 페이지네이션을 위한 전체 개수 조회
    total_elements = query.count()
    total_pages = math.ceil(total_elements / size) if size > 0 else 0

    # 5. 실제 데이터 조회 (정렬 및 페이지네이션 적용)
    if sort == 'incomplete_first':
        # 미완료(status_code != '03') 민원을 우선 정렬하고, 그 다음 최신순으로 정렬
        query = query.order_by((Petition.status_code != '03').desc(), Petition.created_at.desc())
    elif sort == 'due_date_impending':
        # 미완료 민원을 우선하고, 그 안에서 처리기한이 임박한 순(오름차순)으로 정렬합니다.
        # 처리기한이 없는 민원은 각 그룹의 뒤로 보냅니다.
        # MySQL은 `NULLS LAST` 구문을 지원하지 않으므로, `due_date`가 NULL인 경우를
        # 별도로 처리하여 정렬 순서의 뒤로 보냅니다.
        incompleteness_order = case(
            (Petition.status_code != '03', 1),
            else_=2
        )
        # `Petition.due_date.is_(None)`은 due_date가 NULL이면 True(1), 아니면 False(0)를 반환합니다.
        # 따라서 NULL인 항목들이 뒤로 정렬됩니다.
        query = query.order_by(incompleteness_order, Petition.due_date.is_(None), Petition.due_date.asc())
    else:
        # 기본 정렬: 최신순
        query = query.order_by(Petition.created_at.desc())

    results = query.offset(page * size).limit(size).all()

    # 6. 응답 데이터 형식으로 변환
    content = [
        PetitionContent(
            complaintId=p.petition_id,
            title=p.title,
            statusName=STATUS_MAP.get(p.status_code),
            taskName=task_name,
            assigneeName=assignee_name,
            receivedAt=p.received_at.isoformat() if p.received_at else None,
            dueDate=p.due_date.isoformat() if p.due_date else None,
            answeredAt=p.answered_at.isoformat() if p.answered_at else None,
            departmentCode=p.department_code,
            departmentName=department_name,
        ) for p, task_name, assignee_name, department_name in results
    ]

    return PaginatedPetitionResponse(
        content=content,
        totalElements=total_elements,
        totalPages=total_pages,
        page=page,
        size=size,
    )