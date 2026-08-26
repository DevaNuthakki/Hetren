from dataclasses import replace

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.core.decision import (
    CriticalAssessment,
    DecisionReason,
    DecisionResult,
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
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    ASRCriticalNumberAssuranceStatus,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FINDINGS_METRIC,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    EN_US_CRITICAL_NUMBER_PROFILE,
    build_critical_number_fidelity_observations,
    evaluate_critical_number_fidelity,
)
from hvee.packs.asr.critical_number_release_shadow import (
    ASRCriticalNumberShadowEvidenceState,
    ASRCriticalNumberShadowTransition,
    evaluate_asr_critical_number_matched_release_shadow,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)


_REFERENCES = (
    "invoice 48217 total $1,250",
    "dose 5 mg",
    "pay 15 percent today",
    "meeting at 9:15 AM",
)


def _quality_record(
    *,
    metric: str,
    run_id: int,
    test_case_id: int,
    value: float,
) -> ObservationEvidenceRecord:
    if metric == "wer":
        metric_key = "asr.wer.normalized-basic"
        evaluator_key = "hetren.asr.wer.normalized-basic"
    else:
        metric_key = "asr.cer.normalized-basic"
        evaluator_key = "hetren.asr.cer.normalized-basic"

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


def _observation_record(
    observation: Observation,
    *,
    run_id: int,
    test_case_id: int,
) -> ObservationEvidenceRecord:
    return ObservationEvidenceRecord(
        metric_key=observation.metric_key,
        metric_version=observation.metric_version,
        evaluator_key=observation.evaluator_key,
        evaluator_version=observation.evaluator_version,
        evaluation_type=observation.evaluation_type,
        scope="test_case",
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
        status=observation.status,
        value_type=observation.value_type,
        value=observation.value,
        status_detail=observation.status_detail,
    )


def _critical_records(
    *,
    run_id: int,
    test_case_id: int,
    reference_text: str,
    generated_text: str,
) -> tuple[ObservationEvidenceRecord, ...]:
    evaluation = evaluate_critical_number_fidelity(
        reference_text=reference_text,
        generated_text=generated_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
    )
    return tuple(
        _observation_record(
            observation,
            run_id=run_id,
            test_case_id=test_case_id,
        )
        for observation in (
            build_critical_number_fidelity_observations(evaluation)
        )
    )


def _policy() -> ASRMatchedReleaseAssurancePolicyV1:
    return ASRMatchedReleaseAssurancePolicyV1(
        interval=PairedIntervalPolicy(
            method=PairedIntervalMethod.BOOTSTRAP_PERCENTILE_V1,
            confidence_level=0.95,
            minimum_usable_pairs=4,
            resamples=256,
            random_seed=12345,
        ),
        normalized_wer_noninferiority_margin=0.01,
        normalized_cer_noninferiority_margin=None,
    )


def _inputs(
    *,
    references: tuple[str, ...] = _REFERENCES,
    baseline_overrides: dict[int, str] | None = None,
    candidate_overrides: dict[int, str] | None = None,
):
    baseline_overrides = baseline_overrides or {}
    candidate_overrides = candidate_overrides or {}
    quality_records = []
    critical_records = []

    for test_case_id, reference in enumerate(references, start=1):
        baseline_value = 0.20 + test_case_id * 0.01
        for metric in ("wer", "cer"):
            quality_records.extend(
                (
                    _quality_record(
                        metric=metric,
                        run_id=10,
                        test_case_id=test_case_id,
                        value=baseline_value,
                    ),
                    _quality_record(
                        metric=metric,
                        run_id=20,
                        test_case_id=test_case_id,
                        value=baseline_value + 0.005,
                    ),
                )
            )

        critical_records.extend(
            _critical_records(
                run_id=10,
                test_case_id=test_case_id,
                reference_text=reference,
                generated_text=baseline_overrides.get(
                    test_case_id,
                    reference,
                ),
            )
        )
        critical_records.extend(
            _critical_records(
                run_id=20,
                test_case_id=test_case_id,
                reference_text=reference,
                generated_text=candidate_overrides.get(
                    test_case_id,
                    reference,
                ),
            )
        )

    return tuple(quality_records) + tuple(critical_records)


