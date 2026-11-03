import json

import pytest
from jsonschema import Draft202012Validator

from packages.action_gateway import GatedTool, StageStatus
from packages.action_space import (
    DECISION_VERBS,
    PROBE_BUDGET,
    PROBE_VERBS,
    RECOVERY_VERBS,
    VERBS,
    WORLD_RECOVERY_VERBS,
    Action,
    parse_action,
    probe_gateway,
    recovery_gateway,
)
from packages.contracts import ContractError, canonical_sha256


def test_catalog_has_the_agreed_verbs():
    assert set(PROBE_VERBS) == {
        "inspect", "resolve", "find_owners", "compare_with_source", "history", "retry",
    }
    assert set(RECOVERY_VERBS) == {"set_mapping", "restore_from_source", "reroute", "rerun"}
    assert set(WORLD_RECOVERY_VERBS) == set(RECOVERY_VERBS) - {"rerun"}
    assert set(DECISION_VERBS) == {"no_intervention", "insufficient_evidence", "abstain"}
    assert PROBE_BUDGET == 4


def test_every_schema_is_valid_and_closed():
    for spec in VERBS.values():
        Draft202012Validator.check_schema(spec.args_schema)
        variants = spec.args_schema.get("oneOf", [spec.args_schema])
        assert all(variant["additionalProperties"] is False for variant in variants), spec.name


def test_restore_from_source_applies_to_accounts_only():
    Action("recover", "restore_from_source", {"entity": "account", "id": "A-1234"})

    for entity, identifier in (("queue", "Q-MAIN"), ("ticket", "T-1234")):
        with pytest.raises(ContractError, match="schema"):
            Action("recover", "restore_from_source", {"entity": entity, "id": identifier})


def test_retry_applies_to_read_tools_only():
    Action("probe", "retry", {"tool": "read_ticket", "target": "T-1234"})
    Action("probe", "retry", {"tool": "lookup_account", "target": "A-1234"})

    for args in (
        {"tool": "route_ticket", "target": "T-1234"},
        {"tool": "lookup_account", "target": "T-1234"},
    ):
        with pytest.raises(ContractError):
            Action("probe", "retry", args)


@pytest.mark.parametrize(
    "action",
    [
        {"action": "probe", "verb": "inspect", "args": {"entity": "ticket", "id": "T-1234"}},
        {"action": "probe", "verb": "inspect", "args": {"entity": "routing_policy"}},
        {"action": "probe", "verb": "find_owners", "args": {"customer_ref": "C-1234"}},
        {"action": "recover", "verb": "set_mapping", "args": {"customer_ref": "C-1234", "account_id": "A-1234"}},
        {"action": "recover", "verb": "rerun", "args": {}},
        {"action": "decide", "verb": "insufficient_evidence", "args": {"missing": ["account_observation"]}},
        {"action": "decide", "verb": "abstain", "args": {"reason": "no_recovery_available"}},
        {"action": "decide", "verb": "no_intervention", "args": {}},
    ],
)
def test_valid_actions_parse_and_round_trip(action):
    parsed = parse_action(json.dumps(action))

    assert parsed.canonical_payload() == action
    assert parse_action(parsed.canonical_payload()) == parsed
    assert parsed.action_sha256 == canonical_sha256(action)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("not json", "valid JSON"),
        ({"action": "probe", "verb": "inspect"}, "exactly"),
        ({"action": "probe", "verb": "inspect", "args": {}, "extra": 1}, "exactly"),
        ({"action": "act", "verb": "inspect", "args": {}}, "kind"),
        ({"action": "probe", "verb": "delete_ticket", "args": {}}, "unknown verb"),
        ({"action": "probe", "verb": "set_mapping", "args": {"customer_ref": "C-1234", "account_id": "A-1234"}}, "kind"),
        ({"action": "probe", "verb": "inspect", "args": {"entity": "ticket", "id": "A-1234"}}, "schema"),
        ({"action": "probe", "verb": "resolve", "args": {"customer_ref": "C-1234", "note": "x"}}, "schema"),
        ({"action": "decide", "verb": "insufficient_evidence", "args": {"missing": []}}, "schema"),
        ({"action": "decide", "verb": "abstain", "args": {"reason": "Free text reason"}}, "schema"),
    ],
)
def test_invalid_actions_are_rejected(value, message):
    with pytest.raises(ContractError, match=message):
        parse_action(value)


# Permission scopes


class World:
    def __init__(self) -> None:
        self.value = 0

    def state(self) -> str:
        return canonical_sha256({"value": self.value})


def _tools(world):
    def probe(**kwargs):
        return {"value": world.value}

    def write(**kwargs):
        world.value += 1
        return {"value": world.value}

    return [
        GatedTool(name, probe if name in PROBE_VERBS else write, VERBS[name].args_schema, VERBS[name].description)
        for name in (*PROBE_VERBS, *WORLD_RECOVERY_VERBS)
    ]


def test_probe_gateway_allows_probes_only():
    world = World()
    gateway = probe_gateway([t for t in _tools(world) if t.name in PROBE_VERBS], world.state)

    assert gateway.invoke("resolve", {"customer_ref": "C-1234"}).status is StageStatus.SUCCEEDED
    assert gateway.invoke("set_mapping", {"customer_ref": "C-1234", "account_id": "A-1234"}).status is StageStatus.DENIED

    # Write tools passed alongside are never registered on a probe gateway.
    mixed = probe_gateway(_tools(world), world.state)
    assert set(mixed.tool_names()) == set(PROBE_VERBS)
    assert mixed.invoke("reroute", {"ticket_id": "T-1234", "queue_id": "Q-MAIN"}).records[-1].payload["reason"] == "unknown_tool"
    assert world.value == 0

    with pytest.raises(ContractError, match="exactly"):
        probe_gateway([t for t in _tools(world) if t.name != "retry"], world.state)


def test_recovery_gateway_allows_exactly_the_proposed_call():
    world = World()
    action = Action("recover", "set_mapping", {"customer_ref": "C-1234", "account_id": "A-1234"})
    gateway = recovery_gateway(_tools(world), world.state, action)

    other = gateway.invoke("set_mapping", {"customer_ref": "C-1234", "account_id": "A-9999"})
    assert other.records[-1].payload["reason"] == "call_outside_scope"
    assert gateway.invoke("set_mapping", action.args).status is StageStatus.SUCCEEDED
    assert world.value == 1
    assert gateway.tool_names() == ("set_mapping",)


def test_recovery_gateway_refuses_non_world_actions():
    world = World()

    for action in (
        Action("recover", "rerun", {}),
        Action("probe", "resolve", {"customer_ref": "C-1234"}),
        Action("decide", "no_intervention", {}),
    ):
        with pytest.raises(ContractError, match="world recovery"):
            recovery_gateway(_tools(world), world.state, action)
