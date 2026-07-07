from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    JWT_SECRET: str

    AI_SERVER: str

    class Config:
        env_file = ".env"

settings = Settings()

# 사용할 때에는 다음과 같음
# 어느 파일에서든 밑과 같이 사용하면 됨
# from app.core.config import settings

# print(settings.DB_HOST)