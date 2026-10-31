from dataclasses import FrozenInstanceError
from functools import partial
import json

import pytest

from environments.support.faults import (
    IdentifierMappingSwap,
    inject_fault,
)
from environments.support.fixtures import SupportEnvironment
from environments.support.tools import (
    READ_ONLY_TOOLS,
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
    lookup_account,
    read_ticket,
    route_ticket,
)
from packages.action_gateway import (
    AllowAllPolicy,
    AllowListPolicy,
    GatedTool,
    StageStatus,
    ToolGateway,
    to_agent_trace,
)
from packages.contracts import ContractError


SEED_STATE_SHA256 = (
    "5c8e1bc9bf26ec05ca4d27582e061592545e2758da893e1fab38f2b3eee5c82b"
)

FAULT_MARKERS = (
    "fault",
    "swap",
    "identifier_mapping",
    "inject",
)


def _observations(environment: SupportEnvironment) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []

    for ticket_id in environment.ticket_ids():
        ticket = read_ticket(environment, ticket_id=ticket_id)
        observations.append(ticket)
        observations.append(
            lookup_account(environment, account_id=ticket["account_id"])
        )

    return observations


def _support_gateway(environment: SupportEnvironment, policy=None) -> ToolGateway:
    return ToolGateway(
        tools=[
            GatedTool(
                name,
                partial(function, environment),
                SUPPORT_TOOL_SCHEMAS[name],
                SUPPORT_TOOL_DESCRIPTIONS[name],
            )
            for name, function in SUPPORT_TOOLS.items()
        ],
        policy=policy or AllowAllPolicy(),
        state_sha256=environment.state_sha256,
    )


def _gateway_session(environment: SupportEnvironment) -> ToolGateway:
    """Allowed, denied and failed calls through the gateway."""
    gateway = _support_gateway(
        environment, policy=AllowListPolicy({"read_ticket", "lookup_account"})
    )

    for ticket_id in environment.ticket_ids():
        ticket = gateway.invoke("read_ticket", {"ticket_id": ticket_id})
        gateway.invoke(
            "lookup_account", {"account_id": ticket.observation["account_id"]}
        )

    gateway.invoke("read_ticket", {"ticket_id": "T-9999"})
    gateway.invoke("route_ticket", {"ticket_id": "T-1001", "queue_id": "Q-GENERAL"})
    return gateway


# Fixtures and reset


def test_seed_state_hash_is_pinned():
    assert SupportEnvironment().state_sha256() == SEED_STATE_SHA256


def test_independent_environments_share_the_seed_state():
    first = SupportEnvironment()
    second = SupportEnvironment()

    assert first.snapshot() == second.snapshot()
    assert first.state_sha256() == second.state_sha256()


def test_seed_contents_are_synthetic_and_consistent():
    environment = SupportEnvironment()

    assert environment.ticket_ids() == (
        "T-1001", "T-1002", "T-1003", "T-1004", "T-1005",
    )
    assert environment.queue_ids() == ("Q-GENERAL", "Q-PRIORITY", "Q-TRIAGE")

    for customer_ref in environment.customer_refs():
        account = environment.get_account(
            environment.resolve_customer(customer_ref)
        )
        assert account.customer_ref == customer_ref

    for ticket_id in environment.ticket_ids():
        ticket = environment.get_ticket(ticket_id)
        assert ticket.queue_id is None
        assert ticket.status == "open"

    for queue_id in environment.queue_ids():
        assert environment.get_queue(queue_id).ticket_ids == ()


def test_reset_restores_seed_after_routing():
    environment = SupportEnvironment()

    route_ticket(environment, ticket_id="T-1001", queue_id="Q-PRIORITY")
    route_ticket(environment, ticket_id="T-1002", queue_id="Q-GENERAL")
    assert environment.state_sha256() != SEED_STATE_SHA256

    environment.reset()

    assert environment.state_sha256() == SEED_STATE_SHA256


def test_reset_removes_injected_fault():
    environment = SupportEnvironment()
    inject_fault(environment, IdentifierMappingSwap("C-3101", "C-3102"))
    assert environment.state_sha256() != SEED_STATE_SHA256

    environment.reset()

    assert environment.state_sha256() == SEED_STATE_SHA256
    assert environment.resolve_customer("C-3101") == "A-2001"