def _evaluate(
    *,
    references: tuple[str, ...] = _REFERENCES,
    baseline_overrides: dict[int, str] | None = None,
    candidate_overrides: dict[int, str] | None = None,
    transform_records=None,
):
    records = _inputs(
        references=references,
        baseline_overrides=baseline_overrides,
        candidate_overrides=candidate_overrides,
    )
    if transform_records is not None:
        records = transform_records(records)

    return evaluate_asr_critical_number_matched_release_shadow(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2, 3, 4),
        policy=_policy(),
        records=records,
    )


def test_candidate_violation_changes_only_hypothetical_decision():
    result = _evaluate(
        candidate_overrides={
            1: "invoice 48271 total $1,250",
        }
    )

    assert result.official.critical == CriticalAssessment.CLEAR
    assert result.official.decision.verdict == DecisionVerdict.PASS
    assert result.official.decision.reason == DecisionReason.CLAIM_SUPPORTED

    assert result.hypothetical_critical == CriticalAssessment.VIOLATED
    assert result.hypothetical_decision.verdict == DecisionVerdict.FAIL
    assert result.hypothetical_decision.reason == (
        DecisionReason.CRITICAL_VIOLATION
    )
    assert result.would_change_official_decision is True

    case = result.cases[0]
    assert case.baseline.state == (
        ASRCriticalNumberShadowEvidenceState.PRESERVED
    )
    assert case.candidate.state == (
        ASRCriticalNumberShadowEvidenceState.VIOLATED
    )
    assert case.transition == (
        ASRCriticalNumberShadowTransition.INTRODUCED_VIOLATION
    )
    assert any(
        finding["finding_type"] == "substitution"
        for finding in case.candidate.findings
    )


def test_clear_candidate_keeps_hypothetical_result_equal_to_official():
    result = _evaluate()

    assert result.hypothetical_critical == CriticalAssessment.CLEAR
    assert result.critical_integrity == IntegrityAssessment.VALID
    assert result.critical_evidence == EvidenceAssessment.SUFFICIENT
    assert result.hypothetical_decision == result.official.decision
    assert result.would_change_official_decision is False
    assert all(
        case.transition == ASRCriticalNumberShadowTransition.CLEAR
        for case in result.cases
    )


def test_not_applicable_case_is_explicit_and_critical_clear():
    result = _evaluate(
        references=(
            *_REFERENCES[:3],
            "plain transcript without numeric evidence",
        )
    )

    case = result.cases[3]
    assert case.baseline.state == (
        ASRCriticalNumberShadowEvidenceState.NOT_APPLICABLE
    )
    assert case.candidate.state == (
        ASRCriticalNumberShadowEvidenceState.NOT_APPLICABLE
    )
    assert case.transition == ASRCriticalNumberShadowTransition.CLEAR
    assert result.hypothetical_critical == CriticalAssessment.CLEAR


def test_unsupported_candidate_is_inconclusive_not_clear():
    result = _evaluate(
        candidate_overrides={
            2: "dose 1/2 mg",
        }
    )

    case = result.cases[1]
    assert case.candidate.state == (
        ASRCriticalNumberShadowEvidenceState.INCONCLUSIVE
    )
    assert result.hypothetical_critical is None
    assert result.critical_integrity == IntegrityAssessment.VALID
    assert result.critical_evidence == EvidenceAssessment.INSUFFICIENT
    assert result.hypothetical_decision.verdict == (
        DecisionVerdict.INCONCLUSIVE
    )
    assert result.hypothetical_decision.reason == (
        DecisionReason.EVIDENCE_INSUFFICIENT
    )
    assert result.official.decision.verdict == DecisionVerdict.PASS


