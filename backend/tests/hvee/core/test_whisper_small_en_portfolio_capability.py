from __future__ import annotations

import hashlib
import unittest

from hvee.core.capability_registry import (
    CapabilityEgressPolicy,
    CapabilityQualificationState,
    CapabilityRegistry,
    ComponentKind,
    ModelAccessTier,
    calculate_model_runtime_binding_sha256,
)
from hvee.core.internal_engine import (
    InternalInterventionKind,
    InternalRuntimeCapability,
    calculate_internal_runtime_capability_sha256,
)
from hvee.core.whisper_small_en_portfolio_capability import (
    WHISPER_SMALL_EN_EXPECTED_RUNTIME_KEY,
    WHISPER_SMALL_EN_EXPECTED_RUNTIME_VERSION,
    WHISPER_SMALL_EN_MODEL_KEY,
    WHISPER_SMALL_EN_PORTFOLIO_BINDING_KEY,
    WHISPER_SMALL_EN_PORTFOLIO_BINDING_VERSION,
    WhisperSmallEnPortfolioCapabilityError,
    WhisperSmallEnPortfolioLocation,
    build_whisper_small_en_portfolio_binding,
    register_whisper_small_en_internal_capabilities,
)


def digest(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def make_location(
    *,
    tenant_key: str = "tenant-a",
    system_key: str = "voice-system-a",
) -> WhisperSmallEnPortfolioLocation:
    return WhisperSmallEnPortfolioLocation(
        tenant_key=tenant_key,
        project_key="speech-project",
        system_key=system_key,
        component_key="asr-model",
        version_key="small-en-v1",
    )


def make_runtime_capability(
    *,
    runtime_key: str = (
        WHISPER_SMALL_EN_EXPECTED_RUNTIME_KEY
    ),
    runtime_version: str = (
        WHISPER_SMALL_EN_EXPECTED_RUNTIME_VERSION
    ),
    raw_tensor_egress: bool = False,
) -> InternalRuntimeCapability:
    return InternalRuntimeCapability(
        runtime_key=runtime_key,
        runtime_version=runtime_version,
        runtime_identity_sha256=(
            digest(
                "qualified-whisper-runtime"
            )
        ),
        runtime_model_sha256=(
            digest(
                "qualified-whisper-model"
            )
        ),
        supported_interventions=(
            (
                InternalInterventionKind
                .CAPTURE_ACTIVATION_SUMMARY
            ),
            (
                InternalInterventionKind
                .ZERO_MODULE_OUTPUT
            ),
        ),
        raw_tensor_egress=(
            raw_tensor_egress
        ),
    )


class WhisperSmallEnPortfolioCapabilityTests(
    unittest.TestCase
):
    def test_identity_constants_are_explicit(
        self,
    ):
        self.assertEqual(
            WHISPER_SMALL_EN_PORTFOLIO_BINDING_KEY,
            "whisper_small_en_internal_binding",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_PORTFOLIO_BINDING_VERSION,
            "1.0.0",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_MODEL_KEY,
            "openai/whisper-small.en",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_EXPECTED_RUNTIME_KEY,
            "pytorch_internal_runtime",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_EXPECTED_RUNTIME_VERSION,
            "1.0.0-foundation",
        )

    def test_builds_model_portfolio_binding(
        self,
    ):
        capability = (
            make_runtime_capability()
        )

        binding = (
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location()
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    capability
                ),
            )
        )

        self.assertEqual(
            binding.component.component_kind,
            ComponentKind.MODEL,
        )

        self.assertEqual(
            binding.model_key,
            "openai/whisper-small.en",
        )

        self.assertEqual(
            binding.runtime_key,
            capability.runtime_key,
        )

        self.assertEqual(
            binding.runtime_version,
            capability.runtime_version,
        )

        self.assertEqual(
            binding.runtime_identity_sha256,
            capability.runtime_identity_sha256,
        )

        self.assertEqual(
            binding.runtime_model_sha256,
            capability.runtime_model_sha256,
        )

        self.assertEqual(
            binding.access_tier,
            ModelAccessTier.AUTHORIZED_INTERNALS,
        )

    def test_tenant_identity_changes_binding_identity(
        self,
    ):
        capability = (
            make_runtime_capability()
        )

        first = (
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location(
                        tenant_key="tenant-a"
                    )
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    capability
                ),
            )
        )

        second = (
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location(
                        tenant_key="tenant-b"
                    )
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    capability
                ),
            )
        )

        self.assertNotEqual(
            calculate_model_runtime_binding_sha256(
                first
            ),
            calculate_model_runtime_binding_sha256(
                second
            ),
        )

    def test_system_identity_changes_binding_identity(
        self,
    ):
        capability = (
            make_runtime_capability()
        )

        first = (
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location(
                        system_key="voice-agent-a"
                    )
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    capability
                ),
            )
        )

        second = (
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location(
                        system_key="voice-agent-b"
                    )
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    capability
                ),
            )
        )

        self.assertNotEqual(
            calculate_model_runtime_binding_sha256(
                first
            ),
            calculate_model_runtime_binding_sha256(
                second
            ),
        )

    def test_registration_bridges_runtime_capabilities(
        self,
    ):
        registry = CapabilityRegistry()

        capability = (
            make_runtime_capability()
        )

        evidence = (
            digest(
                "whisper-binding-evidence"
            ),
        )

        binding, registrations = (
            register_whisper_small_en_internal_capabilities(
                registry=registry,
                location=(
                    make_location()
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    capability
                ),
                qualification_state=(
                    CapabilityQualificationState.QUALIFIED
                ),
                qualification_scope=(
                    "whisper-small-en-qualified-binding-v1"
                ),
                qualification_evidence_sha256=(
                    evidence
                ),
            )
        )

        self.assertEqual(
            registry.binding_count,
            1,
        )

        self.assertEqual(
            registry.capability_count,
            2,
        )

        self.assertEqual(
            len(registrations),
            2,
        )

        expected_keys = {
            (
                "internal_engine."
                + intervention.value
            )
            for intervention in (
                capability
                .supported_interventions
            )
        }

        self.assertEqual(
            {
                item.capability_key
                for item in registrations
            },
            expected_keys,
        )

        source_sha = (
            calculate_internal_runtime_capability_sha256(
                capability
            )
        )

        binding_sha = (
            calculate_model_runtime_binding_sha256(
                binding
            )
        )

        for registration in registrations:
            self.assertEqual(
                registration.binding_identity_sha256,
                binding_sha,
            )

            self.assertEqual(
                registration.source_capability_sha256,
                source_sha,
            )

            self.assertEqual(
                registration.egress_policy,
                CapabilityEgressPolicy.AGGREGATE_ONLY,
            )

            self.assertEqual(
                registration.required_access_tier,
                ModelAccessTier.AUTHORIZED_INTERNALS,
            )

    def test_registration_is_idempotent(
        self,
    ):
        registry = CapabilityRegistry()

        kwargs = {
            "registry": registry,
            "location": make_location(),
            "provider_key": "openai",
            "model_version": "small.en",
            "runtime_capability": (
                make_runtime_capability()
            ),
            "qualification_state": (
                CapabilityQualificationState.QUALIFIED
            ),
            "qualification_scope": (
                "whisper-small-en-qualified-binding-v1"
            ),
            "qualification_evidence_sha256": (
                digest(
                    "whisper-binding-evidence"
                ),
            ),
        }

        first = (
            register_whisper_small_en_internal_capabilities(
                **kwargs
            )
        )

        second = (
            register_whisper_small_en_internal_capabilities(
                **kwargs
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            registry.binding_count,
            1,
        )

        self.assertEqual(
            registry.capability_count,
            2,
        )

    def test_wrong_runtime_key_fails_closed(
        self,
    ):
        with self.assertRaises(
            WhisperSmallEnPortfolioCapabilityError
        ):
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location()
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    make_runtime_capability(
                        runtime_key="other-runtime"
                    )
                ),
            )

    def test_wrong_runtime_version_fails_closed(
        self,
    ):
        with self.assertRaises(
            WhisperSmallEnPortfolioCapabilityError
        ):
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location()
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    make_runtime_capability(
                        runtime_version="other-version"
                    )
                ),
            )

    def test_raw_tensor_egress_fails_closed(
        self,
    ):
        with self.assertRaises(
            WhisperSmallEnPortfolioCapabilityError
        ):
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location()
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    make_runtime_capability(
                        raw_tensor_egress=True
                    )
                ),
            )

    def test_checkpoint_and_configuration_identity_are_preserved(
        self,
    ):
        checkpoint_sha = digest(
            "checkpoint"
        )

        configuration_sha = digest(
            "configuration"
        )

        binding = (
            build_whisper_small_en_portfolio_binding(
                location=(
                    make_location()
                ),
                provider_key="openai",
                model_version="small.en",
                runtime_capability=(
                    make_runtime_capability()
                ),
                checkpoint_sha256=(
                    checkpoint_sha
                ),
                configuration_sha256=(
                    configuration_sha
                ),
            )
        )

        self.assertEqual(
            binding.checkpoint_sha256,
            checkpoint_sha,
        )

        self.assertEqual(
            binding.configuration_sha256,
            configuration_sha,
        )


if __name__ == "__main__":
    unittest.main()
