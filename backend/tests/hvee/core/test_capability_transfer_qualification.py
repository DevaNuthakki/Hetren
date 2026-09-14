from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from hvee.core.capability_registry import (
    ModelAccessTier,
)
from hvee.core.capability_transfer_qualification import (
    CAPABILITY_TRANSFER_QUALIFICATION_SCHEMA_VERSION,
    STANDARD_BEHAVIORAL_REQUIRED_GATES,
    STANDARD_INTERNAL_CAPTURE_REQUIRED_GATES,
    STANDARD_REVERSIBLE_INTERVENTION_REQUIRED_GATES,
    CapabilityTransferCase,
    CapabilityTransferPack,
    CapabilityTransferQualificationError,
    TransferCapabilityDisposition,
    TransferGateKind,
    TransferGateResult,
    TransferGateStatus,
    TransferPackVerdict,
    build_behavioral_transfer_case,
    build_internal_capture_transfer_case,
    build_reversible_intervention_transfer_case,
    calculate_transfer_case_sha256,
    calculate_transfer_evaluation_sha256,
    evaluate_capability_transfer,
)


def digest(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def gate(
    key: str,
    *,
    status: TransferGateStatus = TransferGateStatus.PASS,
    reason_code: str | None = None,
) -> TransferGateResult:
    kind = TransferGateKind(
        key
    )

    evidence = (
        (
            digest(
                "evidence:"
                + key
                + ":"
                + status.value
            ),
        )
        if status
        is not TransferGateStatus.NOT_RUN
        else ()
    )

    if (
        status
        in {
            TransferGateStatus.FAIL,
            TransferGateStatus.NOT_RUN,
        }
        and reason_code
        is None
    ):
        reason_code = (
            "TEST_REASON"
        )

    return TransferGateResult(
        gate_key=key,
        gate_kind=kind,
        status=status,
        evidence_sha256=evidence,
        reason_code=reason_code,
    )


def passing_results(
    keys: tuple[str, ...],
) -> tuple[
    TransferGateResult,
    ...
]:
    return tuple(
        gate(
            key
        )
        for key in keys
    )


def make_behavioral_case(
    target: str = "target-binding",
):
    return build_behavioral_transfer_case(
        case_key="behavioral-case",
        capability_key="behavioral.compare",
        capability_version="1.0.0",
        source_binding_identity_sha256=(
            digest(
                "source-binding"
            )
        ),
        source_capability_sha256=(
            digest(
                "source-capability"
            )
        ),
        target_binding_identity_sha256=(
            digest(
                target
            )
        ),
    )


def make_internal_case(
    target: str = "target-binding",
):
    return build_internal_capture_transfer_case(
        case_key="capture-case",
        capability_key=(
            "internal_engine."
            "capture_activation_summary"
        ),
        capability_version="1.0.0",
        source_binding_identity_sha256=(
            digest(
                "source-binding"
            )
        ),
        source_capability_sha256=(
            digest(
                "capture-capability"
            )
        ),
        target_binding_identity_sha256=(
            digest(
                target
            )
        ),
    )


def make_intervention_case(
    target: str = "target-binding",
):
    return build_reversible_intervention_transfer_case(
        case_key="intervention-case",
        capability_key=(
            "internal_engine."
            "zero_module_output"
        ),
        capability_version="1.0.0",
        source_binding_identity_sha256=(
            digest(
                "source-binding"
            )
        ),
        source_capability_sha256=(
            digest(
                "intervention-capability"
            )
        ),
        target_binding_identity_sha256=(
            digest(
                target
            )
        ),
    )


class CapabilityTransferQualificationTests(
    unittest.TestCase
):
    def test_schema_version_is_explicit(
        self,
    ):
        self.assertEqual(
            CAPABILITY_TRANSFER_QUALIFICATION_SCHEMA_VERSION,
            "1.0.0",
        )

    def test_behavioral_gate_contract_is_explicit(
        self,
    ):
        self.assertEqual(
            STANDARD_BEHAVIORAL_REQUIRED_GATES,
            (
                "binding_identity",
                "evidence_integrity",
                "capability_discovery",
                "behavioral_baseline",
                "replayability",
                "egress_policy",
            ),
        )

    def test_internal_capture_adds_non_perturbation(
        self,
    ):
        self.assertEqual(
            STANDARD_INTERNAL_CAPTURE_REQUIRED_GATES,
            (
                *STANDARD_BEHAVIORAL_REQUIRED_GATES,
                "non_perturbation",
            ),
        )

    def test_reversible_intervention_requires_restoration(
        self,
    ):
        self.assertEqual(
            STANDARD_REVERSIBLE_INTERVENTION_REQUIRED_GATES,
            (
                *STANDARD_BEHAVIORAL_REQUIRED_GATES,
                "reversibility",
                "state_restoration",
            ),
        )

    def test_transfer_case_hash_is_deterministic(
        self,
    ):
        first = (
            make_behavioral_case()
        )

        second = (
            make_behavioral_case()
        )

        self.assertEqual(
            calculate_transfer_case_sha256(
                first
            ),
            calculate_transfer_case_sha256(
                second
            ),
        )

    def test_passing_gate_requires_evidence(
        self,
    ):
        with self.assertRaises(
            CapabilityTransferQualificationError
        ):
            TransferGateResult(
                gate_key="binding_identity",
                gate_kind=(
                    TransferGateKind.BINDING_IDENTITY
                ),
                status=(
                    TransferGateStatus.PASS
                ),
                evidence_sha256=(),
            )

    def test_behavioral_case_qualifies_on_closed_api(
        self,
    ):
        case = (
            make_behavioral_case()
        )

        result = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=(
                    passing_results(
                        case.required_gate_keys
                    )
                ),
            )
        )

        self.assertEqual(
            result.disposition,
            TransferCapabilityDisposition.QUALIFIED,
        )

        self.assertEqual(
            result.reason_code,
            "ALL_REQUIRED_GATES_PASS",
        )

    def test_internal_capture_is_unavailable_on_closed_api(
        self,
    ):
        case = (
            make_internal_case()
        )

        result = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=(),
            )
        )

        self.assertEqual(
            result.disposition,
            TransferCapabilityDisposition.UNAVAILABLE,
        )

        self.assertEqual(
            result.reason_code,
            "TARGET_ACCESS_TIER_INSUFFICIENT",
        )

    def test_internal_capture_is_unavailable_on_private_inference(
        self,
    ):
        case = (
            make_internal_case()
        )

        result = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.PRIVATE_INFERENCE
                ),
                gate_results=(),
            )
        )

        self.assertEqual(
            result.disposition,
            TransferCapabilityDisposition.UNAVAILABLE,
        )

    def test_internal_capture_qualifies_with_authorized_internals(
        self,
    ):
        case = (
            make_internal_case()
        )

        result = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.AUTHORIZED_INTERNALS
                ),
                gate_results=(
                    passing_results(
                        case.required_gate_keys
                    )
                ),
            )
        )

        self.assertEqual(
            result.disposition,
            TransferCapabilityDisposition.QUALIFIED,
        )

    def test_failed_required_gate_is_unqualified(
        self,
    ):
        case = (
            make_behavioral_case()
        )

        results = list(
            passing_results(
                case.required_gate_keys
            )
        )

        index = (
            case.required_gate_keys.index(
                "behavioral_baseline"
            )
        )

        results[
            index
        ] = gate(
            "behavioral_baseline",
            status=(
                TransferGateStatus.FAIL
            ),
            reason_code=(
                "BEHAVIORAL_TRANSFER_FAILED"
            ),
        )

        result = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=(
                    results
                ),
            )
        )

        self.assertEqual(
            result.disposition,
            TransferCapabilityDisposition.UNQUALIFIED,
        )

        self.assertIn(
            "behavioral_baseline",
            result.reason_code,
        )

    def test_missing_required_gate_is_blocked(
        self,
    ):
        case = (
            make_behavioral_case()
        )

        results = tuple(
            gate(
                key
            )
            for key
            in case.required_gate_keys
            if key
            != "replayability"
        )

        result = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=results,
            )
        )

        self.assertEqual(
            result.disposition,
            TransferCapabilityDisposition.BLOCKED,
        )

        self.assertIn(
            "replayability",
            result.reason_code,
        )

    def test_not_run_required_gate_is_blocked(
        self,
    ):
        case = (
            make_behavioral_case()
        )

        results = list(
            passing_results(
                case.required_gate_keys
            )
        )

        index = (
            case.required_gate_keys.index(
                "replayability"
            )
        )

        results[
            index
        ] = gate(
            "replayability",
            status=(
                TransferGateStatus.NOT_RUN
            ),
            reason_code=(
                "REPLAY_NOT_EXECUTED"
            ),
        )

        result = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=results,
            )
        )

        self.assertEqual(
            result.disposition,
            TransferCapabilityDisposition.BLOCKED,
        )

    def test_required_not_applicable_is_unqualified(
        self,
    ):
        case = (
            make_intervention_case()
        )

        results = list(
            passing_results(
                case.required_gate_keys
            )
        )

        index = (
            case.required_gate_keys.index(
                "state_restoration"
            )
        )

        results[
            index
        ] = gate(
            "state_restoration",
            status=(
                TransferGateStatus.NOT_APPLICABLE
            ),
        )

        result = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.AUTHORIZED_INTERNALS
                ),
                gate_results=results,
            )
        )

        self.assertEqual(
            result.disposition,
            TransferCapabilityDisposition.UNQUALIFIED,
        )

    def test_evaluation_hash_is_order_independent(
        self,
    ):
        case = (
            make_behavioral_case()
        )

        forward = (
            passing_results(
                case.required_gate_keys
            )
        )

        reverse = tuple(
            reversed(
                forward
            )
        )

        first = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=forward,
            )
        )

        second = (
            evaluate_capability_transfer(
                case=case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=reverse,
            )
        )

        self.assertEqual(
            calculate_transfer_evaluation_sha256(
                first
            ),
            calculate_transfer_evaluation_sha256(
                second
            ),
        )

    def test_all_qualified_pack_passes(
        self,
    ):
        target = (
            "shared-target"
        )

        behavioral_case = (
            make_behavioral_case(
                target
            )
        )

        internal_case = (
            make_internal_case(
                target
            )
        )

        behavioral = (
            evaluate_capability_transfer(
                case=behavioral_case,
                target_access_tier=(
                    ModelAccessTier.AUTHORIZED_INTERNALS
                ),
                gate_results=(
                    passing_results(
                        behavioral_case.required_gate_keys
                    )
                ),
            )
        )

        internal = (
            evaluate_capability_transfer(
                case=internal_case,
                target_access_tier=(
                    ModelAccessTier.AUTHORIZED_INTERNALS
                ),
                gate_results=(
                    passing_results(
                        internal_case.required_gate_keys
                    )
                ),
            )
        )

        pack = CapabilityTransferPack(
            target_binding_identity_sha256=(
                digest(
                    target
                )
            ),
            evaluations=(
                internal,
                behavioral,
            ),
        )

        self.assertEqual(
            pack.verdict,
            TransferPackVerdict.PASS,
        )

    def test_closed_api_pack_can_be_partial(
        self,
    ):
        target = (
            "api-target"
        )

        behavioral_case = (
            make_behavioral_case(
                target
            )
        )

        internal_case = (
            make_internal_case(
                target
            )
        )

        behavioral = (
            evaluate_capability_transfer(
                case=behavioral_case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=(
                    passing_results(
                        behavioral_case.required_gate_keys
                    )
                ),
            )
        )

        internal = (
            evaluate_capability_transfer(
                case=internal_case,
                target_access_tier=(
                    ModelAccessTier.CLOSED_API
                ),
                gate_results=(),
            )
        )

        pack = CapabilityTransferPack(
            target_binding_identity_sha256=(
                digest(
                    target
                )
            ),
            evaluations=(
                behavioral,
                internal,
            ),
        )

        self.assertEqual(
            behavioral.disposition,
            TransferCapabilityDisposition.QUALIFIED,
        )

        self.assertEqual(
            internal.disposition,
            TransferCapabilityDisposition.UNAVAILABLE,
        )

        self.assertEqual(
            pack.verdict,
            TransferPackVerdict.PARTIAL,
        )

    def test_pack_snapshot_is_order_independent(
        self,
    ):
        target = (
            "stable-target"
        )

        behavioral_case = (
            make_behavioral_case(
                target
            )
        )

        internal_case = (
            make_internal_case(
                target
            )
        )

        behavioral = (
            evaluate_capability_transfer(
                case=behavioral_case,
                target_access_tier=(
                    ModelAccessTier.AUTHORIZED_INTERNALS
                ),
                gate_results=(
                    passing_results(
                        behavioral_case.required_gate_keys
                    )
                ),
            )
        )

        internal = (
            evaluate_capability_transfer(
                case=internal_case,
                target_access_tier=(
                    ModelAccessTier.AUTHORIZED_INTERNALS
                ),
                gate_results=(
                    passing_results(
                        internal_case.required_gate_keys
                    )
                ),
            )
        )

        first = CapabilityTransferPack(
            target_binding_identity_sha256=(
                digest(
                    target
                )
            ),
            evaluations=(
                behavioral,
                internal,
            ),
        )

        second = CapabilityTransferPack(
            target_binding_identity_sha256=(
                digest(
                    target
                )
            ),
            evaluations=(
                internal,
                behavioral,
            ),
        )

        self.assertEqual(
            first.snapshot_payload(),
            second.snapshot_payload(),
        )

        self.assertEqual(
            first.snapshot_sha256(),
            second.snapshot_sha256(),
        )

    def test_contract_contains_no_whisper_hardcoding(
        self,
    ):
        path = Path(
            "backend/hvee/core/"
            "capability_transfer_qualification.py"
        )

        source = path.read_text(
            encoding="utf-8"
        ).lower()

        self.assertNotIn(
            "whisper",
            source,
        )

        self.assertNotIn(
            "small.en",
            source,
        )

        self.assertNotIn(
            "medium.en",
            source,
        )

        self.assertNotIn(
            "large-v3",
            source,
        )


if __name__ == "__main__":
    unittest.main()