def test_missing_candidate_observation_fails_closed():
    def remove_preserved(records):
        return tuple(
            record
            for record in records
            if not (
                record.evaluation_run_id == 20
                and record.test_case_id == 1
                and record.metric_key
                == CRITICAL_NUMBER_PRESERVED_METRIC.key
            )
        )

    result = _evaluate(transform_records=remove_preserved)

    assert result.cases[0].candidate.state == (
        ASRCriticalNumberShadowEvidenceState.MISSING
    )
    assert result.hypothetical_critical is None
    assert result.critical_evidence == EvidenceAssessment.INSUFFICIENT
    assert result.hypothetical_decision.verdict == (
        DecisionVerdict.INCONCLUSIVE
    )
    assert result.official.decision.verdict == DecisionVerdict.PASS


def test_proven_candidate_violation_dominates_another_missing_case():
    def remove_second_preserved(records):
        return tuple(
            record
            for record in records
            if not (
                record.evaluation_run_id == 20
                and record.test_case_id == 2
                and record.metric_key
                == CRITICAL_NUMBER_PRESERVED_METRIC.key
            )
        )

    result = _evaluate(
        candidate_overrides={
            1: "invoice 48271 total $1,250",
        },
        transform_records=remove_second_preserved,
    )

    assert result.cases[1].candidate.state == (
        ASRCriticalNumberShadowEvidenceState.MISSING
    )
    assert result.hypothetical_critical == CriticalAssessment.VIOLATED
    assert result.critical_evidence == EvidenceAssessment.SUFFICIENT
    assert result.hypothetical_decision.verdict == DecisionVerdict.FAIL
    assert result.hypothetical_decision.reason == (
        DecisionReason.CRITICAL_VIOLATION
    )


def test_duplicate_candidate_observation_marks_shadow_integrity_invalid():
    def duplicate_outcome(records):
        duplicate = next(
            record
            for record in records
            if (
                record.evaluation_run_id == 20
                and record.test_case_id == 1
                and record.metric_key
                == CRITICAL_NUMBER_OUTCOME_METRIC.key
            )
        )
        return records + (duplicate,)

    result = _evaluate(transform_records=duplicate_outcome)

    assert result.cases[0].candidate.state == (
        ASRCriticalNumberShadowEvidenceState.DUPLICATE
    )
    assert result.critical_integrity == IntegrityAssessment.INVALID
    assert result.hypothetical_decision.verdict == DecisionVerdict.INVALID
    assert result.hypothetical_decision.reason == (
        DecisionReason.INTEGRITY_INVALID
    )
    assert result.official.decision.verdict == DecisionVerdict.PASS


def test_inconsistent_candidate_findings_are_invalid_not_trusted():
    def forge_findings(records):
        forged = []
        for record in records:
            if (
                record.evaluation_run_id == 20
                and record.test_case_id == 1
                and record.metric_key
                == CRITICAL_NUMBER_FINDINGS_METRIC.key
            ):
                record = replace(record, value=[])
            forged.append(record)
        return tuple(forged)

    result = _evaluate(
        candidate_overrides={
            1: "invoice 48271 total $1,250",
        },
        transform_records=forge_findings,
    )

    assert result.cases[0].candidate.state == (
        ASRCriticalNumberShadowEvidenceState.INVALID
    )
    assert result.critical_integrity == IntegrityAssessment.INVALID
    assert result.hypothetical_decision.verdict == DecisionVerdict.INVALID
    assert result.official.decision.verdict == DecisionVerdict.PASS


