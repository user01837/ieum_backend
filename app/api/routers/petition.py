import math
from fastapi import APIRouter, Depends, Query, HTTPException, status, Form, File, UploadFile, BackgroundTasks, Header
from sqlalchemy.orm import Session
from sqlalchemy import or_, case, func
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Optional
import httpx

from app.db.session import get_db
from app.models.petition import Petition
from app.models.user import User
from app.models.task import Task
from app.models.department import Department
from app.models.task_assignee import TaskAssignee
from app.api.routers.auth import get_current_user
from app.models.petition_attachment import PetitionAttachment
from app.core.config import settings
from app.services.s3_service import upload_file_to_s3

# --- 상수 및 맵 ---

STATUS_MAP = {
    "01": "대기중",
    "02": "처리중",
    "03": "완료",
}

POSITION_MAP = {
    "01": "부장",
    "02": "팀장",
    "03": "주무관",
}

VALID_DEPARTMENT_CODES = {"01", "02", "03", "04", "05", "06", "07", "08"}

# --- Pydantic 스키마 ---

class PetitionContent(BaseModel):
    complaintId: int
    title: str
    statusName: str | None
    taskName: str | None
    assigneeName: str | None
    assigneePositionName: str | None
    receivedAt: str | None
    dueDate: str | None
    answeredAt: str | None
    departmentCode: str | None
    departmentName: str | None

class PaginatedPetitionResponse(BaseModel):
    content: List[PetitionContent]
    totalElements: int
    totalPages: int
    page: int
    size: int

class AssigneeDetail(BaseModel):
    userId: str
    name: str
    positionName: str | None

class AttachmentDetail(BaseModel):
    attachmentId: int
    fileName: str
    fileUrl: str
    isStaffUpload: bool

class PetitionDetailResponse(BaseModel):
    complaintId: int
    title: str
    content: str
    statusCode: str | None
    statusName: str | None
    departmentName: str | None
    taskName: str | None
    assignee: AssigneeDetail | None
    receivedAt: str | None
    dueDate: str | None
    answeredAt: str | None
    manualAnswer: str | None
    attachments: List[AttachmentDetail]

class DeleteAttachmentResponse(BaseModel):
    message: str
    complaintId: int

class ExternalPetitionRequest(BaseModel):
    title: str
    content: str

class ExternalPetitionResponse(BaseModel):
    petitionId: int
    departmentCode: str
    dueDate: str

# --- 라우터 ---

router = APIRouter()

# --- 비공개 헬퍼 함수 ---

def _call_ai_to_index_petition(petition_data: dict):
    """
    완료된 민원 정보를 AI 서버에 보내 색인을 요청하는 헬퍼 함수입니다.
    BackgroundTasks를 통해 비동기적으로 실행됩니다.
    """
    try:
        # AI 서버의 색인 API 엔드포인트 (실제 경로에 따라 수정 필요)
        ai_endpoint_url = f"{settings.AI_SERVER.rstrip('/')}/api/index-complaint"

        # 동기 방식으로 AI 서버에 POST 요청
        response = httpx.post(ai_endpoint_url, json=petition_data, timeout=30.0)
        response.raise_for_status()
        
        # 성공 시 로그 (실제 운영에서는 logging 모듈 사용 권장)
        print(f"INFO: Successfully indexed petition ID: {petition_data.get('complaint_id')}")

    except httpx.RequestError as exc:
        print(f"ERROR: AI server connection error while indexing petition: {exc}")
    except httpx.HTTPStatusError as exc:
        print(f"ERROR: AI server status error while indexing petition: {exc.response.status_code} - {exc.response.text}")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while indexing petition: {e}")

