from datetime import datetime, timezone, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
import math

from app.db.session import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.models.department import Department
from app.api.routers.auth import get_current_user

router = APIRouter()

# ----------------------------------------------------------------
# 상수
# ----------------------------------------------------------------

STAGE_NAME_MAP = {
    "01": "저장",
    "02": "승인완료",
}

ROLE_NAME_MAP = {
    "01": "주관",
    "02": "협력",
}

# ----------------------------------------------------------------
# Pydantic 스키마
# ----------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    name: str
    businessContent: str
    startDate: Optional[str] = None
    deadline: Optional[str] = None
    memberUserIds: List[int]

class ProjectCreateResponse(BaseModel):
    projectId: int

class ProjectUpdateRequest(BaseModel):
    name: str
    businessContent: str
    startDate: Optional[str] = None
    deadline: Optional[str] = None
    overview: Optional[str] = None
    reportContent: Optional[str] = None
    memberUserIds: List[int]

class MemberItem(BaseModel):
    userId: int
    name: str
    roleName: str

class ProjectListItem(BaseModel):
    projectId: int
    name: str
    stageName: str
    departmentName: str
    startDate: Optional[str]
    deadline: Optional[str]
    createdAt: str
    roleType: str

class ProjectListResponse(BaseModel):
    content: List[ProjectListItem]
    totalElements: int
    totalPages: int
    page: int
    size: int

class ProjectDetailResponse(BaseModel):
    projectId: int
    name: str
    stageCode: str
    stageName: str
    departmentName: str
    startDate: Optional[str]
    deadline: Optional[str]
    businessContent: Optional[str]
    overview: Optional[str]
    reportContent: Optional[str]
    approvedAt: Optional[str]
    createdAt: str
    members: List[MemberItem]

class AiDraftResponse(BaseModel):
    overview: str
    reportContent: str

# ----------------------------------------------------------------
# 유틸
# ----------------------------------------------------------------

def date_to_str(d) -> Optional[str]:
    return d.isoformat() if d else None

def datetime_to_str(dt) -> Optional[str]:
    return dt.isoformat() if dt else None

def str_to_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return date.fromisoformat(s)

def get_department_name(department_code: Optional[str], db: Session) -> str:
    if not department_code:
        return ""
    dept = db.query(Department).filter(
        Department.department_code == department_code
    ).first()
    return dept.name if dept else ""

def build_detail_response(project: Project, db: Session) -> ProjectDetailResponse:
    members_raw = db.query(ProjectMember, User).join(
        User, ProjectMember.user_id == User.user_id
    ).filter(ProjectMember.project_id == project.project_id).all()

    members = [
        MemberItem(
            userId=u.user_id,
            name=u.name,
            roleName=ROLE_NAME_MAP.get(pm.role_code, ""),
        )
        for pm, u in members_raw
    ]

    return ProjectDetailResponse(
        projectId=project.project_id,
        name=project.name,
        stageCode=project.stage_code or "",
        stageName=STAGE_NAME_MAP.get(project.stage_code, ""),
        departmentName=get_department_name(project.department_code, db),
        startDate=date_to_str(project.start_date),
        deadline=date_to_str(project.deadline),
        businessContent=project.business_content,
        overview=project.overview,
        reportContent=project.report_content,
        approvedAt=datetime_to_str(project.approved_at),
        createdAt=datetime_to_str(project.created_at),
        members=members,
    )

# ----------------------------------------------------------------
# 엔드포인트
# ----------------------------------------------------------------

# 1. 프로젝트 목록 조회
@router.get(
    "",
    response_model=ProjectListResponse,
    summary="프로젝트 목록 조회",
)
def get_project_list(
    scope: str = Query(..., description="MY(내 주관) | JOINED(내 참여) | PREDECESSOR(전임자)"),
    stage: Optional[str] = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if scope == "MY":
        # 내가 주관(role_code=01)인 프로젝트
        project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == current_user.user_id,
            ProjectMember.role_code == "01",
        ).subquery()
        query = db.query(Project).filter(Project.project_id.in_(project_ids))

    elif scope == "JOINED":
        # 내가 협력(role_code=02)으로 참여한 프로젝트
        project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == current_user.user_id,
            ProjectMember.role_code == "02",
        ).subquery()
        query = db.query(Project).filter(Project.project_id.in_(project_ids))

    elif scope == "PREDECESSOR":
        # 전임자의 주관 프로젝트
        if not current_user.predecessor_user_id:
            return ProjectListResponse(content=[], totalElements=0, totalPages=0, page=page, size=size)
        project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == current_user.predecessor_user_id,
            ProjectMember.role_code == "01",
        ).subquery()
        query = db.query(Project).filter(Project.project_id.in_(project_ids))

    else:
        raise HTTPException(status_code=400, detail="유효하지 않은 scope 값입니다.")

    if stage:
        query = query.filter(Project.stage_code == stage)

    total_elements = query.count()
    total_pages = math.ceil(total_elements / size)
    items = query.offset(page * size).limit(size).all()

    content = [
        ProjectListItem(
            projectId=p.project_id,
            name=p.name,
            stageName=STAGE_NAME_MAP.get(p.stage_code, ""),
            departmentName=get_department_name(p.department_code, db),
            startDate=date_to_str(p.start_date),
            deadline=date_to_str(p.deadline),
            createdAt=datetime_to_str(p.created_at),
            roleType=scope,
        )
        for p in items
    ]

    return ProjectListResponse(
        content=content,
        totalElements=total_elements,
        totalPages=total_pages,
        page=page,
        size=size,
    )


