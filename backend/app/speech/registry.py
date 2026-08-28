import os

from app.speech.base import ASRProvider
from app.speech.faster_whisper_provider import (
    FasterWhisperASRProvider,
)
from app.speech.mock_provider import MockASRProvider


def _get_product_environment_value(
    setting_name: str,
    default: str,
) -> str:
    hetren_value = os.getenv(f"HETREN_{setting_name}")

    if hetren_value is not None:
        return hetren_value

    # Compatibility for pre-Hetren deployments.
    return os.getenv(
        f"OVRIN_{setting_name}",
        default,
    )


def get_asr_provider(
    provider_name: str | None = None,
    *,
    model_name: str | None = None,
    device: str = "cpu",
    compute_type: str = "int8_float32",
) -> ASRProvider:
    """
    Build an explicitly configured ASR provider.

    Environment fallback remains for existing synchronous application
    workflows. The standalone runner supplies validated settings
    directly instead.
    """
    raw_provider_name = (
        provider_name
        if provider_name is not None
        else _get_product_environment_value(
            "ASR_PROVIDER",
            "mock_local",
        )
    )
    normalized_provider = (
        raw_provider_name.strip()
        .lower()
        .replace("-", "_")
    )

    if normalized_provider == "mock":
        normalized_provider = "mock_local"

    configured_model = (
        model_name.strip()
        if model_name is not None
        and model_name.strip()
        else _get_product_environment_value(
            "ASR_MODEL",
            "",
        ).strip()
    )

    if normalized_provider == "mock_local":
        return MockASRProvider(
            default_model_name=(
                configured_model
                or "mock-asr-foundation"
            ),
        )

    if normalized_provider == "faster_whisper":
        return FasterWhisperASRProvider(
            default_model_name=(
                configured_model
                or "large-v3-turbo"
            ),
            device=device,
            compute_type=compute_type,
        )

    raise ValueError(
        "Unsupported ASR provider: "
        f"{normalized_provider}. "
        "Supported providers: mock_local, "
        "faster_whisper"
    )
