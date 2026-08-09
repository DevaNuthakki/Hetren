from __future__ import annotations

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    ObservationStatus,
)
from hvee.core.decision import (
    EvidenceAssessment,
    IntegrityAssessment,
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
from hvee.core.paired_assurance import (
    PairedIntervalMethod,
    PairedIntervalPolicy,
)
from hvee.core.paired_interval import (
    PairedIntervalReason,
    calculate_paired_mean_delta_interval,
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


def _policy(
    *,
    minimum: int = 2,
    resamples: int = 2000,
    seed: int = 12345,
) -> PairedIntervalPolicy:
    return PairedIntervalPolicy(
        method=(
            PairedIntervalMethod
            .BOOTSTRAP_PERCENTILE_V1
        ),
        confidence_level=0.95,
        minimum_usable_pairs=minimum,
        resamples=resamples,
        random_seed=seed,
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


def _cohort(
    pairs: tuple[
        tuple[int, float, float],
        ...,
    ],
):
    records = []

    for (
        test_case_id,
        baseline,
        candidate,
    ) in pairs:
        records.extend(
            (
                _record(
                    run_id=10,
                    test_case_id=test_case_id,
                    value=baseline,
                ),
                _record(
                    run_id=20,
                    test_case_id=test_case_id,
                    value=candidate,
                ),
            )
        )

    return build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=tuple(
            test_case_id
            for test_case_id, _, _
            in pairs
        ),
        requirement=REQUIREMENT,
        records=tuple(records),
    )


def test_constant_delta_has_exact_interval():
    cohort = _cohort(
        (
            (1, 0.30, 0.32),
            (2, 0.20, 0.22),
            (3, 0.10, 0.12),
            (4, 0.40, 0.42),
        )
    )

    result = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=_policy(),
        )
    )

    assert result.ready is True
    assert result.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.evidence == (
        EvidenceAssessment.SUFFICIENT
    )
    assert result.reason == (
        PairedIntervalReason.READY
    )

    assert result.mean_delta == (
        pytest.approx(0.02)
    )
    assert result.lower_bound == (
        pytest.approx(0.02)
    )
    assert result.upper_bound == (
        pytest.approx(0.02)
    )


def test_bootstrap_is_deterministic_for_same_policy():
    cohort = _cohort(
        (
            (1, 0.30, 0.20),
            (2, 0.10, 0.15),
            (3, 0.20, 0.20),
            (4, 0.40, 0.35),
            (5, 0.15, 0.18),
        )
    )

    policy = _policy(
        resamples=3000,
        seed=98765,
    )

    first = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=policy,
        )
    )
    second = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=policy,
        )
    )

    assert first == second
    assert first.ready is True

    assert first.mean_delta == (
        pytest.approx(
            (-0.10 + 0.05 + 0.0 - 0.05 + 0.03)
            / 5
        )
    )

    assert first.lower_bound is not None
    assert first.upper_bound is not None
    assert (
        first.lower_bound
        <= first.upper_bound
    )


def test_incomplete_cohort_produces_no_interval():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.20,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                value=0.10,
            ),
            _record(
                run_id=10,
                test_case_id=2,
                value=0.30,
            ),
        ),
    )

    result = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=_policy(),
        )
    )

    assert result.ready is False
    assert result.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.evidence == (
        EvidenceAssessment.INSUFFICIENT
    )
    assert result.reason == (
        PairedIntervalReason.COHORT_INCOMPLETE
    )

    assert result.mean_delta is None
    assert result.lower_bound is None
    assert result.upper_bound is None


