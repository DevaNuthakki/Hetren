from __future__ import annotations

import copy
import math

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.decision import (
    ClaimAssessment,
    CriticalAssessment,
    DecisionInputs,
    DecisionResult,
    DecisionVerdict,
    EvidenceAssessment,
    IntegrityAssessment,
    decide,
)
from hvee.core.decision_evidence import (
    DECISION_EVIDENCE_SCHEMA_VERSION,
    build_decision_evidence_bundle,
    calculate_policy_sha256,
    verify_decision_evidence_bundle,
)
from hvee.core.evidence_readiness import EvidenceTarget


PROVENANCE_SHA256 = "a" * 64
OBSERVATION_SHA256 = "b" * 64


def _policy_snapshot() -> dict[str, object]:
    return {
        "max_normalized_wer": 0.2,
        "max_normalized_cer": None,
        "missing_output": "critical",
        "unexpected_output": "claim",
        "numeric_sequence_match": "disabled",
    }


def _readiness_snapshot() -> dict[str, object]:
    return {
        "required_count": 2,
        "usable_count": 2,
        "missing": [],
        "unavailable": [],
        "invalid": [],
        "duplicates": [],
    }


def _decision_result() -> DecisionResult:
    return decide(
        DecisionInputs(
            integrity=IntegrityAssessment.VALID,
            critical=CriticalAssessment.CLEAR,
            evidence=EvidenceAssessment.SUFFICIENT,
            claim=ClaimAssessment.SUPPORTED,
        )
    )


def _build_bundle(
    **overrides: object,
):
    values: dict[str, object] = {
        "evaluation_type": "asr",
        "target": EvidenceTarget(
            evaluation_run_id=11,
            test_case_id=22,
        ),
        "policy_key": (
            "hetren.asr.test-case-quality"
        ),
        "policy_version": "1.0.0",
        "policy_snapshot": _policy_snapshot(),
        "result_provenance_id": 33,
        "provenance_sha256": (
            PROVENANCE_SHA256
        ),
        "observation_evidence_sha256": (
            OBSERVATION_SHA256
        ),
        "integrity": IntegrityAssessment.VALID,
        "evidence": (
            EvidenceAssessment.SUFFICIENT
        ),
        "critical": CriticalAssessment.CLEAR,
        "claim": ClaimAssessment.SUPPORTED,
        "decision": _decision_result(),
        "readiness_snapshot": (
            _readiness_snapshot()
        ),
        "findings": [
            {
                "rule": "max_normalized_wer",
                "disposition": "claim",
                "outcome": "satisfied",
                "observed_value": 0.1,
                "limit": 0.2,
            },
        ],
    }

    values.update(overrides)

    return build_decision_evidence_bundle(
        **values,
    )


def test_build_decision_evidence_bundle_is_complete():
    bundle = _build_bundle()

    assert bundle.payload[
        "schema_version"
    ] == DECISION_EVIDENCE_SCHEMA_VERSION

    assert bundle.payload["target"] == {
        "evaluation_run_id": 11,
        "test_case_id": 22,
    }

    assert bundle.payload["evidence"] == {
        "result_provenance_id": 33,
        "provenance_sha256": (
            PROVENANCE_SHA256
        ),
        "observation_evidence_sha256": (
            OBSERVATION_SHA256
        ),
    }

    assert bundle.payload[
        "assessments"
    ] == {
        "integrity": "valid",
        "evidence": "sufficient",
        "critical": "clear",
        "claim": "supported",
    }

    assert bundle.payload["decision"] == {
        "verdict": "pass",
        "reason": "claim_supported",
    }

    assert len(bundle.policy_sha256) == 64
    assert len(bundle.decision_sha256) == 64


def test_policy_digest_binds_key_version_and_snapshot():
    snapshot = _policy_snapshot()

    baseline = calculate_policy_sha256(
        policy_key="hetren.asr.policy",
        policy_version="1.0.0",
        policy_snapshot=snapshot,
    )

    assert baseline != calculate_policy_sha256(
        policy_key="hetren.asr.other-policy",
        policy_version="1.0.0",
        policy_snapshot=snapshot,
    )

    assert baseline != calculate_policy_sha256(
        policy_key="hetren.asr.policy",
        policy_version="2.0.0",
        policy_snapshot=snapshot,
    )

    changed_snapshot = dict(snapshot)
    changed_snapshot[
        "max_normalized_wer"
    ] = 0.3

    assert baseline != calculate_policy_sha256(
        policy_key="hetren.asr.policy",
        policy_version="1.0.0",
        policy_snapshot=changed_snapshot,
    )


def test_policy_digest_ignores_dictionary_insertion_order():
    first = {
        "a": 1,
        "b": {
            "x": 2,
            "y": 3,
        },
    }

    second = {
        "b": {
            "y": 3,
            "x": 2,
        },
        "a": 1,
    }

    assert calculate_policy_sha256(
        policy_key="hetren.test.policy",
        policy_version="1",
        policy_snapshot=first,
    ) == calculate_policy_sha256(
        policy_key="hetren.test.policy",
        policy_version="1",
        policy_snapshot=second,
    )


