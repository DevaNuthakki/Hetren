from __future__ import annotations

from dataclasses import dataclass

from hvee.core.capability_registry import (
    CapabilityQualificationState,
    CapabilityRegistration,
    CapabilityRegistry,
    ComponentKind,
    ModelAccessTier,
    ModelRuntimeBinding,
    PortfolioComponentIdentity,
    register_internal_runtime_capabilities,
)
from hvee.core.internal_engine import (
    InternalRuntimeCapability,
)


WHISPER_SMALL_EN_PORTFOLIO_BINDING_KEY = (
    "whisper_small_en_internal_binding"
)

WHISPER_SMALL_EN_PORTFOLIO_BINDING_VERSION = (
    "1.0.0"
)

WHISPER_SMALL_EN_MODEL_KEY = (
    "openai/whisper-small.en"
)

WHISPER_SMALL_EN_EXPECTED_RUNTIME_KEY = (
    "pytorch_internal_runtime"
)

WHISPER_SMALL_EN_EXPECTED_RUNTIME_VERSION = (
    "1.0.0-foundation"
)


class WhisperSmallEnPortfolioCapabilityError(
    ValueError
):
    pass


def _require_nonempty(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise WhisperSmallEnPortfolioCapabilityError(
            f"{field_name} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise WhisperSmallEnPortfolioCapabilityError(
            f"{field_name} must not be empty"
        )

    return normalized


@dataclass(frozen=True)
class WhisperSmallEnPortfolioLocation:
    tenant_key: str
    project_key: str
    system_key: str
    component_key: str
    version_key: str

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "tenant_key",
            "project_key",
            "system_key",
            "component_key",
            "version_key",
        ):
            _require_nonempty(
                getattr(
                    self,
                    field_name,
                ),
                field_name=field_name,
            )


def _validate_runtime_capability(
    runtime_capability: InternalRuntimeCapability,
) -> None:
    if not isinstance(
        runtime_capability,
        InternalRuntimeCapability,
    ):
        raise WhisperSmallEnPortfolioCapabilityError(
            "runtime_capability must be an InternalRuntimeCapability"
        )

    if (
        runtime_capability.runtime_key
        != WHISPER_SMALL_EN_EXPECTED_RUNTIME_KEY
    ):
        raise WhisperSmallEnPortfolioCapabilityError(
            "Whisper small.en binding requires the qualified "
            "PyTorch internal runtime key"
        )

    if (
        runtime_capability.runtime_version
        != WHISPER_SMALL_EN_EXPECTED_RUNTIME_VERSION
    ):
        raise WhisperSmallEnPortfolioCapabilityError(
            "Whisper small.en binding requires the qualified "
            "PyTorch internal runtime version"
        )

    if runtime_capability.raw_tensor_egress is not False:
        raise WhisperSmallEnPortfolioCapabilityError(
            "Whisper small.en binding must deny raw tensor egress"
        )


def build_whisper_small_en_portfolio_binding(
    *,
    location: WhisperSmallEnPortfolioLocation,
    provider_key: str,
    model_version: str,
    runtime_capability: InternalRuntimeCapability,
    checkpoint_sha256: str | None = None,
    configuration_sha256: str | None = None,
) -> ModelRuntimeBinding:
    if not isinstance(
        location,
        WhisperSmallEnPortfolioLocation,
    ):
        raise WhisperSmallEnPortfolioCapabilityError(
            "location must be a WhisperSmallEnPortfolioLocation"
        )

    _validate_runtime_capability(
        runtime_capability
    )

    provider_key = _require_nonempty(
        provider_key,
        field_name="provider_key",
    )

    model_version = _require_nonempty(
        model_version,
        field_name="model_version",
    )

    component = PortfolioComponentIdentity(
        tenant_key=location.tenant_key,
        project_key=location.project_key,
        system_key=location.system_key,
        component_key=location.component_key,
        component_kind=ComponentKind.MODEL,
        version_key=location.version_key,
    )

    return ModelRuntimeBinding(
        binding_key=(
            WHISPER_SMALL_EN_PORTFOLIO_BINDING_KEY
        ),
        binding_version=(
            WHISPER_SMALL_EN_PORTFOLIO_BINDING_VERSION
        ),
        component=component,
        provider_key=provider_key,
        model_key=(
            WHISPER_SMALL_EN_MODEL_KEY
        ),
        model_version=model_version,
        runtime_key=(
            runtime_capability.runtime_key
        ),
        runtime_version=(
            runtime_capability.runtime_version
        ),
        runtime_identity_sha256=(
            runtime_capability.runtime_identity_sha256
        ),
        runtime_model_sha256=(
            runtime_capability.runtime_model_sha256
        ),
        access_tier=(
            ModelAccessTier.AUTHORIZED_INTERNALS
        ),
        checkpoint_sha256=(
            checkpoint_sha256
        ),
        configuration_sha256=(
            configuration_sha256
        ),
    )


def register_whisper_small_en_internal_capabilities(
    *,
    registry: CapabilityRegistry,
    location: WhisperSmallEnPortfolioLocation,
    provider_key: str,
    model_version: str,
    runtime_capability: InternalRuntimeCapability,
    qualification_state: CapabilityQualificationState,
    qualification_scope: str,
    qualification_evidence_sha256: tuple[str, ...],
    checkpoint_sha256: str | None = None,
    configuration_sha256: str | None = None,
) -> tuple[
    ModelRuntimeBinding,
    tuple[
        CapabilityRegistration,
        ...,
    ],
]:
    _validate_runtime_capability(
        runtime_capability
    )

    binding = (
        build_whisper_small_en_portfolio_binding(
            location=location,
            provider_key=provider_key,
            model_version=model_version,
            runtime_capability=runtime_capability,
            checkpoint_sha256=checkpoint_sha256,
            configuration_sha256=configuration_sha256,
        )
    )

    registrations = (
        register_internal_runtime_capabilities(
            registry=registry,
            binding=binding,
            runtime_capability=runtime_capability,
            qualification_state=(
                qualification_state
            ),
            qualification_scope=(
                qualification_scope
            ),
            qualification_evidence_sha256=(
                qualification_evidence_sha256
            ),
        )
    )

    return (
        binding,
        registrations,
    )
