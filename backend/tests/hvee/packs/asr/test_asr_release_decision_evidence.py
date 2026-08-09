from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.decision_evidence import (
    calculate_decision_sha256,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.release_decision_evidence import (
    ASR_MATCHED_RELEASE_DECISION_EVIDENCE_SCHEMA_VERSION,
    ASRMatchedCaseEvidenceBinding,
    build_asr_matched_release_decision_evidence,
    verify_asr_matched_release_decision_evidence,
)


def _digest(value: int) -> str:
    return f"{value:064x}"


def _record(
    *,
    metric: str,
    run_id: int,
    test_case_id: int,
    value: float,
) -> ObservationEvidenceRecord:
    if metric == "wer":
        metric_key = (
            "asr.wer.normalized-basic"
        )
        evaluator_key = (
            "hetren.asr.wer.normalized-basic"
        )
    elif metric == "cer":
        metric_key = (
            "asr.cer.normalized-basic"
        )
        evaluator_key = (
            "hetren.asr.cer.normalized-basic"
        )
    else:
        raise AssertionError(
            "unsupported metric"
        )

    return ObservationEvidenceRecord(
        metric_key=metric_key,
        metric_version="1.0.0",
        evaluator_key=evaluator_key,
        evaluator_version="1.0.0",
        evaluation_type="asr",
        scope="test_case",
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=value,
    )


def _records(
    *,
    wer_delta: float = 0.005,
    cer_delta: float = 0.0,
) -> tuple[ObservationEvidenceRecord, ...]:
    records = []

    for test_case_id in range(
        1,
        5,
    ):
        baseline = (
            0.20
            + test_case_id * 0.01
        )

        records.extend(
            (
                _record(
                    metric="wer",
                    run_id=10,
                    test_case_id=test_case_id,
                    value=baseline,
                ),
                _record(
                    metric="wer",
                    run_id=20,
                    test_case_id=test_case_id,
                    value=(
                        baseline + wer_delta
                    ),
                ),
                _record(
                    metric="cer",
                    run_id=10,
                    test_case_id=test_case_id,
                    value=(
                        baseline / 2.0
                    ),
                ),
                _record(
                    metric="cer",
                    run_id=20,
                    test_case_id=test_case_id,
                    value=(
                        baseline / 2.0
                        + cer_delta
                    ),
                ),
            )
        )

    return tuple(records)


def _bindings() -> tuple[
    ASRMatchedCaseEvidenceBinding,
    ...,
]:
    return tuple(
        ASRMatchedCaseEvidenceBinding(
            test_case_id=test_case_id,
            baseline_result_provenance_id=(
                100 + test_case_id
            ),
            baseline_provenance_sha256=(
                _digest(
                    1000 + test_case_id
                )
            ),
            baseline_observation_evidence_sha256=(
                _digest(
                    2000 + test_case_id
                )
            ),
            candidate_result_provenance_id=(
                200 + test_case_id
            ),
            candidate_provenance_sha256=(
                _digest(
                    3000 + test_case_id
                )
            ),
            candidate_observation_evidence_sha256=(
                _digest(
                    4000 + test_case_id
                )
            ),
        )
        for test_case_id
        in range(1, 5)
    )


def _policy(
    *,
    wer_margin: float = 0.01,
) -> ASRMatchedReleaseAssurancePolicyV1:
    return ASRMatchedReleaseAssurancePolicyV1(
        interval=PairedIntervalPolicy(
            method=(
                PairedIntervalMethod
                .BOOTSTRAP_PERCENTILE_V1
            ),
            confidence_level=0.95,
            minimum_usable_pairs=4,
            resamples=128,
            random_seed=98765,
        ),
        normalized_wer_noninferiority_margin=(
            wer_margin
        ),
        normalized_cer_noninferiority_margin=None,
    )


def _build(
    *,
    records=None,
    bindings=None,
    policy=None,
):
    return (
        build_asr_matched_release_decision_evidence(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(
                1,
                2,
                3,
                4,
            ),
            records=(
                _records()
                if records is None
                else records
            ),
            evidence_bindings=(
                _bindings()
                if bindings is None
                else bindings
            ),
            policy=(
                _policy()
                if policy is None
                else policy
            ),
        )
    )


def test_builds_deterministic_release_decision_evidence():
    first = _build()
    second = _build()

    assert first == second

    assert first.payload[
        "schema_version"
    ] == (
        ASR_MATCHED_RELEASE_DECISION_EVIDENCE_SCHEMA_VERSION
    )

    assert first.payload[
        "evaluation_type"
    ] == "asr"

    assert first.payload["target"] == {
        "baseline_run_id": 10,
        "candidate_run_id": 20,
        "declared_test_case_ids": [
            1,
            2,
            3,
            4,
        ],
    }

    assert (
        first.payload[
            "decision"
        ][
            "verdict"
        ]
        == "pass"
    )

    assert (
        first.payload[
            "decision"
        ][
            "reason"
        ]
        == "claim_supported"
    )

    assert (
        first.payload[
            "assessments"
        ][
            "critical"
        ]
        == "clear"
    )

    assert (
        len(
            first.payload[
                "evidence_bindings"
            ]
        )
        == 4
    )

    assert (
        first.payload[
            "metrics"
        ][
            "normalized_wer"
        ]
        is not None
    )

    assert (
        first.payload[
            "metrics"
        ][
            "normalized_cer"
        ]
        is None
    )

    assert len(
        first.policy_sha256
    ) == 64

    assert len(
        first.decision_sha256
    ) == 64


def test_policy_identity_and_complete_snapshot_are_bound():
    passing = _build(
        policy=_policy(
            wer_margin=0.01
        )
    )

    failing = _build(
        policy=_policy(
            wer_margin=0.004
        )
    )

    assert (
        passing.policy_sha256
        != failing.policy_sha256
    )
    assert (
        passing.decision_sha256
        != failing.decision_sha256
    )

    assert (
        passing.payload[
            "decision"
        ][
            "verdict"
        ]
        == "pass"
    )

    assert (
        failing.payload[
            "decision"
        ][
            "verdict"
        ]
        == "fail"
    )


def test_evidence_binding_changes_release_digest():
    original = _build()

    bindings = list(
        _bindings()
    )

    first = bindings[0]

    bindings[0] = (
        ASRMatchedCaseEvidenceBinding(
            test_case_id=first.test_case_id,
            baseline_result_provenance_id=(
                first
                .baseline_result_provenance_id
            ),
            baseline_provenance_sha256=(
                first
                .baseline_provenance_sha256
            ),
            baseline_observation_evidence_sha256=(
                _digest(9999)
            ),
            candidate_result_provenance_id=(
                first
                .candidate_result_provenance_id
            ),
            candidate_provenance_sha256=(
                first
                .candidate_provenance_sha256
            ),
            candidate_observation_evidence_sha256=(
                first
                .candidate_observation_evidence_sha256
            ),
        )
    )

    changed = _build(
        bindings=tuple(bindings)
    )

    assert (
        original.decision_sha256
        != changed.decision_sha256
    )

    assert (
        original.payload["decision"]
        == changed.payload["decision"]
    )


def test_bindings_must_exactly_cover_declared_cohort():
    with pytest.raises(
        HveeContractError,
        match="exactly cover",
    ):
        _build(
            bindings=_bindings()[:-1]
        )


def test_verifier_accepts_exact_reproducible_bundle():
    bundle = _build()

    rebuilt = (
        verify_asr_matched_release_decision_evidence(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(
                1,
                2,
                3,
                4,
            ),
            records=_records(),
            evidence_bindings=_bindings(),
            policy=_policy(),
            payload=bundle.payload,
            expected_decision_sha256=(
                bundle.decision_sha256
            ),
        )
    )

    assert rebuilt == bundle


def test_simple_payload_tampering_breaks_digest():
    bundle = _build()

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "decision"
    ][
        "verdict"
    ] = "fail"

    with pytest.raises(
        HveeContractError,
        match="expected SHA-256",
    ):
        verify_asr_matched_release_decision_evidence(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(
                1,
                2,
                3,
                4,
            ),
            records=_records(),
            evidence_bindings=_bindings(),
            policy=_policy(),
            payload=tampered,
            expected_decision_sha256=(
                bundle.decision_sha256
            ),
        )


