from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.decision_evidence import (
    verify_decision_evidence_bundle,
)
from hvee.core.evidence_readiness import (
    EvidenceTarget,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr.decision_evidence import (
    build_asr_policy_snapshot,
    build_asr_test_case_decision_evidence,
)
from hvee.packs.asr.decision_policy import (
    ASRRuleDisposition,
    ASRTestCaseDecisionPolicyV1,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_WER_EVALUATOR,
    NORMALIZED_WER_METRIC,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    TRANSCRIPT_INTEGRITY_EVALUATOR,
)


TARGET = EvidenceTarget(
    evaluation_run_id=10,
    test_case_id=20,
)

PROVENANCE_SHA256 = "a" * 64
OBSERVATION_SHA256 = "b" * 64


def _policy(
    *,
    max_wer: float = 0.20,
) -> ASRTestCaseDecisionPolicyV1:
    return ASRTestCaseDecisionPolicyV1(
        max_normalized_wer=max_wer,
        missing_output=(
            ASRRuleDisposition.CRITICAL
        ),
    )


def _record(
    *,
    metric,
    evaluator,
    value_type: MetricValueType,
    value: object,
) -> ObservationEvidenceRecord:
    return ObservationEvidenceRecord(
        metric_key=metric.key,
        metric_version=metric.version,
        evaluator_key=evaluator.key,
        evaluator_version=evaluator.version,
        evaluation_type="asr",
        scope="test_case",
        evaluation_run_id=(
            TARGET.evaluation_run_id
        ),
        test_case_id=TARGET.test_case_id,
        status=ObservationStatus.SUCCESS,
        value_type=value_type,
        value=value,
    )


def _records() -> tuple[
    ObservationEvidenceRecord,
    ...,
]:
    return (
        _record(
            metric=NORMALIZED_WER_METRIC,
            evaluator=NORMALIZED_WER_EVALUATOR,
            value_type=MetricValueType.NUMBER,
            value=0.10,
        ),
        _record(
            metric=MISSING_OUTPUT_METRIC,
            evaluator=TRANSCRIPT_INTEGRITY_EVALUATOR,
            value_type=MetricValueType.BOOLEAN,
            value=False,
        ),
    )


def _bundle(
    *,
    policy: ASRTestCaseDecisionPolicyV1 | None = None,
    records: tuple[
        ObservationEvidenceRecord,
        ...,
    ]
    | None = None,
    target: EvidenceTarget = TARGET,
):
    return build_asr_test_case_decision_evidence(
        policy=policy or _policy(),
        records=(
            _records()
            if records is None
            else records
        ),
        target=target,
        result_provenance_id=30,
        provenance_sha256=(
            PROVENANCE_SHA256
        ),
        observation_evidence_sha256=(
            OBSERVATION_SHA256
        ),
    )


def test_policy_snapshot_is_explicit():
    assert build_asr_policy_snapshot(
        _policy()
    ) == {
        "max_normalized_wer": 0.20,
        "max_normalized_cer": None,
        "missing_output": "critical",
        "unexpected_output": "disabled",
        "numeric_sequence_match": "disabled",
    }


def test_builds_verifiable_asr_decision_evidence():
    bundle = _bundle()

    assert bundle.payload[
        "evaluation_type"
    ] == "asr"

    assert bundle.payload["target"] == {
        "evaluation_run_id": 10,
        "test_case_id": 20,
    }

    assert bundle.payload[
        "decision"
    ] == {
        "verdict": "pass",
        "reason": "claim_supported",
    }

    assert [
        finding["rule"]
        for finding
        in bundle.payload["findings"]
    ] == [
        "max_normalized_wer",
        "missing_output",
    ]

    assert verify_decision_evidence_bundle(
        payload=bundle.payload,
        expected_decision_sha256=(
            bundle.decision_sha256
        ),
    )


def test_readiness_snapshot_binds_requirement_state():
    bundle = _bundle()

    readiness = bundle.payload[
        "readiness"
    ]

    assert readiness[
        "required_count"
    ] == 2
    assert readiness[
        "usable_count"
    ] == 2
    assert readiness["missing"] == []
    assert readiness["unavailable"] == []
    assert readiness["invalid"] == []
    assert readiness["duplicates"] == []


def test_builder_evaluates_exact_supplied_policy_configuration():
    permissive = _bundle(
        policy=_policy(
            max_wer=0.20,
        )
    )

    strict = _bundle(
        policy=_policy(
            max_wer=0.05,
        )
    )

    assert permissive.payload[
        "decision"
    ]["verdict"] == "pass"

    assert strict.payload[
        "decision"
    ]["verdict"] == "fail"

    assert (
        permissive.policy_sha256
        != strict.policy_sha256
    )

    assert (
        permissive.decision_sha256
        != strict.decision_sha256
    )

    assert strict.payload[
        "findings"
    ][0]["outcome"] == "violated"


def test_finding_change_is_bound_into_decision_digest():
    bundle = _bundle()

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "findings"
    ][0]["observed_value"] = 0.19

    assert not verify_decision_evidence_bundle(
        payload=tampered,
        expected_decision_sha256=(
            bundle.decision_sha256
        ),
    )


def test_missing_required_observation_is_serialized():
    records = (
        _record(
            metric=NORMALIZED_WER_METRIC,
            evaluator=NORMALIZED_WER_EVALUATOR,
            value_type=MetricValueType.NUMBER,
            value=0.10,
        ),
    )

    bundle = _bundle(
        records=records,
    )

    readiness = bundle.payload[
        "readiness"
    ]

    assert readiness[
        "required_count"
    ] == 2
    assert readiness[
        "usable_count"
    ] == 1
    assert len(
        readiness["missing"]
    ) == 1

    assert (
        readiness["missing"][0][
            "metric"
        ]["key"]
        == MISSING_OUTPUT_METRIC.key
    )

    assert bundle.payload[
        "decision"
    ]["verdict"] == "inconclusive"


def test_decision_evidence_requires_test_case_target():
    run_target = EvidenceTarget(
        evaluation_run_id=10,
    )

    with pytest.raises(
        HveeContractError,
        match="test-case target",
    ):
        _bundle(
            target=run_target,
        )


def test_policy_change_cannot_reuse_precomputed_findings():
    baseline = _bundle(
        policy=_policy(
            max_wer=0.20,
        )
    )

    strict = _bundle(
        policy=_policy(
            max_wer=0.05,
        )
    )

    assert baseline.payload[
        "findings"
    ][0]["limit"] == 0.20

    assert strict.payload[
        "findings"
    ][0]["limit"] == 0.05

    assert baseline.payload[
        "findings"
    ][0]["outcome"] == "satisfied"

    assert strict.payload[
        "findings"
    ][0]["outcome"] == "violated"
