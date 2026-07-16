from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.db.session import get_db
from app.models.user import User
from app.models.task import Task
from app.api.routers.auth import get_current_user
from app.models.task_assignee import TaskAssignee

router = APIRouter()

# 민원처리 페이지
class MyTaskResponse(BaseModel):
    """담당 업무 응답 모델"""
    taskId: int
    name: str

@router.get(
    "/my-tasks",
    response_model=List[MyTaskResponse],
    summary="현재 사용자의 담당 업무 목록 조회",
    dependencies=[Depends(get_current_user)]
)
def get_my_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자가 담당자로 배정된 업무(Task) 목록을 조회합니다.
    """
    # 1. task_assignee 테이블에서 현재 사용자의 task_id 목록을 조회
    assigned_task_ids_query = db.query(TaskAssignee.task_id)\
        .filter(TaskAssignee.user_id == current_user.user_id)

    # 2. 해당 task_id 목록을 사용하여 Task 테이블에서 업무 정보 조회
    my_tasks = db.query(Task).filter(Task.task_id.in_(assigned_task_ids_query)).order_by(Task.name).all()

    # 3. 응답 모델에 맞게 데이터 변환
    return [MyTaskResponse(taskId=task.task_id, name=task.name) for task in my_tasks]

# 부서관리 페이지
# API 1번: 내 부서 Task 목록 조회

class AssigneeItem(BaseModel):
    userId: int
    name: str

class TaskListItem(BaseModel):
    taskId: int
    name: str
    assignees: List[AssigneeItem]

@router.get(
    "",
    response_model=List[TaskListItem],
    summary="내 부서 Task 목록 조회",
)
def get_department_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = db.query(Task).filter(
        Task.department_code == current_user.department_code
    ).all()

    result = []
    for task in tasks:
        assignee_rows = (
            db.query(TaskAssignee, User)
            .join(User, TaskAssignee.user_id == User.user_id)
            .filter(TaskAssignee.task_id == task.task_id)
            .all()
        )
        assignees = [
            AssigneeItem(userId=int(u.user_id), name=u.name)
            for _, u in assignee_rows
        ]
        result.append(TaskListItem(
            taskId=task.task_id,
            name=task.name,
            assignees=assignees,
        ))

    return result