def test_records_are_immutable_and_snapshots_do_not_alias_state():
    environment = SupportEnvironment()
    ticket = environment.get_ticket("T-1001")

    with pytest.raises(FrozenInstanceError):
        ticket.queue_id = "Q-PRIORITY"  # type: ignore[misc]

    snapshot = environment.snapshot()
    snapshot["tickets"][0]["status"] = "routed"  # type: ignore[index]
    snapshot["customer_directory"]["C-3101"] = "A-2002"  # type: ignore[index]

    assert environment.state_sha256() == SEED_STATE_SHA256


@pytest.mark.parametrize(
    ("getter", "value"),
    [
        ("get_ticket", "T-9999"),
        ("get_account", "A-9999"),
        ("get_queue", "Q-MISSING"),
        ("resolve_customer", "C-9999"),
        ("get_ticket", "ticket-1"),
        ("get_account", ""),
        ("get_queue", 7),
    ],
)
def test_unknown_or_malformed_identifiers_are_rejected(getter, value):
    with pytest.raises(ContractError):
        getattr(SupportEnvironment(), getter)(value)


# Plain tools


def test_tool_registry_matches_schemas_and_descriptions():
    assert set(SUPPORT_TOOLS) == {"read_ticket", "lookup_account", "route_ticket"}
    assert set(SUPPORT_TOOL_SCHEMAS) == set(SUPPORT_TOOLS)
    assert set(SUPPORT_TOOL_DESCRIPTIONS) == set(SUPPORT_TOOLS)
    assert READ_ONLY_TOOLS == {"read_ticket", "lookup_account"}

    for name, schema in SUPPORT_TOOL_SCHEMAS.items():
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"]), name


def test_read_ticket_resolves_account_through_directory():
    observation = read_ticket(SupportEnvironment(), ticket_id="T-1003")

    assert observation == {
        "ticket_id": "T-1003",
        "customer_ref": "C-3103",
        "account_id": "A-2003",
        "subject": "API rate limit questions",
        "body": "Asking whether the API rate limit can be raised.",
        "priority": "normal",
        "queue_id": None,
        "status": "open",
    }


def test_lookup_account_reports_its_own_customer_ref():
    observation = lookup_account(SupportEnvironment(), account_id="A-2003")

    assert observation == {
        "account_id": "A-2003",
        "customer_ref": "C-3103",
        "display_name": "Copperleaf Sample Inc",
        "tier": "enterprise",
        "region": "us",
    }


def test_read_only_tools_do_not_change_state():
    environment = SupportEnvironment()

    _observations(environment)

    assert environment.state_sha256() == SEED_STATE_SHA256


def test_route_ticket_moves_ticket_and_updates_queue_membership():
    environment = SupportEnvironment()

    first = route_ticket(environment, ticket_id="T-1004", queue_id="Q-TRIAGE")
    assert first == {
        "ticket_id": "T-1004",
        "queue_id": "Q-TRIAGE",
        "previous_queue_id": None,
        "status": "routed",
    }
    after_first = environment.state_sha256()
    assert after_first != SEED_STATE_SHA256

    second = route_ticket(environment, ticket_id="T-1004", queue_id="Q-GENERAL")
    assert second["previous_queue_id"] == "Q-TRIAGE"
    assert environment.get_queue("Q-TRIAGE").ticket_ids == ()
    assert environment.get_queue("Q-GENERAL").ticket_ids == ("T-1004",)
    assert environment.get_ticket("T-1004").queue_id == "Q-GENERAL"
    assert environment.state_sha256() not in (SEED_STATE_SHA256, after_first)


def test_rerouting_to_the_same_queue_is_idempotent():
    environment = SupportEnvironment()
    route_ticket(environment, ticket_id="T-1001", queue_id="Q-PRIORITY")
    before = environment.state_sha256()

    result = route_ticket(environment, ticket_id="T-1001", queue_id="Q-PRIORITY")

    assert result["previous_queue_id"] == "Q-PRIORITY"
    assert environment.get_queue("Q-PRIORITY").ticket_ids == ("T-1001",)
    assert environment.state_sha256() == before


def test_failed_route_leaves_state_unchanged():
    environment = SupportEnvironment()

    with pytest.raises(ContractError):
        route_ticket(environment, ticket_id="T-1001", queue_id="Q-MISSING")
    with pytest.raises(ContractError):
        route_ticket(environment, ticket_id="T-9999", queue_id="Q-GENERAL")

    assert environment.state_sha256() == SEED_STATE_SHA256


def test_observations_are_json_serializable():
    environment = SupportEnvironment()
    observations = _observations(environment) + [
        route_ticket(environment, ticket_id="T-1002", queue_id="Q-GENERAL")
    ]

    for observation in observations:
        assert json.loads(json.dumps(observation)) == observation


