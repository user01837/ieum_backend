import traceback
import math
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, case
from pydantic import BaseModel
from pydantic import Field
from typing import Optional, List

from app.db.session import get_db
from app.models.user import User
from app.models.department import Department
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from app.models.petition import Petition
from app.models.petition_assignee_history import PetitionAssigneeHistory
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.models.project_member_history import ProjectMemberHistory
from app.api.routers.auth import get_current_user, get_password_hash
from app.core.config import settings

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

class UserCreationRequest(BaseModel):
    userId: str
    name: str
    departmentCode: str
    positionCode: str
    predecessorUserId: Optional[str] = None

class UserCreationResponse(BaseModel):
    userId: str
    name: str
    message: str

class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    departmentCode: Optional[str] = None
    positionCode: Optional[str] = None
    predecessorUserId: Optional[str] = None
    statusCode: Optional[str] = Field(None, description="재직 상태 코드: 01(재직), 02(휴직), 03(퇴직)")

class UserUpdateResponse(BaseModel):
    userId: str
    message: str

class PasswordResetResponse(BaseModel):
    userId: str
    message: str
    temporaryPassword: str

class AdminStatsResponse(BaseModel):
    totalUsers: int
    activeUsers: int
    leaveUsers: int
    resignedUsers: int
    totalDepartments: int

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
    if current_user.system_role_code != '02':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")

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

    if departmentCode:
        query = query.filter(User.department_code == departmentCode)
    if status:
        query = query.filter(User.status_code == status)
    if keyword:
        query = query.filter(User.name.contains(keyword) | User.user_id.contains(keyword))

    total_elements = query.count()
    total_pages = math.ceil(total_elements / size) if size > 0 else 0
    results = query.order_by(User.user_id).offset(page * size).limit(size).all()
    user_ids = [u.user_id for u, _, _ in results]

    task_map = {}
    if user_ids:
        task_assignments = db.query(TaskAssignee.user_id, Task.name).join(Task, TaskAssignee.task_id == Task.task_id).filter(TaskAssignee.user_id.in_(user_ids), Task.is_deleted == False).order_by(TaskAssignee.user_id, Task.task_id).all()
        for user_id, task_name in task_assignments:
            if user_id not in task_map:
                task_map[user_id] = []
            task_map[user_id].append(task_name)

    content = []
    for user, dept_name, pred_name in results:
        predecessor_info = PredecessorInfo(userId=str(user.predecessor_user_id), name=pred_name) if user.predecessor_user_id and pred_name else None
        content.append(UserManagementInfo(userId=str(user.user_id), name=user.name, departmentName=dept_name, positionName=POSITION_MAP.get(user.position_code), taskNames=task_map.get(user.user_id, []), predecessor=predecessor_info, statusName=USER_STATUS_MAP.get(user.status_code)))

    return PaginatedUserManagementResponse(content=content, totalElements=total_elements, totalPages=total_pages, page=page, size=size)


