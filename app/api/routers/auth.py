from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from passlib.context import CryptContext

# --- 설정 및 의존성 임포트 ---
# config.py에서 설정값(JWT_SECRET 등)을 가져옵니다.
from app.core.config import settings

# --- 데이터베이스 및 모델 임포트 ---
from app.db.session import get_db
from app.models.user import User
from fastapi.security import OAuth2PasswordBearer # OAuth2PasswordBearer 임포트

# --- Pydantic 스키마 정의 ---

class UserLoginRequest(BaseModel):
    """로그인 요청 시 Body에 포함될 데이터 모델"""
    userId: str
    password: str
    department_code: str = Field(max_length=10)

class UserInfo(BaseModel):
    """응답에 포함될 사용자 정보 모델"""
    userId: str
    name: str
    position_code: str | None
    department_code: str | None
    system_role_code: str | None
    mustChangePassword: bool

class TokenResponse(BaseModel):
    """로그인 성공 시 반환될 데이터 모델"""
    accessToken: str
    refreshToken: str
    mustChangePassword: bool
    token_type: str = "bearer"
    user: UserInfo

class RefreshTokenRequest(BaseModel):
    """리프레시 토큰을 포함하는 요청 모델"""
    refreshToken: str

class AccessTokenResponse(BaseModel):
    """새로운 Access Token을 포함하는 응답 모델"""
    accessToken: str

class PasswordChangeRequest(BaseModel):
    """비밀번호 변경 요청 모델"""
    oldPassword: str
    newPassword: str

# --- 보안 및 JWT 설정 ---

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 30분
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 7일

# OAuth2PasswordBearer 인스턴스 생성. tokenUrl은 로그인 엔드포인트 경로를 가리킵니다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- 현재 사용자 가져오기 의존성 함수 ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 인증 정보입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # JWT 토큰 디코딩
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # user_id로 데이터베이스에서 사용자 조회
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

# --- 라우터 생성 ---
router = APIRouter()

# --- 유틸리티 함수 ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """입력된 비밀번호와 해시된 비밀번호를 비교합니다."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """비밀번호를 해시합니다."""
    return pwd_context.hash(password)

def create_token(data: dict, expires_delta: timedelta) -> str:
    """JWT 토큰을 생성합니다."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

# --- API 엔드포인트 ---

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="사용자 로그인 및 토큰 발급",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "요청값 오류 (사번 또는 비밀번호 누락)"},
        status.HTTP_401_UNAUTHORIZED: {"description": "사번 또는 비밀번호 불일치"},
    }
)
def login(login_request: UserLoginRequest, db: Session = Depends(get_db)):
    """
    사용자 ID와 비밀번호로 로그인하여 **AccessToken**과 **RefreshToken**을 발급받습니다.

    - `mustChangePassword`가 `true`인 경우, 클라이언트에서 비밀번호 변경을 유도해야 합니다.
    """
    # 데이터베이스에서 사용자 조회
    user = db.query(User).filter(User.user_id == login_request.userId).first()

    # 사용자, 비밀번호, 부서코드 확인
    if not user or not verify_password(login_request.password, user.password) or user.department_code != login_request.department_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사번, 비밀번호 또는 부서가 일치하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 토큰에 담을 데이터 (사용자 ID와 직책 코드 포함)
    token_data = {"sub": str(user.user_id), "pos": user.position_code}

    # 토큰 생성
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    access_token = create_token(token_data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token({"sub": str(user.user_id)}, refresh_token_expires)

    # DB에 Refresh Token 및 마지막 로그인 시간 저장
    user.refresh_token = refresh_token
    user.token_expires_at = datetime.now(timezone.utc) + refresh_token_expires
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    # 비밀번호 변경 필요 여부 확인
    must_change = getattr(user, 'must_change_password', False)

    # 응답에 포함할 사용자 정보 생성
    user_info = UserInfo(
        userId=str(user.user_id),
        name=user.name,
        position_code=user.position_code,
        department_code=user.department_code,
        system_role_code=user.system_role_code,
        mustChangePassword=must_change
    )

    return TokenResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        mustChangePassword=must_change,
        user=user_info
    )

@router.get(
    "/me",
    response_model=UserInfo,
    summary="현재 로그인된 사용자 정보 조회",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "인증 실패 (유효하지 않거나 만료된 토큰)"},
    }
)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    유효한 Access Token을 사용하여 현재 로그인된 사용자 정보를 조회합니다.
    토큰은 'Authorization: Bearer <AccessToken>' 헤더에 포함되어야 합니다.
    """
    # get_current_user 의존성 함수가 이미 사용자를 검증하고 가져왔으므로 바로 반환합니다.
    return UserInfo(
        userId=str(current_user.user_id),
        name=current_user.name,
        position_code=current_user.position_code,
        department_code=current_user.department_code,
        system_role_code=current_user.system_role_code,
        mustChangePassword=current_user.must_change_password
    )

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="사용자 로그아웃",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "유효하지 않은 리프레시 토큰"},
    }
)
async def logout(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    리프레시 토큰을 사용하여 사용자를 로그아웃 처리합니다.

    - 데이터베이스에 저장된 사용자의 Refresh Token을 무효화합니다.
    - 클라이언트는 이 API 호출 후 Access Token과 Refresh Token을 모두 폐기해야 합니다.
    """
    user_to_logout = db.query(User).filter(User.refresh_token == request.refreshToken).first()

    # 토큰이 DB에 없더라도 에러를 발생시키지 않고 정상 처리(204)하여,
    # 클라이언트가 이미 로그아웃된 상태에서 다시 로그아웃을 시도해도 문제가 없도록 합니다.
    if user_to_logout:
        user_to_logout.refresh_token = None
        user_to_logout.token_expires_at = None
        db.commit()

    # 204 응답에는 본문이 없으므로 아무것도 반환하지 않습니다.

@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Access Token 재발급",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Refresh Token 만료 또는 불일치"},
    }
)
def refresh_access_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    유효한 Refresh Token을 사용하여 만료된 Access Token을 재발급합니다.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh Token이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # DB에서 리프레시 토큰으로 사용자 조회
    user = db.query(User).filter(User.refresh_token == request.refreshToken).first()

    # 사용자가 없거나, DB에 저장된 토큰 만료 시간이 지났으면 에러 발생
    if not user or not user.token_expires_at or user.token_expires_at < datetime.now(timezone.utc):
        raise credentials_exception

    # 새로운 Access Token 생성
    token_data = {"sub": str(user.user_id), "pos": user.position_code}
    new_access_token = create_token(
        data=token_data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return AccessTokenResponse(accessToken=new_access_token)

@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="비밀번호 변경",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "현재 비밀번호 불일치 또는 인증 실패"},
    }
)
def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 로그인된 사용자의 비밀번호를 변경합니다.

    - `must_change_password`가 true였던 사용자가 변경 시, 해당 플래그를 false로 업데이트합니다.
    """
    # 현재 비밀번호가 맞는지 확인
    if not verify_password(request.oldPassword, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="현재 비밀번호가 일치하지 않습니다."
        )

    # 새로운 비밀번호를 해시하여 업데이트
    current_user.password = get_password_hash(request.newPassword)
    
    # 비밀번호 변경 강제 플래그가 있었다면 해제
    if current_user.must_change_password:
        current_user.must_change_password = False
    
    db.commit()