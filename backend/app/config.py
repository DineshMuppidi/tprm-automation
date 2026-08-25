from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://tprm:tprm@localhost:5432/tprm"

    auth_secret: str = "dev-only-secret-change-me-before-any-real-deployment"
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

    # Phase 2 monitoring providers — each is mock (default, offline, free)
    # or live (real API calls; see docs/architecture/integrations.md)
    cert_registry_provider: str = "mock"
    breach_provider: str = "mock"
    news_provider: str = "mock"
    financial_provider: str = "mock"

    hibp_api_key: str = ""
    nvd_api_key: str = ""
    newsapi_api_key: str = ""

    # Alert escalation SLA (Phase 2 spec §3): minutes before an
    # unacknowledged alert of this severity auto-escalates
    escalation_sla_minutes_critical: int = 60
    escalation_sla_minutes_high: int = 240
    alert_suppression_default_days: int = 90

    # Phase 5 hardening
    rate_limit_requests_per_minute: int = 120
    staff_session_ttl_hours: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
