from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.petition import Petition
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.department import Department

router = APIRouter()

# --- 상수 및 맵 ---

STATUS_MAP = {
    "01": "대기중",
    "02": "확인중",
    "03": "처리중",
    "04": "완료",
}

ROLE_NAME_MAP = {
    "01": "주관",
    "02": "협력",
}

STAGE_NAME_MAP = {
    "01": "저장",
    "02": "승인완료",
}

# --- Pydantic 스키마 ---

class MyPetitionSummary(BaseModel):
    total: int
    waiting: int
    checked: int
    inProgress: int
    completed: int

class UrgentPetitionItem(BaseModel):
    complaintId: int
    title: str
    dueDate: Optional[str]
    dDay: int

class RecentPetitionItem(BaseModel):
    complaintId: int
    receivedAt: Optional[str]
    dueDate: Optional[str]
    title: str
    statusName: Optional[str]

class MyProjectItem(BaseModel):
    projectId: int
    name: str
    departmentName: Optional[str]
    roleName: Optional[str]
    stageName: Optional[str]

class AnnouncementItem(BaseModel):
    id: int
    category: str
    title: str
    date: str

class HomeDashboardResponse(BaseModel):
    myPetitionSummary: MyPetitionSummary
    announcements: List[AnnouncementItem]
    urgentPetitions: List[UrgentPetitionItem]
    recentPetitions: List[RecentPetitionItem]
    myProjects: List[MyProjectItem]

# --- 엔드포인트 ---

@router.get(
    "",
    response_model=HomeDashboardResponse,
    summary="사용자 홈 대시보드 데이터 조회",
)
def get_home_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    일반 사용자의 홈 화면에 필요한 데이터를 종합하여 반환합니다.
    """
    # 1. 내 민원 현황 (이번 달)
    today = date.today()
    first_day_of_month = today.replace(day=1)

    my_petitions_this_month_query = db.query(Petition).filter(
        Petition.assignee_user_id == current_user.user_id,
        Petition.received_at >= first_day_of_month,
    )

    total = my_petitions_this_month_query.count()
    waiting = my_petitions_this_month_query.filter(Petition.status_code == "01").count()
    checked = my_petitions_this_month_query.filter(Petition.status_code == "02").count()
    in_progress = my_petitions_this_month_query.filter(Petition.status_code == "03").count()
    completed = my_petitions_this_month_query.filter(Petition.status_code == "04").count()

    my_petition_summary = MyPetitionSummary(total=total, waiting=waiting, checked=checked, inProgress=in_progress, completed=completed)

    # 2. 공지사항 (추후 구현)
    announcements = []

    # 3. 긴급 민원 (D-3 이내, 최대 5개)
    three_days_later = today + timedelta(days=3)
    urgent_petitions_results = db.query(Petition).filter(
        Petition.assignee_user_id == current_user.user_id,
        Petition.status_code != "04",
        Petition.due_date != None,
        Petition.due_date >= today,
        Petition.due_date <= three_days_later,
    ).order_by(Petition.due_date.asc()).limit(5).all()

    urgent_petitions = [UrgentPetitionItem(complaintId=p.petition_id, title=p.title, dueDate=p.due_date.isoformat() if p.due_date else None, dDay=(p.due_date - today).days) for p in urgent_petitions_results]

    # 4. 최근 접수 민원 (최신 3개)
    recent_petitions_results = db.query(Petition).filter(Petition.assignee_user_id == current_user.user_id).order_by(Petition.received_at.desc()).limit(3).all()
    recent_petitions = [RecentPetitionItem(complaintId=p.petition_id, receivedAt=p.received_at.isoformat() if p.received_at else None, dueDate=p.due_date.isoformat() if p.due_date else None, title=p.title, statusName=STATUS_MAP.get(p.status_code)) for p in recent_petitions_results]

    # 5. 내 사업/프로젝트 목록 (최신 5개)
    user_project_ids_query = db.query(ProjectMember.project_id).filter(ProjectMember.user_id == current_user.user_id).subquery()

    my_projects_results = db.query(
        Project,
        Department.name.label("department_name"),
        ProjectMember.role_code
    ).join(
        user_project_ids_query, Project.project_id == user_project_ids_query.c.project_id
    ).join(
        ProjectMember,
        (Project.project_id == ProjectMember.project_id) & (ProjectMember.user_id == current_user.user_id)
    ).outerjoin(
        Department, Project.department_code == Department.department_code
    ).order_by(Project.created_at.desc()).limit(5).all()

    my_projects = [MyProjectItem(projectId=p.project_id, name=p.name, departmentName=dept_name, roleName=ROLE_NAME_MAP.get(role_code), stageName=STAGE_NAME_MAP.get(p.stage_code)) for p, dept_name, role_code in my_projects_results]

    return HomeDashboardResponse(
        myPetitionSummary=my_petition_summary,
        announcements=announcements,
        urgentPetitions=urgent_petitions,
        recentPetitions=recent_petitions,
        myProjects=my_projects,
    )