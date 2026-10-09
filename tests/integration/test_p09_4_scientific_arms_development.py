from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from environments.agent.p09_4_multistep_incident import (
    P094FaultMode,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
)
from packages.engines.behavioral.p09_4_checkpoint_replay import (
    capture_p09_4_out_of_rfs_replay_baseline,
    capture_p09_4_replay_baseline,
)
import packages.engines.behavioral.p09_4_scientific_arms as arms
from packages.engines.behavioral.p09_4_scientific_arms import (
    CALIBRATED_REPLAY_COSTS,
    P094ScientificArm,
    SCIENTIFIC_BUDGET_UNITS,
    build_scientific_development_problem,
    run_scientific_arm,
    select_c1_experiment_key,
)


DEVELOPMENT_C1_SEED = bytes(
    range(
        32
    )
)


def _tool_selection_baseline(
    run_id: str,
):
    return (
        capture_p09_4_replay_baseline(
            P094FaultMode.TOOL_SELECTION,
            run_id=run_id,
        )
    )


def test_scientific_problem_overlays_only_frozen_costs_and_budget():
    baseline = _tool_selection_baseline(
        "k3-problem-overlay"
    )

    problem = (
        build_scientific_development_problem(
            baseline.run.trace
        )
    )

    assert (
        problem.budget_units
        == SCIENTIFIC_BUDGET_UNITS
        == 13
    )

    assert {
        experiment.key:
            experiment.cost_units
        for experiment
        in problem.experiments
    } == CALIBRATED_REPLAY_COSTS

    assert tuple(
        experiment.key
        for experiment
        in problem.experiments
    ) == tuple(
        CALIBRATED_REPLAY_COSTS
    )


def test_scientific_arm_surface_matches_k1_four_arm_contract():
    assert tuple(
        arm.value
        for arm in P094ScientificArm
    ) == (
        "trace_only",
        "seeded_random_active",
        "max_information_gain_active",
        "heal_information_gain_per_cost",
    )


def test_c0_is_trace_only_and_executes_zero_replay_work():
    baseline = _tool_selection_baseline(
        "k3-c0"
    )

    result = run_scientific_arm(
        arm=P094ScientificArm.TRACE_ONLY,
        case_id="development-c0",
        baseline=baseline,
    )

    assert (
        result.status
        is DiagnosisStatus.INCONCLUSIVE
    )

    assert (
        result.terminal_reason
        == "trace_only"
    )

    assert result.observations == ()
    assert result.selections == ()
    assert result.experiment_sequence == ()
    assert result.declared_cost_units == 0
    assert result.actual_cost_units == 0
    assert result.workflow_step_count == 0
    assert result.remaining_budget_units == 13
    assert result.diagnosed_hypothesis_key is None


def test_c1_selection_is_seeded_deterministic_and_never_generates_seed():
    keys = tuple(
        sorted(
            CALIBRATED_REPLAY_COSTS
        )
    )

    first = select_c1_experiment_key(
        raw_seed=DEVELOPMENT_C1_SEED,
        case_id="development-c1",
        sequence=0,
        eligible_experiment_keys=keys,
    )

    second = select_c1_experiment_key(
        raw_seed=DEVELOPMENT_C1_SEED,
        case_id="development-c1",
        sequence=0,
        eligible_experiment_keys=keys,
    )

    assert first == second
    assert first[0] in keys
    assert len(
        first[1]
    ) == 64

    with pytest.raises(
        ContractError
    ):
        select_c1_experiment_key(
            raw_seed=b"too-short",
            case_id="development-c1",
            sequence=0,
            eligible_experiment_keys=keys,
        )

    source = inspect.getsource(
        arms
    )

    assert "os.urandom" not in source
    assert "secrets." not in source
    assert "P094FaultMode" not in source
    assert "evaluator" not in source.lower()


def test_c1_complete_run_is_deterministic_for_same_development_seed():
    baseline = _tool_selection_baseline(
        "k3-c1-deterministic"
    )

    first = run_scientific_arm(
        arm=(
            P094ScientificArm.SEEDED_RANDOM_ACTIVE
        ),
        case_id="development-c1-run",
        baseline=baseline,
        c1_raw_seed=DEVELOPMENT_C1_SEED,
    )

    second = run_scientific_arm(
        arm=(
            P094ScientificArm.SEEDED_RANDOM_ACTIVE
        ),
        case_id="development-c1-run",
        baseline=baseline,
        c1_raw_seed=DEVELOPMENT_C1_SEED,
    )

    assert first == second
    assert (
        first.result_sha256
        == second.result_sha256
    )

    assert all(
        (
            selection.c1_selection_digest_sha256
            is not None
        )
        if selection.phase == "active"
        else (
            selection.c1_selection_digest_sha256
            is None
        )
        for selection
        in first.selections
    )


