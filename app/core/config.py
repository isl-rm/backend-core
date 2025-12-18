from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Backend Core"
    API_V1_STR: str = "/api/v1"

    # MongoDB
    MONGODB_URL: str = "mongodb://root:example@localhost:27017"
    MONGODB_DB_NAME: str ="admin"# "backend_core_db"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",
    ]

    # Logging & Sentry
    ENVIRONMENT: str = "local"  # local, dev, prod
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str | None = None

    # Caching
    # Set to None to disable caching entirely.
    # - Local dev: redis://localhost:6379/0
    # - Docker Compose: redis://redis:6379/0
    REDIS_URL: str | None = "redis://localhost:6379/0"
    # Keep this small to reduce staleness risk; this mainly targets "polling" style reads.
    VITALS_CACHE_TTL_SECONDS: int = 30

    # Security
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_LOGIN_ATTEMPTS: int = 5
    # Default cookie SameSite for refresh tokens. Set to "none" (with HTTPS) if the
    # frontend is on a different domain; keep "lax" for same-site CSRF protection.
    REFRESH_TOKEN_SAMESITE: str = "lax"  # lax, strict, none

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )


settings = Settings()
