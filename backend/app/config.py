from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agenticinventory"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Groq LLM
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_LIGHTWEIGHT_MODEL: str = "llama-3.1-8b-instant"
    GROQ_TEMPERATURE: float = 0.3
    GROQ_MAX_TOKENS: int = 1024

    # Intelligence APIs
    NEWS_API_KEY: str = ""
    OPENWEATHER_API_KEY: str = ""
    CALENDARIFIC_API_KEY: str = ""
    INTELLIGENCE_DEFAULT_LOCATION: str = "New York,US"

    # SMTP Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "AgenticInventory AI"
    ADMIN_NOTIFICATION_EMAIL: str = ""
    # Used to build deep-links in admin notification emails (per spec 003-email-redesign US2 FR-003).
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    # When set, every supplier purchase-order email is sent to this address
    # regardless of category mapping. Useful for demo / staging where the
    # category supplier emails are placeholders.
    SUPPLIER_OVERRIDE_EMAIL: str = "gohil.rohitbhai@maqsoftware.com"

    # App
    APP_NAME: str = "AgenticInventory AI"
    DEBUG: bool = False

    # Autonomous monitoring loop
    AUTONOMOUS_LOOP_ENABLED: bool = True
    AUTONOMOUS_LOOP_INTERVAL_SECONDS: int = 300
    AUTONOMOUS_AUTO_ORDER_ENABLED: bool = True
    # Small pause between per-item pipelines so the 8B Instant model has
    # time to refresh its per-minute token budget (TPM). Each item makes
    # ~4 LLM calls (~2k tokens); without spacing we burst past Groq's TPM.
    PIPELINE_ITEM_DELAY_SECONDS: float = 6.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
