import json
import random
import socket

import pytest

from environments.support.fixtures import SupportEnvironment
from environments.support.generator import generate_world
from packages.action_space import PROBE_BUDGET, parse_action
from packages.hetren_evidence import compact_evidence, render_evidence
from packages.support_agent import BEHAVIOURS
from packages.support_evaluator import assert_no_leaks, scan_content, sensitive_tokens
from packages.support_evaluator.injectors import INJECTORS, inject
from packages.support_evaluator.labeler import (
    RECOVERY_ORDER,
    label_case,
    label_run,
    verify_label,
)
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.sampling import run_agent_on


WORLD_SEED, CASE_SEED = 3, 1003


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _run(kind, variant, behaviour, world_seed=WORLD_SEED, case_seed=CASE_SEED, transform=None):
    case = inject(kind, generate_world(world_seed), random.Random(case_seed), variant)
    environment = SupportEnvironment(case.spec)
    record = run_agent_on(environment, case.truth.target_ticket_id, behaviour)
    evidence = record.evidence_payload()

    if transform is not None:
        evidence = transform(evidence)

    return case, environment, evidence


def _withhold_lookup(evidence):
    withheld = json.loads(json.dumps(evidence))
    lookup = next(r["invocation_id"] for r in withheld["stage_records"] if r["tool_name"] == "lookup_account")
    withheld["stage_records"] = [
        r for r in withheld["stage_records"]
        if not (r["invocation_id"] == lookup and r["stage"] in ("attempted", "observed"))
    ]
    return withheld


# Expected label (verb) for every case kind x variant x behaviour

N, RR, RO, SM, RS, AB = (
    "no_intervention", "rerun", "reroute", "set_mapping", "restore_from_source", "abstain",
)

EXPECTED = {
    #                                              trust retry give_up follow_text case_sensitive
    ("mapping_swap", "swap"):                       (SM, SM, SM, SM, SM),
    ("mapping_swap", "redirect"):                   (SM, SM, SM, SM, SM),
    ("mapping_swap", "nway"):                       (SM, SM, SM, SM, SM),
    ("stale_account_record", "default"):            (RS, RS, RS, RS, RS),
    ("mishandled_tool_error", "transient"):         (RR, N, RR, RR, RR),
    ("mishandled_tool_error", "persistent"):        (AB, AB, AB, AB, AB),
    ("misleading_ticket_text", "claim_false"):      (N, N, N, RO, N),
    ("misleading_ticket_text", "claim_true"):       (N, N, N, N, N),
    ("missing_account", "unmapped_ref"):            (SM, SM, SM, SM, SM),
    ("missing_account", "deleted_account"):         (RO, RO, RO, RO, RO),
    ("queue_misconfiguration", "description_swap"): (AB, AB, AB, AB, AB),
    ("tier_format_drift", "case"):                  (N, N, N, N, RS),
    ("tier_format_drift", "abbreviation"):          (RS, RS, RS, RS, RS),
    ("tier_format_drift", "whitespace"):            (RS, RS, RS, RS, RS),
    ("merged_account", "default"):                  (N, N, RO, N, N),
    ("recent_tier_change", "default"):              (N, N, N, N, N),
    ("transient_error_retried", "default"):         (RR, N, RR, RR, RR),
    ("clean_world", "default"):                     (N, N, N, N, N),
}

EXPECTED_RULE = {
    N: {"outcome_correct"},
    RR: {"smallest_verified_change"},
    RO: {"smallest_verified_change"},
    SM: {"smallest_verified_change"},
    RS: {"smallest_verified_change"},
    AB: {"persistent_tool_error", "no_verified_recovery"},
}


def test_table_covers_every_case_and_behaviour():
    assert set(EXPECTED) == {(k, v) for k, (_, vs) in INJECTORS.items() for v in vs}
    assert all(len(row) == len(BEHAVIOURS) for row in EXPECTED.values())


@pytest.mark.parametrize(("kind", "variant"), sorted(EXPECTED))
def test_run_labels_match_the_expected_table(kind, variant):
    for behaviour, expected in zip(BEHAVIOURS, EXPECTED[(kind, variant)]):
        case, environment, evidence = _run(kind, variant, behaviour)
        label = label_run(case, environment, evidence, behaviour)

        assert label.verb == expected, behaviour
        assert label.rule in EXPECTED_RULE[expected], (behaviour, label.rule)
        parse_action(label.label)

        if label.label["action"] == "recover" and label.verb != "rerun":
            assert label.label["args"] in list(case.truth.remedy_if_wrong_arguments), behaviour


