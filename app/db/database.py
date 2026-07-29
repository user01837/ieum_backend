from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base
from app.core.config import settings


DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)


engine = create_engine(
    DATABASE_URL,
    echo=True,
    # 커넥션을 꺼내 쓰기 전에 살아있는지 확인한다. 세션을 짧게 열고 닫는 구조에서는
    # MySQL wait_timeout으로 죽은 커넥션을 잡을 확률이 높아지므로 필수에 가깝다.
    pool_pre_ping=True,
    # MySQL 기본 wait_timeout(8시간)보다 짧게 잡아 유휴 커넥션을 주기적으로 재생성한다.
    pool_recycle=3600,
)

Base = declarative_base()


def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("DB 연결 성공:", result.fetchone())

    except Exception as e:
        print("DB 연결 실패:", e)