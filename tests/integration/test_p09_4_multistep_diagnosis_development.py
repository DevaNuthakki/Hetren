import inspect

import pytest

from environments.agent.p09_4_multistep_incident import (
    P094FaultMode,
    run_p09_4_multistep_incident,
)

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    InterventionKind,
    Verdict,
)

from packages.core.hetren_diagnosis.lifecycle import (
    replay_observations,
    select_next_decision,
)

from packages.engines.behavioral.p09_4_multistep_diagnosis import (
    build_development_problem,
    development_probe_keys,
    execute_development_probe,
)


PRIMARY_FAULTS = (
    P094FaultMode.TOOL_SELECTION,
    P094FaultMode.PARAMETER_TRANSFORMATION,
    P094FaultMode.SEQUENCING_ORCHESTRATION,
    P094FaultMode.STATE_CONTEXT,
    P094FaultMode.ENVIRONMENT_INTERACTION,
)


FAULT_TO_HYPOTHESIS = {
    P094FaultMode.TOOL_SELECTION:
        "tool_selection_fault",

    P094FaultMode.PARAMETER_TRANSFORMATION:
        "parameter_transformation_fault",

    P094FaultMode.SEQUENCING_ORCHESTRATION:
        "sequencing_orchestration_fault",

    P094FaultMode.STATE_CONTEXT:
        "state_context_fault",

    P094FaultMode.ENVIRONMENT_INTERACTION:
        "environment_interaction_fault",
}


FAULT_TO_TARGET_PROBE = {
    P094FaultMode.TOOL_SELECTION:
        "p1-canonical-tool",

    P094FaultMode.PARAMETER_TRANSFORMATION:
        "p2-canonical-parameter",

    P094FaultMode.SEQUENCING_ORCHESTRATION:
        "p3-canonical-prerequisite-order",

    P094FaultMode.STATE_CONTEXT:
        "p4-fresh-context",

    P094FaultMode.ENVIRONMENT_INTERACTION:
        "p5-environment-contract",
}


PROBE_KEYS = (
    "p1-canonical-tool",
    "p2-canonical-parameter",
    "p3-canonical-prerequisite-order",
    "p4-fresh-context",
    "p5-environment-contract",
)


MATRIX = tuple(
    (
        fault_mode,
        experiment_key,
    )
    for fault_mode in PRIMARY_FAULTS
    for experiment_key in PROBE_KEYS
)


def _problem_for(
    fault_mode,
    *,
    run_id,
):
    baseline = (
        run_p09_4_multistep_incident(
            fault_mode,
            run_id=run_id,
        )
    )

    assert baseline.passed is False

    return (
        baseline,
        build_development_problem(
            baseline.trace
        ),
    )


def _run_sequential_diagnosis(
    fault_mode,
    *,
    run_id,
):
    (
        baseline,
        problem,
    ) = _problem_for(
        fault_mode,
        run_id=run_id,
    )

    observations = []

    for _ in range(
        5
    ):
        decision = (
            select_next_decision(
                problem,
                tuple(
                    observations
                ),
            )
        )

        if (
            decision.status
            is DiagnosisStatus.DIAGNOSED
        ):
            break

        assert (
            decision.status
            is DiagnosisStatus.ACTIVE
        )

        assert (
            decision.experiment_key
            is not None
        )

        result = (
            execute_development_probe(
                problem=problem,
                experiment_key=(
                    decision.experiment_key
                ),
                fault_mode=fault_mode,
                sequence=len(
                    observations
                ),
            )
        )

        observations.append(
            result.observation
        )

    final_decision = (
        select_next_decision(
            problem,
            tuple(
                observations
            ),
        )
    )

    posterior = replay_observations(
        problem,
        tuple(
            observations
        ),
    )

    survivors = tuple(
        key
        for (
            key,
            probability,
        )
        in posterior.items()
        if probability > 1e-12
    )

    return (
        baseline,
        problem,
        tuple(
            observations
        ),
        final_decision,
        survivors,
    )


