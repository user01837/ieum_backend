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
        predecessor_info = PredecessorInfo(userId=str(user.predecessor_user_id), name=pred_name) if user.predecessor_user_id and pred_name else None
        content.append(UserManagementInfo(userId=str(user.user_id), name=user.name, departmentName=dept_name, positionName=POSITION_MAP.get(user.position_code), taskNames=task_map.get(user.user_id, []), predecessor=predecessor_info, statusName=USER_STATUS_MAP.get(user.status_code)))

    return PaginatedUserManagementResponse(content=content, totalElements=total_elements, totalPages=total_pages, page=page, size=size)

@router.post(
    "/users",
    response_model=UserCreationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="신규 직원 생성 (관리자용)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "관리자 권한 필요"},
        status.HTTP_404_NOT_FOUND: {"description": "전임자로 지정된 직원을 찾을 수 없음"},
        status.HTTP_409_CONFLICT: {"description": "이미 존재하는 사번"},
    }
)
def create_user(
    request: UserCreationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    관리자가 신규 직원을 시스템에 등록합니다.

    - **userId**: 사번
    - **name**: 이름
    - **departmentCode**: 부서 코드
    - **positionCode**: 직책 코드
    - **predecessorUserId**: (선택) 전임자 사번
    """
    # 1. 관리자 권한 확인
    if current_user.system_role_code != '02':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )

    # 2. 사번 중복 확인
    existing_user = db.query(User).filter(User.user_id == request.userId).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 존재하는 사번입니다."
        )

    # 3. 전임자 존재 여부 확인
    if request.predecessorUserId:
        predecessor = db.query(User).filter(User.user_id == request.predecessorUserId).first()
        if not predecessor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="전임자로 지정된 직원을 찾을 수 없습니다."
            )

    # 4. 비밀번호 해시 생성
    hashed_password = get_password_hash(settings.DEFAULT_PASSWORD)

    # 5. 시스템 역할 결정 (부서코드 '09'는 관리자)
    system_role = '02' if request.departmentCode == '09' else '01'

    # 6. 새 사용자 객체 생성
    new_user = User(
        user_id=request.userId, name=request.name, password=hashed_password,
        department_code=request.departmentCode, position_code=request.positionCode,
        predecessor_user_id=request.predecessorUserId, system_role_code=system_role,
        status_code='01', must_change_password=True
    )

    db.add(new_user)
    db.commit()

    return UserCreationResponse(userId=str(new_user.user_id), name=new_user.name, message="신규 직원이 성공적으로 생성되었습니다.")

@router.patch(
    "/users/{userId}",
    response_model=UserUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="직원 정보 수정 (관리자용)",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "잘못된 요청 데이터"},
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "관리자 권한 필요"},
        status.HTTP_404_NOT_FOUND: {"description": "직원, 부서 또는 전임자를 찾을 수 없음"},
    }
)
def update_user(
    userId: str,
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    관리자가 특정 직원의 정보를 수정합니다.

    - **name**: 이름
    - **departmentCode**: 부서 코드
    - **positionCode**: 직책 코드
    - **predecessorUserId**: 전임자 사번 (null로 설정하여 제거 가능)
    - **statusCode**: 재직 상태 코드 ('01': 재직, '02': 휴직, '03': 퇴직)
    """
    # 1. 관리자 권한 확인
    if current_user.system_role_code != '02':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )

    # 2. 수정할 직원 조회 (동시 수정을 방지하기 위해 비관적 잠금 사용)
    user_to_update = db.query(User).filter(User.user_id == userId).with_for_update().first()
    if not user_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="수정할 직원을 찾을 수 없습니다."
        )

    # 3. 요청된 데이터로 정보 업데이트
    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="수정할 정보가 없습니다."
        )

    # 부서 변경을 가장 먼저 처리하여 업무 담당을 초기화합니다.
    if "departmentCode" in update_data and request.departmentCode:
        if user_to_update.department_code != request.departmentCode:
            # --- 부서 이동에 따른 미완료 민원 이관 로직 (시작) ---
            moving_user_id = userId
            # 이동하는 직원의 후임자 찾기
            successor = db.query(User).filter(User.predecessor_user_id == moving_user_id).first()
            
            # 이동하는 직원의 미완료 민원 목록 조회
            incomplete_petitions = db.query(Petition).filter(
                Petition.assignee_user_id == moving_user_id,
                Petition.status_code != '04'
            ).all()

            if successor:
                # Case 2: 후임자가 있으면 후임자에게 이관
                successor_id = successor.user_id
                for p in incomplete_petitions:
                    p.assignee_user_id = successor_id
                    p.status_code = "01"
                    db.add(PetitionAssigneeHistory(
                        petition_id=p.petition_id,
                        from_user_id=moving_user_id,
                        to_user_id=successor_id,
                        change_type="01", # 이관
                    ))
            elif incomplete_petitions:
                # Case 1: 후임자가 없으면 새 부서의 부장에게 임시 이관
                new_dept_code = request.departmentCode
                department_head = db.query(User).filter(
                    User.department_code == new_dept_code,
                    User.position_code == '01' # '부장'
                ).first()

                if department_head:
                    department_head_id = department_head.user_id
                    for p in incomplete_petitions:
                        p.assignee_user_id = department_head_id
                        p.status_code = "01"
                        db.add(PetitionAssigneeHistory(
                            petition_id=p.petition_id,
                            from_user_id=moving_user_id,
                            to_user_id=department_head_id,
                            change_type="02", # 임시 이관
                        ))
                else: # 부장이 없으면 담당자 없음으로 처리
                    for p in incomplete_petitions:
                        p.assignee_user_id = None
                        p.status_code = "01"
                        db.add(PetitionAssigneeHistory(
                            petition_id=p.petition_id,
                            from_user_id=moving_user_id,
                            to_user_id=None,
                            change_type="02", # 임시 이관
                        ))
            # --- 부서 이동에 따른 미완료 민원 이관 로직 (끝) ---

            # 부서가 변경되었으므로, 기존 담당 업무를 모두 초기화합니다.
            db.query(TaskAssignee).filter(TaskAssignee.user_id == userId).delete(synchronize_session=False)

            # 부서 이동 시, 기존 전임자가 새 부서 소속이 아니면 전임자 관계를 해제합니다.
            if user_to_update.predecessor_user_id:
                predecessor = db.query(User).filter(User.user_id == user_to_update.predecessor_user_id).first()
                if predecessor and predecessor.department_code != request.departmentCode:
                    user_to_update.predecessor_user_id = None
            
            user_to_update.department_code = request.departmentCode
            
            # 시스템 역할 업데이트 (관리자 부서 '09' 여부)
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
        user_to_update.status_code = request.statusCode

    if "predecessorUserId" in update_data:
        predecessor_id = request.predecessorUserId
        if predecessor_id and str(predecessor_id) == str(userId):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="자기 자신을 전임자로 지정할 수 없습니다.")

        # 전임자가 새로 지정되거나 변경될 때만 업무 승계 로직 실행
        if predecessor_id and str(user_to_update.predecessor_user_id) != str(predecessor_id):
            successor_id = userId
            predecessor_user = db.query(User).filter(User.user_id == predecessor_id).first()
            if not predecessor_user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전임자로 지정된 직원을 찾을 수 없습니다.")

            # --- 민원 이관 로직 ---
            # 1. 전임자에게 '현재' 배정된 미완료 민원을 후임자에게 직접 이관
            petitions_to_transfer_directly = db.query(Petition).filter(
                Petition.assignee_user_id == predecessor_id,
                Petition.status_code != '04'
            ).all()

            for p in petitions_to_transfer_directly:
                p.assignee_user_id = successor_id
                p.status_code = "01"
                db.add(PetitionAssigneeHistory(
                    petition_id=p.petition_id,
                    from_user_id=predecessor_id,
                    to_user_id=successor_id,
                    change_type="01", # 이관
                ))

            # 2. 부장에게 '임시 이관'되었던 전임자의 민원을 후임자에게 이관 (Case 3)
            department_head = db.query(User).filter(
                User.department_code == predecessor_user.department_code,
                User.position_code == '01' # '부장'
            ).first()

            if department_head:
                department_head_id = department_head.user_id

                # 각 민원별 최신 이력 ID를 찾는 서브쿼리
                latest_history_subquery = db.query(
                    PetitionAssigneeHistory.petition_id,
                    func.max(PetitionAssigneeHistory.history_id).label('max_history_id')
                ).group_by(PetitionAssigneeHistory.petition_id).subquery()

                # 이관할 민원 조회
                petitions_to_transfer = db.query(Petition).join(
                    PetitionAssigneeHistory, Petition.petition_id == PetitionAssigneeHistory.petition_id
                ).join(
                    latest_history_subquery,
                    (PetitionAssigneeHistory.petition_id == latest_history_subquery.c.petition_id) &
                    (PetitionAssigneeHistory.history_id == latest_history_subquery.c.max_history_id)
                ).filter(
                    Petition.assignee_user_id == department_head_id,
                    Petition.status_code != '04',
                    PetitionAssigneeHistory.from_user_id == predecessor_id,
                    PetitionAssigneeHistory.to_user_id == department_head_id,
                    PetitionAssigneeHistory.change_type == '02' # 임시 이관
                ).all()

                for p in petitions_to_transfer:
                    p.assignee_user_id = successor_id
                    p.status_code = "01"
                    db.add(PetitionAssigneeHistory(
                        petition_id=p.petition_id,
                        from_user_id=department_head_id,
                        to_user_id=successor_id,
                        change_type="01", # 이관
                    ))

            # --- 담당 업무(Task) 승계 로직 ---
            predecessor_task_ids = {
                row.task_id for row in db.query(TaskAssignee.task_id).filter(TaskAssignee.user_id == str(predecessor_id)).all()
            }

            # 2. 후임자(현재 수정 대상 직원)의 task_id 목록 조회
            successor_task_ids = {
                row.task_id for row in db.query(TaskAssignee.task_id).filter(TaskAssignee.user_id == str(userId)).all()
            }

            # 3. 승계할 task_id 목록 계산 (전임자는 담당하고 있으나 후임자는 담당하고 있지 않은 업무)
            tasks_to_inherit = predecessor_task_ids - successor_task_ids

            # 4. 새로운 담당 업무 할당
            for task_id in tasks_to_inherit:
                new_assignment = TaskAssignee(user_id=str(userId), task_id=task_id)
                db.add(new_assignment)

        user_to_update.predecessor_user_id = predecessor_id

    # 4. 변경사항 저장
    db.commit()

    return UserUpdateResponse(userId=userId, message="직원 정보가 성공적으로 수정되었습니다.")

