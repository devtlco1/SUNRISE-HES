from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    project_name: str = "sunrise-hes-platform"
    company_name: str = (
        "Abraj Al Anwar Contracting, General Trading and Commercial Agencies Company"
    )
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://sunrise:sunrise@postgres:5432/sunrise_hes"
    redis_url: str = "redis://redis:6379/0"
    redis_queue_stream_name: str = "hes:dispatch"
    redis_queue_consumer_group_name: str = "hes-worker-group"
    redis_queue_claim_timeout_seconds: int = 300
    redis_queue_stale_claim_threshold_seconds: int = 300
    redis_queue_dead_letter_stream_name: str | None = None
    redis_queue_validate_on_startup: bool = False
    redis_queue_ensure_stream_on_startup: bool = False
    redis_queue_ensure_consumer_group_on_startup: bool = False
    queue_backend: str = "mock"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    jwt_secret_key: str = "change-me-before-production-with-at-least-32-characters"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_issuer: str = "sunrise-hes-platform"
    internal_api_token: str = "sunrise-internal-token-change-me"
    bootstrap_super_admin_username: str | None = None
    bootstrap_super_admin_email: str | None = None
    bootstrap_super_admin_full_name: str = "Platform Super Admin"
    bootstrap_super_admin_password: str | None = Field(default=None, min_length=12)
    enable_runtime_relay_control_gurux_mapper: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator(
        "bootstrap_super_admin_username",
        "bootstrap_super_admin_email",
        "bootstrap_super_admin_password",
        mode="before",
    )
    @classmethod
    def empty_strings_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("bootstrap_super_admin_password")
    @classmethod
    def validate_bootstrap_password(cls, value: str | None) -> str | None:
        if value is not None and len(value) < 12:
            raise ValueError("Bootstrap super admin password must be at least 12 characters.")
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def normalize_cors_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            value = value.split(",")

        normalized = [origin.strip().rstrip("/") for origin in value if origin.strip()]
        if not normalized:
            raise ValueError("cors_allowed_origins must include at least one origin.")
        return normalized

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT secret key must be at least 32 characters.")
        return value

    @field_validator("internal_api_token")
    @classmethod
    def validate_internal_api_token(cls, value: str) -> str:
        if len(value) < 16:
            raise ValueError("Internal API token must be at least 16 characters.")
        return value

    @field_validator("queue_backend")
    @classmethod
    def normalize_queue_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("queue_backend must not be empty.")
        return normalized

    @field_validator("redis_queue_stream_name")
    @classmethod
    def validate_redis_queue_stream_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("redis_queue_stream_name must not be empty.")
        return normalized

    @field_validator("redis_queue_consumer_group_name")
    @classmethod
    def validate_redis_queue_consumer_group_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("redis_queue_consumer_group_name must not be empty.")
        return normalized

    @field_validator("redis_queue_claim_timeout_seconds")
    @classmethod
    def validate_redis_queue_claim_timeout_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("redis_queue_claim_timeout_seconds must be greater than zero.")
        return value

    @field_validator("redis_queue_stale_claim_threshold_seconds")
    @classmethod
    def validate_redis_queue_stale_claim_threshold_seconds(cls, value: int) -> int:
        if value < 0:
            raise ValueError("redis_queue_stale_claim_threshold_seconds must not be negative.")
        return value

    @field_validator("redis_queue_dead_letter_stream_name", mode="before")
    @classmethod
    def normalize_redis_queue_dead_letter_stream_name(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @model_validator(mode="after")
    def validate_redis_transport_startup_policy(self) -> "Settings":
        if (
            self.redis_queue_ensure_stream_on_startup
            or self.redis_queue_ensure_consumer_group_on_startup
        ) and not self.redis_queue_validate_on_startup:
            raise ValueError(
                "redis_queue_validate_on_startup must be enabled when Redis startup ensure "
                "flags are enabled."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