def test_invalid_cohort_produces_no_interval():
    cohort = build_matched_observation_cohort(
        baseline_run_id=10,
        candidate_run_id=20,
        declared_test_case_ids=(1, 2),
        requirement=REQUIREMENT,
        records=(
            _record(
                run_id=10,
                test_case_id=1,
                value=0.20,
            ),
            _record(
                run_id=20,
                test_case_id=1,
                value=0.10,
            ),
            _record(
                run_id=10,
                test_case_id=2,
                value=0.30,
            ),
            _record(
                run_id=20,
                test_case_id=2,
                status=ObservationStatus.INVALID,
                status_detail="invalid observation",
            ),
        ),
    )

    result = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=_policy(),
        )
    )

    assert result.ready is False
    assert result.integrity == (
        IntegrityAssessment.INVALID
    )
    assert result.evidence == (
        EvidenceAssessment.INSUFFICIENT
    )
    assert result.reason == (
        PairedIntervalReason.INTEGRITY_INVALID
    )

    assert result.mean_delta is None
    assert result.lower_bound is None
    assert result.upper_bound is None


def test_minimum_pair_requirement_is_enforced():
    cohort = _cohort(
        (
            (1, 0.20, 0.10),
            (2, 0.30, 0.20),
            (3, 0.10, 0.10),
        )
    )

    result = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=_policy(
                minimum=4
            ),
        )
    )

    assert result.ready is False
    assert result.integrity == (
        IntegrityAssessment.VALID
    )
    assert result.evidence == (
        EvidenceAssessment.INSUFFICIENT
    )
    assert result.reason == (
        PairedIntervalReason
        .MINIMUM_PAIRS_NOT_MET
    )

    assert result.usable_pairs == 3
    assert result.mean_delta is None
    assert result.lower_bound is None
    assert result.upper_bound is None


def test_exact_minimum_pair_requirement_is_allowed():
    cohort = _cohort(
        (
            (1, 0.30, 0.20),
            (2, 0.20, 0.10),
            (3, 0.10, 0.05),
        )
    )

    result = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=_policy(
                minimum=3
            ),
        )
    )

    assert result.ready is True
    assert result.usable_pairs == 3
    assert result.mean_delta is not None
    assert result.lower_bound is not None
    assert result.upper_bound is not None


def test_wrong_cohort_type_is_rejected():
    with pytest.raises(
        HveeContractError,
        match="MatchedObservationCohort",
    ):
        calculate_paired_mean_delta_interval(
            cohort=object(),  # type: ignore[arg-type]
            policy=_policy(),
        )


def test_wrong_policy_type_is_rejected():
    cohort = _cohort(
        (
            (1, 0.20, 0.10),
            (2, 0.30, 0.20),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="PairedIntervalPolicy",
    ):
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=object(),  # type: ignore[arg-type]
        )


def test_bootstrap_percentile_v1_golden_vector():
    """
    Pin the deterministic v1 resampling procedure.

    Changing these bounds requires a new statistical method version,
    not a silent implementation change.
    """

    cohort = _cohort(
        (
            (1, 0.20, 0.10),
            (2, 0.10, 0.15),
            (3, 0.20, 0.20),
            (4, 0.40, 0.35),
            (5, 0.15, 0.18),
        )
    )

    policy = PairedIntervalPolicy(
        method=(
            PairedIntervalMethod
            .BOOTSTRAP_PERCENTILE_V1
        ),
        confidence_level=0.95,
        minimum_usable_pairs=2,
        resamples=128,
        random_seed=98765,
    )

    result = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=policy,
        )
    )

    assert result.ready is True

    assert result.mean_delta == (
        pytest.approx(
            -0.014000000000000002,
            abs=1e-15,
        )
    )

    assert result.lower_bound == (
        pytest.approx(
            -0.06330000000000001,
            abs=1e-15,
        )
    )

    assert result.upper_bound == (
        pytest.approx(
            0.035300000000000005,
            abs=1e-15,
        )
    )


def test_bootstrap_result_is_independent_of_global_random_state():
    import random

    cohort = _cohort(
        (
            (1, 0.30, 0.20),
            (2, 0.10, 0.15),
            (3, 0.20, 0.20),
            (4, 0.40, 0.35),
        )
    )

    policy = _policy(
        resamples=256,
        seed=444,
    )

    random.seed(1)
    first = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=policy,
        )
    )

    for _ in range(1000):
        random.random()

    random.seed(999999)

    second = (
        calculate_paired_mean_delta_interval(
            cohort=cohort,
            policy=policy,
        )
    )

    assert first == second