@router.post(
    "/users",
    response_model=UserCreationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="신규 직원 생성 (관리자용)",
)
def create_user(
    request: UserCreationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.system_role_code != '02':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")

    existing_user = db.query(User).filter(User.user_id == request.userId).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 존재하는 사번입니다.")

    if request.predecessorUserId:
        predecessor = db.query(User).filter(User.user_id == request.predecessorUserId).first()
        if not predecessor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전임자로 지정된 직원을 찾을 수 없습니다.")

    hashed_password = get_password_hash(settings.DEFAULT_PASSWORD)
    system_role = '02' if request.departmentCode == '09' else '01'

    new_user = User(
        user_id=request.userId, name=request.name, password=hashed_password,
        department_code=request.departmentCode, position_code=request.positionCode,
        predecessor_user_id=request.predecessorUserId, system_role_code=system_role,
        status_code='01', must_change_password=True
    )

    db.add(new_user)
    db.flush()

    # --- 전임자 지정 시 사업 승계 로직 ---
    if request.predecessorUserId:
        predecessor_id = request.predecessorUserId
        successor_id = request.userId
        predecessor_user = db.query(User).filter(User.user_id == predecessor_id).first()

        # 1. 전임자가 직접 주관 중인 저장된 사업 → 후임자로 이관
        predecessor_owner_memberships = db.query(ProjectMember).join(
            Project, ProjectMember.project_id == Project.project_id
        ).filter(
            ProjectMember.user_id == predecessor_id,
            ProjectMember.role_code == "01",
            Project.stage_code == "01",
        ).all()

        for pm in predecessor_owner_memberships:
            existing = db.query(ProjectMember).filter(
                ProjectMember.project_id == pm.project_id,
                ProjectMember.user_id == successor_id,
            ).first()
            if existing:
                existing.role_code = "01"
                pm.role_code = "02"
            else:
                pm.user_id = successor_id
            db.add(ProjectMemberHistory(
                project_id=pm.project_id,
                from_user_id=predecessor_id,
                to_user_id=successor_id,
                change_type="01",
            ))

        # 협력 직원으로 참여 중이던 사업도 후임자로 승계
        predecessor_collaborator_memberships = db.query(ProjectMember).join(
            Project, ProjectMember.project_id == Project.project_id
        ).filter(
            ProjectMember.user_id == predecessor_id,
            ProjectMember.role_code == "02",
            Project.stage_code == "01",
        ).all()

        for pm in predecessor_collaborator_memberships:
            pm.user_id = successor_id

            db.add(ProjectMemberHistory(
                project_id=pm.project_id,
                from_user_id=predecessor_id,
                to_user_id=successor_id,
                change_type="01",
            ))

        # 2. 부장한테 임시 이관됐던 저장 사업 → 후임자로 재배정
        _transfer_temporarily_assigned_projects(db, predecessor_id, successor_id)

        # --- 전임자 지정 시 민원 승계 로직 ---
        predecessor_petitions = db.query(Petition).filter(
            Petition.assignee_user_id == predecessor_id,
            Petition.status_code != '04'
        ).all()

        for p in predecessor_petitions:
            p.assignee_user_id = successor_id
            p.status_code = "01"  # 후임자가 확인하도록 '대기중'으로 변경
            db.add(PetitionAssigneeHistory(
                petition_id=p.petition_id,
                from_user_id=predecessor_id,
                to_user_id=successor_id,
                change_type="01",  # 정식 승계
            ))

        # --- 전임자 지정 시 담당 업무(Task) 승계 로직 ---
        predecessor_task_ids = {row.task_id for row in db.query(TaskAssignee.task_id).filter(TaskAssignee.user_id == str(predecessor_id)).all()}
        for task_id in predecessor_task_ids:
            # 이미 배정된 업무는 중복 추가되지 않도록 별도 확인 없이 추가 (PK 위반 시 무시됨)
            db.merge(TaskAssignee(user_id=str(successor_id), task_id=task_id))

    db.commit()

    return UserCreationResponse(userId=str(new_user.user_id), name=new_user.name, message="신규 직원이 성공적으로 생성되었습니다.")

def _transfer_petitions_on_user_change(
    db: Session,
    moving_user: User,
    target_department_code: str
):
    """
    사용자 변경(부서이동, 퇴직 등) 시 미완료 민원을 이관합니다.

    1. 후임자가 있으면 후임자에게 이관합니다.
    2. 후임자가 없으면 대상 부서의 부장에게 임시 이관합니다.
    3. 부장도 없으면 담당자 없음으로 처리합니다.
    """
    moving_user_id = moving_user.user_id

    successor = db.query(User).filter(User.predecessor_user_id == moving_user_id).first()

    incomplete_petitions = db.query(Petition).filter(
        Petition.assignee_user_id == moving_user_id,
        Petition.status_code != '04'
    ).all()

    if not incomplete_petitions:
        return

    if successor:
        successor_id = successor.user_id
        for p in incomplete_petitions:
            p.assignee_user_id = successor_id
            p.status_code = "01"
            db.add(PetitionAssigneeHistory(
                petition_id=p.petition_id,
                from_user_id=moving_user_id,
                to_user_id=successor_id,
                change_type="01",
            ))
    else:
        department_head = db.query(User).filter(
            User.department_code == target_department_code,
            User.position_code == '01'
        ).first()

        target_assignee_id = department_head.user_id if department_head else None

        for p in incomplete_petitions:
            p.assignee_user_id = target_assignee_id
            p.status_code = "01"
            db.add(PetitionAssigneeHistory(
                petition_id=p.petition_id,
                from_user_id=moving_user_id,
                to_user_id=target_assignee_id,
                change_type="02",
            ))

# 사업
def _transfer_temporarily_assigned_projects(
    db: Session,
    predecessor_id: str,
    successor_id: str,
):
    """
    전임자로부터 임시 이관(change_type='02')받은 부장이
    현재도 주관자(role_code='01')인 저장(stage_code='01') 사업
    → 후임자로 정식 이관(change_type='01')
    부서 이동 여부와 무관하게 PROJECT_MEMBER_HISTORY 이력 기반으로 조회
    """
    projects_to_transfer = db.query(ProjectMember, ProjectMemberHistory).join(
        ProjectMemberHistory,
        (ProjectMember.project_id == ProjectMemberHistory.project_id) &
        (ProjectMember.user_id == ProjectMemberHistory.to_user_id)
    ).join(
        Project, ProjectMember.project_id == Project.project_id
    ).filter(
        ProjectMemberHistory.from_user_id == predecessor_id,
        ProjectMemberHistory.change_type == "02",
        ProjectMember.role_code == "01",
        Project.stage_code == "01",
    ).all()

    for pm, history in projects_to_transfer:
        current_manager_id = pm.user_id
        existing = db.query(ProjectMember).filter(
            ProjectMember.project_id == pm.project_id,
            ProjectMember.user_id == successor_id,
        ).first()
        if existing:
            existing.role_code = "01"
            pm.role_code = "02"
        else:
            pm.user_id = successor_id
        db.add(ProjectMemberHistory(
            project_id=pm.project_id,
            from_user_id=current_manager_id,
            to_user_id=successor_id,
            change_type="01",
        ))

@router.patch(
    "/users/{userId}",
    response_model=UserUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="직원 정보 수정 (관리자용)",
)
def update_user(
    userId: str,
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.system_role_code != '02':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")

    user_to_update = db.query(User).filter(User.user_id == userId).with_for_update().first()
    if not user_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수정할 직원을 찾을 수 없습니다.")

    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="수정할 정보가 없습니다.")

    # 부서 변경을 가장 먼저 처리
    if "departmentCode" in update_data and request.departmentCode:
        if user_to_update.department_code != request.departmentCode:
            # 이관 로직을 위해 이전 부서 코드를 저장
            old_department_code = user_to_update.department_code
            moving_user_id = userId
            successor = db.query(User).filter(User.predecessor_user_id == moving_user_id).first()

            # --- 부서 이동에 따른 미완료 민원 이관 로직 ---
            # ★★★ 중요: 민원은 '이전' 부서의 부장에게 이관되어야 합니다.
            _transfer_petitions_on_user_change(db, user_to_update, old_department_code)

            # --- 부서 이동에 따른 미완료 사업 이관 로직 ---
            incomplete_project_memberships = db.query(ProjectMember).join(
                Project, ProjectMember.project_id == Project.project_id
            ).filter(
                ProjectMember.user_id == moving_user_id,
                ProjectMember.role_code == "01",
                Project.stage_code == "01",
            ).all()

            if incomplete_project_memberships:
                if successor:
                    transfer_to_id = successor.user_id
                    transfer_change_type = "01"
                else:
                    old_dept_head = db.query(User).filter( # 기존 부서의 부장
                        User.department_code == user_to_update.department_code,
                        User.position_code == "01"
                    ).first()
                    transfer_to_id = old_dept_head.user_id if old_dept_head else None
                    transfer_change_type = "02"

                if transfer_to_id:
                    for pm in incomplete_project_memberships:
                        existing = db.query(ProjectMember).filter(ProjectMember.project_id == pm.project_id, ProjectMember.user_id == transfer_to_id).first()
                        if existing:
                            existing.role_code = "01"
                            pm.role_code = "02"
                        else:
                            pm.user_id = transfer_to_id
                        db.add(ProjectMemberHistory(project_id=pm.project_id, from_user_id=moving_user_id, to_user_id=transfer_to_id, change_type=transfer_change_type))

            # 기존 담당 업무 초기화
            db.query(TaskAssignee).filter(TaskAssignee.user_id == userId).delete(synchronize_session=False)

            user_to_update.department_code = request.departmentCode
            user_to_update.system_role_code = '02' if request.departmentCode == '09' else '01'

    if "name" in update_data:
        user_to_update.name = request.name

    if "positionCode" in update_data and request.positionCode and request.positionCode not in POSITION_MAP:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 직책 코드입니다.")
    if "positionCode" in update_data:
        user_to_update.position_code = request.positionCode

    if "statusCode" in update_data and request.statusCode and request.statusCode not in USER_STATUS_MAP:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 재직상태 코드입니다.")
    if "statusCode" in update_data:
        # 퇴직 또는 휴직 처리 시 미완료 민원 이관
        if request.statusCode in ['02', '03'] and user_to_update.status_code != request.statusCode:
            _transfer_petitions_on_user_change(db, user_to_update, user_to_update.department_code)

            # 퇴직 또는 휴직 처리 시 미완료 사업 이관
            status_moving_user_id = userId
            status_successor = db.query(User).filter(User.predecessor_user_id == status_moving_user_id).first()

            incomplete_project_memberships = db.query(ProjectMember).join(
                Project, ProjectMember.project_id == Project.project_id
            ).filter(
                ProjectMember.user_id == status_moving_user_id,
                ProjectMember.role_code == "01",
                Project.stage_code == "01",
            ).all()

            if incomplete_project_memberships:
                if status_successor:
                    status_transfer_to_id = status_successor.user_id
                    status_transfer_change_type = "01"
                else:
                    dept_head = db.query(User).filter(
                        User.department_code == user_to_update.department_code,
                        User.position_code == "01"
                    ).first()
                    status_transfer_to_id = dept_head.user_id if dept_head else None
                    status_transfer_change_type = "02"

                if status_transfer_to_id:
                    for pm in incomplete_project_memberships:
                        existing = db.query(ProjectMember).filter(
                            ProjectMember.project_id == pm.project_id,
                            ProjectMember.user_id == status_transfer_to_id
                        ).first()
                        if existing:
                            existing.role_code = "01"
                            pm.role_code = "02"
                        else:
                            pm.user_id = status_transfer_to_id
                        db.add(ProjectMemberHistory(
                            project_id=pm.project_id,
                            from_user_id=status_moving_user_id,
                            to_user_id=status_transfer_to_id,
                            change_type=status_transfer_change_type,
                        ))

        user_to_update.status_code = request.statusCode

    if "predecessorUserId" in update_data:
        predecessor_id = request.predecessorUserId
        if predecessor_id and str(predecessor_id) == str(userId):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="자기 자신을 전임자로 지정할 수 없습니다.")

        if predecessor_id and str(user_to_update.predecessor_user_id) != str(predecessor_id):
            successor_id = userId
            predecessor_user = db.query(User).filter(User.user_id == predecessor_id).first()
            if not predecessor_user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전임자로 지정된 직원을 찾을 수 없습니다.")

            # --- 민원 이관 로직 ---
            petitions_to_transfer_directly = db.query(Petition).filter(
                Petition.assignee_user_id == predecessor_id,
                Petition.status_code != '04'
            ).all()

            for p in petitions_to_transfer_directly:
                p.assignee_user_id = successor_id
                p.status_code = "01"
                db.add(PetitionAssigneeHistory(petition_id=p.petition_id, from_user_id=predecessor_id, to_user_id=successor_id, change_type="01"))

            # 전임자로부터 '임시 배정'(change_type='02')받은 사람에게서 후임자로 클로백한다.
            # 부서이동 시 predecessor_user.department_code는 이미 새 부서로 바뀐 뒤라,
            # "전임자의 현재 부서"를 기준으로 부장을 다시 찾으면 실제로 민원을 임시
            # 배정받은 '이전' 부서의 부장을 찾지 못한다 (_transfer_petitions_on_user_change가
            # 부서이동 시 이전 부서 기준으로 임시 배정하기 때문). 따라서 부장을 다시 추정하지 않고,
            # 이력 테이블에서 "전임자 -> 누군가, 임시배정" 기록을 직접 찾아 그 사람에게서 클로백한다.
            latest_history_subquery = db.query(
                PetitionAssigneeHistory.petition_id,
                func.max(PetitionAssigneeHistory.history_id).label('max_history_id')
            ).group_by(PetitionAssigneeHistory.petition_id).subquery()

            petitions_to_transfer = db.query(Petition).join(
                PetitionAssigneeHistory, Petition.petition_id == PetitionAssigneeHistory.petition_id
            ).join(
                latest_history_subquery,
                (PetitionAssigneeHistory.petition_id == latest_history_subquery.c.petition_id) &
                (PetitionAssigneeHistory.history_id == latest_history_subquery.c.max_history_id)
            ).filter(
                Petition.status_code != '04',
                Petition.assignee_user_id == PetitionAssigneeHistory.to_user_id,
                PetitionAssigneeHistory.from_user_id == predecessor_id,
                PetitionAssigneeHistory.change_type == '02'
            ).all()

            for p in petitions_to_transfer:
                temp_holder_id = p.assignee_user_id
                p.assignee_user_id = successor_id
                p.status_code = "01"
                db.add(PetitionAssigneeHistory(petition_id=p.petition_id, from_user_id=temp_holder_id, to_user_id=successor_id, change_type="01"))

            # --- 사업(Project) 승계 로직 ---
            predecessor_owner_memberships = db.query(ProjectMember).join(
                Project, ProjectMember.project_id == Project.project_id
            ).filter(
                ProjectMember.user_id == predecessor_id,
                ProjectMember.role_code == "01",
                Project.stage_code == "01",
            ).all()

            for pm in predecessor_owner_memberships:
                existing = db.query(ProjectMember).filter(
                    ProjectMember.project_id == pm.project_id,
                    ProjectMember.user_id == successor_id,
                ).first()
                if existing:
                    existing.role_code = "01"
                    pm.role_code = "02"
                else:
                    pm.user_id = successor_id
                db.add(ProjectMemberHistory(project_id=pm.project_id, from_user_id=predecessor_id, to_user_id=successor_id, change_type="01"))

            # 협력 직원으로 참여 중이던 사업도 후임자로 승계
            predecessor_collaborator_memberships = db.query(ProjectMember).join(
                Project, ProjectMember.project_id == Project.project_id
            ).filter(
                ProjectMember.user_id == predecessor_id,
                ProjectMember.role_code == "02",
                Project.stage_code == "01",
            ).all()

            for pm in predecessor_collaborator_memberships:
                pm.user_id = successor_id

                db.add(ProjectMemberHistory(
                    project_id=pm.project_id,
                    from_user_id=predecessor_id,
                    to_user_id=successor_id,
                    change_type="01",
                ))
            
            # 부장한테 임시 이관됐던 저장 사업 → 후임자로 재배정
            _transfer_temporarily_assigned_projects(db, predecessor_id, successor_id)

            # --- 담당 업무(Task) 승계 로직 ---
            predecessor_task_ids = {row.task_id for row in db.query(TaskAssignee.task_id).filter(TaskAssignee.user_id == str(predecessor_id)).all()}
            successor_task_ids = {row.task_id for row in db.query(TaskAssignee.task_id).filter(TaskAssignee.user_id == str(userId)).all()}
            tasks_to_inherit = predecessor_task_ids - successor_task_ids

            for task_id in tasks_to_inherit:
                db.add(TaskAssignee(user_id=str(userId), task_id=task_id))

        user_to_update.predecessor_user_id = predecessor_id

    # 변경사항 저장
    try:
        db.commit()
    except Exception as e:
        traceback.print_exc()
        raise

    return UserUpdateResponse(userId=userId, message="직원 정보가 성공적으로 수정되었습니다.")


