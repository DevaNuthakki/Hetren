from __future__ import annotations

from hvee.core.capability_registry import (
    CapabilityAvailability,
    CapabilityEgressPolicy,
    CapabilityExecutionLocation,
    CapabilityQualificationState,
    CapabilityRegistration,
    CapabilityRegistry,
    ModelAccessTier,
    ModelRuntimeBinding,
    calculate_model_runtime_binding_sha256,
)
from hvee.core.internal_engine import (
    InternalInterventionKind,
    InternalRuntimeCapability,
    calculate_internal_runtime_capability_sha256,
)
from hvee.core.whisper_small_en_portfolio_capability import (
    WhisperSmallEnPortfolioLocation,
    build_whisper_small_en_portfolio_binding,
)


WHISPER_SMALL_EN_REAL_QUALIFICATION_SCHEMA_VERSION = "1.0.0"

WHISPER_SMALL_EN_MODEL_ID = "openai/whisper-small.en"

WHISPER_SMALL_EN_IMMUTABLE_REVISION = "e8727524f962ee844a7319d92be39ac1bd25655a"

WHISPER_SMALL_EN_RUNTIME_KEY = "pytorch_internal_runtime"

WHISPER_SMALL_EN_RUNTIME_VERSION = "1.0.0-foundation"

WHISPER_SMALL_EN_RUNTIME_IDENTITY_SHA256 = (
    "9095b2f05431d0360d78bf2401379071908aaab3bf0ee29a6b3fdde2d2e90246"
)

WHISPER_SMALL_EN_RUNTIME_MODEL_SHA256 = (
    "6014ac49b506df900f66f4aca6b0801eed7245594ace97bcaf73e0ae5b863066"
)

WHISPER_SMALL_EN_CONFIGURATION_SHA256 = (
    None
)


WHISPER_SMALL_EN_CAPTURE_EVIDENCE_SHA256 = (
    "8f70accc0cec747ca82af0174c7dfd371dcdae247f1c48d1ef89b1d4ffed1d0f",
    "053d0a4ff66181ecd0d804d7734ec35dcaa16373ba3e4ee81eeae578563f8627",
    "fd3ee143929458bcd5cd029c9122ce389abd803c6cb8ac21193c5d8713ed0315",
    "4bd02f50d98475312b9f31f71405fe517c09c1c2058014344b80b680a17c5456",
    "c11377937444e86af5beb921e6a008fcf9b511d346c9a1d7e727ac67be2f67ea",
    "9ea2c7b4842f7a8634af80bcb343722da9f98a38cc4dfdfa8fe50ab0c6aed29c",
)


WHISPER_SMALL_EN_ZERO_ABLATION_EVIDENCE_SHA256 = (
    "8f70accc0cec747ca82af0174c7dfd371dcdae247f1c48d1ef89b1d4ffed1d0f",
    "053d0a4ff66181ecd0d804d7734ec35dcaa16373ba3e4ee81eeae578563f8627",
    "fd3ee143929458bcd5cd029c9122ce389abd803c6cb8ac21193c5d8713ed0315",
    "4bd02f50d98475312b9f31f71405fe517c09c1c2058014344b80b680a17c5456",
    "ae9e554895cadd647b199d29f0e0bfeabcb4838141c18a99576af4f5d0389519",
    "09c804ca8536a81ed35e4868219bb7dbeeed630876ce495366283aff0b6940ef",
    "d38859499f4220f6f8ba9db6de58365b1c187f82e72e44501ffc3909d6030b57",
)


_COMMON_CONSTRAINTS = (
    "exact_model_identity_required=true",
    "exact_model_revision_required=true",
    "exact_runtime_identity_required=true",
    "exact_runtime_model_identity_required=true",
    "authorized_internal_access_required=true",
    "raw_tensor_egress=false",
    "research_qualification_scope=true",
    "generalization_established=false",
    "production_qualified=false",
    "root_cause_claim_authorized=false",
    "necessity_claim_authorized=false",
    "sufficiency_claim_authorized=false",
    "universal_model_family_support_claimed=false",
)


def build_real_whisper_small_en_runtime_capability(
) -> InternalRuntimeCapability:
    return InternalRuntimeCapability(
        runtime_key=(
            WHISPER_SMALL_EN_RUNTIME_KEY
        ),
        runtime_version=(
            WHISPER_SMALL_EN_RUNTIME_VERSION
        ),
        runtime_identity_sha256=(
            WHISPER_SMALL_EN_RUNTIME_IDENTITY_SHA256
        ),
        runtime_model_sha256=(
            WHISPER_SMALL_EN_RUNTIME_MODEL_SHA256
        ),
        supported_interventions=(
            InternalInterventionKind
            .CAPTURE_ACTIVATION_SUMMARY,
            InternalInterventionKind
            .ZERO_MODULE_OUTPUT,
        ),
        raw_tensor_egress=False,
    )


