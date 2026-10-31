import dataclasses
import inspect

import pytest

from environments.agent.p09_4_multistep_incident import (
    P094DiagnosticIntervention,
    P094FaultMode,
    expected_incident_ids,
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

from packages.core.hetren_diagnosis.open_set import (
    OpenSetReason,
    select_next_open_set_decision,
)

from packages.engines.behavioral.p09_4_checkpoint_replay import (
    P094ReplayBaseline,
    capture_p09_4_out_of_rfs_replay_baseline,
    capture_p09_4_replay_baseline,
    execute_checkpoint_replay,
)

from packages.engines.behavioral.p09_4_multistep_diagnosis import (
    build_development_problem,
    development_probe_keys,
)


CASE_KEYS = (
    "canonical_control",
    "f1_tool_selection",
    "f2_parameter_transformation",
    "f3_sequencing_orchestration",
    "f4_state_context",
    "f5_environment_interaction",
    "out_of_rfs_report_assembly",
)


KNOWN_FAULT_CASES = (
    "f1_tool_selection",
    "f2_parameter_transformation",
    "f3_sequencing_orchestration",
    "f4_state_context",
    "f5_environment_interaction",
)


FAULT_BY_CASE = {
    "canonical_control":
        P094FaultMode.NONE,

    "f1_tool_selection":
        P094FaultMode.TOOL_SELECTION,

    "f2_parameter_transformation":
        P094FaultMode.PARAMETER_TRANSFORMATION,

    "f3_sequencing_orchestration":
        P094FaultMode.SEQUENCING_ORCHESTRATION,

    "f4_state_context":
        P094FaultMode.STATE_CONTEXT,

    "f5_environment_interaction":
        P094FaultMode.ENVIRONMENT_INTERACTION,
}


EXPECTED_HYPOTHESIS = {
    "f1_tool_selection":
        "tool_selection_fault",

    "f2_parameter_transformation":
        "parameter_transformation_fault",

    "f3_sequencing_orchestration":
        "sequencing_orchestration_fault",

    "f4_state_context":
        "state_context_fault",

    "f5_environment_interaction":
        "environment_interaction_fault",
}


EXPECTED_CONFIRMATION_COUNT = {
    "f1_tool_selection":
        1,

    "f2_parameter_transformation":
        2,

    "f3_sequencing_orchestration":
        3,

    "f4_state_context":
        4,

    "f5_environment_interaction":
        5,
}


EXPECTED_OPERATIONS = {
    "p1-canonical-tool":
        (
            "filter_severity",
            "enrich_incidents",
            "validate_incidents",
            "build_triage_report",
        ),

    "p2-canonical-parameter":
        (
            "filter_severity",
            "enrich_incidents",
            "validate_incidents",
            "build_triage_report",
        ),

    "p3-canonical-prerequisite-order":
        (
            "enrich_incidents",
            "validate_incidents",
            "build_triage_report",
        ),

    "p4-fresh-context":
        (
            "load_policy_context",
            "validate_incidents",
            "build_triage_report",
        ),

    "p5-environment-contract":
        (
            "enrich_incidents",
            "validate_incidents",
            "build_triage_report",
        ),
}


def _capture_case(
    case_key,
    *,
    run_id,
):
    if (
        case_key
        == "out_of_rfs_report_assembly"
    ):
        return (
            capture_p09_4_out_of_rfs_replay_baseline(
                run_id=run_id,
            )
        )

    return capture_p09_4_replay_baseline(
        FAULT_BY_CASE[
            case_key
        ],
        run_id=run_id,
    )


def _full_run_case(
    case_key,
    *,
    run_id,
    intervention=None,
):
    if (
        case_key
        == "out_of_rfs_report_assembly"
    ):
        return run_p09_4_out_of_rfs_control(
            run_id=run_id,
            intervention=intervention,
        )

    return run_p09_4_multistep_incident(
        FAULT_BY_CASE[
            case_key
        ],
        run_id=run_id,
        intervention=intervention,
    )


def _experiment(
    problem,
    experiment_key,
):
    return next(
        item
        for item
        in problem.experiments
        if item.key
        == experiment_key
    )


def _replay_observation(
    *,
    problem,
    replay,
    sequence,
):
    experiment = _experiment(
        problem,
        replay.experiment_key,
    )

    verdict = (
        Verdict.PASS
        if replay.passed
        else Verdict.FAIL
    )

    counterexample_sha256 = None

    if verdict is Verdict.FAIL:
        counterexample_sha256 = (
            canonical_sha256(
                {
                    "expected_report": {
                        "incident_ids":
                            expected_incident_ids(),
                    },
                    "actual_report":
                        replay.report.canonical_payload(),
                }
            )
        )

    return Observation(
        sequence=sequence,
        experiment_key=(
            experiment.key
        ),
        experiment_sha256=(
            experiment.experiment_sha256
        ),
        verdict=verdict,
        actual_cost_units=(
            experiment.cost_units
        ),
        evidence_sha256=(
            replay.execution_evidence_sha256
        ),
        counterexample_sha256=(
            counterexample_sha256
        ),
    )


@pytest.mark.parametrize(
    "case_key",
    CASE_KEYS,
)
def test_replay_baseline_matches_historical_full_run(
    case_key,
):
    run_id = (
        "p09-4-a2c6e-baseline-"
        + case_key
    )

    replay_baseline = _capture_case(
        case_key,
        run_id=run_id,
    )

    historical = _full_run_case(
        case_key,
        run_id=run_id,
    )

    assert (
        replay_baseline.run
        == historical
    )

    assert (
        replay_baseline.run.trace.trace_sha256
        == historical.trace.trace_sha256
    )


@pytest.mark.parametrize(
    "case_key",
    CASE_KEYS,
)
@pytest.mark.parametrize(
    "probe_key",
    development_probe_keys(),
)
def test_checkpoint_replay_matches_historical_full_rerun(
    case_key,
    probe_key,
):
    baseline = _capture_case(
        case_key,
        run_id=(
            "p09-4-a2c6e-equivalence-"
            + case_key
        ),
    )

    problem = build_development_problem(
        baseline.run.trace
    )

    replay = execute_checkpoint_replay(
        baseline=baseline,
        problem=problem,
        experiment_key=probe_key,
        sequence=0,
    )

    experiment = _experiment(
        problem,
        probe_key,
    )

    intervention = (
        P094DiagnosticIntervention(
            kind=experiment.intervention_kind,
            target=experiment.intervention_target,
        )
    )

    historical = _full_run_case(
        case_key,
        run_id=(
            "p09-4-a2c6e-reference-"
            + case_key
            + "-"
            + probe_key
        ),
        intervention=intervention,
    )

    assert replay.report == historical.report
    assert replay.passed == historical.passed


@pytest.mark.parametrize(
    "probe_key",
    development_probe_keys(),
)
def test_replay_operation_sequences_are_causally_minimal(
    probe_key,
):
    baseline = _capture_case(
        "canonical_control",
        run_id=(
            "p09-4-a2c6e-operations-"
            + probe_key
        ),
    )

    problem = build_development_problem(
        baseline.run.trace
    )

    replay = execute_checkpoint_replay(
        baseline=baseline,
        problem=problem,
        experiment_key=probe_key,
        sequence=0,
    )

    assert (
        replay.replay_operations
        == EXPECTED_OPERATIONS[
            probe_key
        ]
    )

    assert (
        replay.tool_interaction_count
        == len(
            EXPECTED_OPERATIONS[
                probe_key
            ]
        )
    )


@pytest.mark.parametrize(
    "probe_key",
    development_probe_keys(),
)
def test_checkpoint_replay_is_deterministic_and_isolated(
    probe_key,
):
    baseline = _capture_case(
        "f5_environment_interaction",
        run_id=(
            "p09-4-a2c6e-isolation-"
            + probe_key
        ),
    )

    problem = build_development_problem(
        baseline.run.trace
    )

    first = execute_checkpoint_replay(
        baseline=baseline,
        problem=problem,
        experiment_key=probe_key,
        sequence=0,
    )

    different_probe = next(
        key
        for key
        in development_probe_keys()
        if key
        != probe_key
    )

    execute_checkpoint_replay(
        baseline=baseline,
        problem=problem,
        experiment_key=different_probe,
        sequence=1,
    )

    repeated = execute_checkpoint_replay(
        baseline=baseline,
        problem=problem,
        experiment_key=probe_key,
        sequence=0,
    )

    assert first == repeated
    assert (
        first.execution_evidence_sha256
        == repeated.execution_evidence_sha256
    )


def test_checkpoint_payloads_exclude_latent_truth():
    baseline = _capture_case(
        "f5_environment_interaction",
        run_id="p09-4-a2c6e-checkpoint-boundary",
    )

    forbidden_field_terms = (
        "fault",
        "out_of_rfs",
        "evaluator",
        "diagnosis",
    )

    public_field_names = tuple(
        field.name
        for field
        in dataclasses.fields(
            P094ReplayBaseline
        )
    )

    for field_name in public_field_names:
        assert not any(
            term in field_name.lower()
            for term
            in forbidden_field_terms
        )

    expected_payload_keys = {
        "pre-filter":
            {
                "key",
                "baseline_trace_sha256",
                "service_rows",
                "context",
            },

        "post-filter":
            {
                "key",
                "baseline_trace_sha256",
                "filtered_rows",
                "context",
            },

        "pre-validation":
            {
                "key",
                "baseline_trace_sha256",
                "normalized_rows",
            },
    }

    for checkpoint in baseline.checkpoints:
        payload = (
            checkpoint.canonical_payload()
        )

        assert (
            set(
                payload
            )
            == expected_payload_keys[
                checkpoint.key
            ]
        )

        payload_text = repr(
            payload
        ).lower()

        assert "fault_mode" not in payload_text
        assert "out_of_rfs" not in payload_text
        assert "evaluator" not in payload_text
        assert "diagnosed_hypothesis" not in payload_text


def test_replay_executor_is_truth_blind_and_prediction_blind():
    signature = inspect.signature(
        execute_checkpoint_replay
    )

    assert tuple(
        signature.parameters
    ) == (
        "baseline",
        "problem",
        "experiment_key",
        "sequence",
    )

    source = inspect.getsource(
        execute_checkpoint_replay
    )

    assert "fault_mode" not in source
    assert "out_of_rfs" not in source
    assert "predicted_verdicts" not in source
    assert "evaluator" not in source


def test_replay_lineage_binds_baseline_experiment_checkpoint_and_events():
    baseline = _capture_case(
        "f3_sequencing_orchestration",
        run_id="p09-4-a2c6e-lineage",
    )

    problem = build_development_problem(
        baseline.run.trace
    )

    replay = execute_checkpoint_replay(
        baseline=baseline,
        problem=problem,
        experiment_key=(
            "p3-canonical-prerequisite-order"
        ),
        sequence=2,
    )

    experiment = _experiment(
        problem,
        replay.experiment_key,
    )

    checkpoint = baseline.checkpoint(
        replay.checkpoint_key
    )

    assert (
        replay.baseline_trace_sha256
        == baseline.run.trace.trace_sha256
    )

    assert (
        replay.experiment_sha256
        == experiment.experiment_sha256
    )

    assert (
        replay.checkpoint_state_sha256
        == checkpoint.state_sha256
    )

    assert replay.trace.events

    assert (
        replay.execution_evidence_sha256
        == execute_checkpoint_replay(
            baseline=baseline,
            problem=problem,
            experiment_key=(
                "p3-canonical-prerequisite-order"
            ),
            sequence=2,
        ).execution_evidence_sha256
    )


@pytest.mark.parametrize(
    "case_key",
    KNOWN_FAULT_CASES,
)
def test_open_set_known_fault_semantics_survive_checkpoint_replay(
    case_key,
):
    baseline = _capture_case(
        case_key,
        run_id=(
            "p09-4-a2c6e-open-set-"
            + case_key
        ),
    )

    problem = build_development_problem(
        baseline.run.trace
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
            break

        assert (
            decision.status
            is DiagnosisStatus.ACTIVE
        )

        replay = execute_checkpoint_replay(
            baseline=baseline,
            problem=problem,
            experiment_key=(
                decision.experiment_key
            ),
            sequence=len(
                observations
            ),
        )

        observations.append(
            _replay_observation(
                problem=problem,
                replay=replay,
                sequence=len(
                    observations
                ),
            )
        )

        assert len(
            observations
        ) <= 5

    assert (
        len(
            observations
        )
        == EXPECTED_CONFIRMATION_COUNT[
            case_key
        ]
    )

    assert (
        decision.reason
        is OpenSetReason.RFS_UNIQUE_CONFIRMATION
    )

    assert (
        decision.diagnosed_hypothesis_key
        == EXPECTED_HYPOTHESIS[
            case_key
        ]
    )

    assert (
        observations[
            -1
        ].verdict
        is Verdict.PASS
    )


def test_out_of_rfs_open_set_contradiction_survives_checkpoint_replay():
    baseline = _capture_case(
        "out_of_rfs_report_assembly",
        run_id="p09-4-a2c6e-open-set-out-of-rfs",
    )

    problem = build_development_problem(
        baseline.run.trace
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

        replay = execute_checkpoint_replay(
            baseline=baseline,
            problem=problem,
            experiment_key=(
                decision.experiment_key
            ),
            sequence=len(
                observations
            ),
        )

        observation = _replay_observation(
            problem=problem,
            replay=replay,
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

    assert len(
        observations
    ) == 5

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


def test_confirmation_budget_exhaustion_survives_checkpoint_replay():
    baseline = _capture_case(
        "f5_environment_interaction",
        run_id="p09-4-a2c6e-budget",
    )

    base_problem = build_development_problem(
        baseline.run.trace
    )

    problem = DiagnosisProblem(
        trace=base_problem.trace,
        hypotheses=base_problem.hypotheses,
        experiments=base_problem.experiments,
        budget_units=4,
    )

    observations = []

    for experiment_key in (
        "p1-canonical-tool",
        "p2-canonical-parameter",
        "p3-canonical-prerequisite-order",
        "p4-fresh-context",
    ):
        replay = execute_checkpoint_replay(
            baseline=baseline,
            problem=problem,
            experiment_key=experiment_key,
            sequence=len(
                observations
            ),
        )

        observation = _replay_observation(
            problem=problem,
            replay=replay,
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
