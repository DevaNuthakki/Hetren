import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.decision import (
    ClaimAssessment,
    CriticalAssessment,
    DecisionInputs,
    DecisionReason,
    DecisionVerdict,
    EvidenceAssessment,
    IntegrityAssessment,
    decide,
)
from hvee.core.evidence_readiness import (
    EvidenceTarget,
    ObservationRequirement,
    assess_evidence_readiness,
)
from hvee.core.observation_evidence import (
    ObservationEvidenceRecord,
)


def target(
    *,
    run_id: int = 10,
    test_case_id: int | None = 20,
) -> EvidenceTarget:
    return EvidenceTarget(
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
    )


def requirement(
    metric_key: str,
    *,
    value_type: MetricValueType = (
        MetricValueType.INTEGER
    ),
) -> ObservationRequirement:
    return ObservationRequirement(
        metric_key=metric_key,
        metric_version="1.0.0",
        evaluator_key="hetren.asr.test",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        scope="test_case",
        value_type=value_type,
    )


def record(
    metric_key: str,
    *,
    status: ObservationStatus = (
        ObservationStatus.SUCCESS
    ),
    value_type: MetricValueType = (
        MetricValueType.INTEGER
    ),
    value: object | None = 1,
    status_detail: str | None = None,
    run_id: int = 10,
    test_case_id: int = 20,
) -> ObservationEvidenceRecord:
    return ObservationEvidenceRecord(
        metric_key=metric_key,
        metric_version="1.0.0",
        evaluator_key="hetren.asr.test",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        scope="test_case",
        evaluation_run_id=run_id,
        test_case_id=test_case_id,
        status=status,
        value_type=value_type,
        value=value,
        status_detail=status_detail,
    )


def assess(
    *,
    records,
    requirements,
    evidence_target=None,
):
    return assess_evidence_readiness(
        records=records,
        requirements=requirements,
        target=(
            evidence_target
            if evidence_target is not None
            else target()
        ),
    )


def test_all_required_success_observations_are_sufficient():
    result = assess(
        records=[
            record("asr.first"),
            record("asr.second"),
        ],
        requirements=[
            requirement("asr.first"),
            requirement("asr.second"),
        ],
    )

    assert result.integrity == IntegrityAssessment.VALID
    assert result.evidence == EvidenceAssessment.SUFFICIENT
    assert result.required_count == 2
    assert result.usable_count == 2
    assert result.missing == ()
    assert result.unavailable == ()
    assert result.invalid == ()
    assert result.duplicates == ()


def test_missing_required_observation_is_insufficient():
    result = assess(
        records=[
            record("asr.present"),
        ],
        requirements=[
            requirement("asr.present"),
            requirement("asr.missing"),
        ],
    )

    assert result.integrity == IntegrityAssessment.VALID
    assert result.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.usable_count == 1
    assert [
        item.metric_key
        for item in result.missing
    ] == ["asr.missing"]


@pytest.mark.parametrize(
    "status",
    [
        ObservationStatus.ABSTAINED,
        ObservationStatus.UNSUPPORTED,
        ObservationStatus.TIMED_OUT,
        ObservationStatus.FAILED,
        ObservationStatus.CANCELLED,
    ],
)
def test_unavailable_statuses_are_insufficient_not_invalid(
    status,
):
    result = assess(
        records=[
            record(
                "asr.required",
                status=status,
                value=None,
                status_detail="not available",
            )
        ],
        requirements=[
            requirement("asr.required"),
        ],
    )

    assert result.integrity == IntegrityAssessment.VALID
    assert result.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.usable_count == 0
    assert len(result.unavailable) == 1
    assert result.unavailable[0].status == status


def test_invalid_observation_invalidates_integrity():
    result = assess(
        records=[
            record(
                "asr.required",
                status=ObservationStatus.INVALID,
                value=None,
                status_detail="invalid evaluator output",
            )
        ],
        requirements=[
            requirement("asr.required"),
        ],
    )

    assert result.integrity == IntegrityAssessment.INVALID
    assert result.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.usable_count == 0
    assert len(result.invalid) == 1


def test_value_type_mismatch_invalidates_integrity():
    result = assess(
        records=[
            record(
                "asr.required",
                value_type=MetricValueType.BOOLEAN,
                value=True,
            )
        ],
        requirements=[
            requirement(
                "asr.required",
                value_type=MetricValueType.INTEGER,
            ),
        ],
    )

    assert result.integrity == IntegrityAssessment.INVALID
    assert result.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.usable_count == 0
    assert len(result.invalid) == 1
    assert "value type" in result.invalid[0].status_detail


def test_duplicate_matching_identity_is_invalid():
    result = assess(
        records=[
            record("asr.required"),
            record("asr.required"),
        ],
        requirements=[
            requirement("asr.required"),
        ],
    )

    assert result.integrity == IntegrityAssessment.INVALID
    assert result.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.usable_count == 0
    assert result.duplicates == (
        requirement("asr.required"),
    )


def test_same_identity_for_another_test_case_is_not_a_duplicate():
    result = assess(
        records=[
            record(
                "asr.required",
                test_case_id=20,
            ),
            record(
                "asr.required",
                test_case_id=21,
            ),
        ],
        requirements=[
            requirement("asr.required"),
        ],
        evidence_target=target(
            test_case_id=20,
        ),
    )

    assert result.integrity == IntegrityAssessment.VALID
    assert result.evidence == EvidenceAssessment.SUFFICIENT
    assert result.usable_count == 1


