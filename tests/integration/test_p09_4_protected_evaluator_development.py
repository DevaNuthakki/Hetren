from __future__ import annotations

import inspect

from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
)
import packages.engines.behavioral.p09_4_protected_evaluator as evaluator
from packages.engines.behavioral.p09_4_protected_evaluator import (
    P094EvaluationDecision,
    P094ProtectedTreatmentRecord,
    evaluate_protected_records,
    exact_two_sided_mcnemar_p_value,
)
from packages.engines.behavioral.p09_4_protected_generation import (
    build_development_generation_plan,
)
from packages.engines.behavioral.p09_4_scientific_arms import (
    P094ScientificArm,
)


PROTOCOL_SHA = (
    "46ea27e825bedbfbd8ee0443173884f904f20881fc929a4c44fae30c550e7621"
)

SOURCE_COMMIT = (
    "08aa58c6dba26f2ff7f88b82f5d7448fc84d29f9"
)

SEED = bytes(
    range(
        32
    )
)


def _plan():
    return build_development_generation_plan(
        raw_seed=SEED,
        protocol_sha256=PROTOCOL_SHA,
        source_commit=SOURCE_COMMIT,
    )


def _wrong_hypothesis(
    expected,
):
    candidates = (
        "tool_selection_fault",
        "parameter_transformation_fault",
        "sequencing_orchestration_fault",
        "state_context_fault",
        "environment_interaction_fault",
    )

    return next(
        candidate
        for candidate
        in candidates
        if candidate
        != expected
    )


def _records(
    *,
    c2_correct_ids=None,
    c3_correct_ids=None,
    c3_false_ids=frozenset(),
):
    plan = _plan()

    in_rfs_ids = {
        assignment.case_id
        for assignment
        in plan.hidden_assignments
        if assignment.in_rfs
    }

    if c2_correct_ids is None:
        c2_correct_ids = set(
            in_rfs_ids
        )

    if c3_correct_ids is None:
        c3_correct_ids = set(
            in_rfs_ids
        )

    c2_correct_ids = set(
        c2_correct_ids
    )

    c3_correct_ids = set(
        c3_correct_ids
    )

    records = []

    for truth in plan.hidden_assignments:
        for arm in P094ScientificArm:
            if (
                arm
                is P094ScientificArm.TRACE_ONLY
            ):
                status = (
                    DiagnosisStatus.INCONCLUSIVE
                )

                diagnosis = None

                cost = 0
                experiments = 0
                workflow_steps = 0

            elif not truth.in_rfs:
                status = (
                    DiagnosisStatus.INCONCLUSIVE
                )

                diagnosis = None

                cost = 9
                experiments = 3
                workflow_steps = 24

            else:
                should_be_correct = True

                if (
                    arm
                    is P094ScientificArm.MAX_INFORMATION_GAIN_ACTIVE
                ):
                    should_be_correct = (
                        truth.case_id
                        in c2_correct_ids
                    )

                elif (
                    arm
                    is P094ScientificArm.HEAL_INFORMATION_GAIN_PER_COST
                ):
                    should_be_correct = (
                        truth.case_id
                        in c3_correct_ids
                    )

                if should_be_correct:
                    status = (
                        DiagnosisStatus.DIAGNOSED
                    )

                    diagnosis = (
                        truth.expected_hypothesis_key
                    )

                elif (
                    arm
                    is P094ScientificArm.HEAL_INFORMATION_GAIN_PER_COST
                    and truth.case_id
                    in c3_false_ids
                ):
                    status = (
                        DiagnosisStatus.DIAGNOSED
                    )

                    diagnosis = (
                        _wrong_hypothesis(
                            truth.expected_hypothesis_key
                        )
                    )

                else:
                    status = (
                        DiagnosisStatus.BUDGET_EXHAUSTED
                    )

                    diagnosis = None

                cost = 12
                experiments = 3
                workflow_steps = 24

            records.append(
                P094ProtectedTreatmentRecord(
                    case_id=truth.case_id,
                    arm=arm,
                    status=status,
                    diagnosed_hypothesis_key=(
                        diagnosis
                    ),
                    actual_cost_units=cost,
                    experiment_count=(
                        experiments
                    ),
                    workflow_step_count=(
                        workflow_steps
                    ),
                )
            )

    return (
        plan,
        tuple(
            records
        ),
    )


def test_exact_mcnemar_no_discordance_is_one():
    assert exact_two_sided_mcnemar_p_value(
        c3_only_correct=0,
        c2_only_correct=0,
    ) == 1.0


def test_exact_mcnemar_twelve_zero_matches_frozen_formula():
    assert exact_two_sided_mcnemar_p_value(
        c3_only_correct=12,
        c2_only_correct=0,
    ) == (
        2
        / (
            2
            ** 12
        )
    )


def test_supported_requires_all_five_preregistered_criteria():
    plan = _plan()

    in_rfs = [
        assignment.case_id
        for assignment
        in plan.hidden_assignments
        if assignment.in_rfs
    ]

    c2_correct = set(
        in_rfs[
            24:
        ]
    )

    plan, records = _records(
        c2_correct_ids=(
            c2_correct
        ),
        c3_correct_ids=set(
            in_rfs
        ),
    )

    result = evaluate_protected_records(
        treatment_records=records,
        hidden_assignments=(
            plan.hidden_assignments
        ),
    )

    assert (
        result.decision
        is P094EvaluationDecision.SUPPORTED
    )

    assert (
        result.integrity_valid
        is True
    )

    assert all(
        passed
        for (
            _,
            passed,
        )
        in result.support_criteria
    )


