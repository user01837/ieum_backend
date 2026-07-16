import math
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, aliased
from pydantic import BaseModel
from pydantic import Field
from typing import Optional, List

from app.db.session import get_db
from app.models.user import User
from app.models.department import Department
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
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
        user_to_update.predecessor_user_id = predecessor_id

    if "departmentCode" in update_data and request.departmentCode:
        user_to_update.department_code = request.departmentCode
        if request.departmentCode == '09':
            user_to_update.system_role_code = '02'
        elif user_to_update.system_role_code == '02':
            user_to_update.system_role_code = '01'

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