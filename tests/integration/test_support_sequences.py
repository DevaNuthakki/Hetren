"""Tier 2: up to two recoveries per episode.

- The pruned pair search returns exactly the naive search's first pair.
- Sequence labels: the shortest verified sequence, ``abstain`` otherwise, and
  no search past a persistent tool error.
- Episodes apply recoveries one at a time and are scored on the whole
  sequence; tier 1 inputs and labels are unchanged.
- Richer hypotheses: several draws per variant and every v3 compound pair,
  an adaptive probe menu, and one partner record per distinct label.

Fast tests label with tier 1's hypothesis set (``small_hypotheses``); the
full tier 2 set runs in the slow job.
"""

import json
import random
import re
import socket
from types import SimpleNamespace

import pytest
import tiktoken

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from packages.contracts import ContractError
from packages.hetren_baselines import rules_policy
from packages.hetren_evidence import (
    COMPACT_FORMAT,
    COMPACT_FORMAT_V2,
    TIER2_EVIDENCE_TOKEN_BUDGET,
    compact_evidence,
    render_evidence,
)
from packages.support_agent import BEHAVIOURS
from packages.support_evaluator import scan_case_content
from packages.support_evaluator import sequences
from packages.support_evaluator.cases import COMPOUND_KIND
from packages.support_evaluator.compound import TIER2_COMPOUND_VARIANTS
from packages.support_evaluator.episodes import PreparedCase, run_episode, score, summarize
from packages.support_evaluator.injectors import inject
from packages.support_evaluator.labeler import Renaming, abstract, counterfactuals, label_case, label_run
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on
from packages.support_evaluator.sequences import (
    STOP,
    TIER2_DRAWS,
    _partner_choices,
    apply_recovery,
    label_case_tier2,
    label_sequence,
    naive_pairs,
    search_pairs,
    tier2_counterfactuals,
    verify_sequence,
)


ENCODING = tiktoken.get_encoding("o200k_base")
SWAP_STALE = "mapping_swap.swap+stale_account_record.default"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def small_hypotheses(monkeypatch):
    """Tier 1's hypothesis set, so fast tests exercise episodes without the full enumeration."""
    monkeypatch.setattr(sequences, "tier2_counterfactuals", counterfactuals)


def _case(kind, variant, seeds=range(5000, 5040)):
    for seed in seeds:
        try:
            return seed, inject(kind, generate_world(seed), random.Random(seed - 5000), variant)
        except ContractError:
            continue

    raise AssertionError(f"{kind} {variant} never applies")


def _run(case, behaviour):
    environment = SupportEnvironment(case.spec)
    evidence = run_agent_on(environment, case.truth.target_ticket_id, behaviour).evidence_payload()
    return environment, evidence


def _assert_pruned_matches_naive(variants, seeds, behaviours, enough=None):
    checked = 0

    for variant in variants:
        for seed in seeds:
            if enough is not None and checked >= enough:
                break

            try:
                case = inject("compound", generate_world(5000 + seed), random.Random(seed), variant)
            except ContractError:
                continue

            for behaviour in behaviours:
                environment, evidence = _run(case, behaviour)
                single = label_run(case, environment, evidence, behaviour)

                if single.rule != "no_verified_recovery":
                    continue

                naive = naive_pairs(case, environment, behaviour, single)
                pruned, _ = search_pairs(case, environment, behaviour, single)
                assert pruned == (naive[0] if naive else None), (variant, seed, behaviour)
                checked += 1

    assert checked