def register_real_whisper_small_en_qualified_capabilities(
    *,
    registry: CapabilityRegistry,
    location: WhisperSmallEnPortfolioLocation,
) -> tuple[
    ModelRuntimeBinding,
    tuple[
        CapabilityRegistration,
        CapabilityRegistration,
    ],
]:
    runtime_capability = (
        build_real_whisper_small_en_runtime_capability()
    )

    binding = (
        build_whisper_small_en_portfolio_binding(
            location=location,
            provider_key="openai",
            model_version=(
                WHISPER_SMALL_EN_IMMUTABLE_REVISION
            ),
            runtime_capability=(
                runtime_capability
            ),
            checkpoint_sha256=(
                WHISPER_SMALL_EN_RUNTIME_MODEL_SHA256
            ),
            configuration_sha256=(
                WHISPER_SMALL_EN_CONFIGURATION_SHA256
            ),
        )
    )

    binding_identity = (
        registry.register_binding(
            binding
        )
    )

    expected_identity = (
        calculate_model_runtime_binding_sha256(
            binding
        )
    )

    if (
        binding_identity
        != expected_identity
    ):
        raise RuntimeError(
            "portfolio binding identity mismatch"
        )

    source_capability_sha256 = (
        calculate_internal_runtime_capability_sha256(
            runtime_capability
        )
    )

    capture = CapabilityRegistration(
        capability_key=(
            "internal_engine."
            + InternalInterventionKind
            .CAPTURE_ACTIVATION_SUMMARY
            .value
        ),
        capability_version="1.0.0",
        binding_identity_sha256=(
            binding_identity
        ),
        availability=(
            CapabilityAvailability.AVAILABLE
        ),
        qualification_state=(
            CapabilityQualificationState.QUALIFIED
        ),
        qualification_scope=(
            "whisper-small-en-exact-runtime-"
            "non-perturbing-activation-capture-v1"
        ),
        required_access_tier=(
            ModelAccessTier.AUTHORIZED_INTERNALS
        ),
        execution_location=(
            CapabilityExecutionLocation.PRIVATE_RUNNER
        ),
        egress_policy=(
            CapabilityEgressPolicy.AGGREGATE_ONLY
        ),
        requires_human_approval=False,
        qualification_evidence_sha256=(
            WHISPER_SMALL_EN_CAPTURE_EVIDENCE_SHA256
        ),
        source_capability_sha256=(
            source_capability_sha256
        ),
        constraints=(
            *_COMMON_CONSTRAINTS,
            "non_perturbing_activation_capture_qualified=true",
            "selectors_real_weight_forward_qualified=true",
        ),
    )

    zero_ablation = CapabilityRegistration(
        capability_key=(
            "internal_engine."
            + InternalInterventionKind
            .ZERO_MODULE_OUTPUT
            .value
        ),
        capability_version="1.0.0",
        binding_identity_sha256=(
            binding_identity
        ),
        availability=(
            CapabilityAvailability.AVAILABLE
        ),
        qualification_state=(
            CapabilityQualificationState.QUALIFIED
        ),
        qualification_scope=(
            "whisper-small-en-exact-runtime-"
            "reversible-zero-ablation-v2"
        ),
        required_access_tier=(
            ModelAccessTier.AUTHORIZED_INTERNALS
        ),
        execution_location=(
            CapabilityExecutionLocation.PRIVATE_RUNNER
        ),
        egress_policy=(
            CapabilityEgressPolicy.AGGREGATE_ONLY
        ),
        requires_human_approval=False,
        qualification_evidence_sha256=(
            WHISPER_SMALL_EN_ZERO_ABLATION_EVIDENCE_SHA256
        ),
        source_capability_sha256=(
            source_capability_sha256
        ),
        constraints=(
            *_COMMON_CONSTRAINTS,
            "reversible_zero_ablation_qualified=true",
            "model_state_restoration_required=true",
        ),
    )

    registry.register_capability(
        capture
    )

    registry.register_capability(
        zero_ablation
    )

    return (
        binding,
        (
            capture,
            zero_ablation,
        ),
    )
