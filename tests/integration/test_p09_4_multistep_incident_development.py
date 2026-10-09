from pathlib import Path

import pytest

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    EventKind,
)

from environments.agent.p09_4_multistep_incident import (
    P094FaultMode,
    expected_incident_ids,
    run_p09_4_multistep_incident,
    shared_faulty_incident_ids,
)


PRIMARY_FAULTS = (
    P094FaultMode.TOOL_SELECTION,
    P094FaultMode.PARAMETER_TRANSFORMATION,
    P094FaultMode.SEQUENCING_ORCHESTRATION,
    P094FaultMode.STATE_CONTEXT,
    P094FaultMode.ENVIRONMENT_INTERACTION,
)


ALL_DEVELOPMENT_MODES = (
    P094FaultMode.NONE,
    *PRIMARY_FAULTS,
)


def _operation_surface(
    run,
):
    return tuple(
        (
            event.kind,
            event.component,
            event.operation,
        )
        for event in run.trace.events
    )


def _first_behavioral_divergence(
    control,
    candidate,
):
    differences = []

    for index, (
        control_event,
        candidate_event,
    ) in enumerate(
        zip(
            control.trace.events,
            candidate.trace.events,
            strict=True,
        )
    ):
        control_signature = (
            control_event.input_sha256,
            control_event.output_sha256,
            control_event.state_before_sha256,
            control_event.state_after_sha256,
        )

        candidate_signature = (
            candidate_event.input_sha256,
            candidate_event.output_sha256,
            candidate_event.state_before_sha256,
            candidate_event.state_after_sha256,
        )

        if (
            control_signature
            != candidate_signature
        ):
            differences.append(
                index
            )

    assert differences

    return differences[
        0
    ]


def test_fault_mode_surface_is_explicit_and_development_only():
    assert tuple(
        mode.value
        for mode in P094FaultMode
    ) == (
        "none",
        "tool_selection",
        "parameter_transformation",
        "sequencing_orchestration",
        "state_context",
        "environment_interaction",
    )


def test_canonical_control_passes_expected_workflow():
    run = run_p09_4_multistep_incident(
        P094FaultMode.NONE,
        run_id="p09-4-control",
    )

    assert run.passed is True

    assert (
        run.report.incident_ids
        == expected_incident_ids()
    )

    assert run.report.count == 3


@pytest.mark.parametrize(
    "fault_mode",
    PRIMARY_FAULTS,
)
def test_primary_faults_share_same_coarse_visible_failure(
    fault_mode,
):
    run = run_p09_4_multistep_incident(
        fault_mode,
        run_id=(
            "p09-4-shared-failure-"
            + fault_mode.value
        ),
    )

    assert run.passed is False

    assert (
        run.report.incident_ids
        == shared_faulty_incident_ids()
    )

    assert run.report.count == 2


@pytest.mark.parametrize(
    "fault_mode",
    ALL_DEVELOPMENT_MODES,
)
def test_every_development_run_is_structurally_richer(
    fault_mode,
):
    run = run_p09_4_multistep_incident(
        fault_mode,
        run_id=(
            "p09-4-richness-"
            + fault_mode.value
        ),
    )

    assert run.workflow_step_count == 17

    assert (
        run.tool_interaction_count
        == 7
    )

    kinds = tuple(
        event.kind
        for event in run.trace.events
    )

    assert (
        kinds.count(
            EventKind.TOOL_CALL
        )
        == 7
    )

    assert (
        kinds.count(
            EventKind.TOOL_RESULT
        )
        == 7
    )

    assert (
        kinds.count(
            EventKind.DECISION
        )
        == 1
    )

    assert (
        kinds.count(
            EventKind.STATE_TRANSITION
        )
        == 1
    )

    assert (
        kinds.count(
            EventKind.TERMINATION
        )
        == 1
    )

    assert tuple(
        event.sequence
        for event in run.trace.events
    ) == tuple(
        range(
            17
        )
    )


def test_all_primary_faults_preserve_same_public_operation_surface():
    control = run_p09_4_multistep_incident(
        P094FaultMode.NONE,
        run_id="p09-4-operation-control",
    )

    expected_surface = (
        _operation_surface(
            control
        )
    )

    for fault_mode in PRIMARY_FAULTS:
        run = run_p09_4_multistep_incident(
            fault_mode,
            run_id=(
                "p09-4-operation-"
                + fault_mode.value
            ),
        )

        assert (
            _operation_surface(
                run
            )
            == expected_surface
        )


def test_faults_diverge_at_distinct_causal_workflow_boundaries():
    control = run_p09_4_multistep_incident(
        P094FaultMode.NONE,
        run_id="p09-4-divergence",
    )

    expected_first_divergence = {
        P094FaultMode.STATE_CONTEXT:
            4,

        P094FaultMode.TOOL_SELECTION:
            6,

        P094FaultMode.PARAMETER_TRANSFORMATION:
            6,

        P094FaultMode.ENVIRONMENT_INTERACTION:
            9,

        P094FaultMode.SEQUENCING_ORCHESTRATION:
            11,
    }

    runs = {
        fault_mode:
            run_p09_4_multistep_incident(
                fault_mode,
                run_id="p09-4-divergence",
            )
        for fault_mode
        in PRIMARY_FAULTS
    }

    for (
        fault_mode,
        expected_index,
    ) in expected_first_divergence.items():
        assert (
            _first_behavioral_divergence(
                control,
                runs[
                    fault_mode
                ],
            )
            == expected_index
        )

    tool_event = runs[
        P094FaultMode.TOOL_SELECTION
    ].trace.events[
        6
    ]

    parameter_event = runs[
        P094FaultMode.PARAMETER_TRANSFORMATION
    ].trace.events[
        6
    ]

    assert (
        tool_event.output_sha256
        != parameter_event.output_sha256
    )

    assert (
        tool_event.state_after_sha256
        != parameter_event.state_after_sha256
    )


def test_environment_is_deterministic_for_same_inputs():
    first = run_p09_4_multistep_incident(
        P094FaultMode.SEQUENCING_ORCHESTRATION,
        run_id="p09-4-deterministic",
    )

    second = run_p09_4_multistep_incident(
        P094FaultMode.SEQUENCING_ORCHESTRATION,
        run_id="p09-4-deterministic",
    )

    assert first == second

    assert (
        first.execution_evidence_sha256
        == second.execution_evidence_sha256
    )


def test_invalid_inputs_are_rejected():
    with pytest.raises(
        ContractError,
    ):
        run_p09_4_multistep_incident(
            "tool_selection",
            run_id="invalid-mode",
        )

    with pytest.raises(
        ContractError,
    ):
        run_p09_4_multistep_incident(
            P094FaultMode.TOOL_SELECTION,
            run_id="",
        )


def test_environment_has_no_external_runtime_or_prediction_shortcut():
    source = Path(
        "environments/agent/"
        "p09_4_multistep_incident.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "import random",
        "from random",
        "import socket",
        "from socket",
        "import subprocess",
        "from subprocess",
        "import requests",
        "import httpx",
        "time.time",
        "datetime.now",
        "predicted_verdicts",
        "hidden_fault",
        "case_to_verdict",
    )

    for token in forbidden:
        assert token not in source