# 2. 새 프로젝트 생성
@router.post(
    "",
    response_model=ProjectCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="새 프로젝트 생성",
)
def create_project(
    body: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = Project(
        name=body.name,
        business_content=body.businessContent,
        start_date=str_to_date(body.startDate),
        deadline=str_to_date(body.deadline),
        department_code=current_user.department_code,
        stage_code="01",
    )
    db.add(project)
    db.flush()  # project_id 확보

    # 작성자 본인을 주관자(01)로 PROJECT_MEMBER에 추가
    owner_member = ProjectMember(
        project_id=project.project_id,
        user_id=current_user.user_id,
        role_code="01",
        invited_by=current_user.user_id,
    )
    db.add(owner_member)

    # 협업 멤버 추가 (협력자=02)
    for uid in body.memberUserIds:
        if uid == current_user.user_id:
            continue  # 본인 중복 방지
        member = ProjectMember(
            project_id=project.project_id,
            user_id=uid,
            role_code="02",
            invited_by=current_user.user_id,
        )
        db.add(member)

    db.commit()
    db.refresh(project)

    return ProjectCreateResponse(projectId=project.project_id)


# 3. 프로젝트 상세 조회
@router.get(
    "/{projectId}",
    response_model=ProjectDetailResponse,
    summary="프로젝트 상세 조회",
)
def get_project_detail(
    projectId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.project_id == projectId).first()
    if not project:
        raise HTTPException(status_code=404, detail="존재하지 않는 프로젝트입니다.")

    return build_detail_response(project, db)


# 4. 프로젝트 저장 (수정)
@router.patch(
    "/{projectId}",
    response_model=ProjectDetailResponse,
    summary="프로젝트 저장",
)
def update_project(
    projectId: int,
    body: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.project_id == projectId).first()
    if not project:
        raise HTTPException(status_code=404, detail="존재하지 않는 프로젝트입니다.")

    if project.stage_code == "02":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="승인완료 상태라 수정할 수 없습니다.",
        )

    # 기본 정보 수정
    project.name = body.name
    project.business_content = body.businessContent
    project.start_date = str_to_date(body.startDate)
    project.deadline = str_to_date(body.deadline)
    if body.overview is not None:
        project.overview = body.overview
    if body.reportContent is not None:
        project.report_content = body.reportContent

    # memberUserIds diff 처리
    existing_members = db.query(ProjectMember).filter(
        ProjectMember.project_id == projectId
    ).all()

    # 주관자(role_code=01)는 diff 대상에서 제외
    existing_collab_ids = {
        m.user_id for m in existing_members if m.role_code == "02"
    }
    new_collab_ids = set(body.memberUserIds)

    # 제거: 기존에 있었는데 새 목록에 없는 협력자
    ids_to_remove = existing_collab_ids - new_collab_ids
    if ids_to_remove:
        db.query(ProjectMember).filter(
            ProjectMember.project_id == projectId,
            ProjectMember.user_id.in_(ids_to_remove),
            ProjectMember.role_code == "02",
        ).delete(synchronize_session=False)

    # 추가: 새 목록에 있는데 기존에 없는 협력자
    ids_to_add = new_collab_ids - existing_collab_ids
    for uid in ids_to_add:
        db.add(ProjectMember(
            project_id=projectId,
            user_id=uid,
            role_code="02",
            invited_by=current_user.user_id,
        ))

    db.commit()
    db.refresh(project)

    return build_detail_response(project, db)


# 5. 기획서 승인완료
@router.post(
    "/{projectId}/approve",
    status_code=status.HTTP_200_OK,
    summary="기획서 승인완료",
)
def approve_project(
    projectId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.project_id == projectId).first()
    if not project:
        raise HTTPException(status_code=404, detail="존재하지 않는 프로젝트입니다.")

    if project.stage_code == "02":
        raise HTTPException(status_code=409, detail="이미 승인완료 상태입니다.")

    project.stage_code = "02"
    project.approved_at = datetime.now(timezone.utc)
    db.commit()


# 6. 프로젝트 삭제
@router.delete(
    "/{projectId}",
    status_code=status.HTTP_200_OK,
    summary="프로젝트 삭제",
)
def delete_project(
    projectId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.project_id == projectId).first()
    if not project:
        raise HTTPException(status_code=404, detail="존재하지 않는 프로젝트입니다.")

    if project.stage_code != "01":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="저장(기획중) 상태인 프로젝트만 삭제할 수 있습니다.",
        )

    # 연관된 PROJECT_MEMBER 먼저 삭제 (하드딜리트)
    db.query(ProjectMember).filter(
        ProjectMember.project_id == projectId
    ).delete(synchronize_session=False)

    db.delete(project)
    db.commit()


# 7. AI 기획서 초안 생성
@router.get(
    "/{projectId}/ai-draft",
    response_model=AiDraftResponse,
    summary="AI 기획서 초안 생성",
)
def get_ai_draft(
    projectId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.project_id == projectId).first()
    if not project:
        raise HTTPException(status_code=404, detail="존재하지 않는 프로젝트입니다.")

    # AI 연동은 추후 구현
    # 현재는 빈 값 반환
    return AiDraftResponse(
        overview="",
        reportContent="",
    )