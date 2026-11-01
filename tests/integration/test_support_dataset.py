from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest
import tiktoken

from packages.action_space import parse_action
from packages.support_evaluator.audit import load_dataset, scan_dataset, shortcut_audit
from packages.support_evaluator.dataset import build_dataset
from packages.support_evaluator.plan import PlannedCase, cross_plan


ENCODING = tiktoken.get_encoding("o200k_base")
KINDS = ("mapping_swap", "missing_account")  # small datasets keep CI fast


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    directory = tmp_path_factory.mktemp("dataset") / "v1"
    result = build_dataset(directory, per_cell=2, seed=5, withheld_per_cell=1, processes=1, kinds=KINDS)
    return directory, result


def test_layout_and_manifest_hashes(tiny):
    directory, result = tiny
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))

    assert sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()) == [
        "evaluator/cases.jsonl", "evaluator/labeling_time.jsonl", "evaluator/tags.jsonl",
        "hetren_visible.jsonl", "manifest.json",
    ]
    assert manifest["counts"]["primary_cases"] == 20
    assert manifest["counts"]["records"] == 20 + manifest["counts"]["partner_records"]
    assert directory.with_name(directory.name + ".partial.jsonl").exists()
    for name, digest in {**manifest["files"], **manifest["timing_file"]}.items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
    assert manifest == result["manifest"]


def test_visible_records_hold_only_compact_inputs_and_target_actions(tiny):
    directory, _ = tiny
    visible, evaluator = load_dataset(directory)

    for record in visible:
        assert set(record) == {"case_id", "steps"}
        assert all(set(step) == {"input", "target"} for step in record["steps"])
        targets = [parse_action(step["target"]) for step in record["steps"]]
        assert all(t.kind == "probe" for t in targets[:-1])
        assert targets[-1].kind in ("recover", "decide")

    text = (directory / "hetren_visible.jsonl").read_text(encoding="utf-8")
    for evaluator_only in (
        "case_kind", "twin-", "truth", "behaviour", "world_seed", "remedy_if_wrong",
        "role", "partner", "counterfactual", "labeling_seconds",
    ):
        assert evaluator_only not in text


def test_case_ids_are_neutral_shuffled_and_partners_are_tagged(tiny):
    directory, _ = tiny
    visible, evaluator = load_dataset(directory)
    primaries = [case for case in evaluator if case["role"] == "primary"]
    plan_order = list(cross_plan(2, 5, kinds=KINDS, withheld_per_cell=1))
    in_id_order = [PlannedCase(**c["planned"]) for c in primaries]

    assert [r["case_id"] for r in visible] == [f"case-{i:06d}" for i in range(1, len(visible) + 1)]
    assert sorted(in_id_order, key=repr) == sorted(plan_order, key=repr)
    assert in_id_order != plan_order

    ids = {case["case_id"]: case for case in evaluator}
    for case in evaluator:
        if case["role"] == "partner":
            primary = ids[case["primary_case_id"]]
            assert primary["role"] == "primary"
            assert case["twin_group_id"] == primary["twin_group_id"] is not None


def test_every_visible_record_passes_leakage_and_marker_scans(tiny):
    directory, _ = tiny
    report = scan_dataset(*load_dataset(directory))

    assert report["records"] == len(load_dataset(directory)[0])
    assert report["leak_findings"] == []
    assert report["marker_findings"] == []
    assert report["non_neutral_ids"] == []
    assert report["unexpected_visible_keys"] == []


def test_scan_catches_planted_leaks(tiny):
    directory, _ = tiny
    visible, evaluator = load_dataset(directory)
    planted = json.loads(json.dumps(visible))
    truth = evaluator[0]["truth"]
    planted[0]["steps"][0]["input"]["task"] += f" ({truth['expected_queue_id']} for {truth['target_ticket_id']})"
    planted[1]["steps"][0]["input"]["probes"].append({"note": "stale_account_record"})
    planted[2]["case_id"] = "case-F1-swap"

    report = scan_dataset(planted, evaluator)

    assert {f[1] for f in report["leak_findings"]} >= {"answer_pair", "sensitive_token"}
    assert report["marker_findings"]
    assert report["non_neutral_ids"] == ["case-F1-swap"]


def test_dataset_is_deterministic_across_process_counts(tmp_path):
    a = build_dataset(tmp_path / "a", per_cell=1, seed=9, processes=1, kinds=KINDS[:1])
    b = build_dataset(tmp_path / "b", per_cell=1, seed=9, processes=2, kinds=KINDS[:1])

    assert a["manifest"]["files"] == b["manifest"]["files"]


def test_build_refuses_a_used_directory(tmp_path):
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "x").write_text("x", encoding="utf-8")

    with pytest.raises(FileExistsError):
        build_dataset(tmp_path / "used", per_cell=1, seed=1)


def test_withheld_cases_are_balanced_and_labelled_insufficient(tiny):
    plan = cross_plan(per_cell=6, seed=3, withheld_per_cell=2)
    cells = Counter((p.case_kind, p.behaviour) for p in plan if p.evidence_condition == "withheld")

    assert set(cells.values()) == {2}
    assert len(cells) == 50

    directory, _ = tiny
    visible, evaluator = load_dataset(directory)
    for record, case in zip(visible, evaluator):
        if case["role"] != "primary":
            continue
        withheld = case["planned"]["evidence_condition"] == "withheld"
        assert (record["steps"][-1]["target"]["verb"] == "insufficient_evidence") is withheld


def test_shortcut_audit_runs_and_reports_every_feature(tiny):
    directory, _ = tiny
    results = shortcut_audit(*load_dataset(directory), ENCODING)

    assert {r.feature for r in results} == {
        "step_count", "error_present", "denied_present", "input_tokens", "source_gap_hours",
        "ticket_text", "recency_days", "history_events",
    }
    assert all(0.0 <= r.accuracy <= 1.0 for r in results)


def test_tags_mark_primaries_only_and_compound_matches_the_rule(tiny):
    from packages.support_evaluator.dataset import is_compound

    directory, _ = tiny
    visible, evaluator = load_dataset(directory)
    tags = {json.loads(line)["case_id"]: json.loads(line) for line in (directory / "evaluator" / "tags.jsonl").open()}
    primaries = {c["case_id"]: (v, c) for v, c in zip(visible, evaluator) if c["role"] == "primary"}

    assert set(tags) == set(primaries)
    for case_id, tag in tags.items():
        record, case = primaries[case_id]
        assert tag["compound"] is is_compound(case["truth"], record["steps"][-1]["target"])
        assert tag["first_input_tokens"] > 0


def test_compound_rule():
    from packages.support_evaluator.dataset import is_compound

    truth = {"remedy_if_wrong": "restore_from_source"}
    assert is_compound(truth, {"action": "decide", "verb": "abstain", "args": {}}) is True
    assert is_compound(truth, {"action": "recover", "verb": "restore_from_source", "args": {}}) is False
    assert is_compound(truth, {"action": "decide", "verb": "no_intervention", "args": {}}) is False
    assert is_compound(truth, {"action": "decide", "verb": "insufficient_evidence", "args": {}}) is False
    assert is_compound({"remedy_if_wrong": "abstain"}, {"action": "decide", "verb": "abstain", "args": {}}) is False
