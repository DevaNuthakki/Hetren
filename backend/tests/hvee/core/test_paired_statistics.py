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
    build_matched_observation_cohort,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.core.paired_statistics import (
    summarize_matched_observation_cohort,
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
) -> ObservationEvidenceRecord:
    return ObservationEvidenceRecord(
        metric_key="asr.wer.normalized-basic",
        metric_version="1.0.0",
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
            if status
            == ObservationStatus.SUCCESS
            else None
        ),
        status_detail=status_detail,
    )


def test_complete_cohort_descriptive_statistics():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2, 3),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.30,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                value=0.20,
            ),
            _record(
                run_id=10,
                test_case_id=2,
                value=0.10,
            ),
            _record(
                run_id=20,
                test_case_id=2,
                value=0.15,
            ),
            _record(
                run_id=10,
                test_case_id=3,
                value=0.20,
            ),
            _record(
                run_id=20,
                test_case_id=3,
                value=0.20,
            ),
        ),
    )

    summary = (
        summarize_matched_observation_cohort(
            cohort
        )
    )

    assert summary.total_cases == 3
    assert summary.usable_pairs == 3
    assert summary.incomplete_pairs == 0

    assert summary.complete is True
    assert summary.integrity_valid is True

    assert summary.baseline_mean == (
        pytest.approx(0.20)
    )
    assert summary.candidate_mean == (
        pytest.approx(
            (0.20 + 0.15 + 0.20) / 3
        )
    )

    assert summary.mean_delta == (
        pytest.approx(
            (-0.10 + 0.05 + 0.0) / 3
        )
    )
    assert summary.median_delta == (
        pytest.approx(0.0)
    )
    assert summary.minimum_delta == (
        pytest.approx(-0.10)
    )
    assert summary.maximum_delta == (
        pytest.approx(0.05)
    )

    assert summary.candidate_lower_count == 1
    assert summary.candidate_higher_count == 1
    assert summary.unchanged_count == 1


def test_incomplete_pair_is_never_hidden_from_accounting():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2, 3),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.30,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                value=0.20,
            ),
            _record(
                run_id=10,
                test_case_id=2,
                value=0.10,
            ),
            _record(
                run_id=20,
                test_case_id=2,
                value=0.15,
            ),
            _record(
                run_id=10,
                test_case_id=3,
                value=0.20,
            ),
        ),
    )

    summary = (
        summarize_matched_observation_cohort(
            cohort
        )
    )

    assert summary.total_cases == 3
    assert summary.usable_pairs == 2
    assert summary.incomplete_pairs == 1
    assert summary.complete is False
    assert summary.integrity_valid is True

    assert summary.baseline_mean == (
        pytest.approx(0.20)
    )
    assert summary.candidate_mean == (
        pytest.approx(0.175)
    )

    assert (
        summary.candidate_lower_count
        + summary.candidate_higher_count
        + summary.unchanged_count
        == 2
    )


def test_no_usable_pairs_produce_no_numeric_summary():
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

    summary = (
        summarize_matched_observation_cohort(
            cohort
        )
    )

    assert summary.total_cases == 1
    assert summary.usable_pairs == 0
    assert summary.incomplete_pairs == 1
    assert summary.complete is False

    assert summary.baseline_mean is None
    assert summary.candidate_mean is None
    assert summary.mean_delta is None
    assert summary.median_delta is None
    assert summary.minimum_delta is None
    assert summary.maximum_delta is None

    assert summary.candidate_lower_count == 0
    assert summary.candidate_higher_count == 0
    assert summary.unchanged_count == 0


def test_invalid_pair_remains_visible_in_summary_state():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2),
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
                value=0.08,
            ),
            _record(
                run_id=10,
                test_case_id=2,
                value=0.20,
            ),
            _record(
                run_id=20,
                test_case_id=2,
                status=ObservationStatus.INVALID,
                status_detail=(
                    "invalid candidate observation"
                ),
            ),
        ),
    )

    summary = (
        summarize_matched_observation_cohort(
            cohort
        )
    )

    assert summary.total_cases == 2
    assert summary.usable_pairs == 1
    assert summary.incomplete_pairs == 1
    assert summary.complete is False
    assert summary.integrity_valid is False

    assert summary.baseline_mean == (
        pytest.approx(0.10)
    )
    assert summary.candidate_mean == (
        pytest.approx(0.08)
    )


def test_exact_equal_values_are_unchanged():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.25,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                value=0.25,
            ),
        ),
    )

    summary = (
        summarize_matched_observation_cohort(
            cohort
        )
    )

    assert summary.mean_delta == 0.0
    assert summary.minimum_delta == 0.0
    assert summary.maximum_delta == 0.0

    assert summary.candidate_lower_count == 0
    assert summary.candidate_higher_count == 0
    assert summary.unchanged_count == 1


def test_statistics_reject_wrong_input_type():
    with pytest.raises(
        HveeContractError,
        match="MatchedObservationCohort",
    ):
        summarize_matched_observation_cohort(
            object()  # type: ignore[arg-type]
        )
