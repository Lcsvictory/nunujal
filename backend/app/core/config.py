from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NunuJal API"
    app_env: str = "development"
    frontend_url: str = "https://nunujal.o-r.kr"
    local_frontend_url: str = "http://localhost:5073"
    server_port: int = 8028
    google_redirect_uri: str = "https://nunujal.o-r.kr/api/auth/google/callback"
    jwt_secret: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    contribution_ai_provider: str = "google_gemini"
    ollama_base_url: str = "http://nunujal.o-r.kr:12812"
    gemini_api_key: str | None = None
    contribution_model_name: str = "gemini-2.5-flash"
    google_genai_thinking_level: str = "HIGH"
    google_genai_thinking_budget: int | None = -1
    google_genai_use_response_schema: bool = True
    contribution_prompt_version: str = "v1"
    contribution_policy_version: str = "v1"
    contribution_request_timeout_seconds: int = 600
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "ap-northeast-2"
    s3_bucket_name: str | None = None
    s3_upload_prefix: str = "uploads"
    s3_presigned_expire_seconds: int = 300
    max_upload_total_bytes: int = 50 * 1024 * 1024

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