# Fault injection


def test_swap_changes_resolution_for_affected_tickets_only():
    clean = SupportEnvironment()
    faulty = SupportEnvironment()
    inject_fault(faulty, IdentifierMappingSwap("C-3101", "C-3102"))

    for ticket_id in clean.ticket_ids():
        clean_ticket = read_ticket(clean, ticket_id=ticket_id)
        faulty_ticket = read_ticket(faulty, ticket_id=ticket_id)
        affected = clean_ticket["customer_ref"] in ("C-3101", "C-3102")

        assert (clean_ticket != faulty_ticket) is affected
        assert {
            key: value
            for key, value in faulty_ticket.items()
            if key != "account_id"
        } == {
            key: value
            for key, value in clean_ticket.items()
            if key != "account_id"
        }

    assert read_ticket(faulty, ticket_id="T-1001")["account_id"] == "A-2002"
    assert read_ticket(faulty, ticket_id="T-1005")["account_id"] == "A-2002"
    assert read_ticket(faulty, ticket_id="T-1002")["account_id"] == "A-2001"


def test_fault_is_observable_only_as_an_evidence_inconsistency():
    environment = SupportEnvironment()
    inject_fault(environment, IdentifierMappingSwap("C-3103", "C-3104"))

    ticket = read_ticket(environment, ticket_id="T-1003")
    account = lookup_account(environment, account_id=ticket["account_id"])

    assert ticket["customer_ref"] == "C-3103"
    assert account["customer_ref"] == "C-3104"
    assert account["tier"] == "standard"


def test_fault_leaves_no_marker_in_environment_or_observations():
    environment = SupportEnvironment()
    attributes_before = set(vars(environment))

    inject_fault(environment, IdentifierMappingSwap("C-3101", "C-3102"))

    assert set(vars(environment)) == attributes_before

    gateway = _gateway_session(environment)
    trace = to_agent_trace("run-0001", gateway.records)

    surfaces = json.dumps(
        {
            "snapshot": environment.snapshot(),
            "observations": _observations(environment),
            "route": route_ticket(
                environment, ticket_id="T-1001", queue_id="Q-GENERAL"
            ),
            "stage_records": [
                record.canonical_payload() for record in gateway.records
            ],
            "trace": trace.canonical_payload(),
        }
    ).lower()

    assert {record.status for record in gateway.records} == {
        StageStatus.PROPOSED,
        StageStatus.ALLOWED,
        StageStatus.DENIED,
        StageStatus.STARTED,
        StageStatus.SUCCEEDED,
        StageStatus.FAILED,
    }

    for marker in FAULT_MARKERS:
        assert marker not in surfaces, marker


def test_fault_does_not_change_tickets_accounts_or_queues():
    clean = SupportEnvironment().snapshot()
    environment = SupportEnvironment()
    inject_fault(environment, IdentifierMappingSwap("C-3101", "C-3104"))
    faulty = environment.snapshot()

    for key in ("tickets", "accounts", "queues"):
        assert faulty[key] == clean[key]
    assert faulty["customer_directory"] != clean["customer_directory"]


@pytest.mark.parametrize(
    "refs",
    [
        ("C-3101", "C-3101"),
        ("C-3101", "C-9999"),
        ("C-9999", "C-3102"),
        ("bad", "C-3102"),
    ],
)
def test_invalid_faults_are_rejected_without_state_change(refs):
    environment = SupportEnvironment()

    with pytest.raises(ContractError):
        inject_fault(environment, IdentifierMappingSwap(*refs))

    assert environment.state_sha256() == SEED_STATE_SHA256


def test_injection_requires_a_support_environment_and_known_fault():
    with pytest.raises(ContractError):
        inject_fault(object(), IdentifierMappingSwap("C-3101", "C-3102"))  # type: ignore[arg-type]
    with pytest.raises(ContractError):
        inject_fault(SupportEnvironment(), object())  # type: ignore[arg-type]


# Support tools through the generic gateway


def test_unknown_ticket_becomes_failed_observation_with_unchanged_state():
    environment = SupportEnvironment()

    result = _support_gateway(environment).invoke(
        "read_ticket", {"ticket_id": "T-9999"}
    )

    assert result.status is StageStatus.FAILED
    assert result.error == {"type": "ContractError", "message": "unknown ticket_id"}
    observed = result.records[-1]
    assert observed.state_before_sha256 == observed.state_after_sha256
    assert environment.state_sha256() == SEED_STATE_SHA256