def test_wrong_test_case_cannot_satisfy_requirement():
    result = assess(
        records=[
            record(
                "asr.required",
                test_case_id=21,
            ),
        ],
        requirements=[
            requirement("asr.required"),
        ],
        evidence_target=target(
            test_case_id=20,
        ),
    )

    assert result.integrity == IntegrityAssessment.VALID
    assert result.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.missing == (
        requirement("asr.required"),
    )


def test_wrong_run_cannot_satisfy_requirement():
    result = assess(
        records=[
            record(
                "asr.required",
                run_id=11,
            ),
        ],
        requirements=[
            requirement("asr.required"),
        ],
    )

    assert result.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.missing == (
        requirement("asr.required"),
    )


def test_additional_unrequired_observations_are_allowed():
    result = assess(
        records=[
            record("asr.required"),
            record(
                "asr.extra",
                status=ObservationStatus.FAILED,
                value=None,
                status_detail="irrelevant failure",
            ),
        ],
        requirements=[
            requirement("asr.required"),
        ],
    )

    assert result.integrity == IntegrityAssessment.VALID
    assert result.evidence == EvidenceAssessment.SUFFICIENT
    assert result.required_count == 1
    assert result.usable_count == 1


def test_requirement_identity_includes_evaluator_version():
    required = ObservationRequirement(
        metric_key="asr.metric",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.test",
        evaluator_version="2.0.0",
        evaluation_type="asr",
        scope="test_case",
        value_type=MetricValueType.INTEGER,
    )

    result = assess(
        records=[
            record("asr.metric"),
        ],
        requirements=[required],
    )

    assert result.evidence == EvidenceAssessment.INSUFFICIENT
    assert result.missing == (required,)


def test_requirement_identity_includes_scope():
    required = ObservationRequirement(
        metric_key="asr.metric",
        metric_version="1.0.0",
        evaluator_key="hetren.asr.test",
        evaluator_version="1.0.0",
        evaluation_type="asr",
        scope="run",
        value_type=MetricValueType.INTEGER,
    )

    result = assess(
        records=[
            record("asr.metric"),
        ],
        requirements=[required],
    )

    assert result.evidence == EvidenceAssessment.INSUFFICIENT


def test_duplicate_requirement_contract_is_rejected():
    required = requirement("asr.required")

    with pytest.raises(
        HveeContractError,
        match="duplicate scientific identities",
    ):
        assess(
            records=[
                record("asr.required"),
            ],
            requirements=[
                required,
                required,
            ],
        )


def test_empty_requirement_contract_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="at least one",
    ):
        assess(
            records=[],
            requirements=[],
        )


def test_invalid_requirement_scope_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="scope",
    ):
        ObservationRequirement(
            metric_key="asr.metric",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.test",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            scope="unknown",
            value_type=MetricValueType.INTEGER,
        )


def test_invalid_requirement_value_type_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="value type",
    ):
        ObservationRequirement(
            metric_key="asr.metric",
            metric_version="1.0.0",
            evaluator_key="hetren.asr.test",
            evaluator_version="1.0.0",
            evaluation_type="asr",
            scope="test_case",
            value_type="integer",
        )


def test_invalid_target_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="evaluation run id",
    ):
        EvidenceTarget(
            evaluation_run_id=0,
            test_case_id=20,
        )


def test_test_case_requirement_needs_test_case_target():
    with pytest.raises(
        HveeContractError,
        match="test-case target",
    ):
        assess(
            records=[],
            requirements=[
                requirement("asr.required"),
            ],
            evidence_target=target(
                test_case_id=None,
            ),
        )


def test_readiness_feeds_decision_kernel_without_domain_logic():
    readiness = assess(
        records=[
            record(
                "asr.required",
                status=ObservationStatus.TIMED_OUT,
                value=None,
                status_detail="evaluator timed out",
            )
        ],
        requirements=[
            requirement("asr.required"),
        ],
    )

    decision = decide(
        DecisionInputs(
            integrity=readiness.integrity,
            critical=CriticalAssessment.CLEAR,
            evidence=readiness.evidence,
            claim=ClaimAssessment.SUPPORTED,
        )
    )

    assert decision.verdict == DecisionVerdict.INCONCLUSIVE
    assert (
        decision.reason
        == DecisionReason.EVIDENCE_INSUFFICIENT
    )


def test_invalid_evidence_feeds_invalid_decision():
    readiness = assess(
        records=[
            record(
                "asr.required",
                status=ObservationStatus.INVALID,
                value=None,
                status_detail="invalid evidence",
            )
        ],
        requirements=[
            requirement("asr.required"),
        ],
    )

    decision = decide(
        DecisionInputs(
            integrity=readiness.integrity,
            critical=CriticalAssessment.VIOLATED,
            evidence=readiness.evidence,
            claim=ClaimAssessment.CONTRADICTED,
        )
    )

    assert decision.verdict == DecisionVerdict.INVALID
    assert (
        decision.reason
        == DecisionReason.INTEGRITY_INVALID
    )
