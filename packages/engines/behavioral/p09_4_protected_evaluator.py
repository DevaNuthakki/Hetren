"""Separated pure evaluator for the preregistered P09.4 protected study.

This module does not execute treatment.

It does not generate protected cases.

It does not create randomness.

It evaluates already-frozen treatment records against evaluator-only hidden
assignments.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import comb

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    canonical_sha256,
)
from packages.engines.behavioral.p09_4_protected_generation import (
    HIDDEN_STRATA,
    IN_RFS_CASES,
    OUT_OF_RFS_CASES,
    P094ProtectedHiddenAssignment,
    TOTAL_CASES,
)
from packages.engines.behavioral.p09_4_scientific_arms import (
    P094ScientificArm,
)


class P094EvaluationDecision(
    str,
    Enum,
):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    BLOCKED = "blocked"


@dataclass(
    frozen=True
)
class P094ProtectedTreatmentRecord:
    case_id: str
    arm: P094ScientificArm
    status: DiagnosisStatus
    diagnosed_hypothesis_key: str | None
    actual_cost_units: int
    experiment_count: int
    workflow_step_count: int

    def __post_init__(
        self,
    ) -> None:
        if (
            not isinstance(
                self.case_id,
                str,
            )
            or not self.case_id
        ):
            raise ContractError(
                "case_id is required"
            )

        if not isinstance(
            self.arm,
            P094ScientificArm,
        ):
            raise ContractError(
                "arm must be a P094ScientificArm"
            )

        if not isinstance(
            self.status,
            DiagnosisStatus,
        ):
            raise ContractError(
                "status must be a DiagnosisStatus"
            )

        if (
            self.status
            is DiagnosisStatus.ACTIVE
        ):
            raise ContractError(
                "protected treatment record must be terminal"
            )

        if (
            self.status
            is DiagnosisStatus.DIAGNOSED
        ):
            if (
                not isinstance(
                    self.diagnosed_hypothesis_key,
                    str,
                )
                or not self.diagnosed_hypothesis_key
            ):
                raise ContractError(
                    "diagnosed treatment requires a hypothesis key"
                )

        elif (
            self.diagnosed_hypothesis_key
            is not None
        ):
            raise ContractError(
                "non-diagnosed treatment cannot retain a hypothesis key"
            )

        for (
            value,
            name,
        ) in (
            (
                self.actual_cost_units,
                "actual_cost_units",
            ),
            (
                self.experiment_count,
                "experiment_count",
            ),
            (
                self.workflow_step_count,
                "workflow_step_count",
            ),
        ):
            if (
                isinstance(
                    value,
                    bool,
                )
                or not isinstance(
                    value,
                    int,
                )
                or value < 0
            ):
                raise ContractError(
                    f"{name} must be a non-negative integer"
                )

        if (
            self.actual_cost_units
            > 13
        ):
            raise ContractError(
                "treatment cost exceeds frozen budget 13"
            )

        if (
            self.arm
            is P094ScientificArm.TRACE_ONLY
            and (
                self.actual_cost_units
                != 0
                or self.experiment_count
                != 0
                or self.workflow_step_count
                != 0
            )
        ):
            raise ContractError(
                "C0 cannot contain active replay resource use"
            )


@dataclass(
    frozen=True
)
class P094ArmEvaluation:
    arm: P094ScientificArm
    in_rfs_denominator: int
    correct_specific_count: int
    false_specific_count: int
    inconclusive_count: int
    budget_exhausted_count: int
    total_actual_cost_units: int
    total_experiment_count: int
    total_workflow_step_count: int

    @property
    def correct_specific_rate(
        self,
    ) -> float:
        return (
            self.correct_specific_count
            / self.in_rfs_denominator
        )


@dataclass(
    frozen=True
)
class P094ProtectedEvaluation:
    decision: P094EvaluationDecision
    integrity_valid: bool
    integrity_error: str | None
    arm_metrics: tuple[
        P094ArmEvaluation,
        ...,
    ]
    c3_only_correct: int | None
    c2_only_correct: int | None
    both_correct: int | None
    neither_correct: int | None
    c3_minus_c2_correct_specific_rate: float | None
    exact_mcnemar_p_value: float | None
    c3_nonworse_fault_strata: int | None
    c3_false_specific_count: int | None
    support_criteria: tuple[
        tuple[
            str,
            bool,
        ],
        ...,
    ]

    @property
    def evaluation_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            {
                "decision":
                    self.decision.value,

                "integrity_valid":
                    self.integrity_valid,

                "integrity_error":
                    self.integrity_error,

                "arm_metrics":
                    [
                        {
                            "arm":
                                metric.arm.value,

                            "in_rfs_denominator":
                                metric.in_rfs_denominator,

                            "correct_specific_count":
                                metric.correct_specific_count,

                            "false_specific_count":
                                metric.false_specific_count,

                            "inconclusive_count":
                                metric.inconclusive_count,

                            "budget_exhausted_count":
                                metric.budget_exhausted_count,

                            "total_actual_cost_units":
                                metric.total_actual_cost_units,

                            "total_experiment_count":
                                metric.total_experiment_count,

                            "total_workflow_step_count":
                                metric.total_workflow_step_count,
                        }
                        for metric
                        in self.arm_metrics
                    ],

                "c3_only_correct":
                    self.c3_only_correct,

                "c2_only_correct":
                    self.c2_only_correct,

                "both_correct":
                    self.both_correct,

                "neither_correct":
                    self.neither_correct,

                "c3_minus_c2_correct_specific_rate":
                    self.c3_minus_c2_correct_specific_rate,

                "exact_mcnemar_p_value":
                    self.exact_mcnemar_p_value,

                "c3_nonworse_fault_strata":
                    self.c3_nonworse_fault_strata,

                "c3_false_specific_count":
                    self.c3_false_specific_count,

                "support_criteria":
                    self.support_criteria,
            }
        )


def exact_two_sided_mcnemar_p_value(
    *,
    c3_only_correct: int,
    c2_only_correct: int,
) -> float:
    for (
        value,
        name,
    ) in (
        (
            c3_only_correct,
            "c3_only_correct",
        ),
        (
            c2_only_correct,
            "c2_only_correct",
        ),
    ):
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
            or value < 0
        ):
            raise ContractError(
                f"{name} must be a non-negative integer"
            )

    discordant = (
        c3_only_correct
        + c2_only_correct
    )

    if discordant == 0:
        return 1.0

    smaller = min(
        c3_only_correct,
        c2_only_correct,
    )

    tail = sum(
        comb(
            discordant,
            k,
        )
        for k
        in range(
            smaller + 1
        )
    )

    return min(
        1.0,
        (
            2.0
            * tail
            / (
                2
                ** discordant
            )
        ),
    )


def _blocked(
    message: str,
) -> P094ProtectedEvaluation:
    return P094ProtectedEvaluation(
        decision=(
            P094EvaluationDecision.BLOCKED
        ),
        integrity_valid=False,
        integrity_error=message,
        arm_metrics=(),
        c3_only_correct=None,
        c2_only_correct=None,
        both_correct=None,
        neither_correct=None,
        c3_minus_c2_correct_specific_rate=None,
        exact_mcnemar_p_value=None,
        c3_nonworse_fault_strata=None,
        c3_false_specific_count=None,
        support_criteria=(),
    )


def _is_correct_specific(
    record: P094ProtectedTreatmentRecord,
    truth: P094ProtectedHiddenAssignment,
) -> bool:
    return (
        truth.expected_hypothesis_key
        is not None
        and record.status
        is DiagnosisStatus.DIAGNOSED
        and record.diagnosed_hypothesis_key
        == truth.expected_hypothesis_key
    )


def _is_false_specific(
    record: P094ProtectedTreatmentRecord,
    truth: P094ProtectedHiddenAssignment,
) -> bool:
    if (
        record.status
        is not DiagnosisStatus.DIAGNOSED
    ):
        return False

    if (
        truth.expected_hypothesis_key
        is None
    ):
        return True

    return (
        record.diagnosed_hypothesis_key
        != truth.expected_hypothesis_key
    )


def evaluate_protected_records(
    *,
    treatment_records: tuple[
        P094ProtectedTreatmentRecord,
        ...,
    ],
    hidden_assignments: tuple[
        P094ProtectedHiddenAssignment,
        ...,
    ],
) -> P094ProtectedEvaluation:
    if not isinstance(
        treatment_records,
        tuple,
    ):
        raise ContractError(
            "treatment_records must be a tuple"
        )

    if not isinstance(
        hidden_assignments,
        tuple,
    ):
        raise ContractError(
            "hidden_assignments must be a tuple"
        )

    if len(
        hidden_assignments
    ) != TOTAL_CASES:
        return _blocked(
            "hidden assignment denominator is not 144"
        )

    if len(
        treatment_records
    ) != (
        TOTAL_CASES
        * len(
            P094ScientificArm
        )
    ):
        return _blocked(
            "treatment record denominator is not 576"
        )

    truth_by_case = {}

    for truth in hidden_assignments:
        if not isinstance(
            truth,
            P094ProtectedHiddenAssignment,
        ):
            return _blocked(
                "hidden assignment has invalid type"
            )

        if truth.case_id in truth_by_case:
            return _blocked(
                "duplicate hidden case ID"
            )

        truth_by_case[
            truth.case_id
        ] = truth

    if len(
        truth_by_case
    ) != TOTAL_CASES:
        return _blocked(
            "hidden case-ID set is incomplete"
        )

    record_by_pair = {}

    for record in treatment_records:
        if not isinstance(
            record,
            P094ProtectedTreatmentRecord,
        ):
            return _blocked(
                "treatment record has invalid type"
            )

        if record.case_id not in truth_by_case:
            return _blocked(
                "treatment record references unknown case"
            )

        pair = (
            record.case_id,
            record.arm,
        )

        if pair in record_by_pair:
            return _blocked(
                "duplicate case-arm treatment record"
            )

        record_by_pair[
            pair
        ] = record

    expected_pairs = {
        (
            case_id,
            arm,
        )
        for case_id
        in truth_by_case
        for arm
        in P094ScientificArm
    }

    if (
        set(
            record_by_pair
        )
        != expected_pairs
    ):
        return _blocked(
            "case-arm treatment matrix is incomplete"
        )

    in_rfs_truth = tuple(
        truth
        for truth
        in hidden_assignments
        if truth.in_rfs
    )

    out_of_rfs_truth = tuple(
        truth
        for truth
        in hidden_assignments
        if not truth.in_rfs
    )

    if len(
        in_rfs_truth
    ) != IN_RFS_CASES:
        return _blocked(
            "in-RFS denominator is not 120"
        )

    if len(
        out_of_rfs_truth
    ) != OUT_OF_RFS_CASES:
        return _blocked(
            "out-of-RFS denominator is not 24"
        )

    arm_metrics = []

    for arm in P094ScientificArm:
        arm_records = tuple(
            record_by_pair[
                (
                    truth.case_id,
                    arm,
                )
            ]
            for truth
            in hidden_assignments
        )

        correct_specific_count = sum(
            _is_correct_specific(
                record_by_pair[
                    (
                        truth.case_id,
                        arm,
                    )
                ],
                truth,
            )
            for truth
            in in_rfs_truth
        )

        false_specific_count = sum(
            _is_false_specific(
                record_by_pair[
                    (
                        truth.case_id,
                        arm,
                    )
                ],
                truth,
            )
            for truth
            in hidden_assignments
        )

        arm_metrics.append(
            P094ArmEvaluation(
                arm=arm,
                in_rfs_denominator=(
                    IN_RFS_CASES
                ),
                correct_specific_count=(
                    correct_specific_count
                ),
                false_specific_count=(
                    false_specific_count
                ),
                inconclusive_count=sum(
                    record.status
                    is DiagnosisStatus.INCONCLUSIVE
                    for record
                    in arm_records
                ),
                budget_exhausted_count=sum(
                    record.status
                    is DiagnosisStatus.BUDGET_EXHAUSTED
                    for record
                    in arm_records
                ),
                total_actual_cost_units=sum(
                    record.actual_cost_units
                    for record
                    in arm_records
                ),
                total_experiment_count=sum(
                    record.experiment_count
                    for record
                    in arm_records
                ),
                total_workflow_step_count=sum(
                    record.workflow_step_count
                    for record
                    in arm_records
                ),
            )
        )

    metrics_by_arm = {
        metric.arm:
            metric
        for metric
        in arm_metrics
    }

    c3 = (
        P094ScientificArm.HEAL_INFORMATION_GAIN_PER_COST
    )

    c2 = (
        P094ScientificArm.MAX_INFORMATION_GAIN_ACTIVE
    )

    both_correct = 0
    c3_only_correct = 0
    c2_only_correct = 0
    neither_correct = 0

    for truth in in_rfs_truth:
        c3_correct = (
            _is_correct_specific(
                record_by_pair[
                    (
                        truth.case_id,
                        c3,
                    )
                ],
                truth,
            )
        )

        c2_correct = (
            _is_correct_specific(
                record_by_pair[
                    (
                        truth.case_id,
                        c2,
                    )
                ],
                truth,
            )
        )

        if (
            c3_correct
            and c2_correct
        ):
            both_correct += 1

        elif c3_correct:
            c3_only_correct += 1

        elif c2_correct:
            c2_only_correct += 1

        else:
            neither_correct += 1

    if (
        both_correct
        + c3_only_correct
        + c2_only_correct
        + neither_correct
        != IN_RFS_CASES
    ):
        return _blocked(
            "paired C3/C2 table does not sum to 120"
        )

    c3_correct = (
        metrics_by_arm[
            c3
        ].correct_specific_count
    )

    c2_correct = (
        metrics_by_arm[
            c2
        ].correct_specific_count
    )

    effect = (
        (
            c3_correct
            - c2_correct
        )
        / IN_RFS_CASES
    )

    p_value = (
        exact_two_sided_mcnemar_p_value(
            c3_only_correct=(
                c3_only_correct
            ),
            c2_only_correct=(
                c2_only_correct
            ),
        )
    )

    in_rfs_strata = tuple(
        stratum
        for stratum
        in HIDDEN_STRATA
        if stratum
        != "out_of_rfs_report_assembly"
    )

    nonworse_count = 0

    for stratum in in_rfs_strata:
        stratum_truth = tuple(
            truth
            for truth
            in in_rfs_truth
            if truth.hidden_stratum
            == stratum
        )

        if len(
            stratum_truth
        ) != 24:
            return _blocked(
                "in-RFS hidden stratum denominator is not 24"
            )

        c3_count = sum(
            _is_correct_specific(
                record_by_pair[
                    (
                        truth.case_id,
                        c3,
                    )
                ],
                truth,
            )
            for truth
            in stratum_truth
        )

        c2_count = sum(
            _is_correct_specific(
                record_by_pair[
                    (
                        truth.case_id,
                        c2,
                    )
                ],
                truth,
            )
            for truth
            in stratum_truth
        )

        if c3_count >= c2_count:
            nonworse_count += 1

    c3_false_specific = (
        metrics_by_arm[
            c3
        ].false_specific_count
    )

    support_criteria = (
        (
            "practical_effect_at_least_0_10",
            (
                c3_correct
                - c2_correct
            )
            >= 12,
        ),
        (
            "c3_only_greater_than_c2_only",
            c3_only_correct
            > c2_only_correct,
        ),
        (
            "exact_mcnemar_p_at_most_0_05",
            p_value
            <= 0.05,
        ),
        (
            "c3_nonworse_in_at_least_4_of_5_fault_strata",
            nonworse_count
            >= 4,
        ),
        (
            "c3_zero_false_specific_across_144",
            c3_false_specific
            == 0,
        ),
    )

    supported = all(
        passed
        for (
            _,
            passed,
        )
        in support_criteria
    )

    return P094ProtectedEvaluation(
        decision=(
            P094EvaluationDecision.SUPPORTED
            if supported
            else P094EvaluationDecision.NOT_SUPPORTED
        ),
        integrity_valid=True,
        integrity_error=None,
        arm_metrics=tuple(
            arm_metrics
        ),
        c3_only_correct=(
            c3_only_correct
        ),
        c2_only_correct=(
            c2_only_correct
        ),
        both_correct=(
            both_correct
        ),
        neither_correct=(
            neither_correct
        ),
        c3_minus_c2_correct_specific_rate=(
            effect
        ),
        exact_mcnemar_p_value=(
            p_value
        ),
        c3_nonworse_fault_strata=(
            nonworse_count
        ),
        c3_false_specific_count=(
            c3_false_specific
        ),
        support_criteria=(
            support_criteria
        ),
    )


__all__ = [
    "P094ArmEvaluation",
    "P094EvaluationDecision",
    "P094ProtectedEvaluation",
    "P094ProtectedTreatmentRecord",
    "evaluate_protected_records",
    "exact_two_sided_mcnemar_p_value",
]