def test_decision_digest_is_deterministic():
    first = _build_bundle()
    second = _build_bundle(
        policy_snapshot={
            "numeric_sequence_match": (
                "disabled"
            ),
            "unexpected_output": "claim",
            "missing_output": "critical",
            "max_normalized_cer": None,
            "max_normalized_wer": 0.2,
        }
    )

    assert first.payload == second.payload
    assert (
        first.policy_sha256
        == second.policy_sha256
    )
    assert (
        first.decision_sha256
        == second.decision_sha256
    )


def test_decision_digest_binds_target():
    first = _build_bundle()

    second = _build_bundle(
        target=EvidenceTarget(
            evaluation_run_id=11,
            test_case_id=23,
        )
    )

    assert (
        first.decision_sha256
        != second.decision_sha256
    )


def test_decision_digest_binds_provenance():
    first = _build_bundle()

    second = _build_bundle(
        provenance_sha256="c" * 64,
    )

    assert (
        first.decision_sha256
        != second.decision_sha256
    )


def test_decision_digest_binds_observation_evidence():
    first = _build_bundle()

    second = _build_bundle(
        observation_evidence_sha256=(
            "d" * 64
        ),
    )

    assert (
        first.decision_sha256
        != second.decision_sha256
    )


def test_decision_digest_binds_findings():
    first = _build_bundle()

    second = _build_bundle(
        findings=[
            {
                "rule": "max_normalized_wer",
                "disposition": "claim",
                "outcome": "violated",
                "observed_value": 0.4,
                "limit": 0.2,
            },
        ]
    )

    assert (
        first.decision_sha256
        != second.decision_sha256
    )


def test_builder_rejects_kernel_inconsistent_decision():
    inconsistent = DecisionResult(
        verdict=DecisionVerdict.FAIL,
        reason=(
            _decision_result().reason
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="decision kernel",
    ):
        _build_bundle(
            decision=inconsistent,
        )


@pytest.mark.parametrize(
    "digest",
    [
        "a" * 63,
        "A" * 64,
        "g" * 64,
    ],
)
def test_builder_rejects_invalid_provenance_digest(
    digest: str,
):
    with pytest.raises(HveeContractError):
        _build_bundle(
            provenance_sha256=digest,
        )


def test_builder_rejects_nan_policy_value():
    snapshot = _policy_snapshot()
    snapshot["invalid"] = math.nan

    with pytest.raises(
        HveeContractError,
        match="deterministic JSON",
    ):
        _build_bundle(
            policy_snapshot=snapshot,
        )


def test_builder_rejects_nan_finding_value():
    with pytest.raises(
        HveeContractError,
        match="deterministic JSON",
    ):
        _build_bundle(
            findings=[
                {
                    "rule": "example",
                    "observed_value": math.nan,
                },
            ]
        )


def test_verifier_accepts_intact_bundle():
    bundle = _build_bundle()

    assert verify_decision_evidence_bundle(
        payload=bundle.payload,
        expected_decision_sha256=(
            bundle.decision_sha256
        ),
    )


def test_verifier_rejects_payload_tampering():
    bundle = _build_bundle()

    tampered = copy.deepcopy(
        bundle.payload
    )
    tampered["evaluation_type"] = (
        "translation"
    )

    assert not verify_decision_evidence_bundle(
        payload=tampered,
        expected_decision_sha256=(
            bundle.decision_sha256
        ),
    )


def test_verifier_rejects_policy_digest_rewrite():
    bundle = _build_bundle()

    tampered = copy.deepcopy(
        bundle.payload
    )
    tampered["policy"]["sha256"] = "f" * 64

    assert not verify_decision_evidence_bundle(
        payload=tampered,
        expected_decision_sha256=(
            bundle.decision_sha256
        ),
    )


def test_verifier_rejects_wrong_decision_digest():
    bundle = _build_bundle()

    assert not verify_decision_evidence_bundle(
        payload=bundle.payload,
        expected_decision_sha256="f" * 64,
    )


def test_verifier_rejects_kernel_inconsistent_verdict_even_if_rehashed():
    bundle = _build_bundle()

    tampered = copy.deepcopy(
        bundle.payload
    )
    tampered["decision"] = {
        "verdict": "fail",
        "reason": "claim_contradicted",
    }

    # The verifier must reject a verdict that cannot be produced from
    # the stored assessments, even when the caller supplies a syntactic
    # digest value.
    assert not verify_decision_evidence_bundle(
        payload=tampered,
        expected_decision_sha256="f" * 64,
    )


def test_verifier_rejects_unknown_top_level_field():
    bundle = _build_bundle()

    tampered = copy.deepcopy(
        bundle.payload
    )
    tampered["unexpected"] = True

    assert not verify_decision_evidence_bundle(
        payload=tampered,
        expected_decision_sha256=(
            bundle.decision_sha256
        ),
    )