@pytest.mark.parametrize(("kind", "variant"), sorted(EXPECTED))
def test_labels_hold_on_a_second_world(kind, variant):
    case, environment, evidence = _run(kind, variant, "trust", world_seed=11, case_seed=2011)
    assert label_run(case, environment, evidence, "trust").verb == EXPECTED[(kind, variant)][0]


def test_persistent_errors_abstain_and_data_errors_do_not():
    persistent = label_run(*_run("mishandled_tool_error", "persistent", "trust")[:3], "trust")
    assert persistent.rule == "persistent_tool_error"
    assert [r["status"] for r in persistent.retry_results] == ["failed"]
    assert {s.action["verb"] for s in persistent.sandboxes} == {"rerun"}

    unmapped = label_run(*_run("missing_account", "unmapped_ref", "trust")[:3], "trust")
    assert unmapped.retry_results == ()
    assert unmapped.verb == "set_mapping"


def test_unexplained_absence_is_insufficient_evidence_but_failed_calls_are_not():
    case, environment, evidence = _run("mapping_swap", "swap", "trust", transform=_withhold_lookup)
    label = label_run(case, environment, evidence, "trust")

    assert label.verb == "insufficient_evidence"
    assert label.rule == "unexplained_absence"
    assert set(label.missing) == {"stage_record_gap", "attempted_stage_lookup_account", "observation_lookup_account"}
    assert label.label["args"] == {"missing": list(label.missing)}

    failed = label_run(*_run("missing_account", "deleted_account", "trust")[:3], "trust")
    assert failed.verb != "insufficient_evidence"


def test_provenance_records_sandboxes_and_the_smallest_change():
    case, environment, evidence = _run("mishandled_tool_error", "transient", "trust")
    label = label_run(case, environment, evidence, "trust")
    provenance = label.provenance_payload()

    assert provenance["sandboxes_run"] == len(label.sandboxes) > 1
    assert provenance["sandboxes_verified"] == len(label.label_set) >= 2
    assert {a["verb"] for a in label.label_set} >= {"rerun", "reroute"}
    assert label.verb == "rerun"
    assert label.label == min(label.label_set, key=lambda a: RECOVERY_ORDER[a["verb"]])
    assert all(not s.verified for s in label.sandboxes if not s.changed_state)


# Planted mislabels are rejected by independent verification


@pytest.mark.parametrize(
    ("kind", "variant", "behaviour", "wrong"),
    [
        ("mapping_swap", "swap", "trust", {"action": "decide", "verb": "no_intervention", "args": {}}),
        ("mapping_swap", "swap", "trust", "reroute_to_expected"),
        ("stale_account_record", "default", "trust", "reroute_to_expected"),
        ("queue_misconfiguration", "description_swap", "trust", "reroute_to_expected"),
        ("mishandled_tool_error", "persistent", "trust", "reroute_to_expected"),
        ("merged_account", "default", "trust", {"action": "decide", "verb": "abstain", "args": {"reason": "x"}}),
        ("recent_tier_change", "default", "trust", {"action": "recover", "verb": "rerun", "args": {}}),
        ("missing_account", "unmapped_ref", "trust", {"action": "decide", "verb": "insufficient_evidence", "args": {"missing": ["x"]}}),
    ],
)
def test_planted_mislabels_fail_verification(kind, variant, behaviour, wrong):
    case, environment, evidence = _run(kind, variant, behaviour)

    if wrong == "reroute_to_expected":
        wrong = {"action": "recover", "verb": "reroute",
                 "args": {"ticket_id": case.truth.target_ticket_id, "queue_id": case.truth.expected_queue_id}}

    assert verify_label(case, environment, evidence, behaviour, wrong) is False


@pytest.mark.parametrize(("kind", "variant"), [
    ("mapping_swap", "swap"), ("stale_account_record", "default"), ("missing_account", "deleted_account"),
    ("queue_misconfiguration", "description_swap"), ("merged_account", "default"),
])
def test_true_labels_pass_verification(kind, variant):
    case, environment, evidence = _run(kind, variant, "trust")
    label = label_run(case, environment, evidence, "trust")

    assert verify_label(case, environment, evidence, "trust", label.label) is True


