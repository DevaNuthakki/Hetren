"""The rules baseline and the episode runner on rebuilt cases.

Each case is rebuilt from a planned case, labelled by the labeler's run
rule, and given to a policy through ``run_episode``; ``score`` checks the
final action by execution.
"""

import random
import socket

import pytest

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from packages.action_space import PROBE_BUDGET
from packages.hetren_baselines import rules_policy
from packages.support_evaluator.episodes import PreparedCase, run_episode, score, summarize
from packages.support_evaluator.injectors import inject
from packages.support_evaluator.labeler import label_run, withhold_observation
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on


WORLD_SEED, CASE_SEED = 11, 3


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _prepared(kind, variant, behaviour, condition="complete"):
    planned = PlannedCase(kind, variant, behaviour, WORLD_SEED, CASE_SEED, condition)
    case = inject(kind, generate_world(WORLD_SEED), random.Random(CASE_SEED), variant)
    environment = SupportEnvironment(case.spec)
    evidence = run_agent_on(environment, case.truth.target_ticket_id, behaviour).evidence_payload()

    if condition == "withheld":
        evidence = withhold_observation(evidence)

    label = label_run(case, environment, evidence, behaviour).label
    return PreparedCase(f"{kind}-{variant}", planned, case, environment, evidence, label)


@pytest.mark.parametrize(
    ("kind", "variant", "behaviour", "condition", "verb"),
    [
        ("mapping_swap", "swap", "trust", "complete", "set_mapping"),
        ("missing_account", "unmapped_ref", "trust", "complete", "set_mapping"),
        ("missing_account", "deleted_account", "trust", "complete", "reroute"),
        ("mishandled_tool_error", "persistent", "trust", "complete", "abstain"),
        ("transient_error_retried", "default", "trust", "complete", "rerun"),
        ("stale_account_record", "default", "trust", "complete", "restore_from_source"),
        ("misleading_ticket_text", "claim_false", "follow_text", "complete", "reroute"),
        ("recent_tier_change", "default", "trust", "complete", "no_intervention"),
        ("merged_account", "default", "trust", "complete", "no_intervention"),
        ("mapping_swap", "swap", "trust", "withheld", "insufficient_evidence"),
    ],
)
def test_rules_reach_a_verified_decision_on_training_families(kind, variant, behaviour, condition, verb):
    prepared = _prepared(kind, variant, behaviour, condition)
    episode = run_episode(rules_policy, prepared)
    row = score(prepared, episode)

    assert row["final"]["verb"] == verb
    assert row["correct"], row
    assert len(row["probes"]) <= PROBE_BUDGET


def test_probes_run_on_a_fork_and_never_change_the_scored_state():
    prepared = _prepared("recent_tier_change", "default", "trust")
    before = prepared.environment.state_sha256()
    episode = run_episode(rules_policy, prepared)

    assert [p["verb"] for p in episode["probes"]] == ["inspect", "compare_with_source"]
    assert prepared.environment.state_sha256() == before


def test_budget_overruns_and_invalid_actions_are_failures():
    prepared = _prepared("recent_tier_change", "default", "trust")
    always_probe = lambda compact: {"action": "probe", "verb": "inspect", "args": {"entity": "routing_policy"}}
    nonsense = lambda compact: {"action": "decide", "verb": "fly", "args": {}}

    over = score(prepared, run_episode(always_probe, prepared))
    invalid = score(prepared, run_episode(nonsense, prepared))

    assert over["failure"] == "probe_budget_exceeded" and len(over["probes"]) == PROBE_BUDGET
    assert invalid["failure"].startswith("invalid_action") and not invalid["correct"]
    summary = summarize([over, invalid])
    assert summary["decision_accuracy"]["k"] == 0
    assert summary["failures"] == {"probe_budget_exceeded": 1, "invalid_action:ContractError": 1}


def test_a_wrong_recovery_on_a_healthy_run_counts_as_a_wrong_intervention():
    prepared = _prepared("merged_account", "default", "trust")
    rerun = lambda compact: {"action": "recover", "verb": "rerun", "args": {}}
    row = score(prepared, run_episode(rerun, prepared))
    summary = summarize([row])

    assert summary["wrong_interventions_on_healthy"]["k"] == 1
    assert not row["correct"]
