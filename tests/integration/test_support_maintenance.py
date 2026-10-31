"""Generic verbs against injected worlds, permission scopes, and sandboxes."""

from functools import partial
import json
import random
import socket

import pytest

from environments.support.fixtures import SupportEnvironment, ToolUnavailableError
from environments.support.generator import generate_world
from environments.support.maintenance import MAINTENANCE_VERB_TOOLS
from environments.support.tools import lookup_account, read_ticket
from packages.action_gateway import GatedTool, StageStatus
from packages.action_space import (
    PROBE_VERBS,
    VERBS,
    WORLD_RECOVERY_VERBS,
    Action,
    probe_gateway,
    recovery_gateway,
)
from packages.support_evaluator import assert_no_leaks, scan_case_content
from packages.support_evaluator.injectors import INJECTORS, inject


FAULT_MARKERS = (
    "fault", "swap", "identifier_mapping", "inject", "stale", "drift",
    "misconfig", "corrupt", "broken",
)
ALL_CASES = [(kind, variant) for kind, (_, variants) in INJECTORS.items() for variant in variants]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _tools(environment):
    return [
        GatedTool(verb, partial(function, environment), VERBS[verb].args_schema, VERBS[verb].description)
        for verb, function in MAINTENANCE_VERB_TOOLS.items()
    ]


def _case(kind, variant, seed=3):
    return inject(kind, generate_world(seed), random.Random(7), variant)


def _probe(environment, verb, **args):
    return probe_gateway(_tools(environment), environment.state_sha256).invoke(verb, args)


def _account_of(case):
    return next(
        account for account in case.spec.accounts
        if account.account_id == case.truth.expected_account_id
    )


def test_every_world_verb_has_a_tool():
    assert set(MAINTENANCE_VERB_TOOLS) == set(PROBE_VERBS) | set(WORLD_RECOVERY_VERBS)


# What each verb reveals in each family


def test_f1_resolve_and_find_owners_show_the_directory_disagreeing_with_owners():
    case = _case("mapping_swap", "swap")
    environment = SupportEnvironment(case.spec)
    owner = _account_of(case)

    resolved = _probe(environment, "resolve", customer_ref=owner.customer_ref).observation
    owners = _probe(environment, "find_owners", customer_ref=owner.customer_ref).observation

    assert resolved["account_id"] != owner.account_id
    assert owners["account_ids"] == [owner.account_id]


def test_merged_account_needs_inspect_or_history_to_tell_apart_from_f1():
    case = _case("merged_account", "default")
    environment = SupportEnvironment(case.spec)
    ticket = environment.get_ticket(case.truth.target_ticket_id)
    account_id = case.truth.expected_account_id

    assert _probe(environment, "resolve", customer_ref=ticket.customer_ref).observation["account_id"] == account_id
    assert _probe(environment, "find_owners", customer_ref=ticket.customer_ref).observation["account_ids"] == []
    record = _probe(environment, "inspect", entity="account", id=account_id).observation["record"]
    assert ticket.customer_ref in record["merged_customer_refs"]
    events = _probe(environment, "history", entity="account", id=account_id).observation["events"]
    assert [event["kind"] for event in events] == ["merged"]


def test_compare_with_source_shows_raw_values_for_f2_f7_and_the_recent_change():
    stale = _probe(SupportEnvironment(_case("stale_account_record", "default").spec), "compare_with_source",
                   entity="account", id=_case("stale_account_record", "default").truth.expected_account_id).observation
    assert stale["working"]["tier"] != stale["source"]["tier"]
    assert stale["working"]["version"] < stale["source"]["version"]

    drift_case = _case("tier_format_drift", "abbreviation")
    drift = _probe(SupportEnvironment(drift_case.spec), "compare_with_source",
                   entity="account", id=drift_case.truth.expected_account_id).observation
    assert drift["working"]["tier"] in ("ent", "std")
    assert drift["working"]["version"] == drift["source"]["version"]

    recent_case = _case("recent_tier_change", "default")
    recent = _probe(SupportEnvironment(recent_case.spec), "compare_with_source",
                    entity="account", id=recent_case.truth.expected_account_id).observation
    assert recent["working"] == recent["source"]

    for observation in (stale, drift, recent):
        assert set(observation) == {"account_id", "working", "source"}


