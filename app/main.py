from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import test_connection
from app.api.routers import auth, department, user

app = FastAPI()

# --- CORS 미들웨어 설정 ---
# 프론트엔드(http://localhost:5173)에서의 요청을 허용하기 위함입니다.
origins = [
    "http://localhost:5173",
    # 필요에 따라 다른 출처(origin)를 추가할 수 있습니다.
    # 예: "http://localhost:3000", "https://your-frontend-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 허용할 출처 목록
    allow_credentials=True,      # 쿠키를 포함한 요청 허용
    allow_methods=["*"],         # 모든 HTTP 메소드 허용
    allow_headers=["*"],         # 모든 HTTP 헤더 허용
)

test_connection()

# --- 라우터 포함 ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(department.router, prefix="/departments", tags=["Departments"])
app.include_router(user.router, prefix="/users", tags=["Users"])

@app.get("/")
def root():
    return {"message": "Hello IEUM Backend"}