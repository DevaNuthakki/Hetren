from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace

from hvee.core.capability_registry import (
    CAPABILITY_REGISTRY_SCHEMA_VERSION,
    CapabilityAvailability,
    CapabilityEgressPolicy,
    CapabilityExecutionLocation,
    CapabilityQualificationState,
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityRegistryError,
    ComponentKind,
    ModelAccessTier,
    ModelRuntimeBinding,
    PortfolioComponentIdentity,
    calculate_capability_registration_sha256,
    calculate_model_runtime_binding_sha256,
    calculate_portfolio_component_identity_sha256,
    register_internal_runtime_capabilities,
)
from hvee.core.internal_engine import (
    InternalInterventionKind,
    InternalRuntimeCapability,
    calculate_internal_runtime_capability_sha256,
)


def digest(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def make_component(
    index: int = 0,
    *,
    tenant_key: str = "tenant-a",
    project_key: str = "project-a",
    system_key: str = "system-a",
) -> PortfolioComponentIdentity:
    return PortfolioComponentIdentity(
        tenant_key=tenant_key,
        project_key=project_key,
        system_key=system_key,
        component_key=f"model-{index}",
        component_kind=ComponentKind.MODEL,
        version_key=f"version-{index}",
    )


def make_binding(
    index: int = 0,
    *,
    tenant_key: str = "tenant-a",
    access_tier: ModelAccessTier = (
        ModelAccessTier.AUTHORIZED_INTERNALS
    ),
    runtime_key: str = "pytorch_internal_runtime",
    runtime_version: str = "1.0.0-foundation",
) -> ModelRuntimeBinding:
    return ModelRuntimeBinding(
        binding_key=f"binding-{index}",
        binding_version="1.0.0",
        component=make_component(
            index,
            tenant_key=tenant_key,
        ),
        provider_key="openai",
        model_key=f"whisper-small-en-{index}",
        model_version=f"checkpoint-{index}",
        runtime_key=runtime_key,
        runtime_version=runtime_version,
        runtime_identity_sha256=(
            digest(
                f"runtime-{tenant_key}-{index}"
            )
        ),
        runtime_model_sha256=(
            digest(
                f"model-{tenant_key}-{index}"
            )
        ),
        access_tier=access_tier,
        checkpoint_sha256=(
            digest(
                f"checkpoint-{tenant_key}-{index}"
            )
        ),
        configuration_sha256=(
            digest(
                f"configuration-{tenant_key}-{index}"
            )
        ),
    )


def make_capability(
    binding: ModelRuntimeBinding,
    *,
    capability_key: str = "behavioral.compare",
    required_access_tier: ModelAccessTier = (
        ModelAccessTier.CLOSED_API
    ),
    qualification_state: CapabilityQualificationState = (
        CapabilityQualificationState.QUALIFIED
    ),
    availability: CapabilityAvailability = (
        CapabilityAvailability.AVAILABLE
    ),
) -> CapabilityRegistration:
    return CapabilityRegistration(
        capability_key=capability_key,
        capability_version="1.0.0",
        binding_identity_sha256=(
            calculate_model_runtime_binding_sha256(
                binding
            )
        ),
        availability=availability,
        qualification_state=qualification_state,
        qualification_scope="product-contract-test",
        required_access_tier=required_access_tier,
        execution_location=(
            CapabilityExecutionLocation.PRIVATE_RUNNER
        ),
        egress_policy=(
            CapabilityEgressPolicy.AGGREGATE_ONLY
        ),
        requires_human_approval=False,
        qualification_evidence_sha256=(
            (
                digest(
                    "qualification-evidence"
                ),
            )
            if (
                qualification_state
                is CapabilityQualificationState.QUALIFIED
            )
            else ()
        ),
        reason_code=(
            "fixture_unavailable"
            if (
                availability
                is CapabilityAvailability.UNAVAILABLE
            )
            else None
        ),
        constraints=(
            "test_constraint=true",
        ),
    )


class CapabilityRegistryTests(
    unittest.TestCase
):
    def test_schema_version_is_explicit(
        self,
    ):
        self.assertEqual(
            CAPABILITY_REGISTRY_SCHEMA_VERSION,
            "1.0.0",
        )

    def test_component_identity_is_deterministic(
        self,
    ):
        component = make_component()

        first = (
            calculate_portfolio_component_identity_sha256(
                component
            )
        )

        second = (
            calculate_portfolio_component_identity_sha256(
                component
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            len(first),
            64,
        )

    def test_tenant_boundary_changes_component_identity(
        self,
    ):
        first = make_component(
            tenant_key="tenant-a"
        )

        second = make_component(
            tenant_key="tenant-b"
        )

        self.assertNotEqual(
            calculate_portfolio_component_identity_sha256(
                first
            ),
            calculate_portfolio_component_identity_sha256(
                second
            ),
        )

    def test_model_binding_requires_model_component(
        self,
    ):
        binding = make_binding()

        non_model_component = replace(
            binding.component,
            component_kind=ComponentKind.AGENT,
        )

        with self.assertRaises(
            CapabilityRegistryError
        ):
            replace(
                binding,
                component=non_model_component,
            )

    def test_binding_identity_changes_with_runtime_identity(
        self,
    ):
        first = make_binding()

        second = replace(
            first,
            runtime_identity_sha256=(
                digest(
                    "different-runtime"
                )
            ),
        )

        self.assertNotEqual(
            calculate_model_runtime_binding_sha256(
                first
            ),
            calculate_model_runtime_binding_sha256(
                second
            ),
        )

    def test_exact_binding_registration_is_idempotent(
        self,
    ):
        registry = CapabilityRegistry()
        binding = make_binding()

        first = registry.register_binding(
            binding
        )

        second = registry.register_binding(
            binding
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            registry.binding_count,
            1,
        )

    def test_conflicting_binding_fails_closed(
        self,
    ):
        registry = CapabilityRegistry()
        binding = make_binding()

        registry.register_binding(
            binding
        )

        changed = replace(
            binding,
            runtime_identity_sha256=(
                digest(
                    "conflicting-runtime"
                )
            ),
        )

        with self.assertRaises(
            CapabilityRegistryError
        ):
            registry.register_binding(
                changed
            )

    def test_registry_has_no_fixed_small_model_ceiling(
        self,
    ):
        registry = CapabilityRegistry()

        count = 512

        for index in range(
            count
        ):
            binding = make_binding(
                index,
                tenant_key="portfolio-tenant",
                access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                runtime_key="provider_api",
                runtime_version="1.0.0",
            )

            registry.register_binding(
                binding
            )

            registry.register_capability(
                make_capability(
                    binding
                )
            )

        self.assertEqual(
            registry.binding_count,
            count,
        )

        self.assertEqual(
            registry.capability_count,
            count,
        )

    def test_same_component_names_are_isolated_by_tenant(
        self,
    ):
        registry = CapabilityRegistry()

        first = make_binding(
            tenant_key="tenant-a"
        )

        second = make_binding(
            tenant_key="tenant-b"
        )

        first_identity = (
            registry.register_binding(
                first
            )
        )

        second_identity = (
            registry.register_binding(
                second
            )
        )

        self.assertNotEqual(
            first_identity,
            second_identity,
        )

        self.assertEqual(
            registry.binding_count,
            2,
        )

    def test_capability_cannot_exceed_binding_access_tier(
        self,
    ):
        registry = CapabilityRegistry()

        binding = make_binding(
            access_tier=(
                ModelAccessTier.CLOSED_API
            )
        )

        registry.register_binding(
            binding
        )

        capability = make_capability(
            binding,
            capability_key=(
                "internal_engine.capture_activation_summary"
            ),
            required_access_tier=(
                ModelAccessTier.AUTHORIZED_INTERNALS
            ),
        )

        with self.assertRaises(
            CapabilityRegistryError
        ):
            registry.register_capability(
                capability
            )

    def test_qualified_capability_requires_evidence(
        self,
    ):
        binding = make_binding()

        with self.assertRaises(
            CapabilityRegistryError
        ):
            CapabilityRegistration(
                capability_key="behavioral.compare",
                capability_version="1.0.0",
                binding_identity_sha256=(
                    calculate_model_runtime_binding_sha256(
                        binding
                    )
                ),
                availability=(
                    CapabilityAvailability.AVAILABLE
                ),
                qualification_state=(
                    CapabilityQualificationState.QUALIFIED
                ),
                qualification_scope="test",
                required_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                execution_location=(
                    CapabilityExecutionLocation.PRIVATE_RUNNER
                ),
                egress_policy=(
                    CapabilityEgressPolicy.AGGREGATE_ONLY
                ),
                requires_human_approval=False,
                qualification_evidence_sha256=(),
            )

    def test_unavailable_capability_requires_reason(
        self,
    ):
        binding = make_binding()

        with self.assertRaises(
            CapabilityRegistryError
        ):
            CapabilityRegistration(
                capability_key="behavioral.compare",
                capability_version="1.0.0",
                binding_identity_sha256=(
                    calculate_model_runtime_binding_sha256(
                        binding
                    )
                ),
                availability=(
                    CapabilityAvailability.UNAVAILABLE
                ),
                qualification_state=(
                    CapabilityQualificationState.UNQUALIFIED
                ),
                qualification_scope="test",
                required_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                execution_location=(
                    CapabilityExecutionLocation.PRIVATE_RUNNER
                ),
                egress_policy=(
                    CapabilityEgressPolicy.NO_EGRESS
                ),
                requires_human_approval=False,
            )

    def test_require_capability_fails_closed_when_unqualified(
        self,
    ):
        registry = CapabilityRegistry()
        binding = make_binding()

        binding_identity = (
            registry.register_binding(
                binding
            )
        )

        capability = make_capability(
            binding,
            qualification_state=(
                CapabilityQualificationState.UNQUALIFIED
            ),
        )

        registry.register_capability(
            capability
        )

        with self.assertRaises(
            CapabilityRegistryError
        ):
            registry.require_qualified_capability(
                binding_identity_sha256=(
                    binding_identity
                ),
                capability_key=(
                    capability.capability_key
                ),
                capability_version=(
                    capability.capability_version
                ),
            )

    def test_require_capability_fails_closed_when_unavailable(
        self,
    ):
        registry = CapabilityRegistry()
        binding = make_binding()

        binding_identity = (
            registry.register_binding(
                binding
            )
        )

        capability = make_capability(
            binding,
            availability=(
                CapabilityAvailability.UNAVAILABLE
            ),
        )

        registry.register_capability(
            capability
        )

        with self.assertRaises(
            CapabilityRegistryError
        ):
            registry.require_qualified_capability(
                binding_identity_sha256=(
                    binding_identity
                ),
                capability_key=(
                    capability.capability_key
                ),
                capability_version=(
                    capability.capability_version
                ),
            )

    def test_qualified_available_capability_resolves(
        self,
    ):
        registry = CapabilityRegistry()
        binding = make_binding()

        binding_identity = (
            registry.register_binding(
                binding
            )
        )

        capability = make_capability(
            binding
        )

        registry.register_capability(
            capability
        )

        resolved = (
            registry.require_qualified_capability(
                binding_identity_sha256=(
                    binding_identity
                ),
                capability_key=(
                    capability.capability_key
                ),
                capability_version=(
                    capability.capability_version
                ),
            )
        )

        self.assertEqual(
            resolved,
            capability,
        )

    def test_capabilities_are_returned_in_stable_order(
        self,
    ):
        registry = CapabilityRegistry()
        binding = make_binding()

        binding_identity = (
            registry.register_binding(
                binding
            )
        )

        for capability_key in (
            "z.capability",
            "a.capability",
            "m.capability",
        ):
            registry.register_capability(
                make_capability(
                    binding,
                    capability_key=(
                        capability_key
                    ),
                )
            )

        ordered = (
            registry.capabilities_for_binding(
                binding_identity
            )
        )

        self.assertEqual(
            [
                capability.capability_key
                for capability in ordered
            ],
            [
                "a.capability",
                "m.capability",
                "z.capability",
            ],
        )

    def test_snapshot_is_insertion_order_independent(
        self,
    ):
        first_registry = (
            CapabilityRegistry()
        )

        second_registry = (
            CapabilityRegistry()
        )

        bindings = [
            make_binding(
                index
            )
            for index in range(
                5
            )
        ]

        for binding in bindings:
            first_registry.register_binding(
                binding
            )

            first_registry.register_capability(
                make_capability(
                    binding
                )
            )

        for binding in reversed(
            bindings
        ):
            second_registry.register_binding(
                binding
            )

            second_registry.register_capability(
                make_capability(
                    binding
                )
            )

        self.assertEqual(
            first_registry.snapshot_payload(),
            second_registry.snapshot_payload(),
        )

        self.assertEqual(
            first_registry.snapshot_sha256(),
            second_registry.snapshot_sha256(),
        )

    def test_capability_hash_is_content_sensitive(
        self,
    ):
        binding = make_binding()

        first = make_capability(
            binding
        )

        second = replace(
            first,
            constraints=(
                "different_constraint=true",
            ),
        )

        self.assertNotEqual(
            calculate_capability_registration_sha256(
                first
            ),
            calculate_capability_registration_sha256(
                second
            ),
        )

    def test_internal_runtime_capability_bridge(
        self,
    ):
        registry = CapabilityRegistry()

        binding = make_binding()

        runtime_capability = (
            InternalRuntimeCapability(
                runtime_key=(
                    binding.runtime_key
                ),
                runtime_version=(
                    binding.runtime_version
                ),
                runtime_identity_sha256=(
                    binding.runtime_identity_sha256
                ),
                runtime_model_sha256=(
                    binding.runtime_model_sha256
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
                raw_tensor_egress=False,
            )
        )

        evidence = (
            digest(
                "internal-runtime-qualification"
            ),
        )

        registrations = (
            register_internal_runtime_capabilities(
                registry=registry,
                binding=binding,
                runtime_capability=(
                    runtime_capability
                ),
                qualification_state=(
                    CapabilityQualificationState.QUALIFIED
                ),
                qualification_scope=(
                    "research-qualified"
                ),
                qualification_evidence_sha256=(
                    evidence
                ),
            )
        )

        expected_keys = {
            (
                "internal_engine."
                + intervention.value
            )
            for intervention in (
                runtime_capability
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

        self.assertEqual(
            registry.binding_count,
            1,
        )

        self.assertEqual(
            registry.capability_count,
            2,
        )

        expected_source_sha256 = (
            calculate_internal_runtime_capability_sha256(
                runtime_capability
            )
        )

        for registration in registrations:
            self.assertEqual(
                registration.source_capability_sha256,
                expected_source_sha256,
            )

            self.assertEqual(
                registration.egress_policy,
                CapabilityEgressPolicy.AGGREGATE_ONLY,
            )

            self.assertEqual(
                registration.required_access_tier,
                ModelAccessTier.AUTHORIZED_INTERNALS,
            )

    def test_internal_bridge_rejects_runtime_mismatch(
        self,
    ):
        registry = CapabilityRegistry()
        binding = make_binding()

        runtime_capability = (
            InternalRuntimeCapability(
                runtime_key="different_runtime",
                runtime_version=(
                    binding.runtime_version
                ),
                runtime_identity_sha256=(
                    binding.runtime_identity_sha256
                ),
                runtime_model_sha256=(
                    binding.runtime_model_sha256
                ),
                supported_interventions=(
                    (
                        InternalInterventionKind
                        .CAPTURE_ACTIVATION_SUMMARY
                    ),
                ),
                raw_tensor_egress=False,
            )
        )

        with self.assertRaises(
            CapabilityRegistryError
        ):
            register_internal_runtime_capabilities(
                registry=registry,
                binding=binding,
                runtime_capability=(
                    runtime_capability
                ),
                qualification_state=(
                    CapabilityQualificationState.QUALIFIED
                ),
                qualification_scope=(
                    "research-qualified"
                ),
                qualification_evidence_sha256=(
                    (
                        digest(
                            "qualification"
                        ),
                    )
                ),
            )

    def test_internal_bridge_rejects_closed_api_access(
        self,
    ):
        registry = CapabilityRegistry()

        binding = make_binding(
            access_tier=(
                ModelAccessTier.CLOSED_API
            )
        )

        runtime_capability = (
            InternalRuntimeCapability(
                runtime_key=(
                    binding.runtime_key
                ),
                runtime_version=(
                    binding.runtime_version
                ),
                runtime_identity_sha256=(
                    binding.runtime_identity_sha256
                ),
                runtime_model_sha256=(
                    binding.runtime_model_sha256
                ),
                supported_interventions=(
                    (
                        InternalInterventionKind
                        .CAPTURE_ACTIVATION_SUMMARY
                    ),
                ),
                raw_tensor_egress=False,
            )
        )

        with self.assertRaises(
            CapabilityRegistryError
        ):
            register_internal_runtime_capabilities(
                registry=registry,
                binding=binding,
                runtime_capability=(
                    runtime_capability
                ),
                qualification_state=(
                    CapabilityQualificationState.QUALIFIED
                ),
                qualification_scope=(
                    "research-qualified"
                ),
                qualification_evidence_sha256=(
                    (
                        digest(
                            "qualification"
                        ),
                    )
                ),
            )


if __name__ == "__main__":
    unittest.main()
