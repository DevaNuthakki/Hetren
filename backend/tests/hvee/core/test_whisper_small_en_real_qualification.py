from __future__ import annotations

import unittest

from hvee.core.capability_registry import (
    CapabilityAvailability,
    CapabilityEgressPolicy,
    CapabilityQualificationState,
    CapabilityRegistry,
    ModelAccessTier,
    calculate_model_runtime_binding_sha256,
)
from hvee.core.internal_engine import (
    InternalInterventionKind,
)
from hvee.core.whisper_small_en_portfolio_capability import (
    WhisperSmallEnPortfolioLocation,
)
from hvee.core.whisper_small_en_real_qualification import (
    WHISPER_SMALL_EN_CAPTURE_EVIDENCE_SHA256,
    WHISPER_SMALL_EN_CONFIGURATION_SHA256,
    WHISPER_SMALL_EN_IMMUTABLE_REVISION,
    WHISPER_SMALL_EN_MODEL_ID,
    WHISPER_SMALL_EN_RUNTIME_IDENTITY_SHA256,
    WHISPER_SMALL_EN_RUNTIME_KEY,
    WHISPER_SMALL_EN_RUNTIME_MODEL_SHA256,
    WHISPER_SMALL_EN_RUNTIME_VERSION,
    WHISPER_SMALL_EN_ZERO_ABLATION_EVIDENCE_SHA256,
    build_real_whisper_small_en_runtime_capability,
    register_real_whisper_small_en_qualified_capabilities,
)


def location(
    tenant_key: str = "tenant-a",
) -> WhisperSmallEnPortfolioLocation:
    return WhisperSmallEnPortfolioLocation(
        tenant_key=tenant_key,
        project_key="reliability",
        system_key="voice-system",
        component_key="speech-model",
        version_key="whisper-small-en",
    )


class RealWhisperQualificationTests(
    unittest.TestCase
):
    def test_exact_model_identity(
        self,
    ):
        self.assertEqual(
            WHISPER_SMALL_EN_MODEL_ID,
            "openai/whisper-small.en",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_IMMUTABLE_REVISION,
            "e8727524f962ee844a7319d92be39ac1bd25655a",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_RUNTIME_MODEL_SHA256,
            "6014ac49b506df900f66f4aca6b0801eed7245594ace97bcaf73e0ae5b863066",
        )

    def test_exact_runtime_identity(
        self,
    ):
        self.assertEqual(
            WHISPER_SMALL_EN_RUNTIME_KEY,
            "pytorch_internal_runtime",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_RUNTIME_VERSION,
            "1.0.0-foundation",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_RUNTIME_IDENTITY_SHA256,
            "9095b2f05431d0360d78bf2401379071908aaab3bf0ee29a6b3fdde2d2e90246",
        )

    def test_runtime_capability_is_exact(
        self,
    ):
        capability = (
            build_real_whisper_small_en_runtime_capability()
        )

        self.assertEqual(
            capability.runtime_identity_sha256,
            WHISPER_SMALL_EN_RUNTIME_IDENTITY_SHA256,
        )

        self.assertEqual(
            capability.runtime_model_sha256,
            WHISPER_SMALL_EN_RUNTIME_MODEL_SHA256,
        )

        self.assertEqual(
            capability.supported_interventions,
            (
                InternalInterventionKind
                .CAPTURE_ACTIVATION_SUMMARY,
                InternalInterventionKind
                .ZERO_MODULE_OUTPUT,
            ),
        )

        self.assertFalse(
            capability.raw_tensor_egress
        )

    def test_evidence_chains_are_capability_specific(
        self,
    ):
        self.assertEqual(
            len(
                WHISPER_SMALL_EN_CAPTURE_EVIDENCE_SHA256
            ),
            6,
        )

        self.assertEqual(
            len(
                WHISPER_SMALL_EN_ZERO_ABLATION_EVIDENCE_SHA256
            ),
            7,
        )

        self.assertNotEqual(
            WHISPER_SMALL_EN_CAPTURE_EVIDENCE_SHA256,
            WHISPER_SMALL_EN_ZERO_ABLATION_EVIDENCE_SHA256,
        )

    def test_registers_exactly_two_capabilities(
        self,
    ):
        registry = CapabilityRegistry()

        binding, registrations = (
            register_real_whisper_small_en_qualified_capabilities(
                registry=registry,
                location=location(),
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
            len(
                registrations
            ),
            2,
        )

        self.assertEqual(
            {
                item.capability_key
                for item in registrations
            },
            {
                "internal_engine.capture_activation_summary",
                "internal_engine.zero_module_output",
            },
        )

        self.assertEqual(
            binding.model_version,
            WHISPER_SMALL_EN_IMMUTABLE_REVISION,
        )

        self.assertEqual(
            binding.runtime_identity_sha256,
            WHISPER_SMALL_EN_RUNTIME_IDENTITY_SHA256,
        )

        self.assertEqual(
            binding.runtime_model_sha256,
            WHISPER_SMALL_EN_RUNTIME_MODEL_SHA256,
        )

        self.assertEqual(
            binding.configuration_sha256,
            WHISPER_SMALL_EN_CONFIGURATION_SHA256,
        )

    def test_capabilities_are_qualified_not_production_claims(
        self,
    ):
        registry = CapabilityRegistry()

        _, registrations = (
            register_real_whisper_small_en_qualified_capabilities(
                registry=registry,
                location=location(),
            )
        )

        required_false = {
            "generalization_established=false",
            "production_qualified=false",
            "root_cause_claim_authorized=false",
            "necessity_claim_authorized=false",
            "sufficiency_claim_authorized=false",
            "universal_model_family_support_claimed=false",
        }

        for item in registrations:
            self.assertEqual(
                item.availability,
                CapabilityAvailability.AVAILABLE,
            )

            self.assertEqual(
                item.qualification_state,
                CapabilityQualificationState.QUALIFIED,
            )

            self.assertEqual(
                item.required_access_tier,
                ModelAccessTier.AUTHORIZED_INTERNALS,
            )

            self.assertEqual(
                item.egress_policy,
                CapabilityEgressPolicy.AGGREGATE_ONLY,
            )

            self.assertTrue(
                required_false.issubset(
                    set(
                        item.constraints
                    )
                )
            )

    def test_registration_is_idempotent(
        self,
    ):
        registry = CapabilityRegistry()

        first = (
            register_real_whisper_small_en_qualified_capabilities(
                registry=registry,
                location=location(),
            )
        )

        second = (
            register_real_whisper_small_en_qualified_capabilities(
                registry=registry,
                location=location(),
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

    def test_tenant_isolation_remains_generic(
        self,
    ):
        first_registry = CapabilityRegistry()
        second_registry = CapabilityRegistry()

        first, _ = (
            register_real_whisper_small_en_qualified_capabilities(
                registry=first_registry,
                location=location(
                    "tenant-a"
                ),
            )
        )

        second, _ = (
            register_real_whisper_small_en_qualified_capabilities(
                registry=second_registry,
                location=location(
                    "tenant-b"
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

    def test_registry_snapshot_is_deterministic(
        self,
    ):
        first_registry = CapabilityRegistry()
        second_registry = CapabilityRegistry()

        register_real_whisper_small_en_qualified_capabilities(
            registry=first_registry,
            location=location(),
        )

        register_real_whisper_small_en_qualified_capabilities(
            registry=second_registry,
            location=location(),
        )

        self.assertEqual(
            first_registry.snapshot_sha256(),
            second_registry.snapshot_sha256(),
        )


if __name__ == "__main__":
    unittest.main()
