from functools import partial

import pytest

from environments.support.faults import IdentifierMappingSwap, inject_fault
from environments.support.fixtures import SupportEnvironment
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
    read_ticket,
)
from packages.action_gateway import (
    AllowListPolicy,
    GatedTool,
    ToolGateway,
    to_agent_trace,
)
from packages.contracts import ContractError
from packages.integrations.run_ids import RunIdAllocator
from packages.support_evaluator import (
    EVALUATOR_FIELD_NAMES,
    EXAMPLES,
    FAULTS,
    NEUTRAL_FILE_NAME,
    NEUTRAL_RUN_ID,
    RunRegistry,
    SupportVerdict,
    answer_pairs,
    assert_no_leaks,
    fault,
    scan_agent_outputs,
    scan_content,
    scan_identifiers,
    sensitive_tokens,
)


AGENT_TOOLS = ("read_ticket", "lookup_account", "route_ticket")


def _environment_fault(fault_id: str) -> IdentifierMappingSwap:
    definition = fault(fault_id)
    assert definition.fault_type == "identifier_mapping_swap"
    return IdentifierMappingSwap(**definition.parameters)


def _gateway(environment: SupportEnvironment) -> ToolGateway:
    return ToolGateway(
        tools=[
            GatedTool(
                name,
                partial(SUPPORT_TOOLS[name], environment),
                SUPPORT_TOOL_SCHEMAS[name],
                SUPPORT_TOOL_DESCRIPTIONS[name],
            )
            for name in AGENT_TOOLS
        ],
        policy=AllowListPolicy(AGENT_TOOLS),
        state_sha256=environment.state_sha256,
    )


def _example_surfaces(example_name: str, run_id: str) -> dict[str, object]:
    """Everything visible after a scripted session for one example."""
    spec = EXAMPLES[example_name]
    environment = SupportEnvironment()

    if spec.fault_id is not None:
        inject_fault(environment, _environment_fault(spec.fault_id))

    gateway = _gateway(environment)
    ticket = gateway.invoke("read_ticket", {"ticket_id": spec.target_ticket_id})
    account = gateway.invoke(
        "lookup_account", {"account_id": ticket.observation["account_id"]}
    )
    queue_id = (
        "Q-PRIORITY" if account.observation["tier"] == "enterprise" else "Q-GENERAL"
    )
    route = gateway.invoke(
        "route_ticket", {"ticket_id": spec.target_ticket_id, "queue_id": queue_id}
    )
    gateway.invoke("read_ticket", {"ticket_id": "T-9999"})

    return {
        "run_id": run_id,
        "tool_definitions": list(gateway.tool_definitions()),
        "tool_outputs": [
            result.observation for result in (ticket, account, route)
        ],
        "stage_records": [record.canonical_payload() for record in gateway.records],
        "trace": to_agent_trace(run_id, gateway.records).canonical_payload(),
    }


# Catalog consistency with the environment


def test_catalog_examples_are_consistent_with_the_environment():
    environment = SupportEnvironment()

    assert set(EXAMPLES) == {"example_correct_run", "example_verified_recovery", "example_insufficient_evidence"}

    for spec in EXAMPLES.values():
        ticket = read_ticket(environment, ticket_id=spec.target_ticket_id)
        assert ticket["account_id"] == spec.expected_account_id
        assert spec.expected_queue_id in environment.queue_ids()

        for ticket_id, queue_id in spec.regression_expectations.items():
            assert ticket_id in environment.ticket_ids()
            assert queue_id in environment.queue_ids()


def test_example_faults_affect_the_target_but_not_regression_tickets():
    for spec in EXAMPLES.values():
        if spec.fault_id is None:
            continue

        clean = SupportEnvironment()
        faulty = SupportEnvironment()
        inject_fault(faulty, _environment_fault(spec.fault_id))

        def resolved(environment, ticket_id):
            return read_ticket(environment, ticket_id=ticket_id)["account_id"]

        assert resolved(faulty, spec.target_ticket_id) != spec.expected_account_id

        for ticket_id in spec.regression_expectations:
            assert resolved(faulty, ticket_id) == resolved(clean, ticket_id)


def test_catalog_fault_payload_matches_environment_payload():
    for fault_id, definition in FAULTS.items():
        assert (
            _environment_fault(fault_id).canonical_payload()
            == definition.fault_payload()
        )


