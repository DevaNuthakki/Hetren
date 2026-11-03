from collections import Counter
from functools import partial
import json
import math
import random
import socket

import pytest

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from environments.support.tools import (
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.integrations.openai_agents import (
    RunProvenance,
    gateway_function_tools,
    run_agent,
)
from packages.support_agent import (
    BEHAVIOURS,
    ScriptedSupportModel,
    build_support_agent,
    task_message,
)
from packages.support_evaluator import CASE_KINDS
from packages.support_evaluator.injectors import INJECTORS, inject
from packages.support_evaluator.plan import DEFAULT_PLAN_KINDS, cross_plan


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _run(environment, ticket_id, behaviour):
    gateway = ToolGateway(
        tools=[
            GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
            for name, f in SUPPORT_TOOLS.items()
        ],
        policy=AllowListPolicy(SUPPORT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    return run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway),
            model=ScriptedSupportModel(behaviour),
        ),
        task_input=task_message(ticket_id), gateway=gateway,
        run_id="run-0001", provenance=RunProvenance.SCRIPTED,
    )


def _case(kind, variant, seed):
    return inject(kind, generate_world(seed), random.Random(1000 + seed), variant)


def _outcome(environment, truth):
    queue_id = environment.get_ticket(truth.target_ticket_id).queue_id

    if queue_id is None:
        return "unrouted"

    return "correct" if queue_id == truth.expected_queue_id else "wrong"


def _calls(record):
    return [
        (r.tool_name, r.status.value) for r in record.stage_records if r.stage.value == "observed"
    ]


# The behaviours themselves


def test_trust_is_the_unchanged_default():
    assert ScriptedSupportModel().behaviour == "trust"
    assert ScriptedSupportModel().hetren_model_id == "scripted-support-model-v1"
    assert ScriptedSupportModel("trust").hetren_model_id == "scripted-support-model-v1"
    assert {ScriptedSupportModel(b).hetren_model_id for b in BEHAVIOURS} == {
        "scripted-support-model-v1",
        "scripted-support-model-v1+retry",
        "scripted-support-model-v1+give_up",
        "scripted-support-model-v1+follow_text",
        "scripted-support-model-v1+case_sensitive",
    }

    with pytest.raises(ValueError):
        ScriptedSupportModel("panic")


def test_retry_repeats_a_failed_call_exactly_once():
    transient = _case("mishandled_tool_error", "transient", 1)
    env = SupportEnvironment(transient.spec)
    record = _run(env, transient.truth.target_ticket_id, "retry")
    failed_tool = transient.spec.tool_errors[0].tool_name

    assert [c for c in _calls(record) if c[0] == failed_tool] == [
        (failed_tool, "failed"), (failed_tool, "succeeded"),
    ]
    assert _outcome(env, transient.truth) == "correct"

    persistent = _case("mishandled_tool_error", "persistent", 1)
    env = SupportEnvironment(persistent.spec)
    record = _run(env, persistent.truth.target_ticket_id, "retry")
    failed_tool = persistent.spec.tool_errors[0].tool_name

    assert [c for c in _calls(record) if c[0] == failed_tool] == [
        (failed_tool, "failed"), (failed_tool, "failed"),
    ]
    assert record.final_message.startswith("I could not complete the request")


def test_give_up_stops_on_inconsistency_instead_of_routing():
    case = _case("mapping_swap", "swap", 1)
    env = SupportEnvironment(case.spec)

    record = _run(env, case.truth.target_ticket_id, "give_up")

    assert record.final_message == "I stopped: the account record does not name the ticket's customer."
    assert [tool for tool, _ in _calls(record)] == ["read_ticket", "lookup_account"]


def test_give_up_stops_on_an_unrecognised_tier():
    case = _case("tier_format_drift", "abbreviation", 1)
    env = SupportEnvironment(case.spec)

    record = _run(env, case.truth.target_ticket_id, "give_up")

    assert record.final_message.startswith("I stopped: no queue matches the")


def test_case_sensitive_fails_on_a_case_variant_that_others_accept():
    case = _case("tier_format_drift", "case", 1)

    for behaviour, expected in (("trust", "correct"), ("case_sensitive", "unrouted")):
        env = SupportEnvironment(case.spec)
        record = _run(env, case.truth.target_ticket_id, behaviour)
        assert _outcome(env, case.truth) == expected

    assert record.final_message.startswith("No queue matches the")


def test_follow_text_routes_by_a_claimed_tier():
    false_claim = _case("misleading_ticket_text", "claim_false", 1)
    env = SupportEnvironment(false_claim.spec)
    _run(env, false_claim.truth.target_ticket_id, "follow_text")
    assert _outcome(env, false_claim.truth) == "wrong"

    true_claim = _case("misleading_ticket_text", "claim_true", 1)
    env = SupportEnvironment(true_claim.spec)
    _run(env, true_claim.truth.target_ticket_id, "follow_text")
    assert _outcome(env, true_claim.truth) == "correct"


@pytest.mark.parametrize("behaviour", BEHAVIOURS)
def test_every_behaviour_routes_clean_worlds_correctly(behaviour):
    spec = generate_world(4)

    for ticket in spec.tickets[:6]:
        env = SupportEnvironment(spec)
        record = _run(env, ticket.ticket_id, behaviour)
        account_id = dict(spec.directory)[ticket.customer_ref]
        tier = next(a.tier for a in spec.accounts if a.account_id == account_id)
        expected = next(q.queue_id for q in spec.queues if f"{tier}-tier" in q.description)

        assert env.get_ticket(ticket.ticket_id).queue_id == expected
        assert record.sdk_evidence.discrepancies == ()


