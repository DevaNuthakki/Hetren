from __future__ import annotations

import pytest

from hvee.core.contracts import (
    MetricValueType,
    ObservationStatus,
)
from hvee.core.matched_evidence import (
    MatchedEvidenceState,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr.matched_evidence import (
    ASR_NORMALIZED_CER_REQUIREMENT,
    ASR_NORMALIZED_WER_REQUIREMENT,
    build_asr_matched_quality_cohorts,
)


def _record(
    *,
    metric: str,
    run_id: int,
    test_case_id: int,
    value: float | None = None,
    status: ObservationStatus = (
        ObservationStatus.SUCCESS
    ),
    status_detail: str | None = None,
    metric_version: str = "1.0.0",
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
            "unsupported test metric"
        )

    return ObservationEvidenceRecord(
        metric_key=metric_key,
        metric_version=metric_version,
        evaluator_key=evaluator_key,
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


def _complete_records():
    return (
        _record(
            metric="wer",
            run_id=10,
            test_case_id=1,
            value=0.20,
        ),
        _record(
            metric="wer",
            run_id=20,
            test_case_id=1,
            value=0.10,
        ),
        _record(
            metric="cer",
            run_id=10,
            test_case_id=1,
            value=0.12,
        ),
        _record(
            metric="cer",
            run_id=20,
            test_case_id=1,
            value=0.08,
        ),
        _record(
            metric="wer",
            run_id=10,
            test_case_id=2,
            value=0.30,
        ),
        _record(
            metric="wer",
            run_id=20,
            test_case_id=2,
            value=0.35,
        ),
        _record(
            metric="cer",
            run_id=10,
            test_case_id=2,
            value=0.18,
        ),
        _record(
            metric="cer",
            run_id=20,
            test_case_id=2,
            value=0.20,
        ),
    )


def test_requirements_pin_current_normalized_scientific_identity():
    assert (
        ASR_NORMALIZED_WER_REQUIREMENT.metric_key
        == "asr.wer.normalized-basic"
    )
    assert (
        ASR_NORMALIZED_WER_REQUIREMENT
        .evaluator_key
        == "hetren.asr.wer.normalized-basic"
    )

    assert (
        ASR_NORMALIZED_CER_REQUIREMENT.metric_key
        == "asr.cer.normalized-basic"
    )
    assert (
        ASR_NORMALIZED_CER_REQUIREMENT
        .evaluator_key
        == "hetren.asr.cer.normalized-basic"
    )

    assert (
        ASR_NORMALIZED_WER_REQUIREMENT.scope
        == "test_case"
    )
    assert (
        ASR_NORMALIZED_CER_REQUIREMENT.scope
        == "test_case"
    )


def test_builds_complete_matched_wer_and_cer_cohorts():
    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(2, 1),
        records=_complete_records(),
    )

    assert cohorts.baseline_run_id == 10
    assert cohorts.candidate_run_id == 20
    assert cohorts.declared_test_case_ids == (
        1,
        2,
    )

    assert cohorts.total_cases == 2
    assert cohorts.complete is True
    assert cohorts.integrity_valid is True

    assert (
        cohorts.normalized_wer.usable_pairs
        == 2
    )
    assert (
        cohorts.normalized_cer.usable_pairs
        == 2
    )

    assert cohorts.normalized_wer.deltas == (
        pytest.approx(
            (
                -0.10,
                0.05,
            )
        )
    )

    assert cohorts.normalized_cer.deltas == (
        pytest.approx(
            (
                -0.04,
                0.02,
            )
        )
    )


def test_missing_wer_does_not_hide_complete_cer():
    records = tuple(
        record
        for record
        in _complete_records()
        if not (
            record.metric_key
            == "asr.wer.normalized-basic"
            and record.evaluation_run_id == 20
            and record.test_case_id == 2
        )
    )

    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2),
        records=records,
    )

    assert cohorts.complete is False
    assert cohorts.integrity_valid is True

    assert (
        cohorts.normalized_wer.usable_pairs
        == 1
    )
    assert (
        cohorts.normalized_wer
        .pairs[1]
        .candidate
        .state
        == MatchedEvidenceState.MISSING
    )

    assert (
        cohorts.normalized_cer.complete
        is True
    )
    assert (
        cohorts.normalized_cer.usable_pairs
        == 2
    )


def test_timed_out_cer_remains_explicit():
    records = tuple(
        record
        for record
        in _complete_records()
        if not (
            record.metric_key
            == "asr.cer.normalized-basic"
            and record.evaluation_run_id == 20
            and record.test_case_id == 2
        )
    ) + (
        _record(
            metric="cer",
            run_id=20,
            test_case_id=2,
            status=ObservationStatus.TIMED_OUT,
            status_detail="CER evaluator timed out",
        ),
    )

    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2),
        records=records,
    )

    candidate = (
        cohorts.normalized_cer
        .pairs[1]
        .candidate
    )

    assert candidate.state == (
        MatchedEvidenceState.UNAVAILABLE
    )
    assert candidate.observation_status == (
        ObservationStatus.TIMED_OUT
    )
    assert candidate.status_detail == (
        "CER evaluator timed out"
    )

    assert cohorts.complete is False
    assert cohorts.integrity_valid is True


def test_invalid_wer_invalidates_combined_integrity():
    records = tuple(
        record
        for record
        in _complete_records()
        if not (
            record.metric_key
            == "asr.wer.normalized-basic"
            and record.evaluation_run_id == 20
            and record.test_case_id == 2
        )
    ) + (
        _record(
            metric="wer",
            run_id=20,
            test_case_id=2,
            status=ObservationStatus.INVALID,
            status_detail="invalid WER observation",
        ),
    )

    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2),
        records=records,
    )

    assert cohorts.integrity_valid is False
    assert cohorts.complete is False

    assert (
        cohorts.normalized_cer.integrity_valid
        is True
    )


def test_wrong_wer_version_is_not_used():
    records = tuple(
        record
        for record
        in _complete_records()
        if not (
            record.metric_key
            == "asr.wer.normalized-basic"
            and record.evaluation_run_id == 20
            and record.test_case_id == 2
        )
    ) + (
        _record(
            metric="wer",
            run_id=20,
            test_case_id=2,
            value=0.35,
            metric_version="2.0.0",
        ),
    )

    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2),
        records=records,
    )

    assert (
        cohorts.normalized_wer
        .pairs[1]
        .candidate
        .state
        == MatchedEvidenceState.MISSING
    )


def test_same_declared_cohort_is_used_for_both_metrics():
    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(2, 1),
        records=_complete_records(),
    )

    assert (
        cohorts.normalized_wer
        .declared_test_case_ids
        == (1, 2)
    )
    assert (
        cohorts.normalized_cer
        .declared_test_case_ids
        == (1, 2)
    )
    assert (
        cohorts.normalized_wer
        .declared_test_case_ids
        == cohorts.normalized_cer
        .declared_test_case_ids
    )
