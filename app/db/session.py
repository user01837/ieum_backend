from sqlalchemy.orm import sessionmaker
from app.db.database import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI 의존성 주입을 위한 데이터베이스 세션 생성기
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()