def test_pruned_search_returns_the_naive_first_pair():
    _assert_pruned_matches_naive(
        [SWAP_STALE, "missing_account.unmapped_ref+transient_error_retried.default"], range(2), ("trust",),
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    "variant",
    [
        SWAP_STALE,
        "mapping_swap.swap+mishandled_tool_error.persistent",
        "mapping_swap.swap+transient_error_retried.default",
        "stale_account_record.default+missing_account.unmapped_ref",
        "missing_account.unmapped_ref+transient_error_retried.default",
        "misleading_ticket_text.claim_false+missing_account.unmapped_ref",
        "stale_account_record.default+mishandled_tool_error.transient",
        "mapping_swap.swap+tier_format_drift.case",
        "mapping_swap.swap+queue_misconfiguration.description_swap",
    ],
)
def test_pruned_search_returns_the_naive_first_pair_across_pair_types(variant):
    _assert_pruned_matches_naive([variant], range(12), BEHAVIOURS, enough=10)


def test_two_faults_need_two_recoveries_and_each_alone_fails():
    _, case = _case("compound", SWAP_STALE)
    environment, evidence = _run(case, "trust")
    label = label_sequence(case, environment, evidence, "trust")

    assert label.single.verb == "abstain"
    assert [a["verb"] for a in label.recoveries] == ["set_mapping", "restore_from_source"]
    assert label.targets == label.recoveries and label.rule == "shortest_verified_sequence"
    assert verify_sequence(case, environment, evidence, "trust", label.recoveries, None)
    assert verify_sequence(case, environment, evidence, "trust", label.recoveries[:1], STOP) is False
    assert verify_sequence(case, environment, evidence, "trust", label.recoveries[1:], STOP) is False
    assert verify_sequence(case, environment, evidence, "trust", [], label.single.label) is False

    # Partial fix and escalate is scored wrong (a documented limitation).
    abstain = {"action": "decide", "verb": "abstain", "args": {"reason": "no_verified_recovery"}}
    assert verify_sequence(case, environment, evidence, "trust", label.recoveries[:1], abstain) is False


def test_single_faults_keep_their_tier1_label_and_stop():
    _, case = _case("stale_account_record", "default")
    environment, evidence = _run(case, "trust")
    label = label_sequence(case, environment, evidence, "trust")

    assert label.recoveries == (label.single.label,) and label.pairs_tried == 0
    assert label.targets == (label.single.label, STOP)
    assert verify_sequence(case, environment, evidence, "trust", label.recoveries, STOP)


def test_a_persistent_tool_error_is_never_searched_past():
    for seed in range(12):
        try:
            case = inject("compound", generate_world(5000 + seed), random.Random(seed),
                          "mapping_swap.swap+mishandled_tool_error.persistent")
        except ContractError:
            continue

        environment, evidence = _run(case, "trust")
        label = label_sequence(case, environment, evidence, "trust")

        if label.single.rule == "persistent_tool_error":
            assert label.pairs_tried == 0 and label.recoveries in ((), (label.single.label,))
            return

    raise AssertionError("no persistent error observed")


def test_recoveries_go_through_a_gateway_scoped_to_the_exact_call():
    _, case = _case("mapping_swap", "swap")
    environment, evidence = _run(case, "trust")
    action = label_run(case, environment, evidence, "trust").label
    applied = apply_recovery(environment.fork(), case.truth.target_ticket_id, "trust", action)

    stages = [(r["stage"], r["status"]) for r in applied.records]
    assert stages == [("proposed", "proposed"), ("authorized", "allowed"), ("attempted", "started"), ("observed", "succeeded")]
    assert applied.records[0]["payload"]["arguments"] == action["args"]
    assert applied.changed and applied.rerun is not None


def test_compact_input_is_v1_without_recoveries_and_v2_with_them():
    _, case = _case("mapping_swap", "swap")
    environment, evidence = _run(case, "trust")
    action = label_run(case, environment, evidence, "trust").label
    applied = apply_recovery(environment.fork(), case.truth.target_ticket_id, "trust", action)

    plain = compact_evidence(evidence)
    after = compact_evidence(evidence, [], [applied.compact_input()])

    assert plain["format"] == COMPACT_FORMAT and "recoveries" not in plain
    assert after["format"] == COMPACT_FORMAT_V2
    assert {k: v for k, v in after.items() if k not in ("format", "recoveries")} == {k: v for k, v in plain.items() if k != "format"}
    entry = after["recoveries"][0]
    assert entry["action"] == action and entry["result"]["outcome"] == "succeeded"
    assert entry["rerun"]["steps"] and entry["probes"] == []