@router.post(
    "/external",
    response_model=ExternalPetitionResponse,
    summary="외부 시스템 민원 접수",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "API 키 불일치/누락"},
    }
)
def create_external_petition(
    req: ExternalPetitionRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """
    국민신문고/정부24 같은 외부 민원 채널이 새 민원을 접수할 때 호출하는 엔드포인트.
    내부 직원용 JWT(get_current_user)가 아니라 API 키로 인증한다.

    ieum_ai의 /api/classify-department로 부서를 자동 분류한다. 분류가 실패해도
    (AI 서버 다운, 타임아웃 등) 민원 접수 자체는 막지 않고 기본 부서(08 행정·일반)로
    접수한다 - 담당자는 이후 temp-save에서 담당자/부서를 재배정할 수 있다.
    """
    if x_api_key != settings.EXTERNAL_PETITION_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 API 키입니다.")

    department_code = "08"
    try:
        classify_url = f"{settings.AI_SERVER.rstrip('/')}/api/classify-department"
        response = httpx.post(
            classify_url,
            json={"title": req.title, "content": req.content},
            timeout=60.0,
        )
        response.raise_for_status()
        department_code = response.json()["department_code"]
    except Exception as e:
        print(f"WARN: 부서 자동분류 실패, 기본 부서(08)로 접수: {e}")

    if department_code not in VALID_DEPARTMENT_CODES:
        print(f"WARN: ieum_ai가 유효하지 않은 department_code를 반환함({department_code!r}), 기본 부서(08)로 접수")
        department_code = "08"

    task_id = None
    try:
        classify_task_url = f"{settings.AI_SERVER.rstrip('/')}/api/classify-task"
        task_response = httpx.post(
            classify_task_url,
            json={
                "complaint_text": f"{req.title}\n{req.content}",
                "department_code": department_code,
            },
            timeout=60.0,
        )
        task_response.raise_for_status()
        task_id = task_response.json().get("task_id")
    except Exception as e:
        print(f"WARN: 담당업무 자동분류 실패, 미배정으로 접수: {e}")

    if task_id is not None and db.query(Task.task_id).filter(
        Task.task_id == task_id,
        Task.is_deleted == False,
    ).first() is None:
        print(f"WARN: ieum_ai가 존재하지 않거나 삭제된 task_id를 반환함({task_id!r}), 미배정으로 접수")
        task_id = None

    assignee_user_id = None
    if task_id is not None:
        candidate_ids = [
            row.user_id for row in
            db.query(TaskAssignee.user_id).filter(TaskAssignee.task_id == task_id).all()
        ]
        if candidate_ids:
            open_counts = {uid: 0 for uid in candidate_ids}
            counted = (
                db.query(Petition.assignee_user_id, func.count(Petition.petition_id))
                .filter(
                    Petition.assignee_user_id.in_(candidate_ids),
                    Petition.status_code != "03",
                )
                .group_by(Petition.assignee_user_id)
                .all()
            )
            for uid, cnt in counted:
                open_counts[uid] = cnt
            assignee_user_id = min(open_counts, key=open_counts.get)

    now = datetime.now()
    petition = Petition(
        title=req.title,
        content=req.content,
        department_code=department_code,
        task_id=task_id,
        assignee_user_id=assignee_user_id,
        status_code="01",
        received_at=now,
        due_date=now + timedelta(days=14),
    )
    db.add(petition)
    db.commit()
    db.refresh(petition)

    return ExternalPetitionResponse(
        petitionId=petition.petition_id,
        departmentCode=department_code,
        dueDate=petition.due_date.isoformat(),
    )

@router.get(
    "/",
    response_model=PaginatedPetitionResponse,
    summary="민원 목록 조회 (페이지네이션)",
    dependencies=[Depends(get_current_user)]
)
def get_petitions(
    scope: str = Query(..., description="조회 범위: ALL(부서전체) | MY(내 민원) | TASK(업무별) | PREDECESSOR(전임자)"),
    petition_status: str = Query(..., alias="status", description="민원 상태 필터: ALL | 01(대기중) | 02(임시저장) | 03(완료)"),
    page: int = Query(..., description="페이지 번호 (0부터 시작)"),
    size: int = Query(10, description="페이지 크기, 기본값 10"),
    sort: Optional[str] = Query(None, description="정렬 옵션: incomplete_first (미완료 우선) | due_date_impending (처리기한 임박순)"),
    taskId: Optional[int] = Query(None, description="Task 필터 (scope=TASK일 때)"),
    departmentCode: Optional[str] = Query(None, alias="departmentCode", description="부서 코드 필터 (관리자용)"),
    keyword: Optional[str] = Query(None, description="검색어 (민원 제목)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    다양한 조건과 페이지네이션을 통해 민원 목록을 조회합니다.
    """
    # 1. 기본 쿼리 생성 (Petition, Task, User 테이블 조인)
    query = db.query(
        Petition,
        Task.name.label("task_name"),
        User,
        Department.name.label("department_name")
    ).outerjoin(
        Task, Petition.task_id == Task.task_id
    ).outerjoin(
        User, Petition.assignee_user_id == User.user_id
    ).outerjoin(
        Department, Petition.department_code == Department.department_code
    )

    is_admin = current_user.system_role_code == '02'

    # 2. Scope 및 권한에 따른 필터링
    if is_admin:
        # 관리자는 '09'(관리자) 부서를 제외한 모든 민원을 볼 수 있음.
        query = query.filter(Petition.department_code != '09')
        # 부서 코드로 추가 필터링 가능.
        if departmentCode:
            query = query.filter(Petition.department_code == departmentCode)
    else:
        # 일반 사용자 필터링 로직
        if scope.upper() == "MY":
            query = query.filter(Petition.assignee_user_id == current_user.user_id)
        elif scope.upper() == "TASK":
            # taskId가 제공된 경우, 해당 업무로 추가 필터링
            if taskId is not None:
                query = query.filter(Petition.task_id == taskId)
            # taskId가 없는 경우, 현재 사용자가 담당하는 모든 업무(삭제되지 않은 업무만)의 민원을 조회
            else:
                # 1. task_assignee 테이블에서 현재 사용자의 삭제되지 않은 task_id를 조회
                user_task_ids_query = db.query(TaskAssignee.task_id).join(
                    Task, TaskAssignee.task_id == Task.task_id
                ).filter(
                    TaskAssignee.user_id == current_user.user_id,
                    Task.is_deleted == False,
                )
                # 2. 해당 task_id 목록에 포함되는 민원들만 필터링
                query = query.filter(Petition.task_id.in_(user_task_ids_query))
        elif scope.upper() == "PREDECESSOR":
            if not current_user.predecessor_user_id:
                # 전임자가 없는 경우 빈 목록을 반환
                return PaginatedPetitionResponse(content=[], totalElements=0, totalPages=0, page=page, size=size)
            query = query.filter(Petition.assignee_user_id == current_user.predecessor_user_id)    
        elif scope.upper() == "ALL":
            query = query.filter(Petition.department_code == current_user.department_code)
        # scope == "ALL"은 별도 필터링 없음

        # 보안/개인정보 보호 규칙 적용:
        # 관리자가 아닌 경우, 자신에게 할당된 민원 또는 '완료' 상태의 민원만 볼 수 있음
        query = query.filter(
            or_(Petition.assignee_user_id == current_user.user_id, Petition.status_code == "03")
        )
    
    # 3. 상태(status)에 따른 필터링
    if petition_status != "ALL":
        query = query.filter(Petition.status_code == petition_status)

    # 키워드 검색
    if keyword:
        query = query.filter(Petition.title.contains(keyword))

    # 4. 페이지네이션을 위한 전체 개수 조회
    total_elements = query.count()
    total_pages = math.ceil(total_elements / size) if size > 0 else 0

    # 5. 실제 데이터 조회 (정렬 및 페이지네이션 적용)
    if sort == 'incomplete_first':
        # 미완료(status_code != '03') 민원을 우선 정렬하고, 그 다음 최신순으로 정렬
        query = query.order_by((Petition.status_code != '03').desc(), Petition.created_at.desc())
    elif sort == 'due_date_impending':
        # 미완료 민원을 우선하고, 그 안에서 처리기한이 임박한 순(오름차순)으로 정렬합니다.
        # 처리기한이 없는 민원은 각 그룹의 뒤로 보냅니다.
        # MySQL은 `NULLS LAST` 구문을 지원하지 않으므로, `due_date`가 NULL인 경우를
        # 별도로 처리하여 정렬 순서의 뒤로 보냅니다.
        incompleteness_order = case(
            (Petition.status_code != '03', 1),
            else_=2
        )
        # `Petition.due_date.is_(None)`은 due_date가 NULL이면 True(1), 아니면 False(0)를 반환합니다.
        # 따라서 NULL인 항목들이 뒤로 정렬됩니다.
        query = query.order_by(incompleteness_order, Petition.due_date.is_(None), Petition.due_date.asc())
    else:
        # 기본 정렬: 최신순
        query = query.order_by(Petition.created_at.desc())

    results = query.offset(page * size).limit(size).all()

    # 6. 응답 데이터 형식으로 변환
    content = [
        PetitionContent(
            complaintId=p.petition_id,
            title=p.title,
            statusName=STATUS_MAP.get(p.status_code),
            taskName=task_name,
            assigneeName=assignee_user.name if assignee_user else None,
            assigneePositionName=POSITION_MAP.get(assignee_user.position_code) if assignee_user else None,
            receivedAt=p.received_at.isoformat() if p.received_at else None,
            dueDate=p.due_date.isoformat() if p.due_date else None,
            answeredAt=p.answered_at.isoformat() if p.answered_at else None,
            departmentCode=p.department_code,
            departmentName=department_name,
        ) for p, task_name, assignee_user, department_name in results
    ]

    return PaginatedPetitionResponse(
        content=content,
        totalElements=total_elements,
        totalPages=total_pages,
        page=page,
        size=size,
    )

@router.get(
    "/{complaintId}",
    response_model=PetitionDetailResponse,
    summary="민원 상세 조회",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "접근 권한 없음"},
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 민원"},
    }
)
def get_petition_detail(
    complaintId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 민원(complaint)의 상세 정보를 조회합니다.
    """
    # 1. 기본 쿼리 생성 (Petition, Task, User, Department 테이블 조인)
    query_result = db.query(
        Petition,
        Task.name.label("task_name"),
        User,
        Department.name.label("department_name")
    ).outerjoin(
        Task, Petition.task_id == Task.task_id
    ).outerjoin(
        User, Petition.assignee_user_id == User.user_id
    ).outerjoin(
        Department, Petition.department_code == Department.department_code
    ).filter(Petition.petition_id == complaintId).first()

    # 2. 민원 존재 여부 확인
    if not query_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 민원입니다."
        )

    p, task_name, assignee_user, department_name = query_result

    # 3. 접근 권한 확인
    is_admin = current_user.system_role_code == '02'
    is_owner = p.assignee_user_id is not None and str(p.assignee_user_id) == str(current_user.user_id)
    is_completed = p.status_code == "03"

    # 관리자가 아니고, 담당자도 아니며, 완료 상태도 아니면 접근 불가
    if not (is_admin or is_owner or is_completed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 민원에 접근할 권한이 없습니다."
        )

    # 4. 담당자 정보 구성
    assignee_info = None
    if assignee_user:
        assignee_info = AssigneeDetail(
            userId=str(assignee_user.user_id),
            name=assignee_user.name,
            positionName=POSITION_MAP.get(assignee_user.position_code)
        )

    # 5. 첨부파일 목록 조회
    attachments_from_db = db.query(PetitionAttachment)\
        .filter(PetitionAttachment.petition_id == complaintId, PetitionAttachment.is_deleted == False)\
        .order_by(PetitionAttachment.attachment_id)\
        .all()
    attachments_list = [
        AttachmentDetail(
            attachmentId=att.attachment_id,
            fileName=att.file_name,
            fileUrl=att.file_url,
            isStaffUpload=att.is_staff_upload) for att in attachments_from_db
    ]


    # 6. 응답 데이터 구성
    return PetitionDetailResponse(
        complaintId=p.petition_id,
        title=p.title,
        content=p.content,
        statusCode=p.status_code,
        statusName=STATUS_MAP.get(p.status_code),
        departmentName=department_name,
        taskName=task_name,
        assignee=assignee_info,
        receivedAt=p.received_at.isoformat() if p.received_at else None,
        dueDate=p.due_date.isoformat() if p.due_date else None,
        answeredAt=p.answered_at.isoformat() if p.answered_at else None,
        manualAnswer=p.manual_answer,
        attachments=attachments_list
    )

@router.put(
    "/{complaintId}/temp-save",
    status_code=status.HTTP_200_OK,
    summary="민원 답변 임시저장 및 담당자 변경",
    responses={
        status.HTTP_200_OK: {"description": "임시저장 성공"},
        status.HTTP_400_BAD_REQUEST: {"description": "요청값 오류"},
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "권한 없음 (담당자만 가능)"},
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 민원"},
    }
)
def temp_save_petition(
    complaintId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    manualAnswer: Optional[str] = Form(None),
    assigneeUserId: Optional[str] = Form(None),
    files: List[UploadFile] = File([])
):
    """
    민원 답변을 임시저장하고, 필요 시 담당자를 변경합니다.
    파일이 함께 전송된 경우, S3에 업로드하고 DB에 정보를 저장합니다.

    - **multipart/form-data** 형식으로 요청해야 합니다.
    - 현재 민원의 담당자만 이 작업을 수행할 수 있습니다.
    - 임시저장 시 민원 상태가 '대기중'('01')이었다면 '처리중'('02')으로 변경됩니다.
    """
    # 0. 요청 유효성 검사: 업데이트할 내용이 하나라도 있는지 확인
    if manualAnswer is None and assigneeUserId is None and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="업데이트할 답변 내용, 변경할 담당자 정보, 또는 파일이 없습니다."
        )

    # 1. 민원 조회 (동시 수정을 방지하기 위해 비관적 잠금 사용)
    petition = db.query(Petition).filter(Petition.petition_id == complaintId).with_for_update().first()

    if not petition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 민원입니다."
        )

    # 2. 권한 확인 (현재 담당자)
    is_current_assignee = petition.assignee_user_id and str(petition.assignee_user_id) == str(current_user.user_id)

    if not (is_current_assignee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 민원을 수정할 권한이 없습니다."
        )

    # 3. 답변 내용 업데이트
    if manualAnswer is not None:
        petition.manual_answer = manualAnswer

    # 4. 담당자 변경 처리
    # assigneeUserId가 form-data에 포함된 경우에만 처리합니다.
    if assigneeUserId is not None:
        # Case 1: 담당자 지정 해제 (프론트엔드에서 빈 문자열 "" 전송)
        if assigneeUserId == "":
            if petition.assignee_user_id is not None:
                petition.assignee_user_id = None
        # Case 2: 담당자 신규 지정 또는 변경
        else:
            new_assignee_id = str(assigneeUserId)
            # DB 값(None 가능)과 Form 값(str)의 안전한 비교를 위해 양쪽 모두 문자열로 변환
            current_assignee_id_str = str(petition.assignee_user_id) if petition.assignee_user_id is not None else ""
            if new_assignee_id != current_assignee_id_str:
                new_assignee = db.query(User).filter(User.user_id == new_assignee_id).first()
                if not new_assignee:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="새로 지정할 담당자를 찾을 수 없습니다."
                    )
                petition.assignee_user_id = new_assignee_id

    # 5. 상태 변경 ('대기중' -> '처리중')
    if petition.status_code == "01":
        petition.status_code = "02"

    # 6. 첨부파일 처리
    if files:
        for file in files:
            # S3에 파일 업로드
            file_url = upload_file_to_s3(file, path_prefix="petitions")

            # DB에 첨부파일 정보 저장
            new_attachment = PetitionAttachment(
                petition_id=petition.petition_id,
                file_name=file.filename,
                file_url=file_url,
                is_staff_upload=True  # 담당자가 업로드
            )
            db.add(new_attachment)

    # 7. 변경사항 저장
    db.commit()

    return {"message": "저장 되었습니다."}

