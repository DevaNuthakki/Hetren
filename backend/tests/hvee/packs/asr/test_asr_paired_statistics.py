from __future__ import annotations

import pytest

from hvee.core.contracts import (
    MetricValueType,
    ObservationStatus,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.packs.asr.matched_evidence import (
    build_asr_matched_quality_cohorts,
)
from hvee.packs.asr.paired_statistics import (
    summarize_asr_matched_quality,
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
        metric_version="1.0.0",
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
    values = (
        # case, baseline WER, candidate WER, baseline CER, candidate CER
        (1, 0.30, 0.20, 0.20, 0.10),
        (2, 0.10, 0.15, 0.08, 0.10),
        (3, 0.20, 0.20, 0.12, 0.12),
    )

    records = []

    for (
        test_case_id,
        baseline_wer,
        candidate_wer,
        baseline_cer,
        candidate_cer,
    ) in values:
        records.extend(
            (
                _record(
                    metric="wer",
                    run_id=10,
                    test_case_id=test_case_id,
                    value=baseline_wer,
                ),
                _record(
                    metric="wer",
                    run_id=20,
                    test_case_id=test_case_id,
                    value=candidate_wer,
                ),
                _record(
                    metric="cer",
                    run_id=10,
                    test_case_id=test_case_id,
                    value=baseline_cer,
                ),
                _record(
                    metric="cer",
                    run_id=20,
                    test_case_id=test_case_id,
                    value=candidate_cer,
                ),
            )
        )

    return tuple(records)


def test_asr_statistics_interpret_lower_values_as_improved():
    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2, 3),
        records=_complete_records(),
    )

    summary = summarize_asr_matched_quality(
        cohorts
    )

    assert summary.total_cases == 3
    assert summary.complete is True
    assert summary.integrity_valid is True

    wer = summary.normalized_wer

    assert wer.metric_key == (
        "asr.wer.normalized-basic"
    )
    assert wer.metric_version == "1.0.0"

    assert wer.improved_count == 1
    assert wer.regressed_count == 1
    assert wer.unchanged_count == 1

    assert wer.baseline_mean == (
        pytest.approx(0.20)
    )
    assert wer.candidate_mean == (
        pytest.approx(
            (0.20 + 0.15 + 0.20) / 3
        )
    )
    assert wer.mean_delta == (
        pytest.approx(
            (-0.10 + 0.05 + 0.0) / 3
        )
    )


def test_cer_uses_same_lower_is_better_semantics():
    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2, 3),
        records=_complete_records(),
    )

    summary = summarize_asr_matched_quality(
        cohorts
    )

    cer = summary.normalized_cer

    assert cer.metric_key == (
        "asr.cer.normalized-basic"
    )

    assert cer.improved_count == 1
    assert cer.regressed_count == 1
    assert cer.unchanged_count == 1

    assert cer.mean_delta == (
        pytest.approx(
            (-0.10 + 0.02 + 0.0) / 3
        )
    )


def test_missing_candidate_evidence_remains_visible():
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
        declared_test_case_ids=(1, 2, 3),
        records=records,
    )

    summary = summarize_asr_matched_quality(
        cohorts
    )

    assert summary.complete is False
    assert summary.integrity_valid is True

    assert (
        summary.normalized_wer.total_cases
        == 3
    )
    assert (
        summary.normalized_wer.usable_pairs
        == 2
    )
    assert (
        summary.normalized_wer.incomplete_pairs
        == 1
    )

    assert (
        summary.normalized_cer.complete
        is True
    )


def test_invalid_metric_evidence_preserves_invalid_integrity():
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
            status=ObservationStatus.INVALID,
            status_detail="invalid CER evidence",
        ),
    )

    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2, 3),
        records=records,
    )

    summary = summarize_asr_matched_quality(
        cohorts
    )

    assert summary.complete is False
    assert summary.integrity_valid is False

    assert (
        summary.normalized_wer.integrity_valid
        is True
    )
    assert (
        summary.normalized_cer.integrity_valid
        is False
    )


def test_all_lower_candidate_values_are_directionally_improved():
    records = (
        _record(
            metric="wer",
            run_id=10,
            test_case_id=1,
            value=0.30,
        ),
        _record(
            metric="wer",
            run_id=20,
            test_case_id=1,
            value=0.20,
        ),
        _record(
            metric="cer",
            run_id=10,
            test_case_id=1,
            value=0.20,
        ),
        _record(
            metric="cer",
            run_id=20,
            test_case_id=1,
            value=0.10,
        ),
    )

    cohorts = build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1,),
        records=records,
    )

    summary = summarize_asr_matched_quality(
        cohorts
    )

    assert (
        summary.normalized_wer.improved_count
        == 1
    )
    assert (
        summary.normalized_wer.regressed_count
        == 0
    )
    assert (
        summary.normalized_wer.mean_delta
        < 0
    )

    assert (
        summary.normalized_cer.improved_count
        == 1
    )
    assert (
        summary.normalized_cer.regressed_count
        == 0
    )
    assert (
        summary.normalized_cer.mean_delta
        < 0
    )
