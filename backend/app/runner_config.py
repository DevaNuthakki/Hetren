from functools import lru_cache

from pydantic import (
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from app.config import PROJECT_ROOT


class LocalRunnerSettings(BaseSettings):
    """
    Configuration for the standalone local or CI runner process.

    The runner communicates with Ovrin exclusively through the HTTP API
    and does not require direct database access.
    """

    api_url: HttpUrl = Field(
        default="http://127.0.0.1:8000",
        validation_alias="OVRIN_RUNNER_API_URL",
    )

    credential: SecretStr = Field(
        min_length=1,
        validation_alias="OVRIN_RUNNER_CREDENTIAL",
    )

    runner_version: str = Field(
        default="0.1.0",
        min_length=1,
        max_length=100,
        validation_alias="OVRIN_RUNNER_VERSION",
    )

    capabilities: list[str] = Field(
        default_factory=lambda: ["asr"],
        min_length=1,
        max_length=50,
        validation_alias="OVRIN_RUNNER_CAPABILITIES",
    )

    request_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        validation_alias=(
            "OVRIN_RUNNER_REQUEST_TIMEOUT_SECONDS"
        ),
    )

    lease_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        validation_alias="OVRIN_RUNNER_LEASE_SECONDS",
    )

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("runner_version")
    @classmethod
    def normalize_runner_version(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Runner version must not be empty."
            )

        return normalized

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(
        cls,
        values: list[str],
    ) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                raise ValueError(
                    "Runner capabilities must contain text values."
                )

            capability = value.strip().lower()

            if not capability:
                raise ValueError(
                    "Runner capabilities must not be empty."
                )

            if len(capability) > 100:
                raise ValueError(
                    "Runner capabilities must not exceed "
                    "100 characters."
                )

            if capability not in seen:
                normalized.append(capability)
                seen.add(capability)

        if not normalized:
            raise ValueError(
                "At least one runner capability is required."
            )

        return normalized

    @property
    def api_base_url(self) -> str:
        return str(self.api_url).rstrip("/")


@lru_cache
def get_local_runner_settings() -> LocalRunnerSettings:
    return LocalRunnerSettings()