def test_denied_route_leaves_state_unchanged():
    environment = SupportEnvironment()
    gateway = _support_gateway(
        environment, policy=AllowListPolicy({"read_ticket", "lookup_account"})
    )

    result = gateway.invoke(
        "route_ticket", {"ticket_id": "T-1001", "queue_id": "Q-PRIORITY"}
    )

    assert result.status is StageStatus.DENIED
    assert [record.stage.value for record in result.records] == [
        "proposed", "authorized",
    ]
    assert environment.state_sha256() == SEED_STATE_SHA256
    assert environment.get_ticket("T-1001").queue_id is None


def test_allowed_route_records_the_state_change():
    environment = SupportEnvironment()

    result = _support_gateway(environment).invoke(
        "route_ticket", {"ticket_id": "T-1001", "queue_id": "Q-PRIORITY"}
    )

    observed = result.records[-1]
    assert result.status is StageStatus.SUCCEEDED
    assert observed.state_before_sha256 == SEED_STATE_SHA256
    assert observed.state_after_sha256 == environment.state_sha256() != SEED_STATE_SHA256


def test_schema_invalid_support_arguments_are_denied():
    environment = SupportEnvironment()

    result = _support_gateway(environment).invoke(
        "read_ticket", {"ticket_id": "ticket-1"}
    )

    assert result.status is StageStatus.DENIED
    assert result.records[-1].payload["reason"] == "arguments_schema_invalid"


# Maintenance tools (never given to the agent)


def test_maintenance_tools_are_separate_from_agent_tools():
    from environments.support.tools import (
        DIAGNOSTIC_TOOLS,
        MAINTENANCE_TOOL_DESCRIPTIONS,
        MAINTENANCE_TOOL_SCHEMAS,
        RECOVERY_TOOLS,
    )

    assert set(DIAGNOSTIC_TOOLS) == {"resolve_customer_ref", "find_accounts_by_customer_ref"}
    assert set(RECOVERY_TOOLS) == {"set_customer_mapping"}
    assert set(MAINTENANCE_TOOL_SCHEMAS) == set(DIAGNOSTIC_TOOLS) | set(RECOVERY_TOOLS)
    assert set(MAINTENANCE_TOOL_DESCRIPTIONS) == set(MAINTENANCE_TOOL_SCHEMAS)
    assert set(SUPPORT_TOOLS).isdisjoint(MAINTENANCE_TOOL_SCHEMAS)


def test_diagnostic_tools_are_read_only_and_report_directory_and_owners():
    from environments.support.tools import find_accounts_by_customer_ref, resolve_customer_ref

    environment = SupportEnvironment()
    inject_fault(environment, IdentifierMappingSwap("C-3103", "C-3104"))
    before = environment.state_sha256()

    assert resolve_customer_ref(environment, customer_ref="C-3103") == {
        "customer_ref": "C-3103", "account_id": "A-2004",
    }
    assert find_accounts_by_customer_ref(environment, customer_ref="C-3103") == {
        "customer_ref": "C-3103", "account_ids": ["A-2003"],
    }
    assert environment.state_sha256() == before

    with pytest.raises(ContractError):
        find_accounts_by_customer_ref(environment, customer_ref="C-9999")


def test_set_customer_mapping_reports_the_previous_value():
    from environments.support.tools import set_customer_mapping

    environment = SupportEnvironment()

    assert set_customer_mapping(environment, customer_ref="C-3101", account_id="A-2002") == {
        "customer_ref": "C-3101", "account_id": "A-2002", "previous_account_id": "A-2001",
    }
    assert environment.resolve_customer("C-3101") == "A-2002"

    with pytest.raises(ContractError):
        set_customer_mapping(environment, customer_ref="C-3101", account_id="A-9999")


def test_maintenance_outputs_carry_no_fault_marker():
    from environments.support.tools import (
        find_accounts_by_customer_ref,
        resolve_customer_ref,
        set_customer_mapping,
    )

    environment = SupportEnvironment()
    inject_fault(environment, IdentifierMappingSwap("C-3103", "C-3104"))
    outputs = json.dumps(
        [
            resolve_customer_ref(environment, customer_ref="C-3103"),
            find_accounts_by_customer_ref(environment, customer_ref="C-3104"),
            set_customer_mapping(environment, customer_ref="C-3103", account_id="A-2003"),
        ]
    ).lower()

    for marker in FAULT_MARKERS:
        assert marker not in outputs, marker