def test_every_example_has_a_distinct_expected_verdict():
    verdicts = [spec.expected_verdict for spec in EXAMPLES.values()]

    assert len(set(verdicts)) == len(verdicts)
    assert set(verdicts) <= set(SupportVerdict)


# Registry and neutral run IDs


def test_run_id_allocator_is_sequential_and_neutral():
    allocator = RunIdAllocator()
    run_ids = [allocator.allocate() for _ in range(3)]

    assert run_ids == ["run-0001", "run-0002", "run-0003"]
    assert_no_leaks(scan_identifiers("run_ids", run_ids, NEUTRAL_RUN_ID))


def test_registry_binds_neutral_run_ids_to_examples():
    allocator = RunIdAllocator()
    registry = RunRegistry()

    correct = registry.register(
        run_id=allocator.allocate(), example_name="example_correct_run", fault_payload=None,
    )
    recovery = registry.register(
        run_id=allocator.allocate(),
        example_name="example_verified_recovery",
        fault_payload=_environment_fault("SUP-F-001").canonical_payload(),
    )

    assert (correct.run_id, correct.fault_id) == ("run-0001", None)
    assert (recovery.run_id, recovery.fault_id) == ("run-0002", "SUP-F-001")
    assert registry.lookup("run-0002").spec.example_name == "example_verified_recovery"
    assert registry.run_ids() == ("run-0001", "run-0002")


@pytest.mark.parametrize(
    ("run_id", "example_name", "fault_payload"),
    [
        ("run-verified-1", "example_verified_recovery", None),
        ("verified_recovery-0001", "example_verified_recovery", None),
        ("run-0001", "unknown_example", None),
        ("run-0001", "example_correct_run", {"fault_type": "identifier_mapping_swap"}),
        ("run-0001", "example_verified_recovery", None),
        (
            "run-0001",
            "example_verified_recovery",
            {
                "fault_type": "identifier_mapping_swap",
                "customer_ref_a": "C-3101",
                "customer_ref_b": "C-3102",
            },
        ),
    ],
)
def test_registry_rejects_invalid_registrations(run_id, example_name, fault_payload):
    with pytest.raises(ContractError):
        RunRegistry().register(
            run_id=run_id, example_name=example_name, fault_payload=fault_payload,
        )


def test_registry_rejects_duplicates_and_unknown_lookups():
    registry = RunRegistry()
    registry.register(run_id="run-0001", example_name="example_correct_run", fault_payload=None)

    with pytest.raises(ContractError):
        registry.register(
            run_id="run-0001", example_name="example_correct_run", fault_payload=None,
        )
    with pytest.raises(ContractError):
        registry.lookup("run-0002")


# Real surfaces are clean


@pytest.mark.parametrize("example_name", sorted(EXAMPLES))
def test_visible_surfaces_contain_no_evaluator_content(example_name):
    surfaces = _example_surfaces(example_name, "run-0001")

    assert_no_leaks(scan_content(surfaces))
    assert_no_leaks(scan_identifiers("run_id", [surfaces["run_id"]], NEUTRAL_RUN_ID))


def test_environment_and_tool_definitions_are_clean():
    environment = SupportEnvironment()

    assert_no_leaks(
        scan_content(
            {
                "snapshot": environment.snapshot(),
                "tool_descriptions": SUPPORT_TOOL_DESCRIPTIONS,
                "tool_schemas": SUPPORT_TOOL_SCHEMAS,
            }
        )
    )


def test_ordinary_observations_are_not_false_positives():
    findings = scan_content(
        {
            "route": {"ticket_id": "T-1003", "queue_id": "Q-PRIORITY"},
            "account": {"account_id": "A-2003", "tier": "enterprise"},
            "queues": ["Q-PRIORITY", "Q-GENERAL"],
            "policy": "Enterprise accounts go to Q-PRIORITY; standard to Q-GENERAL.",
        }
    )

    assert findings == ()


# Planted leaks are caught


def _kinds(findings) -> set[str]:
    return {finding.kind for finding in findings}


