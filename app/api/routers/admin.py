import math
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, aliased
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.models.user import User
from app.models.department import Department
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from app.api.routers.auth import get_current_user

# --- Pydantic 스키마 ---

class PredecessorInfo(BaseModel):
    userId: str
    name: str

class UserManagementInfo(BaseModel):
    userId: str
    name: str
    departmentName: str | None
    positionName: str | None
    taskNames: List[str]
    predecessor: PredecessorInfo | None
    statusName: str | None

class PaginatedUserManagementResponse(BaseModel):
    content: List[UserManagementInfo]
    totalElements: int
    totalPages: int
    page: int
    size: int

# --- 라우터 ---

router = APIRouter()

# --- 코드 → 이름 변환 맵 ---
POSITION_MAP = {
    "01": "부장",
    "02": "팀장",
    "03": "주무관",
}

USER_STATUS_MAP = {
    "01": "재직",
    "02": "휴직",
    "03": "퇴직",
}

@router.get(
    "/users",
    response_model=PaginatedUserManagementResponse,
    summary="직원 목록 조회 (관리자용)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "관리자 권한 필요"},
    }
)
def get_users_for_management(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    departmentCode: Optional[str] = Query(None, alias="departmentCode"),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1),
):
    """
    관리자가 직원을 페이지네이션, 필터, 검색을 통해 조회합니다.
    """
    # 1. 관리자 권한 확인
    if current_user.system_role_code != '02':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )

    # 2. 기본 쿼리 생성
    Predecessor = aliased(User, name='predecessor')
    query = db.query(
        User,
        Department.name.label("department_name"),
        Predecessor.name.label("predecessor_name")
    ).outerjoin(
        Department, User.department_code == Department.department_code
    ).outerjoin(
        Predecessor, User.predecessor_user_id == Predecessor.user_id
    )

    # 3. 필터링
    if departmentCode:
        query = query.filter(User.department_code == departmentCode)
    if status:
        query = query.filter(User.status_code == status)
    if keyword:
        query = query.filter(
            User.name.contains(keyword) | User.user_id.contains(keyword)
        )

    # 4. 페이지네이션을 위한 전체 개수 조회
    total_elements = query.count()
    total_pages = math.ceil(total_elements / size) if size > 0 else 0

    # 5. 정렬 및 페이지네이션 적용하여 직원 목록 조회
    results = query.order_by(User.user_id).offset(page * size).limit(size).all()

    user_ids = [u.user_id for u, _, _ in results]

    # 6. 담당 Task 정보 조회 (N+1 방지)
    task_map = {}
    if user_ids:
        task_assignments = db.query(TaskAssignee.user_id, Task.name).join(Task, TaskAssignee.task_id == Task.task_id).filter(TaskAssignee.user_id.in_(user_ids)).order_by(TaskAssignee.user_id, Task.task_id).all()
        for user_id, task_name in task_assignments:
            if user_id not in task_map:
                task_map[user_id] = []
            task_map[user_id].append(task_name)

    # 7. 응답 데이터 구성
    content = []
    for user, dept_name, pred_name in results:
        predecessor_info = PredecessorInfo(userId=user.predecessor_user_id, name=pred_name) if user.predecessor_user_id and pred_name else None
        content.append(UserManagementInfo(userId=str(user.user_id), name=user.name, departmentName=dept_name, positionName=POSITION_MAP.get(user.position_code), taskNames=task_map.get(user.user_id, []), predecessor=predecessor_info, statusName=USER_STATUS_MAP.get(user.status_code)))

    return PaginatedUserManagementResponse(content=content, totalElements=total_elements, totalPages=total_pages, page=page, size=size)