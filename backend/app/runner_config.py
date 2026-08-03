from functools import lru_cache
from typing import Literal, Self

from pydantic import (
    AliasChoices,
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from app.config import PROJECT_ROOT


def _runner_environment_alias(
    setting_name: str,
) -> AliasChoices:
    return AliasChoices(
        f"HETREN_RUNNER_{setting_name}",
        f"OVRIN_RUNNER_{setting_name}",
    )


class LocalRunnerSettings(BaseSettings):
    """
    Configuration for the standalone local or CI runner process.

    The runner communicates with Hetren exclusively through the HTTP API
    and does not require direct database access.
    """

    api_url: HttpUrl = Field(
        default="http://127.0.0.1:8000",
        validation_alias=_runner_environment_alias("API_URL"),
    )

    credential: SecretStr = Field(
        min_length=1,
        validation_alias=_runner_environment_alias("CREDENTIAL"),
    )

    runner_version: str = Field(
        default="0.1.0",
        min_length=1,
        max_length=100,
        validation_alias=_runner_environment_alias("VERSION"),
    )

    capabilities: list[str] = Field(
        default_factory=lambda: ["asr"],
        min_length=1,
        max_length=50,
        validation_alias=_runner_environment_alias("CAPABILITIES"),
    )

    request_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        validation_alias=(
            _runner_environment_alias("REQUEST_TIMEOUT_SECONDS")
        ),
    )

    lease_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        validation_alias=_runner_environment_alias("LEASE_SECONDS"),
    )

    poll_interval_seconds: float = Field(
        default=5.0,
        gt=0,
        le=300,
        validation_alias=(
            _runner_environment_alias("POLL_INTERVAL_SECONDS")
        ),
    )

    lease_renewal_interval_seconds: float = Field(
        default=60.0,
        gt=0,
        le=1800,
        validation_alias=(
            _runner_environment_alias("LEASE_RENEWAL_INTERVAL_SECONDS")
        ),
    )

    control_poll_interval_seconds: float = Field(
        default=2.0,
        gt=0,
        le=300,
        validation_alias=(
            _runner_environment_alias("CONTROL_POLL_INTERVAL_SECONDS")
        ),
    )

    execution_timeout_seconds: float = Field(
        default=3600.0,
        gt=0,
        le=86400,
        validation_alias=(
            _runner_environment_alias("EXECUTION_TIMEOUT_SECONDS")
        ),
    )

    asr_provider: Literal[
        "mock_local",
        "faster_whisper",
    ] = Field(
        default="mock_local",
        validation_alias=_runner_environment_alias("ASR_PROVIDER"),
    )

    asr_model: str = Field(
        default="mock-asr-foundation",
        min_length=1,
        max_length=200,
        validation_alias=_runner_environment_alias("ASR_MODEL"),
    )

    asr_device: str = Field(
        default="cpu",
        min_length=1,
        max_length=100,
        validation_alias=_runner_environment_alias("ASR_DEVICE"),
    )

    asr_compute_type: str = Field(
        default="int8",
        min_length=1,
        max_length=100,
        validation_alias=(
            _runner_environment_alias("ASR_COMPUTE_TYPE")
        ),
    )

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "asr_provider",
        mode="before",
    )
    @classmethod
    def normalize_asr_provider(
        cls,
        value,
    ):
        if not isinstance(value, str):
            return value

        normalized = (
            value.strip()
            .lower()
            .replace("-", "_")
        )

        if normalized == "mock":
            return "mock_local"

        return normalized

    @field_validator("asr_model")
    @classmethod
    def normalize_asr_model(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Runner ASR model must not be empty."
            )

        return normalized

    @field_validator(
        "asr_device",
        "asr_compute_type",
    )
    @classmethod
    def normalize_asr_runtime_value(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        if not normalized:
            raise ValueError(
                "Runner ASR runtime settings must "
                "not be empty."
            )

        return normalized

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

    @model_validator(mode="after")
    def validate_runner_intervals(self) -> Self:
        if (
            self.lease_renewal_interval_seconds
            >= self.lease_seconds
        ):
            raise ValueError(
                "Runner lease-renewal interval must be "
                "shorter than the job lease duration."
            )

        if (
            self.control_poll_interval_seconds
            >= self.lease_renewal_interval_seconds
        ):
            raise ValueError(
                "Runner control polling must be faster "
                "than lease renewal."
            )

        return self

    @property
    def api_base_url(self) -> str:
        return str(self.api_url).rstrip("/")


@lru_cache
def get_local_runner_settings() -> LocalRunnerSettings:
    return LocalRunnerSettings()