def test_problem_defines_five_rivals_and_five_probes():
    baseline = run_p09_4_multistep_incident(
        P094FaultMode.TOOL_SELECTION,
        run_id="p09-4-a2c2-problem",
    )

    problem = build_development_problem(
        baseline.trace
    )

    assert tuple(
        hypothesis.key
        for hypothesis in problem.hypotheses
    ) == (
        "tool_selection_fault",
        "parameter_transformation_fault",
        "sequencing_orchestration_fault",
        "state_context_fault",
        "environment_interaction_fault",
    )

    assert tuple(
        experiment.key
        for experiment in problem.experiments
    ) == PROBE_KEYS

    assert (
        development_probe_keys()
        == PROBE_KEYS
    )

    assert problem.budget_units == 5

    expected_prediction_keys = tuple(
        sorted(
            hypothesis.key
            for hypothesis
            in problem.hypotheses
        )
    )

    for experiment in problem.experiments:
        assert tuple(
            key
            for (
                key,
                _,
            )
            in experiment.predicted_verdicts
        ) == expected_prediction_keys


def test_probe_contract_surface_matches_a2b_spec():
    baseline = run_p09_4_multistep_incident(
        P094FaultMode.TOOL_SELECTION,
        run_id="p09-4-a2c2-contract",
    )

    problem = build_development_problem(
        baseline.trace
    )

    actual = {
        experiment.key: (
            experiment.intervention_kind,
            experiment.intervention_target,
            experiment.cost_units,
        )
        for experiment
        in problem.experiments
    }

    assert actual == {
        "p1-canonical-tool": (
            InterventionKind.REPLACE_TOOL,
            "strategy/tool-selection",
            1,
        ),
        "p2-canonical-parameter": (
            InterventionKind.OVERRIDE_PARAMETER,
            "strategy/parameter-transformation",
            1,
        ),
        "p3-canonical-prerequisite-order": (
            InterventionKind.REPLAY,
            "orchestration/prerequisite-order",
            1,
        ),
        "p4-fresh-context": (
            InterventionKind.REPLAY,
            "context/fresh-state",
            1,
        ),
        "p5-environment-contract": (
            InterventionKind.REPLAY,
            "environment/response-contract",
            1,
        ),
    }


@pytest.mark.parametrize(
    (
        "fault_mode",
        "experiment_key",
    ),
    MATRIX,
)
def test_each_probe_outcome_comes_from_executed_workflow(
    fault_mode,
    experiment_key,
):
    (
        _,
        problem,
    ) = _problem_for(
        fault_mode,
        run_id=(
            "p09-4-a2c2-matrix-"
            + fault_mode.value
        ),
    )

    result = execute_development_probe(
        problem=problem,
        experiment_key=experiment_key,
        fault_mode=fault_mode,
        sequence=0,
    )

    expected_pass = (
        experiment_key
        == FAULT_TO_TARGET_PROBE[
            fault_mode
        ]
    )

    assert (
        result.agent_run.passed
        is expected_pass
    )

    assert (
        result.observation.verdict
        is (
            Verdict.PASS
            if expected_pass
            else Verdict.FAIL
        )
    )

    assert (
        result.observation.evidence_sha256
        == result.agent_run.execution_evidence_sha256
    )

    assert (
        result.observation.counterexample_sha256
        is None
    ) is expected_pass

    experiment = next(
        item
        for item in problem.experiments
        if item.key
        == experiment_key
    )

    assert (
        result.observation.experiment_sha256
        == experiment.experiment_sha256
    )

    assert (
        result.observation.actual_cost_units
        == experiment.cost_units
    )

    registered_predictions = dict(
        experiment.predicted_verdicts
    )

    assert (
        registered_predictions[
            FAULT_TO_HYPOTHESIS[
                fault_mode
            ]
        ]
        is result.observation.verdict
    )

    if expected_pass:
        canonical = (
            run_p09_4_multistep_incident(
                P094FaultMode.NONE,
                run_id=(
                    "p09-4-a2c2-canonical-"
                    + fault_mode.value
                    + "-"
                    + experiment_key
                ),
            )
        )

        assert (
            result.agent_run.trace.events
            == canonical.trace.events
        )


