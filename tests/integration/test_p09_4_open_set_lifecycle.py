import ast
from pathlib import Path

import pytest

from environments.agent.p09_4_multistep_incident import (
    P094DiagnosticIntervention,
    P094FaultMode,
    run_p09_4_multistep_incident,
    run_p09_4_out_of_rfs_control,
)

from packages.core.hetren_diagnosis.contracts import (
    DiagnosisProblem,
    DiagnosisStatus,
    Observation,
    Verdict,
    canonical_sha256,
)

from packages.core.hetren_diagnosis.lifecycle import (
    select_next_decision,
)

from packages.core.hetren_diagnosis.open_set import (
    OpenSetReason,
    select_next_open_set_decision,
)

from packages.engines.behavioral.p09_4_multistep_diagnosis import (
    build_development_problem,
    execute_development_probe,
)


PRIMARY_FAULTS = (
    P094FaultMode.TOOL_SELECTION,
    P094FaultMode.PARAMETER_TRANSFORMATION,
    P094FaultMode.SEQUENCING_ORCHESTRATION,
    P094FaultMode.STATE_CONTEXT,
    P094FaultMode.ENVIRONMENT_INTERACTION,
)


EXPECTED_OBSERVATION_COUNTS = {
    P094FaultMode.TOOL_SELECTION:
        1,

    P094FaultMode.PARAMETER_TRANSFORMATION:
        2,

    P094FaultMode.SEQUENCING_ORCHESTRATION:
        3,

    P094FaultMode.STATE_CONTEXT:
        4,

    P094FaultMode.ENVIRONMENT_INTERACTION:
        5,
}


