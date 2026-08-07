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

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

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
