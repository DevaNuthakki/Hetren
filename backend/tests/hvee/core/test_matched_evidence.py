from __future__ import annotations

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.evidence_readiness import (
    ObservationRequirement,
)
from hvee.core.matched_evidence import (
    MatchedEvidenceState,
    build_matched_observation_cohort,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)


REQUIREMENT = ObservationRequirement(
    metric_key="asr.wer.normalized-basic",
    metric_version="1.0.0",
    evaluator_key="hetren.asr.wer.normalized-basic",
    evaluator_version="1.0.0",
    evaluation_type="asr",
    scope="test_case",
    value_type=MetricValueType.NUMBER,
)


def _record(
    *,
    run_id: int,
    test_case_id: int,
    value: float | None = None,
    status: ObservationStatus = (
        ObservationStatus.SUCCESS
    ),
    status_detail: str | None = None,
    metric_version: str = "1.0.0",
) -> ObservationEvidenceRecord:
    return ObservationEvidenceRecord(
        metric_key="asr.wer.normalized-basic",
        metric_version=metric_version,
        evaluator_key=(
            "hetren.asr.wer.normalized-basic"
        ),
        evaluator_version="1.0.0",
        evaluation_type="asr",
        scope="test_case",
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
        status=status,
        value_type=MetricValueType.NUMBER,
        value=(
            value
            if status == ObservationStatus.SUCCESS
            else None
        ),
        status_detail=status_detail,
    )


def test_builds_exact_matched_numeric_pairs():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(2, 1),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.10,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                value=0.15,
            ),
            _record(
                run_id=10,
                test_case_id=2,
                value=0.30,
            ),
            _record(
                run_id=20,
                test_case_id=2,
                value=0.20,
            ),
        ),
    )

    assert cohort.declared_test_case_ids == (
        1,
        2,
    )
    assert cohort.total_cases == 2
    assert cohort.usable_pairs == 2
    assert cohort.incomplete_pairs == 0
    assert cohort.complete is True
    assert cohort.integrity_valid is True

    assert cohort.pairs[0].delta == pytest.approx(
        0.05
    )
    assert cohort.pairs[1].delta == pytest.approx(
        -0.10
    )

    assert cohort.deltas == pytest.approx(
        (
            0.05,
            -0.10,
        )
    )


def test_missing_candidate_is_accounted_not_dropped():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.10,
            ),
        ),
    )

    pair = cohort.pairs[0]

    assert (
        pair.baseline.state
        == MatchedEvidenceState.USABLE
    )
    assert (
        pair.candidate.state
        == MatchedEvidenceState.MISSING
    )

    assert pair.usable is False
    assert pair.delta is None

    assert cohort.usable_pairs == 0
    assert cohort.incomplete_pairs == 1
    assert cohort.complete is False
    assert cohort.integrity_valid is True


def test_unavailable_candidate_preserves_status():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.10,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                status=ObservationStatus.TIMED_OUT,
                status_detail="evaluator timed out",
            ),
        ),
    )

    candidate = cohort.pairs[0].candidate

    assert candidate.state == (
        MatchedEvidenceState.UNAVAILABLE
    )
    assert candidate.observation_status == (
        ObservationStatus.TIMED_OUT
    )
    assert candidate.status_detail == (
        "evaluator timed out"
    )

    assert cohort.complete is False
    assert cohort.integrity_valid is True


def test_invalid_evidence_marks_cohort_integrity_invalid():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.10,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                status=ObservationStatus.INVALID,
                status_detail="invalid evaluator output",
            ),
        ),
    )

    candidate = cohort.pairs[0].candidate

    assert candidate.state == (
        MatchedEvidenceState.INVALID
    )
    assert candidate.observation_status == (
        ObservationStatus.INVALID
    )
    assert cohort.integrity_valid is False
    assert cohort.complete is False


def test_duplicate_evidence_marks_integrity_invalid():
    duplicate = _record(
        run_id=20,
        test_case_id=1,
        value=0.20,
    )

    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.10,
            ),
            duplicate,
            duplicate,
        ),
    )

    candidate = cohort.pairs[0].candidate

    assert candidate.state == (
        MatchedEvidenceState.DUPLICATE
    )
    assert cohort.integrity_valid is False
    assert cohort.complete is False


def test_wrong_metric_version_is_missing_not_silently_used():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.10,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                value=0.20,
                metric_version="2.0.0",
            ),
        ),
    )

    assert (
        cohort.pairs[0].candidate.state
        == MatchedEvidenceState.MISSING
    )


def test_extra_unrelated_evidence_is_ignored():
    unrelated = ObservationEvidenceRecord(
        metric_key="asr.cer.normalized-basic",
        metric_version="1.0.0",
        evaluator_key=(
            "hetren.asr.cer.normalized-basic"
        ),
        evaluator_version="1.0.0",
        evaluation_type="asr",
        scope="test_case",
        evaluation_run_id=20,
        test_case_id=1,
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.NUMBER,
        value=0.99,
    )

    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.10,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                value=0.20,
            ),
            unrelated,
        ),
    )

    assert cohort.complete is True
    assert cohort.usable_pairs == 1
    assert cohort.pairs[0].delta == pytest.approx(
        0.10
    )


def test_duplicate_declared_test_cases_are_rejected():
    with pytest.raises(
        HveeContractError,
        match="must be unique",
    ):
        build_matched_observation_cohort(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(1, 1),
            requirement=REQUIREMENT,
            records=(),
        )


def test_same_baseline_and_candidate_run_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="must differ",
    ):
        build_matched_observation_cohort(
            baseline_run_id=10,
            candidate_run_id=10,
            declared_test_case_ids=(1,),
            requirement=REQUIREMENT,
            records=(),
        )


def test_run_scoped_requirement_is_rejected():
    requirement = ObservationRequirement(
        metric_key="latency",
        metric_version="1",
        evaluator_key="latency-evaluator",
        evaluator_version="1",
        evaluation_type="asr",
        scope="run",
        value_type=MetricValueType.NUMBER,
    )

    with pytest.raises(
        HveeContractError,
        match="test-case observation",
    ):
        build_matched_observation_cohort(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(1,),
            requirement=requirement,
            records=(),
        )


def test_boolean_requirement_is_rejected_for_v1():
    requirement = ObservationRequirement(
        metric_key="flag",
        metric_version="1",
        evaluator_key="flag-evaluator",
        evaluator_version="1",
        evaluation_type="asr",
        scope="test_case",
        value_type=MetricValueType.BOOLEAN,
    )

    with pytest.raises(
        HveeContractError,
        match="numeric observation",
    ):
        build_matched_observation_cohort(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(1,),
            requirement=requirement,
            records=(),
        )


def test_successful_wrong_value_type_is_invalid_not_usable():
    wrong_type = ObservationEvidenceRecord(
        metric_key="asr.wer.normalized-basic",
        metric_version="1.0.0",
        evaluator_key=(
            "hetren.asr.wer.normalized-basic"
        ),
        evaluator_version="1.0.0",
        evaluation_type="asr",
        scope="test_case",
        evaluation_run_id=20,
        test_case_id=1,
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.INTEGER,
        value=1,
    )

    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.10,
            ),
            wrong_type,
        ),
    )

    candidate = cohort.pairs[0].candidate

    assert candidate.state == (
        MatchedEvidenceState.INVALID
    )
    assert candidate.observation_status == (
        ObservationStatus.SUCCESS
    )
    assert candidate.status_detail
    assert cohort.integrity_valid is False
    assert cohort.complete is False
    assert cohort.usable_pairs == 0