def test_effect_below_point_ten_is_not_supported_even_when_p_is_small():
    plan = _plan()

    in_rfs = [
        assignment.case_id
        for assignment
        in plan.hidden_assignments
        if assignment.in_rfs
    ]

    c2_correct = set(
        in_rfs[
            6:
        ]
    )

    plan, records = _records(
        c2_correct_ids=(
            c2_correct
        ),
        c3_correct_ids=set(
            in_rfs
        ),
    )

    result = evaluate_protected_records(
        treatment_records=records,
        hidden_assignments=(
            plan.hidden_assignments
        ),
    )

    assert (
        result.c3_minus_c2_correct_specific_rate
        == 0.05
    )

    assert (
        result.decision
        is P094EvaluationDecision.NOT_SUPPORTED
    )


def test_point_ten_effect_without_significant_p_is_not_supported():
    plan = _plan()

    in_rfs = [
        assignment.case_id
        for assignment
        in plan.hidden_assignments
        if assignment.in_rfs
    ]

    c3_correct = set(
        in_rfs[
            :66
        ]
    )

    c2_correct = set(
        in_rfs[
            66:
        ]
    )

    plan, records = _records(
        c2_correct_ids=(
            c2_correct
        ),
        c3_correct_ids=(
            c3_correct
        ),
    )

    result = evaluate_protected_records(
        treatment_records=records,
        hidden_assignments=(
            plan.hidden_assignments
        ),
    )

    assert (
        result.c3_minus_c2_correct_specific_rate
        == 0.10
    )

    assert (
        result.exact_mcnemar_p_value
        > 0.05
    )

    assert (
        result.decision
        is P094EvaluationDecision.NOT_SUPPORTED
    )


def test_fault_stratum_breadth_can_block_otherwise_positive_aggregate():
    plan = _plan()

    by_stratum = {}

    for assignment in plan.hidden_assignments:
        if assignment.in_rfs:
            by_stratum.setdefault(
                assignment.hidden_stratum,
                set(),
            ).add(
                assignment.case_id
            )

    ordered = (
        "tool_selection",
        "parameter_transformation",
        "sequencing_orchestration",
        "state_context",
        "environment_interaction",
    )

    c3_correct = set().union(
        *(
            by_stratum[
                stratum
            ]
            for stratum
            in ordered[
                :3
            ]
        )
    )

    c2_correct = set().union(
        *(
            by_stratum[
                stratum
            ]
            for stratum
            in ordered[
                3:
            ]
        )
    )

    plan, records = _records(
        c2_correct_ids=(
            c2_correct
        ),
        c3_correct_ids=(
            c3_correct
        ),
    )

    result = evaluate_protected_records(
        treatment_records=records,
        hidden_assignments=(
            plan.hidden_assignments
        ),
    )

    assert (
        result.c3_minus_c2_correct_specific_rate
        == 0.20
    )

    assert (
        result.c3_nonworse_fault_strata
        == 3
    )

    assert (
        result.decision
        is P094EvaluationDecision.NOT_SUPPORTED
    )


def test_single_c3_false_specific_blocks_support():
    plan = _plan()

    in_rfs = [
        assignment.case_id
        for assignment
        in plan.hidden_assignments
        if assignment.in_rfs
    ]

    c2_correct = set(
        in_rfs[
            24:
        ]
    )

    false_case = in_rfs[
        0
    ]

    c3_correct = set(
        in_rfs
    )

    c3_correct.remove(
        false_case
    )

    plan, records = _records(
        c2_correct_ids=(
            c2_correct
        ),
        c3_correct_ids=(
            c3_correct
        ),
        c3_false_ids=frozenset(
            {
                false_case,
            }
        ),
    )

    result = evaluate_protected_records(
        treatment_records=records,
        hidden_assignments=(
            plan.hidden_assignments
        ),
    )

    assert (
        result.c3_false_specific_count
        == 1
    )

    assert (
        result.decision
        is P094EvaluationDecision.NOT_SUPPORTED
    )


def test_budget_exhausted_remains_denominator_and_not_false_specific():
    plan = _plan()

    in_rfs = [
        assignment.case_id
        for assignment
        in plan.hidden_assignments
        if assignment.in_rfs
    ]

    c3_correct = set(
        in_rfs[
            1:
        ]
    )

    plan, records = _records(
        c3_correct_ids=(
            c3_correct
        ),
    )

    result = evaluate_protected_records(
        treatment_records=records,
        hidden_assignments=(
            plan.hidden_assignments
        ),
    )

    c3_metric = next(
        metric
        for metric
        in result.arm_metrics
        if metric.arm
        is P094ScientificArm.HEAL_INFORMATION_GAIN_PER_COST
    )

    assert (
        c3_metric.in_rfs_denominator
        == 120
    )

    assert (
        c3_metric.correct_specific_count
        == 119
    )

    assert (
        c3_metric.false_specific_count
        == 0
    )

    assert (
        c3_metric.budget_exhausted_count
        == 1
    )


def test_missing_case_arm_record_produces_blocked_not_smaller_denominator():
    plan, records = _records()

    result = evaluate_protected_records(
        treatment_records=records[
            :-1
        ],
        hidden_assignments=(
            plan.hidden_assignments
        ),
    )

    assert (
        result.decision
        is P094EvaluationDecision.BLOCKED
    )

    assert (
        result.integrity_valid
        is False
    )

    assert (
        result.arm_metrics
        == ()
    )


def test_evaluator_source_has_no_treatment_execution_or_randomness():
    source = inspect.getsource(
        evaluator
    )

    for forbidden in (
        "run_scientific_arm",
        "capture_p09_4_replay_baseline",
        "capture_p09_4_out_of_rfs_replay_baseline",
        "execute_checkpoint_replay",
        "os.urandom",
        "secrets.",
        "write_text",
        "write_bytes",
    ):
        assert forbidden not in source
