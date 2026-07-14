from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.models.department import Department
from app.api.routers.auth import get_current_user

# --- Pydantic 스키마 ---

class UserSearchResult(BaseModel):
    userId: str
    name: str
    positionName: str | None
    departmentName: str | None

# --- 라우터 ---

router = APIRouter()

# --- 직급 코드 → 이름 변환 ---
POSITION_MAP = {
    "01": "부장",
    "02": "팀장",
    "03": "주무관",
}

@router.get(
    "/search",
    response_model=list[UserSearchResult],
    summary="모든 유저 목록 조회 및 검색",
)
def search_users(
    scope: str = Query(..., description="검색 범위: dept(같은 과) | all(전체 부서)"),
    departmentCode: Optional[str] = Query(None, description="부서 코드 필터 (scope=all일 때)"),
    keyword: Optional[str] = Query(None, description="이름 또는 사번 검색어"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(User, Department).outerjoin(
        Department, User.department_code == Department.department_code
    )

    # scope 처리
    if scope == "dept":
        query = query.filter(User.department_code == current_user.department_code)
    elif scope == "all" and departmentCode:
        query = query.filter(User.department_code == departmentCode)

    # 키워드 검색
    if keyword:
        query = query.filter(
            User.name.contains(keyword) | User.user_id.contains(keyword)
        )

    results = query.all()

    return [
        UserSearchResult(
            userId=str(u.user_id),
            name=u.name,
            positionName=POSITION_MAP.get(u.position_code),
            departmentName=dept.name if dept else None,
        )
        for u, dept in results
    ]