def test_c2_initial_selection_is_raw_information_gain_with_key_tiebreak():
    baseline = _tool_selection_baseline(
        "k3-c2"
    )

    result = run_scientific_arm(
        arm=(
            P094ScientificArm.MAX_INFORMATION_GAIN_ACTIVE
        ),
        case_id="development-c2",
        baseline=baseline,
    )

    assert (
        result.selections[
            0
        ].phase
        == "active"
    )

    assert (
        result.selections[
            0
        ].experiment_key
        == "p1-canonical-tool"
    )

    assert (
        result.status
        is DiagnosisStatus.DIAGNOSED
    )

    assert (
        result.diagnosed_hypothesis_key
        == "tool_selection_fault"
    )


def test_c3_initial_selection_uses_existing_information_gain_per_cost_choice():
    baseline = _tool_selection_baseline(
        "k3-c3"
    )

    result = run_scientific_arm(
        arm=(
            P094ScientificArm.HEAL_INFORMATION_GAIN_PER_COST
        ),
        case_id="development-c3",
        baseline=baseline,
    )

    assert (
        result.selections[
            0
        ].phase
        == "active"
    )

    assert (
        result.selections[
            0
        ].experiment_key
        == "p3-canonical-prerequisite-order"
    )


def test_c2_and_c3_start_from_identical_candidate_set_but_different_objective():
    baseline = _tool_selection_baseline(
        "k3-c2-c3-fairness"
    )

    c2 = run_scientific_arm(
        arm=(
            P094ScientificArm.MAX_INFORMATION_GAIN_ACTIVE
        ),
        case_id="development-c2-fairness",
        baseline=baseline,
    )

    c3 = run_scientific_arm(
        arm=(
            P094ScientificArm.HEAL_INFORMATION_GAIN_PER_COST
        ),
        case_id="development-c3-fairness",
        baseline=baseline,
    )

    expected_candidates = tuple(
        sorted(
            CALIBRATED_REPLAY_COSTS
        )
    )

    assert (
        c2.selections[
            0
        ].candidate_experiment_keys
        == expected_candidates
    )

    assert (
        c3.selections[
            0
        ].candidate_experiment_keys
        == expected_candidates
    )

    assert (
        c2.selections[
            0
        ].remaining_budget_before
        == 13
    )

    assert (
        c3.selections[
            0
        ].remaining_budget_before
        == 13
    )

    assert (
        c2.selections[
            0
        ].experiment_key
        != c3.selections[
            0
        ].experiment_key
    )


def test_observation_evidence_and_actual_cost_come_from_checkpoint_replay():
    baseline = _tool_selection_baseline(
        "k3-replay-evidence"
    )

    result = run_scientific_arm(
        arm=(
            P094ScientificArm.MAX_INFORMATION_GAIN_ACTIVE
        ),
        case_id="development-replay-evidence",
        baseline=baseline,
    )

    observation = result.observations[
        0
    ]

    assert (
        observation.experiment_key
        == "p1-canonical-tool"
    )

    assert (
        observation.actual_cost_units
        == 4
    )

    assert (
        result.declared_cost_units
        == result.actual_cost_units
        == 4
    )

    assert (
        result.workflow_step_count
        == 11
    )

    assert len(
        observation.evidence_sha256
    ) == 64

    assert (
        result.evidence_references[
            0
        ]
        == observation.evidence_sha256
    )


def test_out_of_rfs_binding_budget_never_emits_false_specific_diagnosis():
    baseline = (
        capture_p09_4_out_of_rfs_replay_baseline(
            run_id="k3-out-of-rfs",
        )
    )

    result = run_scientific_arm(
        arm=(
            P094ScientificArm.HEAL_INFORMATION_GAIN_PER_COST
        ),
        case_id="development-out-of-rfs",
        baseline=baseline,
    )

    assert result.status in {
        DiagnosisStatus.INCONCLUSIVE,
        DiagnosisStatus.BUDGET_EXHAUSTED,
    }

    assert (
        result.diagnosed_hypothesis_key
        is None
    )

    assert (
        result.actual_cost_units
        <= 13
    )

    assert len(
        result.experiment_sequence
    ) == len(
        set(
            result.experiment_sequence
        )
    )

    assert all(
        observation.actual_cost_units
        == CALIBRATED_REPLAY_COSTS[
            observation.experiment_key
        ]
        for observation
        in result.observations
    )
