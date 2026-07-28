from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.db.session import get_db
from app.models.department import Department
from app.models.user import User
from app.api.routers.auth import get_current_user

router = APIRouter()

# 직책 코드와 이름 매핑 (common_code 테이블 기반)
POSITION_MAP = {
    "01": "부장",
    "02": "팀장",
    "03": "주무관",
}

class DepartmentResponse(BaseModel):
    """부서 정보 응답 모델"""
    code: str
    name: str

class MemberResponse(BaseModel):
    """조직도 구성원 응답 모델"""
    userId: str
    name: str
    positionCode: str | None
    positionName: str | None

@router.get(
    "/",
    response_model=List[DepartmentResponse],
    summary="부서 목록 조회"
)
def get_all_departments(db: Session = Depends(get_db)):
    """
    시스템에 등록된 모든 부서 목록을 조회합니다.
    로그인 페이지의 드롭다운 메뉴에 사용됩니다.
    """
    departments = db.query(Department.department_code.label("code"), Department.name.label("name")) \
        .order_by(Department.department_code).all()
    return departments

@router.get(
    "/{department_code}/members",
    response_model=List[MemberResponse],
    summary="특정 부서의 조직원 목록 조회 (조직도용)",
    dependencies=[Depends(get_current_user)]
)
def get_department_members(department_code: str, db: Session = Depends(get_db)):
    """
    특정 부서에 속한 모든 조직원의 목록을 직책 순으로 정렬하여 반환합니다.
    프론트엔드에서 조직도를 그리는 데 사용됩니다.
    """
    # 1. 부서 존재 여부 확인
    department = db.query(Department).filter(Department.department_code == department_code).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="요청한 부서를 찾을 수 없습니다."
        )

    # 2. 해당 부서의 모든 조직원 조회
    members_from_db = db.query(User).filter(User.department_code == department_code).all()

    # 3. 응답 데이터 형식으로 변환
    member_list = [
        MemberResponse(
            userId=str(member.user_id),
            name=member.name,
            positionCode=member.position_code,
            positionName=POSITION_MAP.get(member.position_code)
        ) for member in members_from_db
    ]
    
    # 4. 직책(부장 > 팀장 > 주무관) 순으로 정렬
    member_list.sort(key=lambda x: x.positionCode or '99')

    return member_list