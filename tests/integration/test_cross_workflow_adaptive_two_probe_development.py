"""Real-execution tests for the shared adaptive development policy."""

from dataclasses import replace
import inspect

import pytest

from environments.agent.incident_triage import (
    IncidentFaultMode,
    expected_incident_ids,
    run_incident_triage,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    Observation,
    Verdict,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.adaptive_two_probe_development import (
    run_adaptive_two_probe_development,
)
from packages.engines.behavioral import deterministic_tool_agent as tool
from packages.engines.behavioral import incident_triage_diagnosis as triage
from packages.engines.behavioral.incident_triage_compound_open_set_development import (
    run_compound_incident_triage,
)


def _run_case(workflow, fault, *, budget=2, corrupt=False):
    """Bind either actual agent environment to the same core policy."""
    if workflow == "tool":
        baseline = tool.run_tool_agent(
            tool.FaultMode(fault),
            run_id="a57-tool-baseline",
        )
        problem = tool.build_diagnosis_problem(baseline.trace)

        def run(experiment, sequence):
            return tool.run_tool_agent(
                tool.FaultMode(fault),
                run_id=f"a57-tool-probe-{sequence}",
                intervention=experiment.intervention_kind,
            )

        def counterexample(executed):
            return canonical_sha256({
                "expected_output": executed.expected_output,
                "actual_output": executed.output,
            })

    else:
        if fault == "compound":
            def execute(run_id, intervention=None):
                return run_compound_incident_triage(
                    run_id=run_id,
                    intervention=intervention,
                )
        else:
            def execute(run_id, intervention=None):
                return run_incident_triage(
                    IncidentFaultMode(fault),
                    run_id=run_id,
                    intervention=intervention,
                )

        baseline = execute("a57-triage-baseline")
        problem = triage.build_diagnosis_problem(baseline.trace)

        def run(experiment, sequence):
            return execute(
                f"a57-triage-probe-{sequence}",
                intervention=experiment.intervention_kind,
            )

        def counterexample(executed):
            incident_ids = expected_incident_ids()
            return canonical_sha256({
                "expected_report": {
                    "service": baseline.report.service,
                    "incident_ids": incident_ids,
                    "count": len(incident_ids),
                },
                "actual_report": executed.report.canonical_payload(),
            })

    assert not baseline.passed
    calls = []

    def execute_probe(experiment, sequence):
        executed = run(experiment, sequence)
        calls.append(experiment.key)

        passed = executed.passed

        observation = Observation(
            sequence=sequence,
            experiment_key=experiment.key,
            experiment_sha256=experiment.experiment_sha256,
            verdict=Verdict.PASS if passed else Verdict.FAIL,
            actual_cost_units=experiment.cost_units,
            evidence_sha256=executed.execution_evidence_sha256,
            counterexample_sha256=(
                None if passed else counterexample(executed)
            ),
        )

        if corrupt:
            observation = replace(
                observation,
                evidence_sha256="0" * 64,
            )

        return observation, executed

    result = run_adaptive_two_probe_development(
        problem,
        execute_probe=execute_probe,
        budget_units=budget,
    )

    return result, calls


@pytest.mark.parametrize(
    "workflow,fault,expected_hypothesis,expected_status,probes",
    [
        (
            "tool", "tool_selection",
            "tool_selection_fault",
            DiagnosisStatus.DIAGNOSED, 1,
        ),
        (
            "tool", "parameter_transformation",
            "parameter_transformation_fault",
            DiagnosisStatus.DIAGNOSED, 2,
        ),
        (
            "triage", "filter_tool_selection",
            "filter_tool_selection_fault",
            DiagnosisStatus.DIAGNOSED, 1,
        ),
        (
            "triage", "threshold_transformation",
            "threshold_transformation_fault",
            DiagnosisStatus.DIAGNOSED, 2,
        ),
        (
            "triage", "compound",
            None,
            DiagnosisStatus.INCONCLUSIVE, 2,
        ),
    ],
)
def test_shared_policy_on_actual_agent_runs(
    workflow, fault, expected_hypothesis, expected_status, probes
):
    result, calls = _run_case(workflow, fault)

    assert result.policy_status is expected_status
    assert result.diagnosed_hypothesis_key == expected_hypothesis
    assert result.experiment_count == probes
    assert result.experiment_cost_units == probes
    assert len(result.diagnostic_runs) == probes
    assert len(calls) == probes

    for observation, executed in zip(
        result.observations,
        result.diagnostic_runs,
    ):
        assert (
            observation.evidence_sha256
            == executed.execution_evidence_sha256
        )

    if fault == "compound":
        assert (
            result.policy_reason
            == "evidence_contradiction"
        )


@pytest.mark.parametrize(
    "workflow,fault",
    [
        ("tool", "parameter_transformation"),
        ("triage", "threshold_transformation"),
        ("triage", "compound"),
    ],
)
def test_insufficient_budget_does_not_certify_cause(
    workflow, fault
):
    result, calls = _run_case(
        workflow, fault, budget=1,
    )

    assert (
        result.policy_status
        is DiagnosisStatus.BUDGET_EXHAUSTED
    )
    assert result.diagnosed_hypothesis_key is None
    assert result.final_open_set_decision is None
    assert result.experiment_count == 1
    assert len(calls) == 1


@pytest.mark.parametrize(
    "workflow,fault",
    [
        ("tool", "tool_selection"),
        ("triage", "filter_tool_selection"),
    ],
)
def test_first_pass_avoids_an_unnecessary_probe(
    workflow, fault
):
    result, calls = _run_case(
        workflow, fault, budget=1,
    )

    assert result.policy_status is DiagnosisStatus.DIAGNOSED
    assert result.experiment_count == 1
    assert len(calls) == 1


@pytest.mark.parametrize(
    "workflow,fault",
    [
        ("tool", "tool_selection"),
        ("triage", "compound"),
    ],
)
def test_corrupted_executed_evidence_is_rejected(
    workflow, fault
):
    with pytest.raises(
        ContractError,
        match="does not match the executed run",
    ):
        _run_case(workflow, fault, corrupt=True)


def test_shared_policy_does_not_import_either_agent():
    from packages.core.hetren_diagnosis import (
        adaptive_two_probe_development as policy,
    )

    source = inspect.getsource(policy)
    assert "environments.agent" not in source
    assert "deterministic_tool_agent" not in source
    assert "incident_triage_diagnosis" not in source


def test_same_tool_agent_inputs_remain_deterministic():
    first, _ = _run_case(
        "tool", "parameter_transformation",
    )
    second, _ = _run_case(
        "tool", "parameter_transformation",
    )
    assert first == second
