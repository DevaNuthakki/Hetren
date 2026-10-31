from packages.core.hetren_diagnosis.contracts import (
    DiagnosisStatus,
    Observation,
    Verdict,
    canonical_sha256,
)

from packages.core.hetren_diagnosis.lifecycle import (
    replay_observations,
    select_next_decision,
)

from environments.agent.p09_4_multistep_incident import (
    P094DiagnosticIntervention,
    run_p09_4_out_of_rfs_control,
    shared_faulty_incident_ids,
)

from packages.engines.behavioral.p09_4_multistep_diagnosis import (
    build_development_problem,
    development_probe_keys,
)


KNOWN_HYPOTHESES = (
    "tool_selection_fault",
    "parameter_transformation_fault",
    "sequencing_orchestration_fault",
    "state_context_fault",
    "environment_interaction_fault",
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
                f"{problem.trace.run_id}:out-of-rfs:"
                f"{sequence}:{experiment.key}"
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

    observation = Observation(
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

    return (
        run,
        observation,
    )


def test_out_of_rfs_control_is_real_failing_multistep_execution():
    run = run_p09_4_out_of_rfs_control(
        run_id="p09-4-a2c3-control",
    )

    assert run.passed is False

    assert run.workflow_step_count == 17

    assert run.tool_interaction_count == 7


def test_out_of_rfs_control_shares_known_fault_coarse_failure_signature():
    run = run_p09_4_out_of_rfs_control(
        run_id="p09-4-a2c3-shared-signature",
    )

    assert (
        run.report.incident_ids
        == shared_faulty_incident_ids()
    )

    assert run.report.count == 2


def test_all_five_registered_probes_fail_on_out_of_rfs_control():
    baseline = (
        run_p09_4_out_of_rfs_control(
            run_id="p09-4-a2c3-all-probes",
        )
    )

    problem = build_development_problem(
        baseline.trace
    )

    assert tuple(
        hypothesis.key
        for hypothesis in problem.hypotheses
    ) == KNOWN_HYPOTHESES

    observed = []

    for sequence, experiment_key in enumerate(
        development_probe_keys()
    ):
        (
            run,
            observation,
        ) = _execute_out_of_rfs_probe(
            problem=problem,
            experiment_key=experiment_key,
            sequence=sequence,
        )

        assert run.passed is False

        assert (
            observation.verdict
            is Verdict.FAIL
        )

        assert (
            observation.evidence_sha256
            == run.execution_evidence_sha256
        )

        observed.append(
            (
                experiment_key,
                observation.verdict,
            )
        )

    assert len(
        observed
    ) == 5


def test_out_of_rfs_probe_execution_is_reproducible_and_isolated():
    baseline_before = (
        run_p09_4_out_of_rfs_control(
            run_id="p09-4-a2c3-isolation",
        )
    )

    problem = build_development_problem(
        baseline_before.trace
    )

    first_key = (
        development_probe_keys()[
            0
        ]
    )

    second_key = (
        development_probe_keys()[
            1
        ]
    )

    first = _execute_out_of_rfs_probe(
        problem=problem,
        experiment_key=first_key,
        sequence=0,
    )

    _execute_out_of_rfs_probe(
        problem=problem,
        experiment_key=second_key,
        sequence=0,
    )

    repeated = _execute_out_of_rfs_probe(
        problem=problem,
        experiment_key=first_key,
        sequence=0,
    )

    baseline_after = (
        run_p09_4_out_of_rfs_control(
            run_id="p09-4-a2c3-isolation",
        )
    )

    assert first == repeated

    assert baseline_before == baseline_after


def test_closed_world_lifecycle_false_specific_diagnoses_out_of_rfs_control():
    baseline = (
        run_p09_4_out_of_rfs_control(
            run_id="p09-4-a2c3-false-certainty",
        )
    )

    problem = build_development_problem(
        baseline.trace
    )

    observations = []
    selected_keys = []
    decision_statuses = []

    while True:
        decision = select_next_decision(
            problem,
            tuple(
                observations
            ),
        )

        decision_statuses.append(
            decision.status
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

        selected_keys.append(
            decision.experiment_key
        )

        (
            _,
            observation,
        ) = _execute_out_of_rfs_probe(
            problem=problem,
            experiment_key=(
                decision.experiment_key
            ),
            sequence=len(
                observations
            ),
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

    assert (
        decision.status
        is DiagnosisStatus.DIAGNOSED
    )

    assert len(
        observations
    ) == 4

    assert tuple(
        selected_keys
    ) == (
        "p1-canonical-tool",
        "p2-canonical-parameter",
        "p3-canonical-prerequisite-order",
        "p4-fresh-context",
    )

    assert all(
        observation.verdict
        is Verdict.FAIL
        for observation
        in observations
    )

    assert survivors == (
        "environment_interaction_fault",
    )

    assert (
        "p5-environment-contract"
        not in selected_keys
    )

    assert (
        DiagnosisStatus.INCONCLUSIVE
        not in decision_statuses
    )


def test_current_contract_has_no_explicit_open_set_terminal_status():
    values = tuple(
        status.value
        for status in DiagnosisStatus
    )

    assert values == (
        "active",
        "diagnosed",
        "inconclusive",
        "budget_exhausted",
    )

    assert "unknown" not in values

    assert "out_of_rfs" not in values
