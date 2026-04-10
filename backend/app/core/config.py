from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NunuJal API"
    app_env: str = "development"
    frontend_url: str = "https://nunujal.o-r.kr"
    server_port: int = 8028
    google_redirect_uri: str = "https://nunujal.o-r.kr/api/auth/google/callback"
    jwt_secret: str
    jwt_expire_minutes: int = 1440

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore" # config 파일에 정의되지 않은 환경 변수는 무시하도록 설정
    )

    session_secret: str
    google_client_secret: str
    google_client_id: str
    database_url: str
    


@lru_cache
def get_settings() -> Settings:
    return Settings()
