from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: Literal[
        "development",
        "test",
        "staging",
        "production",
    ] = Field(
        default="development",
        validation_alias=AliasChoices(
            "HETREN_ENV",
            "OVRIN_ENV",
        ),
    )

    database_url: str = Field(
        validation_alias="DATABASE_URL",
    )

    test_database_url: str | None = Field(
        default=None,
        validation_alias="TEST_DATABASE_URL",
    )

    database_echo: bool = Field(
        default=False,
        validation_alias="DATABASE_ECHO",
    )

    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        validation_alias="HETREN_CORS_ALLOWED_ORIGINS",
    )

    auth_secret_key: SecretStr = Field(
        min_length=32,
        validation_alias="HETREN_AUTH_SECRET_KEY",
    )

    auth_access_token_expire_minutes: int = Field(
        default=15,
        gt=0,
        validation_alias="HETREN_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    auth_refresh_token_expire_days: int = Field(
        default=30,
        gt=0,
        validation_alias="HETREN_AUTH_REFRESH_TOKEN_EXPIRE_DAYS",
    )

    upload_max_audio_bytes: int = Field(
        default=100 * 1024 * 1024,
        gt=0,
        validation_alias="HETREN_UPLOAD_MAX_AUDIO_BYTES",
    )

    upload_max_transcript_bytes: int = Field(
        default=2 * 1024 * 1024,
        gt=0,
        validation_alias="HETREN_UPLOAD_MAX_TRANSCRIPT_BYTES",
    )

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(
        cls,
        value: list[str],
    ) -> list[str]:
        if not value:
            raise ValueError(
                "At least one CORS origin must be configured"
            )

        normalized: list[str] = []

        for origin in value:
            candidate = origin.strip().rstrip("/")

            if (
                candidate == "*"
                or not candidate.startswith(
                    ("http://", "https://")
                )
            ):
                raise ValueError(
                    "CORS origins must be explicit HTTP(S) origins"
                )

            if candidate not in normalized:
                normalized.append(candidate)

        return normalized

    @field_validator("database_url", "test_database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        # Some managed PostgreSQL providers return one of these shorter
        # schemes. Hetren uses psycopg 3 as its SQLAlchemy driver.
        if value.startswith("postgres://"):
            return value.replace(
                "postgres://",
                "postgresql+psycopg://",
                1,
            )

        if value.startswith("postgresql://"):
            return value.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