@pytest.mark.parametrize(
    ("surface", "expected_kind"),
    [
        ({"stage_records": [{"payload": {"note": "SUP-F-001"}}]}, "sensitive_token"),
        ({"prompt": "This run is the example_verified_recovery case."}, "sensitive_token"),
        ({"trace": {"events": [{"operation": "recovery_verified"}]}}, "sensitive_token"),
        ({"tool_output": {"detail": "identifier_mapping_swap active"}}, "sensitive_token"),
        ({"run_record": {"expected_queue_id": "Q-GENERAL"}}, "evaluator_field_name"),
        ({"run_record": {"Fault_ID": None}}, "evaluator_field_name"),
        ({"prompt": "Route T-1003 to Q-PRIORITY."}, "answer_pair"),
        ({"prompt": "T-1003 belongs to A-2003"}, "answer_pair"),
        ({"diagnosis_input": {"hints": {"T-1003": "Q-PRIORITY"}}}, "answer_mapping"),
        ({"diagnosis_input": {"T-1002": "Q-GENERAL"}}, "answer_mapping"),
    ],
)
def test_planted_content_leaks_are_caught(surface, expected_kind):
    findings = scan_content(surface)

    assert expected_kind in _kinds(findings)
    with pytest.raises(AssertionError, match="evaluator-only content leaked"):
        assert_no_leaks(findings)


def test_planted_leak_inside_real_stage_records_is_caught():
    surfaces = _example_surfaces("example_verified_recovery", "run-0001")
    surfaces["stage_records"][2]["payload"] = {"note": "fault SUP-F-001"}

    findings = scan_content(surfaces)

    assert [(f.surface, f.path, f.kind) for f in findings] == [
        ("stage_records", "[2].payload.note", "sensitive_token"),
    ]


@pytest.mark.parametrize(
    ("surface", "identifier", "pattern"),
    [
        ("run_id", "run-example_verified_recovery", NEUTRAL_RUN_ID),
        ("run_id", "run-0001-example_correct_run", NEUTRAL_RUN_ID),
        ("run_id", "example_insufficient_evidence", NEUTRAL_RUN_ID),
        ("file_name", "example_correct_run.json", NEUTRAL_FILE_NAME),
        ("file_name", "capture-0001-SUP-F-001.json", NEUTRAL_FILE_NAME),
        ("file_name", "T-1003-Q-PRIORITY.json", NEUTRAL_FILE_NAME),
    ],
)
def test_planted_identifier_leaks_are_caught(surface, identifier, pattern):
    findings = scan_identifiers(surface, [identifier], pattern)

    assert "non_neutral_identifier" in _kinds(findings)


def test_neutral_identifiers_pass():
    assert_no_leaks(scan_identifiers("run_ids", ["run-0001", "run-0042"], NEUTRAL_RUN_ID))
    assert_no_leaks(
        scan_identifiers("files", ["capture-0001.json", "run-0007.json"], NEUTRAL_FILE_NAME)
    )


def test_scanner_refuses_values_it_cannot_inspect():
    with pytest.raises(TypeError):
        scan_content({"surface": {"value": object()}})
    with pytest.raises(TypeError):
        scan_content({"surface": {1: "non-string key"}})


def test_sensitive_tokens_cover_the_whole_answer_key():
    tokens = sensitive_tokens()

    assert EVALUATOR_FIELD_NAMES <= tokens
    assert set(EXAMPLES) <= tokens
    assert set(FAULTS) <= tokens
    assert {verdict.value for verdict in SupportVerdict} <= tokens
    assert ("T-1003", "Q-PRIORITY") in answer_pairs()
    assert ("T-1002", "Q-GENERAL") in answer_pairs()


# Scope: the agent's own outputs


def test_agent_outputs_may_name_their_decisions():
    outputs = {
        "tool_call_arguments": [{"ticket_id": "T-1003", "queue_id": "Q-PRIORITY"}],
        "final_message": "Routed T-1003 to Q-PRIORITY for account A-2003.",
    }

    assert_no_leaks(scan_agent_outputs(outputs))
    assert "answer_pair" in _kinds(scan_content(outputs))


@pytest.mark.parametrize(
    ("outputs", "expected_kind"),
    [
        ({"final_message": "Fixed the SUP-F-001 issue."}, "sensitive_token"),
        ({"final_message": "Outcome: recovery_verified"}, "sensitive_token"),
        ({"tool_call_arguments": [{"expected_queue_id": "Q-PRIORITY"}]}, "evaluator_field_name"),
    ],
)
def test_agent_outputs_still_fail_field_name_and_token_checks(outputs, expected_kind):
    assert expected_kind in _kinds(scan_agent_outputs(outputs))
