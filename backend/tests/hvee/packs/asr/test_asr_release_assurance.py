from __future__ import annotations

from hvee.core.contracts import (
    MetricValueType,
    ObservationStatus,
)
from hvee.core.decision import (
    ClaimAssessment,
    EvidenceAssessment,
    IntegrityAssessment,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.packs.asr.matched_evidence import (
    build_asr_matched_quality_cohorts,
)
from hvee.packs.asr.release_assurance import (
    evaluate_asr_matched_release_assurance,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
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


def _policy(
    *,
    wer_margin: float | None,
    cer_margin: float | None,
) -> ASRMatchedReleaseAssurancePolicyV1:
    return ASRMatchedReleaseAssurancePolicyV1(
        interval=PairedIntervalPolicy(
            method=(
                PairedIntervalMethod
                .BOOTSTRAP_PERCENTILE_V1
            ),
            confidence_level=0.95,
            minimum_usable_pairs=4,
            resamples=512,
            random_seed=12345,
        ),
        normalized_wer_noninferiority_margin=(
            wer_margin
        ),
        normalized_cer_noninferiority_margin=(
            cer_margin
        ),
    )


def _metric_records(
    *,
    metric: str,
    deltas: tuple[float, ...],
):
    records = []

    for index, delta in enumerate(
        deltas,
        start=1,
    ):
        baseline = 0.20 + (
            index * 0.01
        )

        records.extend(
            (
                _record(
                    metric=metric,
                    run_id=10,
                    test_case_id=index,
                    value=baseline,
                ),
                _record(
                    metric=metric,
                    run_id=20,
                    test_case_id=index,
                    value=(
                        baseline + delta
                    ),
                ),
            )
        )

    return tuple(records)


def _cohorts(
    *,
    wer_deltas: tuple[float, ...],
    cer_deltas: tuple[float, ...] | None = None,
):
    records = list(
        _metric_records(
            metric="wer",
            deltas=wer_deltas,
        )
    )

    if cer_deltas is None:
        cer_deltas = tuple(
            0.0
            for _ in wer_deltas
        )

    records.extend(
        _metric_records(
            metric="cer",
            deltas=cer_deltas,
        )
    )

    return build_asr_matched_quality_cohorts(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=tuple(
            range(
                1,
                len(wer_deltas) + 1,
            )
        ),
        records=tuple(records),
    )


def test_noninferiority_is_supported_when_upper_bound_within_margin():
    cohorts = _cohorts(
        wer_deltas=(
            0.005,
            0.005,
            0.005,
            0.005,
        )
    )

    result = (
        evaluate_asr_matched_release_assurance(
            cohorts=cohorts,
            policy=_policy(
                wer_margin=0.01,
                cer_margin=None,
            ),
        )
    )

    assert result.normalized_wer is not None
    assert (
        result.normalized_wer.claim
        == ClaimAssessment.SUPPORTED
    )
    assert (
        result.normalized_wer
        .interval
        .upper_bound
        <= 0.01
    )

    assert result.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.evidence == (
        EvidenceAssessment.SUFFICIENT
    )
    assert result.claim == (
        ClaimAssessment.SUPPORTED
    )


def test_noninferiority_is_contradicted_only_when_interval_beyond_margin():
    cohorts = _cohorts(
        wer_deltas=(
            0.03,
            0.03,
            0.03,
            0.03,
        )
    )

    result = (
        evaluate_asr_matched_release_assurance(
            cohorts=cohorts,
            policy=_policy(
                wer_margin=0.01,
                cer_margin=None,
            ),
        )
    )

    assert result.normalized_wer is not None
    assert (
        result.normalized_wer.claim
        == ClaimAssessment.CONTRADICTED
    )

    assert (
        result.normalized_wer
        .interval
        .lower_bound
        > 0.01
    )

    assert result.claim == (
        ClaimAssessment.CONTRADICTED
    )


def test_interval_overlapping_margin_is_unresolved_not_contradicted():
    cohorts = _cohorts(
        wer_deltas=(
            -0.02,
            0.04,
            -0.02,
            0.04,
        )
    )

    result = (
        evaluate_asr_matched_release_assurance(
            cohorts=cohorts,
            policy=_policy(
                wer_margin=0.01,
                cer_margin=None,
            ),
        )
    )

    assessment = result.normalized_wer

    assert assessment is not None
    assert assessment.interval.ready is True

    assert (
        assessment.interval.lower_bound
        <= 0.01
    )
    assert (
        assessment.interval.upper_bound
        > 0.01
    )

    assert assessment.claim == (
        ClaimAssessment.UNRESOLVED
    )

    assert result.evidence == (
        EvidenceAssessment.SUFFICIENT
    )
    assert result.claim == (
        ClaimAssessment.UNRESOLVED
    )


def test_incomplete_metric_evidence_is_insufficient_and_unresolved():
    cohorts = _cohorts(
        wer_deltas=(
            0.0,
            0.0,
            0.0,
            0.0,
        )
    )

    records = []

    for pair in cohorts.normalized_wer.pairs:
        if pair.baseline.value is not None:
            records.append(
                _record(
                    metric="wer",
                    run_id=10,
                    test_case_id=(
                        pair.test_case_id
                    ),
                    value=(
                        pair.baseline.value
                    ),
                )
            )

        if (
            pair.test_case_id != 4
            and pair.candidate.value
            is not None
        ):
            records.append(
                _record(
                    metric="wer",
                    run_id=20,
                    test_case_id=(
                        pair.test_case_id
                    ),
                    value=(
                        pair.candidate.value
                    ),
                )
            )

    records.extend(
        _metric_records(
            metric="cer",
            deltas=(
                0.0,
                0.0,
                0.0,
                0.0,
            ),
        )
    )

    incomplete = (
        build_asr_matched_quality_cohorts(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(
                1,
                2,
                3,
                4,
            ),
            records=tuple(records),
        )
    )

    result = (
        evaluate_asr_matched_release_assurance(
            cohorts=incomplete,
            policy=_policy(
                wer_margin=0.01,
                cer_margin=None,
            ),
        )
    )

    assert result.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.evidence == (
        EvidenceAssessment.INSUFFICIENT
    )
    assert result.claim == (
        ClaimAssessment.UNRESOLVED
    )


def test_invalid_metric_evidence_invalidates_assurance():
    records = list(
        _metric_records(
            metric="wer",
            deltas=(
                0.0,
                0.0,
                0.0,
                0.0,
            ),
        )
    )

    records = [
        record
        for record
        in records
        if not (
            record.evaluation_run_id == 20
            and record.test_case_id == 4
        )
    ]

    records.append(
        _record(
            metric="wer",
            run_id=20,
            test_case_id=4,
            status=ObservationStatus.INVALID,
            status_detail=(
                "invalid WER evidence"
            ),
        )
    )

    records.extend(
        _metric_records(
            metric="cer",
            deltas=(
                0.0,
                0.0,
                0.0,
                0.0,
            ),
        )
    )

    cohorts = (
        build_asr_matched_quality_cohorts(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(
                1,
                2,
                3,
                4,
            ),
            records=tuple(records),
        )
    )

    result = (
        evaluate_asr_matched_release_assurance(
            cohorts=cohorts,
            policy=_policy(
                wer_margin=0.01,
                cer_margin=None,
            ),
        )
    )

    assert result.integrity == (
        IntegrityAssessment.INVALID
    )
    assert result.evidence == (
        EvidenceAssessment.INSUFFICIENT
    )
    assert result.claim == (
        ClaimAssessment.UNRESOLVED
    )


def test_disabled_metric_does_not_affect_combined_claim():
    cohorts = _cohorts(
        wer_deltas=(
            0.0,
            0.0,
            0.0,
            0.0,
        ),
        cer_deltas=(
            0.10,
            0.10,
            0.10,
            0.10,
        ),
    )

    result = (
        evaluate_asr_matched_release_assurance(
            cohorts=cohorts,
            policy=_policy(
                wer_margin=0.01,
                cer_margin=None,
            ),
        )
    )

    assert result.normalized_wer is not None
    assert result.normalized_cer is None

    assert result.claim == (
        ClaimAssessment.SUPPORTED
    )


def test_multiple_enabled_metrics_require_joint_support():
    cohorts = _cohorts(
        wer_deltas=(
            0.005,
            0.005,
            0.005,
            0.005,
        ),
        cer_deltas=(
            0.02,
            0.02,
            0.02,
            0.02,
        ),
    )

    result = (
        evaluate_asr_matched_release_assurance(
            cohorts=cohorts,
            policy=_policy(
                wer_margin=0.01,
                cer_margin=0.01,
            ),
        )
    )

    assert result.normalized_wer is not None
    assert result.normalized_cer is not None

    assert (
        result.normalized_wer.claim
        == ClaimAssessment.SUPPORTED
    )
    assert (
        result.normalized_cer.claim
        == ClaimAssessment.CONTRADICTED
    )

    assert result.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.evidence == (
        EvidenceAssessment.SUFFICIENT
    )
    assert result.claim == (
        ClaimAssessment.CONTRADICTED
    )
