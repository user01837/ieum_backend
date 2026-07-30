from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, and_
from pydantic import BaseModel
from typing import List, Optional, Union
from datetime import date, timedelta

from app.db.session import get_db
from app.api.routers.auth import get_current_user
from app.models.user import User
from app.models.petition import Petition
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.department import Department
from app.models.announcement import Announcement
from app.models.knowledge import Knowledge

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

USER_STATUS_MAP = {
    "01": "재직",
    "02": "휴직",
    "03": "퇴직",
}

# --- Pydantic 스키마 (일반 사용자) ---

class MyPetitionSummary(BaseModel):
    total: int
    waiting: int
    checked: int
    inProgress: int
    completed: int
    delayed: int

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

# --- Pydantic 스키마 (관리자) ---

class AdminDashboardStats(BaseModel):
    totalUsers: int
    activeDepartments: int

class EmployeeStatusSummary(BaseModel):
    active: int
    onLeave: int
    resigned: int

class MonthlyPetitionSummary(BaseModel):
    total: int
    percentageChange: float

class DepartmentPetitionStatus(BaseModel):
    departmentCode: str
    departmentName: str
    waiting: int
    checked: int
    inProgress: int
    completed: int
    delayed: int

class DepartmentKnowledgeStatus(BaseModel):
    departmentName: str
    count: int

class KnowledgeSummary(BaseModel):
    total: int
    byDepartment: List[DepartmentKnowledgeStatus]

class SimpleAnnouncement(BaseModel):
    title: str
    date: str

class DelayedPetition(BaseModel):
    departmentName: Optional[str]
    assigneeName: Optional[str]
    title: str
    dueDate: Optional[str]

class RecentUser(BaseModel):
    userId: str
    name: str
    departmentName: Optional[str]
    statusName: Optional[str]

class AdminDashboardResponse(BaseModel):
    stats: AdminDashboardStats
    employeeStatus: EmployeeStatusSummary
    monthlyPetitionSummary: MonthlyPetitionSummary
    totalDelayedOrUrgentPetitions: int
    departmentPetitionStatus: List[DepartmentPetitionStatus]
    knowledgeSummary: KnowledgeSummary
    announcements: List[SimpleAnnouncement]
    delayedOrUrgentPetitions: List[DelayedPetition]
    recentUsers: List[RecentUser]


# --- 엔드포인트 ---

