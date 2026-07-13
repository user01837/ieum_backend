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
    position_code: str = Field(max_length=10)

class UserInfo(BaseModel):
    """응답에 포함될 사용자 정보 모델"""
    userId: str
    name: str
    position_code: str | None
    department_code: str | None
    system_role_code: str | None

class TokenResponse(BaseModel):
    """로그인 성공 시 반환될 데이터 모델"""
    accessToken: str
    refreshToken: str
    mustChangePassword: bool
    token_type: str = "bearer"
    user: UserInfo

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

    # 사용자 존재 여부 및 비밀번호 확인 (DB의 'password' 컬럼 사용)
    if not user or not verify_password(login_request.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사번 또는 비밀번호가 일치하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 토큰에 담을 데이터 (사용자 ID와 직책 코드 포함)
    token_data = {"sub": str(user.user_id), "pos": user.position_code}

    # 토큰 생성
    access_token = create_token(token_data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token(token_data, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    # DB에 must_change_password 필드가 없는 경우를 대비하여 안전하게 값을 가져옴
    must_change = getattr(user, 'must_change_password', False)

    # 응답에 포함할 사용자 정보 생성
    user_info = UserInfo(
        userId=str(user.user_id),
        name=user.name,
        position_code=user.position_code,
        department_code=user.department_code,
        system_role_code=user.system_role_code
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
        system_role_code=current_user.system_role_code
    )