def _tier2(kind, variant, behaviour="trust"):
    seed, _ = _case(kind, variant)
    return label_case_tier2(PlannedCase(kind, variant, behaviour, seed, seed - 5000, "complete"))


def test_tier2_steps_fix_then_check_and_stay_leak_free_within_budget(small_hypotheses):
    labelled = _tier2("compound", SWAP_STALE)
    targets = [s["target"] for s in labelled.steps if s["target"]["action"] != "probe"]

    assert targets == list(labelled.sequence.targets)
    after_first = [s for s in labelled.steps if s["input"]["format"] == COMPACT_FORMAT_V2]
    assert after_first and after_first[-1]["target"] == labelled.sequence.recoveries[1]
    assert scan_case_content({"steps": labelled.steps}, labelled.case.truth) == ()
    assert max(len(ENCODING.encode(render_evidence(s["input"]))) for s in labelled.steps) <= TIER2_EVIDENCE_TOKEN_BUDGET

    for partner in labelled.partners:
        assert abstract(partner["steps"][0]["input"])[0] == abstract(labelled.steps[0]["input"])[0]


def test_tier2_keeps_tier1_first_steps_for_a_single_fault(small_hypotheses):
    kind, variant = "stale_account_record", "default"
    seed, _ = _case(kind, variant)
    planned = PlannedCase(kind, variant, "trust", seed, seed - 5000, "complete")
    tier1, tier2 = label_case(planned), label_case_tier2(planned)

    assert tier2.steps[: len(tier1.steps)] == tier1.steps
    assert tier2.steps[-1]["target"] == STOP and tier2.steps[-1]["input"]["format"] == COMPACT_FORMAT_V2


def _prepared_tier2(labelled):
    environment = SupportEnvironment(labelled.case.spec)
    evidence = run_agent_on(environment, labelled.case.truth.target_ticket_id, labelled.planned.behaviour).evidence_payload()
    targets = tuple(s["target"] for s in labelled.steps if s["target"]["action"] != "probe")
    return PreparedCase("case", labelled.planned, labelled.case, environment, evidence,
                        labelled.steps[-1]["target"], 2, targets)


def _replay(steps):
    queue = [s["target"] for s in steps]
    return lambda compact: queue.pop(0)


def test_episodes_score_the_whole_sequence(small_hypotheses):
    labelled = _tier2("compound", SWAP_STALE)
    prepared = _prepared_tier2(labelled)
    first = labelled.sequence.recoveries[0]

    replayed = score(prepared, run_episode(_replay(labelled.steps), prepared))
    stopped = score(prepared, run_episode(_replay([{"target": first}, {"target": STOP}]), prepared))
    rules = score(prepared, run_episode(rules_policy, prepared, max_recoveries=1))

    assert replayed["correct"] and replayed["exact"] and len(replayed["recoveries"]) == 2
    assert not stopped["correct"] and not rules["correct"] and len(rules["recoveries"]) == 1
    sequence = summarize([replayed, stopped, rules])["sequence"]
    assert sequence["exact_sequence_match"]["k"] == 1
    assert {k: sequence["stopped_after_one_of_two"][k] for k in ("n", "k", "rate")} == {"n": 3, "k": 2, "rate": 0.6667}


def test_rules_v1_on_a_single_fault_counts_its_recovery_as_an_implicit_stop(small_hypotheses):
    labelled = _tier2("stale_account_record", "default")
    prepared = _prepared_tier2(labelled)
    row = score(prepared, run_episode(rules_policy, prepared, max_recoveries=1))

    assert row["correct"] and row["exact"] and row["tier"] == 2


