from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import test_connection
from app.api.routers import auth, department, user, petition, task, project, upload, admin, ai, dashboard, knowledge, chat, notification, chat_ws, home

app = FastAPI()
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(notification.router, prefix="/notifications", tags=["Notifications"])
app.include_router(chat_ws.router, tags=["Chat WebSocket"])

# --- CORS 미들웨어 설정 ---
# 프론트엔드(http://localhost:5173)에서의 요청을 허용하기 위함입니다.
origins = [
    "http://localhost:5173",
    # 필요에 따라 다른 출처(origin)를 추가할 수 있습니다.
    # 예: "http://localhost:3000", "https://your-frontend-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app",  # 모든 Vercel 프리뷰 도메인 허용
    allow_origins=[
        "http://localhost:5173",
        "http://15.165.117.26",
        "https://ggieum.site",
        "https://www.ggieum.site",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

test_connection()

# --- 라우터 포함 ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(department.router, prefix="/departments", tags=["Departments"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge"])
app.include_router(project.router, prefix="/projects", tags=["Projects"])
app.include_router(petition.router, prefix="/petitions", tags=["Petitions"])
app.include_router(task.router, prefix="/tasks", tags=["Tasks"])
app.include_router(upload.router, prefix="/upload", tags=["File Upload"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(ai.router, prefix="/ai", tags=["AI"])
app.include_router(home.router, prefix="/home", tags=["Home"])

@app.get("/")
def root():
    return {"message": "Hello IEUM Backend"}