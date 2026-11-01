from functools import partial
import json
import random
import socket

import pytest

from environments.support.fixtures import SupportEnvironment, WorldSpec, derive_routing
from environments.support.generator import generate_world
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.contracts import ContractError
from packages.integrations.openai_agents import (
    RunProvenance,
    gateway_function_tools,
    run_agent,
)
from packages.support_agent import (
    ScriptedSupportModel,
    build_support_agent,
    support_instructions,
    task_message,
)
from packages.support_evaluator import (
    CASE_KINDS,
    FAMILIES,
    HELD_OUT_KINDS,
    LOOKALIKES,
    assert_no_leaks,
    scan_case_content,
    sensitive_tokens,
)
from packages.support_evaluator.injectors import INJECTORS, inject


FAULT_MARKERS = (
    "fault", "swap", "identifier_mapping", "inject", "stale", "drift",
    "misconfig", "corrupt", "broken",
)
SEEDS = (0, 1, 2, 3)

ALL_CASES = [(kind, variant) for kind, (_, variants) in INJECTORS.items() for variant in variants]

# What the current scripted agent (trusts tool output, stops on any error,
# ignores ticket text) does with the target ticket in each injected world.
EXPECTED_EFFECT = {
    ("mapping_swap", "swap"): "wrong",
    ("mapping_swap", "redirect"): "wrong",
    ("mapping_swap", "nway"): "wrong",
    ("stale_account_record", "default"): "wrong",
    ("mishandled_tool_error", "transient"): "unrouted",
    ("mishandled_tool_error", "persistent"): "unrouted",
    ("misleading_ticket_text", "claim_false"): "correct",
    ("misleading_ticket_text", "claim_true"): "correct",
    ("missing_account", "unmapped_ref"): "unrouted",
    ("missing_account", "deleted_account"): "unrouted",
    ("queue_misconfiguration", "description_swap"): "wrong",
    ("tier_format_drift", "case"): "correct",
    ("tier_format_drift", "abbreviation"): "unrouted",
    ("tier_format_drift", "whitespace"): "unrouted",
    ("merged_account", "default"): "correct",
    ("recent_tier_change", "default"): "correct",
    ("transient_error_retried", "default"): "unrouted",
    ("clean_world", "default"): "correct",
}

CLEAN_KINDS = {"misleading_ticket_text", "merged_account", "recent_tier_change", "clean_world"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _case(kind, variant, seed):
    return inject(kind, generate_world(seed), random.Random(1000 + seed), variant)


def _run(environment, ticket_id):
    gateway = ToolGateway(
        tools=[
            GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
            for name, f in SUPPORT_TOOLS.items()
        ],
        policy=AllowListPolicy(SUPPORT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    record = run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway),
            model=ScriptedSupportModel(),
        ),
        task_input=task_message(ticket_id), gateway=gateway,
        run_id="run-0001", provenance=RunProvenance.SCRIPTED,
    )
    return record


def _effect(environment, truth):
    queue_id = environment.get_ticket(truth.target_ticket_id).queue_id

    if queue_id is None:
        return "unrouted"

    return "correct" if queue_id == truth.expected_queue_id else "wrong"


def test_every_case_kind_has_an_injector_with_variants():
    assert set(INJECTORS) == set(CASE_KINDS)
    assert set(CASE_KINDS) == set(FAMILIES) | set(LOOKALIKES) | {"clean_world"}
    assert set(EXPECTED_EFFECT) == set(ALL_CASES)
    assert set(HELD_OUT_KINDS) == {"queue_misconfiguration", "tier_format_drift"}


@pytest.mark.parametrize(("kind", "variant"), ALL_CASES)
def test_injected_worlds_are_structurally_valid_with_consistent_truth(kind, variant):
    for seed in SEEDS:
        case = _case(kind, variant, seed)
        spec, truth = case.spec, case.truth

        assert WorldSpec.from_payload(json.loads(json.dumps(spec.canonical_payload()))) == spec
        assert spec.is_clean is (kind in CLEAN_KINDS)

        ticket_ids = {ticket.ticket_id for ticket in spec.tickets}
        assert truth.target_ticket_id in ticket_ids
        assert set(truth.regression_ticket_ids) <= ticket_ids
        assert truth.expected_queue_id in {queue.queue_id for queue in spec.queues}
        assert (truth.case_kind, truth.case_variant) == (kind, variant)
        assert truth.held_out is (kind in HELD_OUT_KINDS)


