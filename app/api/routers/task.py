from fastapi import APIRouter, Depends, status, HTTPException
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
# API 1: 내 부서 Task 목록 조회
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

# 부서관리 페이지
class TaskCreateRequest(BaseModel):
    name: str

class TaskCreateResponse(BaseModel):
    taskId: int
    name: str

# API 2번: 새 Task 생성
@router.post(
    "",
    response_model=TaskCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="새 Task 생성",
)
def create_task(
    body: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = Task(
        name=body.name,
        department_code=current_user.department_code,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return TaskCreateResponse(taskId=task.task_id, name=task.name)

# 부서관리 페이지
# 3. Task 삭제
@router.delete(
    "/{taskId}",
    status_code=status.HTTP_200_OK,
    summary="Task 삭제",
)
def delete_task(
    taskId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.task_id == taskId).first()
    if not task:
        raise HTTPException(status_code=404, detail="존재하지 않는 Task입니다.")

    db.query(TaskAssignee).filter(TaskAssignee.task_id == taskId).delete(synchronize_session=False)
    db.delete(task)
    db.commit()

class AssigneeRequest(BaseModel):
    userId: int

# 부서관리 페이지
# 4. 담당자 지정
@router.post(
    "/{taskId}/assignees",
    status_code=status.HTTP_200_OK,
    summary="담당자 지정",
)
def add_assignee(
    taskId: int,
    body: AssigneeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.task_id == taskId).first()
    if not task:
        raise HTTPException(status_code=404, detail="존재하지 않는 Task입니다.")

    user = db.query(User).filter(User.user_id == str(body.userId)).first()
    if not user:
        raise HTTPException(status_code=404, detail="존재하지 않는 유저입니다.")

    existing = db.query(TaskAssignee).filter(
        TaskAssignee.task_id == taskId,
        TaskAssignee.user_id == str(body.userId),
    ).first()
    if existing:
        return

    assignee = TaskAssignee(task_id=taskId, user_id=str(body.userId))
    db.add(assignee)
    db.commit()

# 부서관리 페이지
# 5. 담당자 해제
@router.delete(
    "/{taskId}/assignees/{userId}",
    status_code=status.HTTP_200_OK,
    summary="담당자 해제",
)
def remove_assignee(
    taskId: int,
    userId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignee = db.query(TaskAssignee).filter(
        TaskAssignee.task_id == taskId,
        TaskAssignee.user_id == str(userId),
    ).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="존재하지 않는 담당자입니다.")

    db.delete(assignee)
    db.commit()

