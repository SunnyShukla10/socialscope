from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List


class Settings(BaseSettings):
    LOCAL_ADMIN_EMAIL: str = "admin@socialscope.local"
    LOCAL_ADMIN_PASSWORD: str = "password123"
    BUILD_ID: str = "pilot-local"
    DATABASE_URL: str = "postgresql+asyncpg://socialscope:socialscope@localhost:5434/socialscope"
    REDIS_URL: str = "redis://localhost:6381/0"
    SECRET_KEY: str = "change-me-in-production"
    XPOZ_API_KEY: str = ""
    SOCIALVAULT_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    XPOZ_REQUESTS_PER_PERIOD: int = Field(default=28, gt=0)
    XPOZ_RATE_PERIOD_SECONDS: float = Field(default=60.0, gt=0)
    XPOZ_MAX_CONCURRENCY: int = Field(default=2, gt=0)
    XPOZ_OPERATION_TIMEOUT_SECONDS: float = Field(default=300.0, gt=0)
    XPOZ_NO_PROGRESS_TIMEOUT_SECONDS: float = Field(default=300.0, gt=0)
    XPOZ_MAX_PAGES: int = Field(default=100, gt=0)
    XPOZ_RETRY_TIME_BUDGET_SECONDS: float = Field(default=60.0, ge=0)
    XPOZ_MAX_REPEATED_502: int = Field(default=2, gt=0)
    SOCIALVAULT_MAX_CONCURRENCY: int = Field(default=5, gt=0)
    SOCIALVAULT_REQUESTS_PER_PERIOD: int = Field(default=8, gt=0)
    SOCIALVAULT_RATE_PERIOD_SECONDS: float = Field(default=1.0, gt=0)
    SOCIALVAULT_REQUEST_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    SOCIALVAULT_NO_PROGRESS_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0)
    SOCIALVAULT_MAX_PAGES: int = Field(default=100, gt=0)
    SOCIALVAULT_RETRY_TIME_BUDGET_SECONDS: float = Field(default=60.0, ge=0)
    SOCIALVAULT_MAX_REPEATED_502: int = Field(default=3, gt=0)
    SOCIALVAULT_PAGINATION_404_RETRIES: int = Field(default=1, ge=0, le=2)
    SOCIALVAULT_EARLY_RESTART_MAX_PAGES: int = Field(default=5, ge=0)
    SOCIALVAULT_EARLY_RESTART_MAX_TARGET_RATIO: float = Field(default=0.3, gt=0, lt=1)
    COLLECTION_CANCELLATION_POLL_SECONDS: float = Field(default=1.0, gt=0)
    COLLECTION_ABANDONED_JOB_STALE_SECONDS: float = Field(default=900.0, gt=0)
    COLLECTION_ABANDONED_RECONCILE_INTERVAL_SECONDS: float = Field(default=60.0, gt=0)
    COLLECTION_ABANDONED_INSPECT_TIMEOUT_SECONDS: float = Field(default=1.0, gt=0)
    COLLECTION_ABANDONED_RECONCILE_BATCH_SIZE: int = Field(default=100, gt=0)
    PROVIDER_MAX_RETRIES: int = Field(default=3, ge=0)
    PROVIDER_RETRY_BASE_SECONDS: float = Field(default=1.0, ge=0)
    PROVIDER_RETRY_MAX_SECONDS: float = Field(default=30.0, ge=0)
    COLLECTION_WORKER_CONCURRENCY: int = Field(default=1, gt=0)
    QUERY_SAFE_DEFAULT_MAX_LENGTH: int = Field(default=200, gt=0)
    XPOZ_QUERY_MAX_LENGTH: int = Field(default=200, gt=0)
    SOCIALVAULT_QUERY_MAX_LENGTH: int = Field(default=200, gt=0)
    QUERY_LENGTH_WARNING_RATIO: float = Field(default=0.8, gt=0, le=1)
    CORS_ORIGINS: str = "http://localhost:3002,http://127.0.0.1:3002"
    LOG_LEVEL: str = "INFO"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str) -> str:
        return v

    def get_cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