@router.post(
    "/users/{userId}/reset-password",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="직원 비밀번호 초기화 (관리자용)",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "잘못된 요청 (자기 자신 초기화 시도)"},
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "관리자 권한 필요"},
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 직원"},
    }
)
def reset_user_password(
    userId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    관리자가 특정 직원의 비밀번호를 기본값으로 초기화하고,
    다음 로그인 시 비밀번호를 변경하도록 강제합니다.
    """
    # 1. 관리자 권한 확인
    if current_user.system_role_code != '02':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )

    # 2. 초기화할 직원 조회
    user_to_reset = db.query(User).filter(User.user_id == userId).first()
    if not user_to_reset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="비밀번호를 초기화할 직원을 찾을 수 없습니다."
        )

    # 3. 자기 자신의 비밀번호는 이 API로 초기화 불가 (보안상)
    if str(user_to_reset.user_id) == str(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자기 자신의 비밀번호는 '비밀번호 변경' 메뉴를 이용해 변경해야 합니다."
        )

    # 4. 비밀번호 초기화 및 변경 강제 플래그 설정
    hashed_password = get_password_hash(settings.DEFAULT_PASSWORD)
    user_to_reset.password = hashed_password
    user_to_reset.must_change_password = True

    # 5. 변경사항 저장
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
    responses={
        status.HTTP_200_OK: {"description": "집계 반환"},
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "관리자 권한 필요"},
    }
)
def get_admin_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    관리자 대시보드에 필요한 주요 통계(총 직원 수, 상태별 직원 수, 부서 수)를 조회합니다.
    """
    # 1. 관리자 권한 확인
    if current_user.system_role_code != '02':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )

    # 2. 직원 상태별 통계 조회 (효율적인 단일 쿼리)
    user_stats = db.query(
        func.count(User.user_id).label("total"),
        func.sum(case((User.status_code == '01', 1), else_=0)).label("active"),
        func.sum(case((User.status_code == '02', 1), else_=0)).label("leave"),
        func.sum(case((User.status_code == '03', 1), else_=0)).label("resigned")
    ).one()

    # 3. 부서 수 조회
    department_count = db.query(Department).count()

    # 4. 응답 데이터 구성
    return AdminStatsResponse(
        totalUsers=user_stats.total or 0,
        activeUsers=user_stats.active or 0,
        leaveUsers=user_stats.leave or 0,
        resignedUsers=user_stats.resigned or 0,
        totalDepartments=department_count
    )