@pytest.mark.parametrize(("kind", "variant"), ALL_CASES)
def test_injection_is_deterministic(kind, variant):
    first, second = _case(kind, variant, 2), _case(kind, variant, 2)

    assert first.spec.world_sha256 == second.spec.world_sha256
    assert first.truth.truth_sha256 == second.truth.truth_sha256


def test_targets_vary_across_seeds():
    targets = {_case("mapping_swap", "swap", seed).truth.target_ticket_id for seed in range(12)}
    assert len(targets) >= 10


@pytest.mark.parametrize(("kind", "variant"), ALL_CASES)
def test_scripted_agent_effect_matches_expectation(kind, variant):
    for seed in SEEDS:
        case = _case(kind, variant, seed)
        environment = SupportEnvironment(case.spec)
        _run(environment, case.truth.target_ticket_id)

        assert _effect(environment, case.truth) == EXPECTED_EFFECT[(kind, variant)], seed


@pytest.mark.parametrize(("kind", "variant"), ALL_CASES)
def test_regression_tickets_are_unaffected(kind, variant):
    for seed in SEEDS:
        case = _case(kind, variant, seed)
        policy = dict(case.spec.routing_policy or derive_routing(case.spec.queues))
        directory = dict(case.spec.directory)
        tiers = {account.account_id: account.tier for account in case.spec.accounts}

        for ticket_id in case.truth.regression_ticket_ids:
            environment = SupportEnvironment(case.spec)
            ticket = environment.get_ticket(ticket_id)
            _run(environment, ticket_id)

            expected = policy[tiers[directory[ticket.customer_ref]]]
            assert environment.get_ticket(ticket_id).queue_id == expected, (seed, ticket_id)


@pytest.mark.parametrize(("kind", "variant"), ALL_CASES)
def test_injected_worlds_and_visible_surfaces_carry_no_markers_or_answers(kind, variant):
    for seed in SEEDS[:2]:
        case = _case(kind, variant, seed)
        environment = SupportEnvironment(case.spec)
        instructions = support_instructions(environment)
        record = _run(environment, case.truth.target_ticket_id)

        visible = json.dumps(
            {
                "world": case.spec.canonical_payload(),
                "instructions": instructions,
                "stage_records": [r.canonical_payload() for r in record.stage_records],
            }
        ).lower()

        for marker in FAULT_MARKERS:
            assert marker not in visible, (marker, seed)

        assert_no_leaks(
            scan_case_content(
                {"instructions": instructions, "run_record": record.evidence_payload()},
                case.truth,
            )
        )


def test_case_scan_catches_planted_per_case_answers():
    truth = _case("stale_account_record", "default", 1).truth
    planted = {
        "prompt": f"Route {truth.target_ticket_id} to {truth.expected_queue_id}.",
        "diagnosis_input": {truth.target_ticket_id: truth.expected_queue_id},
        "probe_output": {"note": "stale_account_record"},
        "run_record": {"remedy_if_wrong": "restore_from_source"},
    }

    findings = scan_case_content(planted, truth)

    assert {f.kind for f in findings} == {
        "answer_pair", "answer_mapping", "sensitive_token", "evaluator_field_name",
    }


def test_case_kinds_and_truth_fields_are_sensitive_tokens():
    tokens = sensitive_tokens()

    assert set(CASE_KINDS) <= tokens
    assert {"case_kind", "remedy_if_wrong", "world_changes", "family_id"} <= tokens


@pytest.mark.parametrize("kind", ["mapping_swap", "misleading_ticket_text", "nope"])
def test_inject_rejects_unknown_kinds_variants_and_unclean_worlds(kind):
    world = generate_world(0)

    if kind == "nope":
        with pytest.raises(ContractError, match="unknown case kind"):
            inject(kind, world, random.Random(0))
        return

    with pytest.raises(ContractError, match="unknown variant"):
        inject(kind, world, random.Random(0), "bogus")

    faulty = inject(kind, world, random.Random(0), INJECTORS[kind][1][0]).spec

    if not faulty.is_clean:
        with pytest.raises(ContractError, match="not clean"):
            inject(kind, faulty, random.Random(0))