@router.post(
    "/{complaintId}/answer",
    status_code=status.HTTP_200_OK,
    summary="민원 답변 완료",
    responses={
        status.HTTP_200_OK: {"description": "답변 완료 성공"},
        status.HTTP_400_BAD_REQUEST: {"description": "요청값 오류 또는 이미 처리된 민원"},
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "권한 없음 (담당자만 가능)"},
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 민원"},
    }
)
def answer_petition(
    complaintId: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    manualAnswer: str = Form(...),
    files: List[UploadFile] = File([])
):
    """
    민원 답변을 최종 제출하고 상태를 '완료'로 변경합니다.
    파일이 함께 전송된 경우, S3에 업로드하고 DB에 정보를 저장합니다.

    - **multipart/form-data** 형식으로 요청해야 합니다.
    - 현재 민원의 담당자만 이 작업을 수행할 수 있습니다.
    - 답변이 제출되면 `answered_at`이 기록되고 상태 코드가 '03'(완료)으로 변경됩니다.
    """
    # 1. 민원 조회 (동시 수정을 방지하기 위해 비관적 잠금 사용)
    petition = db.query(Petition).filter(Petition.petition_id == complaintId).with_for_update().first()

    if not petition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 민원입니다."
        )

    # 2. 권한 확인 (관리자 또는 담당자만 가능)
    is_admin = current_user.system_role_code == '02'
    is_current_assignee = petition.assignee_user_id and str(petition.assignee_user_id) == str(current_user.user_id)

    if not (is_admin or is_current_assignee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 민원에 답변할 권한이 없습니다."
        )

    # 3. 이미 완료된 민원인지 확인
    if petition.status_code == '03':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 답변이 완료된 민원입니다."
        )

    # 4. 답변 내용, 상태, 답변 시간 업데이트
    petition.manual_answer = manualAnswer
    petition.status_code = "03"
    petition.answered_at = datetime.now()

    # 5. 첨부파일 처리
    if files:
        for file in files:
            # S3에 파일 업로드
            file_url = upload_file_to_s3(file, path_prefix="petitions")

            # DB에 첨부파일 정보 저장
            new_attachment = PetitionAttachment(
                petition_id=petition.petition_id,
                file_name=file.filename,
                file_url=file_url,
                is_staff_upload=True  # 담당자가 업로드
            )
            db.add(new_attachment)

    # 6. 변경사항 저장
    db.commit()

    # 7. AI 서버에 색인 요청 (백그라운드 작업)
    task = db.query(Task).filter(Task.task_id == petition.task_id).first()
    domain_code = task.name if task else "기타"

    ai_payload = {
        "complaint_id": petition.petition_id,
        "title": petition.title,
        "content": petition.content,
        "department_code": petition.department_code,
        "domain_code": domain_code,
        "status_code": "완료"
    }
    background_tasks.add_task(
        _call_ai_to_index_petition,
        ai_payload
    )

    return {"message": "답변이 완료되었습니다."}