# Outcome of every behaviour on every case kind and variant (pinned)


C, W, U = "correct", "wrong", "unrouted"

EXPECTED = {
    #                                     trust retry give_up follow_text case_sensitive
    ("mapping_swap", "swap"):                     (W, W, U, W, W),
    ("mapping_swap", "redirect"):                 (W, W, U, W, W),
    ("mapping_swap", "nway"):                     (W, W, U, W, W),
    ("stale_account_record", "default"):          (W, W, W, W, W),
    ("mishandled_tool_error", "transient"):       (U, C, U, U, U),
    ("mishandled_tool_error", "persistent"):      (U, U, U, U, U),
    ("misleading_ticket_text", "claim_false"):    (C, C, C, W, C),
    ("misleading_ticket_text", "claim_true"):     (C, C, C, C, C),
    ("missing_account", "unmapped_ref"):          (U, U, U, U, U),
    ("missing_account", "deleted_account"):       (U, U, U, U, U),
    ("queue_misconfiguration", "description_swap"): (W, W, W, W, W),
    ("tier_format_drift", "case"):                (C, C, C, C, U),
    ("tier_format_drift", "abbreviation"):        (U, U, U, U, U),
    ("tier_format_drift", "whitespace"):          (U, U, U, U, U),
    ("merged_account", "default"):                (C, C, U, C, C),
    ("recent_tier_change", "default"):            (C, C, C, C, C),
    ("transient_error_retried", "default"):       (U, C, U, U, U),
    ("clean_world", "default"):                   (C, C, C, C, C),
}


def test_expected_table_covers_every_case_and_behaviour():
    assert set(EXPECTED) == {(k, v) for k, (_, vs) in INJECTORS.items() for v in vs}
    assert BEHAVIOURS == ("trust", "retry", "give_up", "follow_text", "case_sensitive")


@pytest.mark.parametrize(("kind", "variant"), sorted(EXPECTED))
def test_behaviour_outcomes_match_the_pinned_table(kind, variant):
    for behaviour, expected in zip(BEHAVIOURS, EXPECTED[(kind, variant)]):
        for seed in range(4):
            case = _case(kind, variant, seed)
            env = SupportEnvironment(case.spec)
            _run(env, case.truth.target_ticket_id, behaviour)

            assert _outcome(env, case.truth) == expected, (behaviour, seed)


# The crossing plan


def test_plan_crosses_every_kind_with_every_behaviour_equally():
    plan = cross_plan(per_cell=6, seed=0)
    cells = Counter((case.case_kind, case.behaviour) for case in plan)

    assert set(cells) == {(kind, behaviour) for kind in DEFAULT_PLAN_KINDS for behaviour in BEHAVIOURS}
    assert set(cells.values()) == {6}
    assert len(plan) == len(DEFAULT_PLAN_KINDS) * len(BEHAVIOURS) * 6
    assert set(CASE_KINDS) - set(DEFAULT_PLAN_KINDS) == {"clean_world"}


def test_behaviour_carries_no_information_about_the_family():
    plan = cross_plan(per_cell=6, seed=0)
    total = len(plan)
    joint = Counter((c.case_kind, c.behaviour) for c in plan)
    kinds = Counter(c.case_kind for c in plan)
    behaviours = Counter(c.behaviour for c in plan)

    mutual_information = sum(
        (n / total) * math.log((n / total) / ((kinds[k] / total) * (behaviours[b] / total)))
        for (k, b), n in joint.items()
    )

    assert abs(mutual_information) < 1e-12


def test_variants_cycle_evenly_within_each_kind_and_behaviour():
    plan = cross_plan(per_cell=6, seed=0)

    for kind in DEFAULT_PLAN_KINDS:
        variants = INJECTORS[kind][1]
        for behaviour in BEHAVIOURS:
            counts = Counter(
                c.case_variant for c in plan if c.case_kind == kind and c.behaviour == behaviour
            )
            assert max(counts.values()) - min(counts.values()) <= 1
            assert set(counts) == set(variants)


def test_plan_is_reproducible_and_seeds_differ():
    assert cross_plan(2, seed=5) == cross_plan(2, seed=5)
    assert cross_plan(2, seed=5) != cross_plan(2, seed=6)
    seeds = [(c.world_seed, c.case_seed) for c in cross_plan(6, seed=0)]
    assert len(set(seeds)) == len(seeds)


# Where the behaviour is visible


@pytest.mark.parametrize("behaviour", [b for b in BEHAVIOURS if b != "trust"])
def test_behaviour_name_appears_only_in_the_model_id(behaviour):
    case = _case("mapping_swap", "swap", 2)
    record = _run(SupportEnvironment(case.spec), case.truth.target_ticket_id, behaviour)
    evidence = record.evidence_payload()

    assert evidence["model_id"] == f"scripted-support-model-v1+{behaviour}"
    without_model_id = {key: value for key, value in evidence.items() if key != "model_id"}
    assert behaviour not in json.dumps(without_model_id)
