# 부서관리 페이지 - 대시보드

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta

from app.db.session import get_db
from app.models.petition import Petition
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from app.models.user import User
from app.api.routers.auth import get_current_user

router = APIRouter()

# 대시보드 - 이번달 민원 건수
class ComplaintSummaryResponse(BaseModel):
    total: int
    waiting: int
    checked: int
    inProgress: int
    completed: int

@router.get(
    "/complaints/summary",
    response_model=ComplaintSummaryResponse,
    summary="이번달 민원 건수",
)
def get_complaints_summary(
    department_code: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_dept = department_code or current_user.department_code
    today = date.today()
    first_day = today.replace(day=1)

    query = db.query(Petition).filter(
        Petition.department_code == target_dept,
        Petition.received_at >= first_day,
    )

    total = query.count()
    waiting = query.filter(Petition.status_code == "01").count()
    checked = query.filter(Petition.status_code == "02").count()
    in_progress = query.filter(Petition.status_code == "03").count()
    completed = query.filter(Petition.status_code == "04").count()

    return ComplaintSummaryResponse(
        total=total,
        waiting=waiting,
        checked=checked,
        inProgress=in_progress,
        completed=completed,
    )


# 처리기한 임박 목록
class DueSoonItem(BaseModel):
    complaintId: int
    title: str
    receivedAt: Optional[str]
    assigneeName: Optional[str]
    dDay: int

@router.get(
    "/complaints/due-soon",
    response_model=List[DueSoonItem],
    summary="처리기한 임박(D-3 이내) 및 지연 민원 목록",
)
def get_due_soon_complaints(
    department_code: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_dept = department_code or current_user.department_code
    today = date.today()
    three_days_later = today + timedelta(days=3)

    results = (
        db.query(Petition, User)
        .outerjoin(User, Petition.assignee_user_id == User.user_id)
        .filter(
            Petition.department_code == target_dept,
            Petition.status_code != "04",
            Petition.due_date != None,
            Petition.due_date <= three_days_later,
        )
        .order_by(Petition.due_date.asc())
        .all()
    )

    items = []
    for p, assignee in results:
        d_day = (p.due_date - today).days
        items.append(DueSoonItem(
            complaintId=p.petition_id,
            title=p.title,
            receivedAt=p.received_at.isoformat() if p.received_at else None,
            assigneeName=assignee.name if assignee else None,
            dDay=d_day,
        ))

    return items


# Task 현황
class TaskSummaryResponse(BaseModel):
    totalTasks: int
    unassignedTasks: int
    membersWithoutTask: int

@router.get(
    "/tasks/summary",
    response_model=TaskSummaryResponse,
    summary="Task 현황",
)
def get_tasks_summary(
    department_code: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_dept = department_code or current_user.department_code

    total_tasks = db.query(Task).filter(
        Task.department_code == target_dept,
        Task.is_deleted == False,
    ).count()

    assigned_task_ids = db.query(TaskAssignee.task_id).join(
        Task, TaskAssignee.task_id == Task.task_id
    ).filter(
        Task.department_code == target_dept,
        Task.is_deleted == False,
    ).distinct().subquery()

    unassigned_tasks = db.query(Task).filter(
        Task.department_code == target_dept,
        Task.is_deleted == False,
        Task.task_id.notin_(assigned_task_ids),
    ).count()

    dept_members = db.query(User).filter(
        User.department_code == target_dept
    ).all()

    assigned_user_ids = {
        row.user_id for row in db.query(TaskAssignee.user_id).join(
            Task, TaskAssignee.task_id == Task.task_id
        ).filter(
            Task.department_code == target_dept,
            Task.is_deleted == False,
        ).all()
    }

    members_without_task = sum(
        1 for m in dept_members if m.user_id not in assigned_user_ids
    )

    return TaskSummaryResponse(
        totalTasks=total_tasks,
        unassignedTasks=unassigned_tasks,
        membersWithoutTask=members_without_task,
    )