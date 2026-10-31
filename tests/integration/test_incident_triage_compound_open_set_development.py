"""Development-only compound-fault open-set acceptance tests."""

from dataclasses import fields

import pytest

from environments.agent.incident_triage import (
    IncidentFaultMode,
    run_incident_triage,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    InterventionKind,
    Verdict,
)
from packages.core.hetren_diagnosis.open_set import (
    OpenSetReason,
    select_next_open_set_decision,
)
from packages.engines.behavioral.incident_triage_compound_open_set_development import (
    run_compound_incident_triage,
    run_compound_open_set_development,
)
from scripts.incident_triage_evidence_report import SCENARIOS


def test_compound_fixture_combines_actual_known_configuration_faults():
    tool_fault = run_incident_triage(
        IncidentFaultMode.FILTER_TOOL_SELECTION,
        run_id="a5-known-tool",
    )
    threshold_fault = run_incident_triage(
        IncidentFaultMode.THRESHOLD_TRANSFORMATION,
        run_id="a5-known-threshold",
    )
    compound = run_compound_incident_triage(
        run_id="a5-combined",
    )

    assert not compound.passed
    assert (
        compound.selected_filter_tool
        == tool_fault.selected_filter_tool
    )
    assert compound.threshold == threshold_fault.threshold
    assert compound.trace.events
    assert compound.execution_evidence_sha256


@pytest.mark.parametrize(
    "intervention",
    [
        InterventionKind.REPLACE_TOOL,
        InterventionKind.OVERRIDE_PARAMETER,
    ],
)
def test_single_intervention_does_not_fix_compound_failure(
    intervention,
):
    baseline = run_compound_incident_triage(
        run_id="a5-single-baseline",
    )
    attempted = run_compound_incident_triage(
        run_id=f"a5-single-{intervention.value}",
        intervention=intervention,
    )

    assert not baseline.passed
    assert not attempted.passed
    assert (
        baseline.execution_evidence_sha256
        != attempted.execution_evidence_sha256
    )

    if intervention is InterventionKind.REPLACE_TOOL:
        assert (
            attempted.selected_filter_tool
            == "inclusive_severity_filter"
        )
        assert attempted.threshold == baseline.threshold
    else:
        assert (
            attempted.selected_filter_tool
            == baseline.selected_filter_tool
        )
        assert attempted.threshold != baseline.threshold


def test_real_execution_contradicts_known_single_fault_hypotheses():
    result = run_compound_open_set_development(
        run_id="a5-contradiction",
    )

    assert not result.baseline_run.passed
    assert len(result.observations) == 2
    assert len(result.diagnostic_runs) == 2
    assert len(result.decisions) == 3

    assert (
        result.decisions[0].status
        is DiagnosisStatus.ACTIVE
    )
    # The original open-set contract legitimately diagnoses after
    # the first probe within its single-fault reference set. In this
    # predeclared compound challenge, that result is provisional.
    assert (
        result.decisions[1].status
        is DiagnosisStatus.DIAGNOSED
    )
    assert (
        result.decisions[1].reason
        is OpenSetReason.RFS_UNIQUE_CONFIRMATION
    )
    assert (
        result.decisions[1].diagnosed_hypothesis_key
        == "threshold_transformation_fault"
    )

    assert (
        result.final_decision.status
        is DiagnosisStatus.INCONCLUSIVE
    )
    assert (
        result.final_decision.reason
        is OpenSetReason.EVIDENCE_CONTRADICTION
    )
    assert (
        result.final_decision.diagnosed_hypothesis_key
        is None
    )
    assert result.final_decision.experiment_key is None
    assert result.final_decision.replay.contradicted

    observed_keys = {
        item.experiment_key
        for item in result.observations
    }
    assert observed_keys == {
        experiment.key
        for experiment in result.problem.experiments
    }

    for index, (observation, run) in enumerate(
        zip(result.observations, result.diagnostic_runs)
    ):
        assert observation.sequence == index
        assert observation.verdict is Verdict.FAIL
        assert not run.passed
        assert (
            observation.evidence_sha256
            == run.execution_evidence_sha256
        )
        assert observation.counterexample_sha256 is not None

        experiment = next(
            item
            for item in result.problem.experiments
            if item.key == observation.experiment_key
        )
        assert (
            observation.experiment_sha256
            == experiment.experiment_sha256
        )

    assert (
        result.diagnostic_runs[0].trace.trace_sha256
        != result.diagnostic_runs[1].trace.trace_sha256
    )


def test_compound_result_has_no_repair_or_authorization_surface():
    result = run_compound_open_set_development(
        run_id="a5-no-authority",
    )

    names = {field.name for field in fields(type(result))}

    assert names.isdisjoint({
        "repair",
        "proposal",
        "execution_approval",
        "verification_report",
        "eligibility",
        "authorization",
        "deployment_authorized",
    })
    assert result.final_decision.diagnosed_hypothesis_key is None


def test_compound_decision_is_deterministic_for_identical_inputs():
    first = run_compound_open_set_development(
        run_id="a5-repeated",
    )
    second = run_compound_open_set_development(
        run_id="a5-repeated",
    )
    assert first == second


@pytest.mark.parametrize(
    "run_id",
    [
        "",
        " ",
        "../unsafe",
        "contains space",
        "bad:identifier",
        None,
        123,
    ],
)
def test_invalid_run_identifiers_are_rejected(run_id):
    with pytest.raises(ContractError):
        run_compound_open_set_development(
            run_id=run_id,
        )


def test_unsupported_intervention_is_rejected():
    with pytest.raises(ContractError):
        run_compound_incident_triage(
            run_id="a5-replay-rejected",
            intervention=InterventionKind.REPLAY,
        )


def test_existing_public_fault_modes_and_cli_are_unchanged():
    assert tuple(mode.value for mode in IncidentFaultMode) == (
        "filter_tool_selection",
        "threshold_transformation",
    )
    assert SCENARIOS == (
        "filter_tool_selection",
        "threshold_transformation",
    )


def test_second_real_probe_falsifies_provisional_diagnosis():
    result = run_compound_open_set_development(
        run_id="a5-falsification-audit",
    )

    assert len(result.observations) == 2

    provisional = select_next_open_set_decision(
        result.problem,
        result.observations[:1],
    )

    assert provisional == result.decisions[1]
    assert provisional.status is DiagnosisStatus.DIAGNOSED
    assert (
        provisional.diagnosed_hypothesis_key
        == "threshold_transformation_fault"
    )

    # The second experiment is an explicitly predeclared challenge,
    # not a planner-selected experiment after DIAGNOSED.
    challenge = result.observations[1]
    assert challenge.experiment_key == "e2-override-threshold"
    assert challenge.verdict is Verdict.FAIL
    assert (
        challenge.evidence_sha256
        == result.diagnostic_runs[1].execution_evidence_sha256
    )

    final = select_next_open_set_decision(
        result.problem,
        result.observations,
    )

    assert final == result.final_decision
    assert final.status is DiagnosisStatus.INCONCLUSIVE
    assert final.reason is OpenSetReason.EVIDENCE_CONTRADICTION
    assert final.diagnosed_hypothesis_key is None
    assert final.replay.contradiction_sequence == 1
    assert (
        final.replay.contradiction_experiment_key
        == challenge.experiment_key
    )