def test_rehashed_fabricated_verdict_still_fails_rebuild():
    bundle = _build()

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "decision"
    ][
        "verdict"
    ] = "fail"

    tampered[
        "decision"
    ][
        "reason"
    ] = "claim_contradicted"

    forged_digest = (
        calculate_decision_sha256(
            tampered
        )
    )

    with pytest.raises(
        HveeContractError,
        match="reproducibly rebuilt",
    ):
        verify_asr_matched_release_decision_evidence(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(
                1,
                2,
                3,
                4,
            ),
            records=_records(),
            evidence_bindings=_bindings(),
            policy=_policy(),
            payload=tampered,
            expected_decision_sha256=(
                forged_digest
            ),
        )


def test_changed_observations_cannot_verify_old_release_evidence():
    bundle = _build()

    changed_records = _records(
        wer_delta=0.03
    )

    with pytest.raises(
        HveeContractError,
        match="reproducibly rebuilt",
    ):
        verify_asr_matched_release_decision_evidence(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(
                1,
                2,
                3,
                4,
            ),
            records=changed_records,
            evidence_bindings=_bindings(),
            policy=_policy(),
            payload=bundle.payload,
            expected_decision_sha256=(
                bundle.decision_sha256
            ),
        )


def test_unsorted_bindings_canonicalize_to_same_bundle():
    normal = _build()

    reversed_bindings = tuple(
        reversed(
            _bindings()
        )
    )

    reordered = _build(
        bindings=reversed_bindings
    )

    assert reordered == normal