@router.get(
    "",
    response_model=Union[HomeDashboardResponse, AdminDashboardResponse],
    summary="사용자 홈 대시보드 데이터 조회",
)
def get_home_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    사용자의 역할(일반/관리자)에 따라 홈 화면에 필요한 데이터를 종합하여 반환합니다.
    """
    today = date.today()

    # 관리자 대시보드
    if current_user.system_role_code == '02':
        # 1. 직원 및 부서 통계
        user_stats = db.query(
            func.count(User.user_id).label("total"),
            func.sum(case((User.status_code == '01', 1), else_=0)).label("active"),
            func.sum(case((User.status_code == '02', 1), else_=0)).label("leave"),
            func.sum(case((User.status_code == '03', 1), else_=0)).label("resigned")
        ).one()
        department_count = db.query(Department).filter(Department.department_code != '09').count()

        stats = AdminDashboardStats(
            totalUsers=user_stats.total or 0,
            activeDepartments=department_count
        )
        employee_status = EmployeeStatusSummary(
            active=user_stats.active or 0,
            onLeave=user_stats.leave or 0,
            resigned=user_stats.resigned or 0
        )

        # 2. 금월 전체 민원 및 전월 대비 증감률
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)

        this_month_petitions_count = db.query(Petition).filter(Petition.received_at >= first_day_this_month).count()
        last_month_petitions_count = db.query(Petition).filter(
            Petition.received_at >= first_day_last_month,
            Petition.received_at < first_day_this_month
        ).count()

        percentage_change = 0.0
        if last_month_petitions_count > 0:
            percentage_change = round(((this_month_petitions_count - last_month_petitions_count) / last_month_petitions_count) * 100, 1)
        
        monthly_petition_summary = MonthlyPetitionSummary(
            total=this_month_petitions_count,
            percentageChange=percentage_change
        )

        # 3. 처리 지연/임박 민원 (개수 및 목록)
        three_days_from_now = today + timedelta(days=3)
        
        total_delayed_or_urgent_petitions = db.query(Petition).filter(
            Petition.status_code != '04',
            Petition.due_date != None,
            Petition.due_date <= three_days_from_now
        ).count()

        delayed_urgent_list_results = db.query(
            Petition,
            Department.name.label("department_name"),
            User.name.label("assignee_name")
        ).outerjoin(
            Department, Petition.department_code == Department.department_code
        ).outerjoin(
            User, Petition.assignee_user_id == User.user_id
        ).filter(
            Petition.status_code != '04',
            Petition.due_date != None,
            Petition.due_date <= three_days_from_now
        ).order_by(Petition.due_date.asc()).limit(5).all()

        delayed_or_urgent_petitions_list = [
            DelayedPetition(
                departmentName=dept_name,
                assigneeName=assignee_name,
                title=p.title,
                dueDate=p.due_date.isoformat() if p.due_date else None
            ) for p, dept_name, assignee_name in delayed_urgent_list_results
        ]

        # 4. 부서별 민원 처리 현황 (월별)
        all_departments = db.query(Department).filter(Department.department_code != '09').all()
        department_map = {d.department_code: {"departmentName": d.name, "waiting": 0, "checked": 0, "inProgress": 0, "completed": 0, "delayed": 0} for d in all_departments}

        department_petition_stats = db.query(
            Petition.department_code,
            func.sum(case((Petition.status_code == '01', 1), else_=0)).label("waiting"),
            func.sum(case((Petition.status_code == '02', 1), else_=0)).label("checked"),
            func.sum(case((Petition.status_code == '03', 1), else_=0)).label("in_progress"),
            func.sum(case((Petition.status_code == '04', 1), else_=0)).label("completed"),
            func.sum(case(
                (and_(Petition.status_code != '04', Petition.due_date != None, Petition.due_date < today), 1), else_=0
            )).label("delayed")
        ).filter(
            Petition.received_at >= first_day_this_month,
            Petition.department_code.in_(department_map.keys())
        ).group_by(Petition.department_code).all()

        for row in department_petition_stats:
            if row.department_code in department_map:
                department_map[row.department_code]['waiting'] = row.waiting
                department_map[row.department_code]['checked'] = row.checked
                department_map[row.department_code]['inProgress'] = row.in_progress
                department_map[row.department_code]['completed'] = row.completed
                department_map[row.department_code]['delayed'] = row.delayed

        department_petition_status_list = [DepartmentPetitionStatus(departmentCode=code, **data) for code, data in department_map.items()]

        # 5. 지식베이스 부서별 등록 현황
        dept_code_to_name = {d.department_code: d.name for d in all_departments}
        knowledge_map = {code: 0 for code in dept_code_to_name.keys()}
        
        knowledge_stats = db.query(
            Knowledge.department_code,
            func.count(Knowledge.knowledge_id).label("count")
        ).filter(
            Knowledge.is_deleted == False,
            Knowledge.department_code.in_(dept_code_to_name.keys())
        ).group_by(Knowledge.department_code).all()

        for row in knowledge_stats:
            if row.department_code in knowledge_map:
                knowledge_map[row.department_code] = row.count

        knowledge_by_dept_list = [DepartmentKnowledgeStatus(departmentName=dept_code_to_name[code], count=count) for code, count in knowledge_map.items()]
        total_knowledge = sum(knowledge_map.values())
        knowledge_summary = KnowledgeSummary(total=total_knowledge, byDepartment=knowledge_by_dept_list)

        # 6. 공지사항
        announcement_results = db.query(Announcement).filter(Announcement.is_deleted == False).order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).limit(5).all()
        announcements_list = [SimpleAnnouncement(title=a.title, date=a.created_at.date().isoformat()) for a in announcement_results]

        # 7. 최근 등록/수정 직원 현황
        recent_users_results = db.query(User, Department.name.label("department_name")).outerjoin(Department, User.department_code == Department.department_code).order_by(User.updated_at.desc()).limit(5).all()
        recent_users_list = [RecentUser(userId=str(user.user_id), name=user.name, departmentName=dept_name, statusName=USER_STATUS_MAP.get(user.status_code)) for user, dept_name in recent_users_results]

        # 8. 최종 응답 반환
        return AdminDashboardResponse(
            stats=stats,
            employeeStatus=employee_status,
            monthlyPetitionSummary=monthly_petition_summary,
            totalDelayedOrUrgentPetitions=total_delayed_or_urgent_petitions,
            departmentPetitionStatus=department_petition_status_list,
            knowledgeSummary=knowledge_summary,
            announcements=announcements_list,
            delayedOrUrgentPetitions=delayed_or_urgent_petitions_list,
            recentUsers=recent_users_list,
        )

    # 일반 사용자 대시보드
    else:
        # 1. 내 민원 현황 (이번 달)
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

        delayed = my_petitions_this_month_query.filter(
            Petition.status_code != "04",
            Petition.due_date != None,
            Petition.due_date < today,
        ).count()


        my_petition_summary = MyPetitionSummary(total=total, waiting=waiting, checked=checked, inProgress=in_progress, completed=completed, delayed=delayed)
 
        # 2. 공지사항 (최근 4개)
        announcement_results = db.query(Announcement).filter(
            Announcement.is_deleted == False
        ).order_by(
            Announcement.is_pinned.desc(),
            Announcement.created_at.desc()
        ).limit(4).all()

        announcements = [
            AnnouncementItem(
                id=a.announcement_id,
                category="공지",
                title=a.title,
                date=a.created_at.date().isoformat()) for a in announcement_results
        ]

        # 3. 긴급 민원 (D-3 이내, 최대 5개)
        three_days_later = today + timedelta(days=3)
        urgent_petitions_results = db.query(Petition).filter(
            Petition.assignee_user_id == current_user.user_id,
            Petition.status_code != "04",
            Petition.due_date != None,
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