from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Backend Core"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = ""  # local, dev, prod (from .env)

    # MongoDB (from .env)
    MONGODB_URL: str = ""
    MONGODB_DB_NAME: str = ""

    # CORS (from .env, comma-separated)
    BACKEND_CORS_ORIGINS: List[str] = []

    # Logging & Sentry
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str | None = None

    # Caching (from .env, set empty to disable)
    REDIS_URL: str | None = None
    VITALS_CACHE_TTL_SECONDS: int = 30

    # Security (from .env)
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_LOGIN_ATTEMPTS: int = 5
    REFRESH_TOKEN_SAMESITE: str = "lax"  # lax, strict, none

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )


settings = Settings()