def test_f5_probes_distinguish_unmapped_refs_from_deleted_accounts():
    unmapped = _case("missing_account", "unmapped_ref")
    env = SupportEnvironment(unmapped.spec)
    ref = _account_of(unmapped).customer_ref
    assert _probe(env, "resolve", customer_ref=ref).observation["account_id"] is None
    assert _probe(env, "find_owners", customer_ref=ref).observation["account_ids"] == [unmapped.truth.expected_account_id]

    deleted = _case("missing_account", "deleted_account")
    env = SupportEnvironment(deleted.spec)
    ref = env.get_ticket(deleted.truth.target_ticket_id).customer_ref
    assert _probe(env, "resolve", customer_ref=ref).observation["account_id"] is not None
    assert _probe(env, "find_owners", customer_ref=ref).observation["account_ids"] == []


def test_f6_inspect_shows_queue_config_disagreeing_with_the_policy():
    case = _case("queue_misconfiguration", "description_swap")
    environment = SupportEnvironment(case.spec)
    policy = _probe(environment, "inspect", entity="routing_policy").observation["record"]
    config = _probe(environment, "inspect", entity="queue", id=policy["enterprise"]).observation["record"]

    assert "enterprise-tier" not in config["description"]


# Retry probe and sandboxes


def _run_failed_lookup(environment, account_id):
    with pytest.raises(ToolUnavailableError):
        lookup_account(environment, account_id=account_id)


@pytest.mark.parametrize(("variant", "expected"), [("transient", "succeeded"), ("persistent", "failed")])
def test_retry_probe_tells_transient_from_persistent_errors(variant, expected):
    case = _case("mishandled_tool_error", variant)
    environment = SupportEnvironment(case.spec)
    rule = case.spec.tool_errors[0]
    call = {"read_ticket": read_ticket, "lookup_account": lookup_account}[rule.tool_name]
    argument = "ticket_id" if rule.tool_name == "read_ticket" else "account_id"

    with pytest.raises(ToolUnavailableError):
        call(environment, **{argument: rule.target})

    before = environment.state_sha256()
    result = _probe(environment, "retry", tool=rule.tool_name, target=rule.target)

    assert result.status is StageStatus.SUCCEEDED
    assert result.observation["status"] == expected
    assert environment.state_sha256() == before


def test_fork_copies_state_and_error_counters_independently():
    case = _case("mishandled_tool_error", "transient")
    environment = SupportEnvironment(case.spec)
    rule = case.spec.tool_errors[0]
    call = {"read_ticket": read_ticket, "lookup_account": lookup_account}[rule.tool_name]
    argument = "ticket_id" if rule.tool_name == "read_ticket" else "account_id"

    with pytest.raises(ToolUnavailableError):
        call(environment, **{argument: rule.target})

    sandbox = environment.fork()
    assert sandbox.state_sha256() == environment.state_sha256()
    assert sandbox.tool_error_calls() == environment.tool_error_calls() == (1,)

    call(sandbox, **{argument: rule.target})
    assert sandbox.tool_error_calls() == (2,)
    assert environment.tool_error_calls() == (1,)

    queue_id = case.spec.queues[0].queue_id
    sandbox.assign_ticket(case.truth.target_ticket_id, queue_id)
    assert sandbox.state_sha256() != environment.state_sha256()
    assert environment.get_ticket(case.truth.target_ticket_id).queue_id is None


def test_fork_without_counters_would_fail_the_retry():
    case = _case("mishandled_tool_error", "transient")
    environment = SupportEnvironment(case.spec)
    rule = case.spec.tool_errors[0]

    fresh = SupportEnvironment(case.spec)
    assert _probe(fresh, "retry", tool=rule.tool_name, target=rule.target).observation["status"] == "failed"
    assert environment.fork().tool_error_calls() == (0,)


# Recoveries through scoped gateways


def _recover(environment, verb, **args):
    action = Action("recover", verb, args)
    return recovery_gateway(_tools(environment), environment.state_sha256, action).invoke(verb, action.args)