@router.post(
    "/users/{userId}/reset-password",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="직원 비밀번호 초기화 (관리자용)",
)
def reset_user_password(
    userId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.system_role_code != '02':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")

    user_to_reset = db.query(User).filter(User.user_id == userId).first()
    if not user_to_reset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="비밀번호를 초기화할 직원을 찾을 수 없습니다.")

    if str(user_to_reset.user_id) == str(current_user.user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="자기 자신의 비밀번호는 '비밀번호 변경' 메뉴를 이용해 변경해야 합니다.")

    hashed_password = get_password_hash(settings.DEFAULT_PASSWORD)
    user_to_reset.password = hashed_password
    user_to_reset.must_change_password = True

    db.commit()

    return PasswordResetResponse(
        userId=userId,
        message="비밀번호가 성공적으로 초기화되었습니다.",
        temporaryPassword=settings.DEFAULT_PASSWORD
    )


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="관리자 대시보드 통계 조회",
)
def get_admin_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.system_role_code != '02':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")

    user_stats = db.query(
        func.count(User.user_id).label("total"),
        func.sum(case((User.status_code == '01', 1), else_=0)).label("active"),
        func.sum(case((User.status_code == '02', 1), else_=0)).label("leave"),
        func.sum(case((User.status_code == '03', 1), else_=0)).label("resigned")
    ).one()

    department_count = db.query(Department).count()

    return AdminStatsResponse(
        totalUsers=user_stats.total or 0,
        activeUsers=user_stats.active or 0,
        leaveUsers=user_stats.leave or 0,
        resignedUsers=user_stats.resigned or 0,
        totalDepartments=department_count
    )