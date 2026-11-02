"""A proposed recovery whose tool call fails (unknown ticket, queue or
account) is scored wrong with its reason, never crashes scoring, in tier 1
and at either step of a tier 2 sequence.

``set_mapping`` with an unknown customer reference is not a failed call:
the directory accepts a new reference by design, so it is an ordinary
change, scored by execution (wrong in tier 1, where it fixes nothing)."""

from dataclasses import replace
import json

import pytest

from packages.support_evaluator.dataset import build_dataset
from packages.support_evaluator.episodes import prepare, run_episode, score


# Builds and labels a dataset; runs in the slow CI job.
pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    """A tier 1 case whose label is a verified set_mapping."""
    directory = tmp_path_factory.mktemp("dataset") / "v2"
    build_dataset(directory, per_cell=1, seed=5, processes=1, kinds=("mapping_swap",))

    for line, case_line in zip((directory / "hetren_visible.jsonl").open(), (directory / "evaluator" / "cases.jsonl").open()):
        visible, case = json.loads(line), json.loads(case_line)

        if case["role"] == "primary" and visible["steps"][-1]["target"]["verb"] == "set_mapping":
            return prepare(visible, case)

    raise AssertionError("no set_mapping case in the tiny dataset")


def _invalid(prepared):
    ticket = prepared.case.truth.target_ticket_id
    ref = prepared.label["args"]["customer_ref"]
    account = prepared.label["args"]["account_id"]
    return {
        "unknown queue": {"action": "recover", "verb": "reroute", "args": {"ticket_id": ticket, "queue_id": "Q-NOWHERE"}},
        "unknown ticket": {"action": "recover", "verb": "reroute", "args": {"ticket_id": "T-0000", "queue_id": "Q-TRIAGE"}},
        "unknown account": {"action": "recover", "verb": "set_mapping", "args": {"customer_ref": ref, "account_id": "A-0000"}},
        "new customer ref": {"action": "recover", "verb": "set_mapping", "args": {"customer_ref": "C-0000", "account_id": account}},
        "unknown account to restore": {"action": "recover", "verb": "restore_from_source", "args": {"entity": "account", "id": "A-0000"}},
    }


def _episode(*actions):
    queue = list(actions)
    return lambda compact: queue.pop(0)


def test_the_label_itself_verifies(prepared):
    row = score(prepared, run_episode(_episode(prepared.label), prepared))
    assert row["correct"] and row["recovery_failures"] == []


@pytest.mark.parametrize("name", ["unknown queue", "unknown ticket", "unknown account", "unknown account to restore"])
def test_tier1_recovery_with_unknown_ids_is_wrong_with_its_reason(prepared, name):
    action = _invalid(prepared)[name]
    row = score(prepared, run_episode(_episode(action), prepared))

    assert not row["correct"] and row["failure"] is None
    assert [(f["step"], f["verb"]) for f in row["recovery_failures"]] == [(0, action["verb"])]
    assert row["recovery_failures"][0]["error"].startswith("ContractError: unknown")


def test_mapping_a_new_customer_ref_is_a_change_not_a_failure(prepared):
    row = score(prepared, run_episode(_episode(_invalid(prepared)["new customer ref"]), prepared))
    assert not row["correct"] and row["recovery_failures"] == []


@pytest.mark.parametrize("name", ["unknown queue", "unknown ticket", "unknown account"])
def test_tier2_failed_step_makes_the_sequence_wrong_at_either_step(prepared, name):
    tier2 = replace(prepared, max_recoveries=2, targets=(prepared.label, {"action": "decide", "verb": "no_intervention", "args": {}}))
    bad = _invalid(prepared)[name]

    # A failed first step followed by the right fix would otherwise verify.
    row = score(tier2, run_episode(_episode(bad, prepared.label), tier2))
    assert not row["correct"] and [f["step"] for f in row["recovery_failures"]] == [0]

    # The right fix followed by a failed second step.
    row = score(tier2, run_episode(_episode(prepared.label, bad), tier2))
    assert not row["correct"] and [f["step"] for f in row["recovery_failures"]] == [1]