def test_set_mapping_restores_swapped_and_unmapped_entries():
    swap = _case("mapping_swap", "swap")
    env = SupportEnvironment(swap.spec)
    for argument in swap.truth.remedy_if_wrong_arguments:
        assert _recover(env, "set_mapping", **argument).status is StageStatus.SUCCEEDED
    owner = _account_of(swap)
    assert env.resolve_customer(owner.customer_ref) == owner.account_id

    unmapped = _case("missing_account", "unmapped_ref")
    env = SupportEnvironment(unmapped.spec)
    (argument,) = unmapped.truth.remedy_if_wrong_arguments
    result = _recover(env, "set_mapping", **argument)
    assert result.observation["previous_account_id"] is None
    assert env.resolve_customer(argument["customer_ref"]) == argument["account_id"]


@pytest.mark.parametrize("kind_variant", [("stale_account_record", "default"), ("tier_format_drift", "whitespace")])
def test_restore_from_source_repairs_the_working_record(kind_variant):
    case = _case(*kind_variant)
    env = SupportEnvironment(case.spec)
    account_id = case.truth.expected_account_id

    result = _recover(env, "restore_from_source", entity="account", id=account_id)

    assert result.status is StageStatus.SUCCEEDED
    assert result.observation["after"] == {
        "tier": env.account_source(account_id).tier,
        "version": env.account_source(account_id).version,
        "updated_at": env.account_source(account_id).updated_at,
    }
    assert result.records[-1].state_before_sha256 != result.records[-1].state_after_sha256


def test_reroute_moves_the_ticket_and_out_of_scope_calls_are_denied():
    case = _case("missing_account", "deleted_account")
    env = SupportEnvironment(case.spec)
    (argument,) = case.truth.remedy_if_wrong_arguments

    gateway = recovery_gateway(_tools(env), env.state_sha256, Action("recover", "reroute", argument))
    denied = gateway.invoke("reroute", {**argument, "queue_id": case.spec.queues[0].queue_id
                                        if case.spec.queues[0].queue_id != argument["queue_id"]
                                        else case.spec.queues[1].queue_id})
    assert denied.records[-1].payload["reason"] == "call_outside_scope"
    assert gateway.invoke("reroute", argument).status is StageStatus.SUCCEEDED
    assert env.get_ticket(argument["ticket_id"]).queue_id == argument["queue_id"]


# Probes are read-only, and their outputs are clean, for every case


@pytest.mark.parametrize(("kind", "variant"), ALL_CASES)
def test_every_probe_is_read_only_and_clean_for_every_case(kind, variant):
    case = _case(kind, variant)
    environment = SupportEnvironment(case.spec)
    ticket = environment.get_ticket(case.truth.target_ticket_id)
    account_id = environment.directory_entry(ticket.customer_ref)
    gateway = probe_gateway(_tools(environment), environment.state_sha256)
    start = environment.state_sha256()

    calls = [
        ("inspect", {"entity": "ticket", "id": ticket.ticket_id}),
        ("inspect", {"entity": "routing_policy"}),
        ("inspect", {"entity": "queue", "id": case.spec.queues[0].queue_id}),
        ("resolve", {"customer_ref": ticket.customer_ref}),
        ("find_owners", {"customer_ref": ticket.customer_ref}),
        ("retry", {"tool": "read_ticket", "target": ticket.ticket_id}),
    ]

    if account_id is not None and account_id in environment.account_ids():
        calls += [
            ("inspect", {"entity": "account", "id": account_id}),
            ("compare_with_source", {"entity": "account", "id": account_id}),
            ("history", {"entity": "account", "id": account_id}),
            ("retry", {"tool": "lookup_account", "target": account_id}),
        ]

    observations = [gateway.invoke(verb, args) for verb, args in calls]

    assert environment.state_sha256() == start
    assert all(r.state_before_sha256 == r.state_after_sha256 for r in gateway.records)

    visible = [r.canonical_payload() for r in gateway.records]
    text = json.dumps(visible).lower()

    for marker in FAULT_MARKERS:
        assert marker not in text, marker

    assert_no_leaks(scan_case_content({"probe_records": visible}, case.truth))
    assert all(result.status is not StageStatus.DENIED for result in observations)
