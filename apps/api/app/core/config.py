from functools import lru_cache

from pydantic import Field, field_validator
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
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    jwt_secret_key: str = "change-me-before-production-with-at-least-32-characters"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_issuer: str = "sunrise-hes-platform"
    internal_api_token: str = "sunrise-internal-token-change-me"
    bootstrap_super_admin_username: str | None = None
    bootstrap_super_admin_email: str | None = None
    bootstrap_super_admin_full_name: str = "Platform Super Admin"
    bootstrap_super_admin_password: str | None = Field(default=None, min_length=12)

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