# Probe labels and twin groups (full labels on representative cases)


@pytest.fixture(scope="module")
def full_labels():
    cases = [
        ("mapping_swap", "swap", "trust"), ("merged_account", "default", "trust"),
        ("stale_account_record", "default", "trust"), ("recent_tier_change", "default", "trust"),
        ("queue_misconfiguration", "description_swap", "trust"), ("missing_account", "deleted_account", "trust"),
    ]
    return {key: label_case(PlannedCase(*key, WORLD_SEED, CASE_SEED)) for key in cases}


def test_f1_and_the_merged_account_form_one_twin_group(full_labels):
    f1 = full_labels[("mapping_swap", "swap", "trust")].probe_label
    merged = full_labels[("merged_account", "default", "trust")].probe_label

    assert f1.twin_group_id is not None
    assert f1.twin_group_id == merged.twin_group_id
    assert "merged_account/default" in f1.consistent
    # The separating probe reads the ownership or merge record itself.
    assert [(p["verb"], p["args"].get("entity")) for p in f1.probes] in (
        [("find_owners", None)], [("inspect", "account")], [("history", "account")],
    )
    assert f1.determined and merged.determined


def test_proactive_detection_twins_are_resolved_by_configuration_not_history(full_labels):
    stale = full_labels[("stale_account_record", "default", "trust")].probe_label
    recent = full_labels[("recent_tier_change", "default", "trust")].probe_label
    f6 = full_labels[("queue_misconfiguration", "description_swap", "trust")].probe_label

    for label in (stale, recent, f6):
        assert label.twin_group_id is not None

    probes = lambda label: [(p["verb"], p["args"].get("entity")) for p in label.probes]
    # F6 is told apart through the routing policy; history never separates it
    # from the recent tier change, which comes from the generator.
    assert ("inspect", "routing_policy") in probes(f6)
    assert ("inspect", "routing_policy") in probes(recent)
    assert ("history", "account") not in probes(recent)
    assert {verb for verb, _ in probes(stale)} & {"compare_with_source", "history", "inspect"}


def test_twin_cases_carry_counterfactual_partners(full_labels):
    f1 = full_labels[("mapping_swap", "swap", "trust")]
    partner_kinds = {p["counterfactual"].split("/")[0] for p in f1.partners}

    assert "merged_account" in partner_kinds
    assert all(p["steps"][-1]["target"]["action"] in ("recover", "decide") for p in f1.partners)
    assert full_labels[("missing_account", "deleted_account", "trust")].partners == ()


def test_unambiguous_runs_need_no_probes_and_have_no_twin(full_labels):
    deleted = full_labels[("missing_account", "deleted_account", "trust")].probe_label

    assert deleted.twin_group_id is None
    assert deleted.probes == ()
    assert deleted.initial_label_entropy == 0


def test_probe_labels_are_valid_actions_within_budget(full_labels):
    for label in full_labels.values():
        assert len(label.probe_label.probes) <= PROBE_BUDGET

        for probe in label.probe_label.probes:
            assert parse_action(probe).kind == "probe"


def test_twin_group_ids_are_stable_and_evaluator_only(full_labels):
    again = label_case(PlannedCase("mapping_swap", "swap", "trust", WORLD_SEED, CASE_SEED))
    twin = full_labels[("mapping_swap", "swap", "trust")].probe_label.twin_group_id

    assert again.probe_label.twin_group_id == twin
    assert twin.startswith("twin-") and "twin-" in sensitive_tokens()
    findings = scan_content({"diagnosis_input": {"note": twin}})
    assert [f.kind for f in findings] == ["sensitive_token"]

    compact = render_evidence(compact_evidence(_run("mapping_swap", "swap", "trust")[2]))
    assert "twin" not in compact
    assert_no_leaks(scan_content({"compact": json.loads(compact)}))


def test_case_label_provenance_is_complete(full_labels):
    payload = full_labels[("mapping_swap", "swap", "trust")].provenance_payload()

    assert payload["run_label"]["rule"] == "smallest_verified_change"
    assert payload["run_label"]["sandboxes_run"] > 0
    assert payload["probe_label"]["twin_group_id"].startswith("twin-")
    assert payload["probe_label"]["consistent_hypotheses"][0] == "actual"
