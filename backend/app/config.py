from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://tprm:tprm@localhost:5432/tprm"

    auth_secret: str = "dev-only-secret-change-me"
    admin_api_key: str = "dev-admin-key"

    llm_provider: str = "mock"          # mock | live
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    email_provider: str = "console"     # console | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "tprm-noreply@example.com"

    app_base_url: str = "http://localhost:5173"
    storage_root: str = "./storage"

    magic_link_ttl_minutes: int = 15
    vendor_session_ttl_hours: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
