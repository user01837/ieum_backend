from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base
from app.core.config import settings


DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)


engine = create_engine(
    DATABASE_URL,
    echo=True
)

Base = declarative_base()


def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("DB 연결 성공:", result.fetchone())

    except Exception as e:
        print("DB 연결 실패:", e)