def test_baseline_gap_does_not_hide_proven_candidate_violation():
    def remove_baseline_outcome(records):
        return tuple(
            record
            for record in records
            if not (
                record.evaluation_run_id == 10
                and record.test_case_id == 1
                and record.metric_key
                == CRITICAL_NUMBER_OUTCOME_METRIC.key
            )
        )

    result = _evaluate(
        candidate_overrides={
            1: "invoice 48271 total $1,250",
        },
        transform_records=remove_baseline_outcome,
    )

    assert result.cases[0].baseline.state == (
        ASRCriticalNumberShadowEvidenceState.MISSING
    )
    assert result.cases[0].transition == (
        ASRCriticalNumberShadowTransition.CANDIDATE_VIOLATION
    )
    assert result.critical_integrity == IntegrityAssessment.VALID
    assert result.hypothetical_critical == CriticalAssessment.VIOLATED
    assert result.hypothetical_decision.verdict == DecisionVerdict.FAIL


def test_resolved_baseline_violation_does_not_fail_candidate():
    result = _evaluate(
        baseline_overrides={
            1: "invoice 48271 total $1,250",
        }
    )

    assert result.cases[0].transition == (
        ASRCriticalNumberShadowTransition.RESOLVED_VIOLATION
    )
    assert result.hypothetical_critical == CriticalAssessment.CLEAR
    assert result.hypothetical_decision == result.official.decision


def test_shadow_is_bound_to_experimental_non_enforcing_assurance():
    result = _evaluate()

    assert result.assurance_status == (
        ASRCriticalNumberAssuranceStatus.EXPERIMENTAL
    )
    assert result.assurance_sha256 == (
        CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1
    )
    assert result.production_qualified is False
    assert result.release_enforcement_eligible is False


def test_shadow_evaluation_is_deterministic():
    first = _evaluate(
        candidate_overrides={
            1: "invoice 48271 total $1,250",
        }
    )
    second = _evaluate(
        candidate_overrides={
            1: "invoice 48271 total $1,250",
        }
    )

    assert first == second


def test_official_assurance_is_rebuilt_from_the_same_raw_records():
    def degrade_candidate_wer(records):
        return tuple(
            replace(record, value=record.value + 0.03)
            if (
                record.evaluation_run_id == 20
                and record.metric_key == "asr.wer.normalized-basic"
            )
            else record
            for record in records
        )

    result = _evaluate(transform_records=degrade_candidate_wer)

    assert result.official.decision.verdict == DecisionVerdict.FAIL
    assert result.official.decision.reason == (
        DecisionReason.CLAIM_CONTRADICTED
    )
    assert result.hypothetical_decision == result.official.decision


def test_shadow_result_rejects_a_forged_hypothetical_decision():
    result = _evaluate()

    with pytest.raises(
        HveeContractError,
        match="shadow decision is inconsistent",
    ):
        replace(
            result,
            hypothetical_decision=DecisionResult(
                verdict=DecisionVerdict.FAIL,
                reason=DecisionReason.CRITICAL_VIOLATION,
            ),
        )


def test_shadow_result_rejects_a_forged_assurance_digest():
    result = _evaluate()

    with pytest.raises(
        HveeContractError,
        match="sealed v1 artifact",
    ):
        replace(
            result,
            assurance_sha256="0" * 64,
        )


def test_shadow_side_rejects_findings_reclassified_as_preserved():
    result = _evaluate(
        candidate_overrides={
            1: "invoice 48271 total $1,250",
        }
    )

    with pytest.raises(
        HveeContractError,
        match="state does not match",
    ):
        replace(
            result.cases[0].candidate,
            state=ASRCriticalNumberShadowEvidenceState.PRESERVED,
            outcome=(
                result.cases[0].baseline.outcome
            ),
        )


def test_records_must_be_raw_observation_tuple():
    records = _inputs()

    with pytest.raises(
        HveeContractError,
        match="observation tuple",
    ):
        evaluate_asr_critical_number_matched_release_shadow(
            baseline_run_id=10,
            candidate_run_id=20,
            declared_test_case_ids=(1, 2, 3, 4),
            policy=_policy(),
            records=list(records),  # type: ignore[arg-type]
        )
