"""Metric formulas on hand-made rows: rates with Wilson intervals, decision
and probe metrics, the undetermined-case rule, groups and the
length-matched slice."""

import json

import pytest

from packages.support_evaluator.metrics import attach_case_facts, length_metrics, rate, summarize, wilson


NOOP = {"action": "decide", "verb": "no_intervention", "args": {}}
ABSTAIN = {"action": "decide", "verb": "abstain", "args": {"reason": "x"}}
MISSING = {"action": "decide", "verb": "insufficient_evidence", "args": {"missing": ["x"]}}
FIX = {"action": "recover", "verb": "rerun", "args": {}}


def row(case_id, label, final, correct, probes=0, recoveries=None, kind="mapping_swap", held_out=False,
        determined=True, oracle=1, failure=None):
    recoveries = [final] if recoveries is None and final and final["action"] == "recover" else (recoveries or [])
    return {
        "case_id": case_id, "label": label, "final": final, "correct": correct, "exact": correct and final == label,
        "probes": [{"verb": "inspect"}] * probes, "recoveries": recoveries, "case_kind": kind, "held_out": held_out,
        "tier": 1, "failure": failure, "determined": determined, "oracle_probes": oracle, "recovery_failures": [],
    }


def test_wilson_interval():
    assert wilson(0, 0) is None
    assert wilson(5, 10) == [0.2366, 0.7634]
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == 1.0
    assert rate(1, 4) == {"n": 4, "k": 1, "rate": 0.25, "ci95": wilson(1, 4)}


ROWS = [
    row("a", FIX, FIX, True, probes=1),                       # verified recovery
    row("b", FIX, NOOP, False, probes=0),                     # missed fault
    row("c", NOOP, NOOP, True, probes=2),                     # healthy, correct
    row("d", NOOP, FIX, False, probes=1),                     # wrong intervention on healthy
    row("e", ABSTAIN, MISSING, False, probes=3, determined=False, oracle=2),
    row("f", MISSING, MISSING, True, probes=0, oracle=0),
    row("g", ABSTAIN, None, False, probes=4, failure="probe_budget_exceeded"),
]


def test_decision_metrics():
    summary = summarize(ROWS)

    assert summary["decision_accuracy"]["k"] == 3 and summary["decision_accuracy"]["n"] == 7
    assert (summary["verified_recovery_rate"]["k"], summary["verified_recovery_rate"]["n"]) == (1, 2)
    assert (summary["wrong_interventions_on_healthy"]["k"], summary["wrong_interventions_on_healthy"]["n"]) == (1, 2)
    assert (summary["insufficient_evidence"]["recall"]["k"], summary["insufficient_evidence"]["recall"]["n"]) == (1, 1)
    # Chosen twice (e and f), right once.
    assert (summary["insufficient_evidence"]["precision"]["k"], summary["insufficient_evidence"]["precision"]["n"]) == (1, 2)
    assert summary["abstain"]["recall"]["n"] == 2 and summary["abstain"]["precision"]["n"] == 0
    assert summary["failures"] == {"probe_budget_exceeded": 1}


def test_undetermined_cases_count_in_decisions_but_not_in_probe_efficiency():
    probes = summarize(ROWS)["probes"]

    # Row e (undetermined, 3 probes, oracle 2) is left out of every probe metric.
    assert probes["undetermined"] == 1 and probes["determined_cases"] == 6
    assert probes["mean_probes"] == round((1 + 0 + 2 + 1 + 0 + 4) / 6, 3)
    assert probes["mean_probes_on_healthy"] == 1.5
    assert probes["oracle_mean_probes"] == round((1 + 1 + 1 + 1 + 0 + 1) / 6, 3)
    assert probes["mean_excess_probes"] == round((0 - 1 + 1 + 0 + 0 + 3) / 6, 3)
    assert probes["probe_budget_exceeded"]["k"] == 1


def test_groups_split_held_out_and_proactive_families():
    rows = [
        row("a", FIX, FIX, True, kind="stale_account_record"),
        row("b", ABSTAIN, ABSTAIN, True, kind="queue_misconfiguration", held_out=True),
        row("c", ABSTAIN, NOOP, False, kind="tier_format_drift", held_out=True, determined=False),
        row("d", NOOP, NOOP, True, kind="mapping_swap"),
    ]
    summary = summarize(rows)

    assert summary["held_out_families"]["decision_accuracy"]["k"] == 1
    assert summary["held_out_families"]["decision_accuracy"]["n"] == 2 and summary["held_out_families"]["undetermined"] == 1
    assert summary["training_families"]["decision_accuracy"]["n"] == 2
    assert summary["proactive_detection"]["decision_accuracy"]["n"] == 2
    assert summary["by_family"]["tier_format_drift"]["held_out"] is True


def test_length_reweighting_removes_a_length_cue():
    # Short runs are mostly healthy and answered right; long runs mostly faulty and answered wrong.
    rows, tokens = [], {}

    for i in range(20):
        short = i < 10
        healthy = (i % 10) < (8 if short else 2)
        label = NOOP if healthy else FIX
        rows.append(row(f"c{i}", label, NOOP, healthy))
        tokens[f"c{i}"] = 100 + i

    result = length_metrics(rows, tokens)

    # Every label is right exactly when it is healthy, so reweighting each label to the
    # overall length distribution gives the share of weight on healthy rows: 0.5.
    assert result["reweighted_accuracy"] == 0.5
    assert sum(d["n"] for d in result["deciles"].values()) == 20


def test_slices_need_tags_and_tier2_adds_compound_pairs():
    rows = [dict(r, tier=2, label_recoveries=1, label_targets=[r["label"]]) for r in ROWS[:4]]
    tags = {r["case_id"]: {"compound": False, "target_recent": False, "compound_pair": i < 2, "first_input_tokens": 100 + i}
            for i, r in enumerate(rows)}
    summary = summarize(rows, tags)

    assert summary["slices"]["compound_pair"]["n"] == 2 and "sequence" in summary
    assert "length_matched" in summary["slices"]


def test_attach_case_facts_reads_the_evaluator_records(tmp_path):
    (tmp_path / "evaluator").mkdir()
    cases = [
        {"case_id": "a", "role": "primary", "probe_label": {"determined": False, "probes": [{}, {}]}},
        {"case_id": "b", "role": "partner", "probe_label": {"determined": True, "probes": []}},
    ]
    (tmp_path / "evaluator" / "cases.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cases))
    new = row("a", FIX, FIX, True)
    old = {k: v for k, v in new.items() if k not in ("determined", "oracle_probes", "tier", "recoveries")}

    # Older tier 1 rows also get their tier and their one recovery back.
    assert attach_case_facts([old], tmp_path)[0] == {**new, "determined": False, "oracle_probes": 2}


@pytest.mark.parametrize("k, n", [(0, 1), (1, 1), (3, 7), (50, 100)])
def test_interval_contains_the_rate(k, n):
    low, high = wilson(k, n)
    assert low <= k / n <= high