def test_tier2_hypotheses_add_draws_and_compounds_without_duplicate_worlds():
    seed, case = _case("mapping_swap", "swap")
    planned = PlannedCase("mapping_swap", "swap", "trust", seed, seed - 5000, "complete")
    worlds = tier2_counterfactuals(planned, case)
    keys = [key for key, _ in worlds]
    hashes = [c.spec.world_sha256 for _, c in worlds]

    assert len(set(hashes)) == len(hashes) and case.spec.world_sha256 not in hashes
    assert all(c.truth.target_ticket_id == case.truth.target_ticket_id for _, c in worlds)
    assert any(key.startswith("mapping_swap/swap#") for key in keys)  # other draws of the case's own variant
    assert {key.split("/", 1)[1] for key in keys if key.startswith(COMPOUND_KIND)} <= set(TIER2_COMPOUND_VARIANTS)
    assert sum(key.startswith(COMPOUND_KIND) for key in keys) > 50
    assert all(int(key.split("#")[1]) < TIER2_DRAWS for key in keys if "#" in key)

    # Draw 0 is tier 1's world for every variant tier 1 also lists.
    tier1 = {key: c.spec.world_sha256 for key, c in counterfactuals(planned, case)}
    assert {key: h for key, h in zip(keys, hashes) if key in tier1} == {k: h for k, h in tier1.items() if h in hashes}


def _hypothesis(key, label_ref):
    renaming = Renaming()
    renaming.apply({"ref": "C-AAAA"})
    targets = ({"action": "recover", "verb": "set_mapping", "args": {"customer_ref": "C-AAAA", "account_id": label_ref}},)
    return SimpleNamespace(key=key, renaming=renaming), SimpleNamespace(targets=targets)


def test_one_partner_per_distinct_label_chosen_by_a_seeded_hash():
    # A-1111 and A-2222 are unseen accounts: both become A#1, the same label.
    pairs = [_hypothesis("a", "A-1111"), _hypothesis("b", "A-2222"), _hypothesis("c", "C-AAAA")]
    others = [h for h, _ in pairs]
    labels = {h.key: seq for h, seq in pairs}

    chosen = _partner_choices("twin-1", others, labels)
    assert len(chosen) == 2 and "c" in {h.key for h in chosen}
    assert chosen == _partner_choices("twin-1", list(reversed(others)), labels)  # not enumeration order

    picks = {next(h.key for h in _partner_choices(f"twin-{i}", others, labels) if h.key != "c") for i in range(20)}
    assert picks == {"a", "b"}  # the seed decides, so neither variant is always preferred


_ID = re.compile(r"\b[TACQ]-[0-9A-Z]{3,12}\b")


@pytest.mark.slow
def test_adaptive_menu_reaches_a_fault_behind_a_failed_read():
    # A transient error hides the account step: tier 1's static menu cannot
    # separate what lies behind it; revealing probes can.
    variant = "mishandled_tool_error.transient+missing_account.deleted_account"
    labelled = None

    for seed in range(5000, 5040):
        try:
            labelled = label_case_tier2(PlannedCase(COMPOUND_KIND, variant, "give_up", seed, seed - 5000, "complete"))
        except ContractError:
            continue

        if labelled.probe_label.initial_label_entropy > 0:
            break

    assert labelled is not None and labelled.probe_label.determined and len(labelled.probe_label.probes) >= 2
    assert scan_case_content({"steps": labelled.steps}, labelled.case.truth) == ()

    for steps in [labelled.steps] + [p["steps"] for p in labelled.partners]:
        assert scan_case_content({"steps": steps}, labelled.case.truth) == ()

        for step in steps:
            if step["target"]["action"] == "probe":
                named = set(_ID.findall(json.dumps(step["target"]["args"])))
                assert named <= set(_ID.findall(json.dumps(step["input"])))  # only entities the policy has seen
