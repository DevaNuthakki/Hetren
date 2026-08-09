from __future__ import annotations

from hvee.core.contracts import (
    MetricValueType,
    ObservationStatus,
)
from hvee.core.decision import (
    ClaimAssessment,
    CriticalAssessment,
    DecisionReason,
    DecisionVerdict,
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
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.release_decision import (
    evaluate_asr_matched_release_decision,
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
    wer_margin: float | None = 0.01,
    cer_margin: float | None = None,
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


def _records_for_metric(
    *,
    metric: str,
    deltas: tuple[float, ...],
) -> tuple[ObservationEvidenceRecord, ...]:
    records = []

    for test_case_id, delta in enumerate(
        deltas,
        start=1,
    ):
        baseline = (
            0.20
            + test_case_id * 0.01
        )

        records.extend(
            (
                _record(
                    metric=metric,
                    run_id=10,
                    test_case_id=test_case_id,
                    value=baseline,
                ),
                _record(
                    metric=metric,
                    run_id=20,
                    test_case_id=test_case_id,
                    value=baseline + delta,
                ),
            )
        )

    return tuple(records)


def _cohorts(
    *,
    wer_deltas: tuple[float, ...],
    cer_deltas: tuple[float, ...] | None = None,
):
    if cer_deltas is None:
        cer_deltas = tuple(
            0.0
            for _ in wer_deltas
        )

    records = (
        _records_for_metric(
            metric="wer",
            deltas=wer_deltas,
        )
        + _records_for_metric(
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
        records=records,
    )


def test_supported_noninferiority_produces_pass():
    result = (
        evaluate_asr_matched_release_decision(
            cohorts=_cohorts(
                wer_deltas=(
                    0.005,
                    0.005,
                    0.005,
                    0.005,
                )
            ),
            policy=_policy(),
        )
    )

    assert result.critical == (
        CriticalAssessment.CLEAR
    )

    assert result.assurance.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.assurance.evidence == (
        EvidenceAssessment.SUFFICIENT
    )
    assert result.assurance.claim == (
        ClaimAssessment.SUPPORTED
    )

    assert result.decision.verdict == (
        DecisionVerdict.PASS
    )
    assert result.decision.reason == (
        DecisionReason.CLAIM_SUPPORTED
    )


def test_contradicted_noninferiority_produces_fail():
    result = (
        evaluate_asr_matched_release_decision(
            cohorts=_cohorts(
                wer_deltas=(
                    0.03,
                    0.03,
                    0.03,
                    0.03,
                )
            ),
            policy=_policy(),
        )
    )

    assert result.assurance.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.assurance.evidence == (
        EvidenceAssessment.SUFFICIENT
    )
    assert result.assurance.claim == (
        ClaimAssessment.CONTRADICTED
    )

    assert result.decision.verdict == (
        DecisionVerdict.FAIL
    )
    assert result.decision.reason == (
        DecisionReason.CLAIM_CONTRADICTED
    )


def test_unresolved_claim_produces_inconclusive():
    result = (
        evaluate_asr_matched_release_decision(
            cohorts=_cohorts(
                wer_deltas=(
                    -0.02,
                    0.04,
                    -0.02,
                    0.04,
                )
            ),
            policy=_policy(),
        )
    )

    assert result.assurance.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.assurance.evidence == (
        EvidenceAssessment.SUFFICIENT
    )
    assert result.assurance.claim == (
        ClaimAssessment.UNRESOLVED
    )

    assert result.decision.verdict == (
        DecisionVerdict.INCONCLUSIVE
    )
    assert result.decision.reason == (
        DecisionReason.CLAIM_UNRESOLVED
    )


def test_incomplete_evidence_produces_inconclusive():
    records = list(
        _records_for_metric(
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

    records.extend(
        _records_for_metric(
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
        evaluate_asr_matched_release_decision(
            cohorts=cohorts,
            policy=_policy(),
        )
    )

    assert result.assurance.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.assurance.evidence == (
        EvidenceAssessment.INSUFFICIENT
    )
    assert result.assurance.claim == (
        ClaimAssessment.UNRESOLVED
    )

    assert result.decision.verdict == (
        DecisionVerdict.INCONCLUSIVE
    )
    assert result.decision.reason == (
        DecisionReason.EVIDENCE_INSUFFICIENT
    )


def test_invalid_evidence_produces_invalid():
    records = list(
        _records_for_metric(
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
                "invalid matched WER evidence"
            ),
        )
    )

    records.extend(
        _records_for_metric(
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
        evaluate_asr_matched_release_decision(
            cohorts=cohorts,
            policy=_policy(),
        )
    )

    assert result.assurance.integrity == (
        IntegrityAssessment.INVALID
    )
    assert result.assurance.evidence == (
        EvidenceAssessment.INSUFFICIENT
    )

    assert result.decision.verdict == (
        DecisionVerdict.INVALID
    )
    assert result.decision.reason == (
        DecisionReason.INTEGRITY_INVALID
    )


def test_multiple_enabled_metrics_require_joint_support_for_pass():
    result = (
        evaluate_asr_matched_release_decision(
            cohorts=_cohorts(
                wer_deltas=(
                    0.005,
                    0.005,
                    0.005,
                    0.005,
                ),
                cer_deltas=(
                    0.005,
                    0.005,
                    0.005,
                    0.005,
                ),
            ),
            policy=_policy(
                wer_margin=0.01,
                cer_margin=0.01,
            ),
        )
    )

    assert result.assurance.claim == (
        ClaimAssessment.SUPPORTED
    )
    assert result.decision.verdict == (
        DecisionVerdict.PASS
    )


def test_one_contradicted_enabled_metric_produces_fail():
    result = (
        evaluate_asr_matched_release_decision(
            cohorts=_cohorts(
                wer_deltas=(
                    0.005,
                    0.005,
                    0.005,
                    0.005,
                ),
                cer_deltas=(
                    0.03,
                    0.03,
                    0.03,
                    0.03,
                ),
            ),
            policy=_policy(
                wer_margin=0.01,
                cer_margin=0.01,
            ),
        )
    )

    assert result.assurance.claim == (
        ClaimAssessment.CONTRADICTED
    )
    assert result.decision.verdict == (
        DecisionVerdict.FAIL
    )
    assert result.decision.reason == (
        DecisionReason.CLAIM_CONTRADICTED
    )
