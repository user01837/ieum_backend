from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.db.session import get_db
from app.models.department import Department

router = APIRouter()

class DepartmentResponse(BaseModel):
    """부서 정보 응답 모델"""
    code: str
    name: str

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
    departments = db.query(Department.department_code.label("code"), Department.name.label("name")).order_by(Department.department_code).all()
    return departments