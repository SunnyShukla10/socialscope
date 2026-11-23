from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator
from typing import List, Literal
from urllib.parse import urlsplit


class Settings(BaseSettings):
    ENV: Literal['development', 'production'] = 'development'
    LOCAL_ADMIN_EMAIL: str = "admin@socialscope.local"
    LOCAL_ADMIN_PASSWORD: str = "password123"
    BUILD_ID: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://socialscope:socialscope@localhost:5434/socialscope"
    REDIS_URL: str = "redis://localhost:6381/0"
    SECRET_KEY: str = "development-only-change-me-before-hosting"
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

    @model_validator(mode='after')
    def validate_production_settings(self):
        if self.ENV != 'production':
            return self
        secret = self.SECRET_KEY.strip()
        if len(secret) < 32 or any(marker in secret.casefold() for marker in
                                  ('change-me', 'replace_with', 'generate_with')):
            raise ValueError('Production requires an independent signing secret of at least 32 characters')
        if any(ord(character) < 32 for character in self.CORS_ORIGINS):
            raise ValueError('Production CORS origins cannot contain control characters')
        origins = self.get_cors_origins()
        if not origins:
            raise ValueError('Production requires an explicit HTTPS browser origin')
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                    or parsed.password is not None or parsed.path or parsed.query or parsed.fragment
                    or any(character.isspace() for character in origin)
                    or '*' in origin or 'YOUR_' in origin.upper() or 'REPLACE_' in origin.upper()):
                raise ValueError('Production CORS origins must be HTTPS origins without paths or placeholders')
            # Accessing port also validates its numeric form and valid range.
            _ = parsed.port
        return self

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore", "hide_input_in_errors": True}


settings = Settings()