@pytest.mark.parametrize(
    "fault_mode",
    PRIMARY_FAULTS,
)
def test_probe_execution_is_isolated_from_other_probe_runs(
    fault_mode,
):
    baseline_before = (
        run_p09_4_multistep_incident(
            fault_mode,
            run_id=(
                "p09-4-a2c2-isolation-"
                + fault_mode.value
            ),
        )
    )

    problem = build_development_problem(
        baseline_before.trace
    )

    target_probe = (
        FAULT_TO_TARGET_PROBE[
            fault_mode
        ]
    )

    first = execute_development_probe(
        problem=problem,
        experiment_key=target_probe,
        fault_mode=fault_mode,
        sequence=0,
    )

    other_probe = next(
        probe
        for probe in PROBE_KEYS
        if probe != target_probe
    )

    execute_development_probe(
        problem=problem,
        experiment_key=other_probe,
        fault_mode=fault_mode,
        sequence=0,
    )

    repeated = execute_development_probe(
        problem=problem,
        experiment_key=target_probe,
        fault_mode=fault_mode,
        sequence=0,
    )

    baseline_after = (
        run_p09_4_multistep_incident(
            fault_mode,
            run_id=(
                "p09-4-a2c2-isolation-"
                + fault_mode.value
            ),
        )
    )

    assert first == repeated

    assert (
        first.agent_run.execution_evidence_sha256
        == repeated.agent_run.execution_evidence_sha256
    )

    assert (
        baseline_before
        == baseline_after
    )

    assert (
        baseline_before.trace.trace_sha256
        == baseline_after.trace.trace_sha256
    )


@pytest.mark.parametrize(
    "fault_mode",
    PRIMARY_FAULTS,
)
def test_existing_lifecycle_can_reach_correct_specific_diagnosis(
    fault_mode,
):
    (
        _,
        _,
        observations,
        final_decision,
        survivors,
    ) = _run_sequential_diagnosis(
        fault_mode,
        run_id=(
            "p09-4-a2c2-sequential-"
            + fault_mode.value
        ),
    )

    assert (
        final_decision.status
        is DiagnosisStatus.DIAGNOSED
    )

    assert survivors == (
        FAULT_TO_HYPOTHESIS[
            fault_mode
        ],
    )

    assert 1 <= len(
        observations
    ) <= 5


def test_development_evidence_requires_sequential_multi_observation_case():
    observation_counts = {}

    for fault_mode in PRIMARY_FAULTS:
        (
            _,
            _,
            observations,
            final_decision,
            survivors,
        ) = _run_sequential_diagnosis(
            fault_mode,
            run_id=(
                "p09-4-a2c2-sequentiality-"
                + fault_mode.value
            ),
        )

        assert (
            final_decision.status
            is DiagnosisStatus.DIAGNOSED
        )

        assert survivors == (
            FAULT_TO_HYPOTHESIS[
                fault_mode
            ],
        )

        observation_counts[
            fault_mode
        ] = len(
            observations
        )

    assert max(
        observation_counts.values()
    ) >= 2

    assert any(
        count >= 2
        for count in observation_counts.values()
    )


def test_probe_executor_does_not_copy_registered_predictions():
    source = inspect.getsource(
        execute_development_probe
    )

    assert "predicted_verdicts" not in source

    assert (
        "diagnostic_run.passed"
        in source
    )

    assert (
        "execution_evidence_sha256"
        in source
    )

    assert (
        "run_p09_4_multistep_incident"
        in source
    )


def test_unknown_probe_key_is_rejected():
    (
        _,
        problem,
    ) = _problem_for(
        P094FaultMode.TOOL_SELECTION,
        run_id="p09-4-a2c2-unknown-probe",
    )

    with pytest.raises(
        ContractError,
    ):
        execute_development_probe(
            problem=problem,
            experiment_key="not-a-probe",
            fault_mode=(
                P094FaultMode.TOOL_SELECTION
            ),
            sequence=0,
        )