@router.delete(
    "/attachments/{attachmentId}",
    status_code=status.HTTP_200_OK,
    response_model=DeleteAttachmentResponse,
    summary="첨부파일 삭제 (소프트 삭제)",
    responses={
        status.HTTP_200_OK: {"description": "첨부파일 삭제 성공"},
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패"},
        status.HTTP_403_FORBIDDEN: {"description": "권한 없음 (담당자만 가능)"},
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 첨부파일"},
    }
)
def delete_attachment(
    attachmentId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 첨부파일을 소프트 삭제 처리합니다.

    - `is_deleted` 플래그를 `True`로, `deleted_at`을 현재 시간으로 설정합니다.
    - 원본 민원의 담당자만 이 작업을 수행할 수 있습니다.
    - 이미 완료된 민원의 첨부파일은 삭제할 수 없습니다.
    """
    # 1. 첨부파일 조회
    attachment = db.query(PetitionAttachment).filter(PetitionAttachment.attachment_id == attachmentId).first()

    if not attachment or attachment.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않거나 이미 삭제된 첨부파일입니다."
        )

    # 2. 원본 민원을 조회하여 권한 확인
    petition = db.query(Petition).filter(Petition.petition_id == attachment.petition_id).first()

    if not petition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="첨부파일에 연결된 민원을 찾을 수 없습니다.")

    # 3. 권한 확인 (담당자이고, 민원이 완료되지 않은 상태여야 함)
    if str(petition.assignee_user_id) != str(current_user.user_id) or petition.status_code == '03':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 첨부파일을 삭제할 권한이 없습니다."
        )

    # 4. 소프트 삭제 처리
    attachment.is_deleted = True
    attachment.deleted_at = datetime.now()

    # 5. 변경사항 저장
    db.commit()

    return DeleteAttachmentResponse(
        message="첨부파일이 삭제되었습니다.",
        complaintId=attachment.petition_id
    )