EXPECTED_HYPOTHESES = {
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


def _known_problem(
    fault_mode,
    *,
    run_id,
    budget_units=None,
):
    baseline = (
        run_p09_4_multistep_incident(
            fault_mode,
            run_id=run_id,
        )
    )

    problem = build_development_problem(
        baseline.trace
    )

    if budget_units is None:
        return (
            baseline,
            problem,
        )

    return (
        baseline,
        DiagnosisProblem(
            trace=problem.trace,
            hypotheses=problem.hypotheses,
            experiments=problem.experiments,
            budget_units=budget_units,
        ),
    )


def _execute_out_of_rfs_probe(
    *,
    problem,
    experiment_key,
    sequence,
):
    experiment = next(
        item
        for item in problem.experiments
        if item.key
        == experiment_key
    )

    intervention = (
        P094DiagnosticIntervention(
            kind=experiment.intervention_kind,
            target=experiment.intervention_target,
        )
    )

    run = (
        run_p09_4_out_of_rfs_control(
            run_id=(
                f"{problem.trace.run_id}:"
                f"open-set:{sequence}:"
                f"{experiment.key}"
            ),
            intervention=intervention,
        )
    )

    verdict = (
        Verdict.PASS
        if run.passed
        else Verdict.FAIL
    )

    counterexample_sha256 = None

    if verdict is Verdict.FAIL:
        counterexample_sha256 = (
            canonical_sha256(
                {
                    "actual_report":
                        run.report.canonical_payload(),
                    "control":
                        "out-of-rfs-report-assembly",
                }
            )
        )

    return Observation(
        sequence=sequence,
        experiment_key=experiment.key,
        experiment_sha256=(
            experiment.experiment_sha256
        ),
        verdict=verdict,
        actual_cost_units=(
            experiment.cost_units
        ),
        evidence_sha256=(
            run.execution_evidence_sha256
        ),
        counterexample_sha256=(
            counterexample_sha256
        ),
    )


def _run_known_open_set(
    fault_mode,
    *,
    run_id,
):
    (
        _,
        problem,
    ) = _known_problem(
        fault_mode,
        run_id=run_id,
    )

    observations = []

    while True:
        decision = (
            select_next_open_set_decision(
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
            return (
                problem,
                tuple(
                    observations
                ),
                decision,
            )

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

        assert len(
            observations
        ) <= 5


def test_existing_diagnosis_status_surface_is_unchanged():
    assert tuple(
        status.value
        for status in DiagnosisStatus
    ) == (
        "active",
        "diagnosed",
        "inconclusive",
        "budget_exhausted",
    )


@pytest.mark.parametrize(
    "fault_mode",
    PRIMARY_FAULTS,
)
def test_known_faults_require_rfs_unique_confirmation(
    fault_mode,
):
    (
        _,
        observations,
        decision,
    ) = _run_known_open_set(
        fault_mode,
        run_id=(
            "p09-4-a2c5-known-"
            + fault_mode.value
        ),
    )

    assert (
        len(
            observations
        )
        == EXPECTED_OBSERVATION_COUNTS[
            fault_mode
        ]
    )

    assert (
        decision.reason
        is OpenSetReason.RFS_UNIQUE_CONFIRMATION
    )

    assert (
        decision.diagnosed_hypothesis_key
        == EXPECTED_HYPOTHESES[
            fault_mode
        ]
    )

    assert (
        observations[
            -1
        ].verdict
        is Verdict.PASS
    )


def test_f5_singleton_requires_p5_confirmation_before_diagnosis():
    fault_mode = (
        P094FaultMode.ENVIRONMENT_INTERACTION
    )

    (
        _,
        problem,
    ) = _known_problem(
        fault_mode,
        run_id="p09-4-a2c5-f5-confirmation",
    )

    observations = []

    for experiment_key in (
        "p1-canonical-tool",
        "p2-canonical-parameter",
        "p3-canonical-prerequisite-order",
        "p4-fresh-context",
    ):
        result = execute_development_probe(
            problem=problem,
            experiment_key=experiment_key,
            fault_mode=fault_mode,
            sequence=len(
                observations
            ),
        )

        assert (
            result.observation.verdict
            is Verdict.FAIL
        )

        observations.append(
            result.observation
        )

    decision = (
        select_next_open_set_decision(
            problem,
            tuple(
                observations
            ),
        )
    )

    assert (
        decision.status
        is DiagnosisStatus.ACTIVE
    )

    assert (
        decision.reason
        is OpenSetReason.CONFIRMATION_REQUIRED
    )

    assert (
        decision.experiment_key
        == "p5-environment-contract"
    )

    assert (
        decision.diagnosed_hypothesis_key
        is None
    )

    p5 = execute_development_probe(
        problem=problem,
        experiment_key=(
            decision.experiment_key
        ),
        fault_mode=fault_mode,
        sequence=4,
    )

    assert (
        p5.observation.verdict
        is Verdict.PASS
    )

    final = (
        select_next_open_set_decision(
            problem,
            (
                *observations,
                p5.observation,
            ),
        )
    )

    assert (
        final.status
        is DiagnosisStatus.DIAGNOSED
    )

    assert (
        final.reason
        is OpenSetReason.RFS_UNIQUE_CONFIRMATION
    )

    assert (
        final.diagnosed_hypothesis_key
        == "environment_interaction_fault"
    )


def test_out_of_rfs_reaches_inconclusive_after_five_failures():
    baseline = (
        run_p09_4_out_of_rfs_control(
            run_id="p09-4-a2c5-out-of-rfs",
        )
    )

    problem = build_development_problem(
        baseline.trace
    )

    observations = []

    while True:
        decision = (
            select_next_open_set_decision(
                problem,
                tuple(
                    observations
                ),
            )
        )

        if (
            decision.status
            is not DiagnosisStatus.ACTIVE
        ):
            break

        assert (
            decision.experiment_key
            is not None
        )

        observation = (
            _execute_out_of_rfs_probe(
                problem=problem,
                experiment_key=(
                    decision.experiment_key
                ),
                sequence=len(
                    observations
                ),
            )
        )

        assert (
            observation.verdict
            is Verdict.FAIL
        )

        observations.append(
            observation
        )

        assert len(
            observations
        ) <= 5

    assert len(
        observations
    ) == 5

    assert tuple(
        observation.experiment_key
        for observation
        in observations
    ) == (
        "p1-canonical-tool",
        "p2-canonical-parameter",
        "p3-canonical-prerequisite-order",
        "p4-fresh-context",
        "p5-environment-contract",
    )

    assert (
        decision.status
        is DiagnosisStatus.INCONCLUSIVE
    )

    assert (
        decision.reason
        is OpenSetReason.EVIDENCE_CONTRADICTION
    )

    assert (
        decision.diagnosed_hypothesis_key
        is None
    )

    assert (
        decision.replay.contradiction_sequence
        == 4
    )

    assert (
        decision.replay.contradiction_experiment_key
        == "p5-environment-contract"
    )

    assert (
        decision.replay.contradiction_verdict
        is Verdict.FAIL
    )


def test_confirmation_budget_exhaustion_stays_budget_exhausted():
    fault_mode = (
        P094FaultMode.ENVIRONMENT_INTERACTION
    )

    (
        _,
        problem,
    ) = _known_problem(
        fault_mode,
        run_id="p09-4-a2c5-budget",
        budget_units=4,
    )

    observations = []

    for experiment_key in (
        "p1-canonical-tool",
        "p2-canonical-parameter",
        "p3-canonical-prerequisite-order",
        "p4-fresh-context",
    ):
        result = execute_development_probe(
            problem=problem,
            experiment_key=experiment_key,
            fault_mode=fault_mode,
            sequence=len(
                observations
            ),
        )

        assert (
            result.observation.verdict
            is Verdict.FAIL
        )

        observations.append(
            result.observation
        )

    decision = (
        select_next_open_set_decision(
            problem,
            tuple(
                observations
            ),
        )
    )

    assert (
        decision.status
        is DiagnosisStatus.BUDGET_EXHAUSTED
    )

    assert (
        decision.reason
        is OpenSetReason.CONFIRMATION_BUDGET_EXHAUSTED
    )

    assert (
        decision.experiment_key
        is None
    )

    assert (
        decision.diagnosed_hypothesis_key
        is None
    )

    assert (
        "p5-environment-contract"
        in decision.candidate_experiment_keys
    )


def test_open_set_decision_is_deterministic_for_identical_inputs():
    fault_mode = (
        P094FaultMode.SEQUENCING_ORCHESTRATION
    )

    (
        _,
        problem,
    ) = _known_problem(
        fault_mode,
        run_id="p09-4-a2c5-deterministic",
    )

    observations = []

    for experiment_key in (
        "p1-canonical-tool",
        "p2-canonical-parameter",
    ):
        result = execute_development_probe(
            problem=problem,
            experiment_key=experiment_key,
            fault_mode=fault_mode,
            sequence=len(
                observations
            ),
        )

        observations.append(
            result.observation
        )

    first = select_next_open_set_decision(
        problem,
        tuple(
            observations
        ),
    )

    second = select_next_open_set_decision(
        problem,
        tuple(
            observations
        ),
    )

    assert first == second


def test_open_set_core_has_no_p09_4_or_evaluator_dependency():
    path = Path(
        "packages/core/"
        "hetren_diagnosis/"
        "open_set.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(
            path
        ),
    )

    modules = []

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            modules.extend(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ) and node.module:
            modules.append(
                node.module
            )

    forbidden_module_terms = (
        "environments.",
        "packages.engines",
        "evaluator",
        "protected",
        "repair",
        "verification",
        "eligibility",
    )

    violations = [
        module
        for module in modules
        if any(
            term in module.lower()
            for term
            in forbidden_module_terms
        )
    ]

    assert violations == []

    assert "P094FaultMode" not in source

    assert "out_of_rfs" not in source


def test_closed_world_behavior_remains_unchanged_and_opt_in():
    fault_mode = (
        P094FaultMode.ENVIRONMENT_INTERACTION
    )

    (
        _,
        problem,
    ) = _known_problem(
        fault_mode,
        run_id="p09-4-a2c5-closed-world-preserved",
    )

    observations = []

    for experiment_key in (
        "p1-canonical-tool",
        "p2-canonical-parameter",
        "p3-canonical-prerequisite-order",
        "p4-fresh-context",
    ):
        result = execute_development_probe(
            problem=problem,
            experiment_key=experiment_key,
            fault_mode=fault_mode,
            sequence=len(
                observations
            ),
        )

        observations.append(
            result.observation
        )

    closed_world = select_next_decision(
        problem,
        tuple(
            observations
        ),
    )

    open_set = (
        select_next_open_set_decision(
            problem,
            tuple(
                observations
            ),
        )
    )

    assert (
        closed_world.status
        is DiagnosisStatus.DIAGNOSED
    )

    assert (
        open_set.status
        is DiagnosisStatus.ACTIVE
    )

    assert (
        open_set.reason
        is OpenSetReason.CONFIRMATION_REQUIRED
    )

    assert (
        open_set.experiment_key
        == "p5-environment-contract"
    )
