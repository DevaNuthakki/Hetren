"""The GGUF acceptance check (Amendment 2): the three criteria, pooled pairing, agreement, stops, shipping."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from packages.hetren_serving.export import LLAMA_CPP_COMMIT, STEM
from packages.support_evaluator import gguf_check as check
from packages.support_evaluator.metrics import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED


ROOT = Path(__file__).resolve().parents[2]
FAST = 300  # resamples in tests; the CLI always uses the protocol's 10,000


def _row(case_id, verb="no_intervention", correct=True, recovered=False):
    action = "decide" if verb in ("no_intervention", "insufficient_evidence", "abstain") else "recover"
    recovery = [{"action": "recover", "verb": "rerun", "args": {}}] if recovered else []
    return {"case_id": case_id, "label": {"action": action, "verb": verb, "args": {}}, "correct": correct,
            "exact": correct, "recoveries": recovery, "failure": None, "recovery_failures": [],
            "final": {"action": "decide", "verb": verb, "args": {}}}


def _tier(n, prefix="case", healthy=0.4):
    return [_row(f"{prefix}-{i:04d}", "no_intervention" if i < healthy * n else "rerun") for i in range(n)]


def _calls(rows, tier, text='{"action": "decide", "verb": "no_intervention", "args": {}}', ids=(1, 151645)):
    return [{"tier": tier, "case_id": r["case_id"], "call": 0, "text": text, "seconds": 2.0, "at_limit": False,
             "finite": True, "discarded": False, "token_ids": list(ids)} for r in rows]


def _systems(n1=550, n2=250):
    fp16 = {1: {"rows": _tier(n1)}, 2: {"rows": _tier(n2)}}  # the same case IDs in both tiers, as can happen

    for t in (1, 2):
        fp16[t]["calls"] = _calls(fp16[t]["rows"], t)

    return copy.deepcopy(fp16), fp16


def _flip(rows, count, start=0, field="correct"):
    for r in rows[start:start + count]:
        if field == "correct":
            r["correct"] = r["exact"] = False
        else:
            r["recoveries"] = [{"action": "recover", "verb": "rerun", "args": {}}]


def test_protocol_constants():
    assert (BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, check.THRESHOLD) == (10_000, 2026, -0.02)
    protocol = (ROOT / "docs/milestone-2/EVAL_PROTOCOL.md").read_text(encoding="utf-8")
    log = (ROOT / "docs/milestone-3/VALIDATION_LOG.md").read_text(encoding="utf-8")
    for digest in check.FP16_ROWS_SHA256.values():
        assert f"`{digest[:8]}…`" in protocol and digest in log
    assert check.DECLARED == {"platform": "mac", "threads": 6, "cache_prompt": True}
    assert check.SHIPPING_ORDER == ("Q4_K_M", "Q8_0")


def test_an_export_identical_to_fp16_is_accepted_with_full_agreement():
    gguf, fp16 = _systems()
    result = check.check_variant("Q4_K_M", gguf, fp16, resamples=FAST)
    assert result["accepted"] and all(c["holds"] for c in result["criteria"].values())
    assert result["pooled"]["cases"] == 800  # tier-keyed: the shared case IDs are not merged
    assert result["episode_agreement"] == {"agree": 800, "cases": 800, "rate": 1.0}
    assert result["unexpected_stops"] == 0


def test_a_tier_point_estimate_below_minus_two_points_rejects():
    gguf, fp16 = _systems()
    _flip(gguf[2]["rows"], 6, start=150)  # 6 of 250 = −2.4 pp in tier 2; pooled −0.75 pp
    result = check.check_variant("Q4_K_M", gguf, fp16, resamples=FAST)
    assert result["criteria"]["tier2_accuracy_point_estimate"] == {"value": -0.024, "threshold": -0.02, "holds": False}
    assert result["criteria"]["pooled_accuracy_lower_bound"]["holds"] and not result["accepted"]


def test_exactly_minus_two_points_in_a_tier_holds():
    gguf, fp16 = _systems()
    _flip(gguf[2]["rows"], 5, start=150)  # 5 of 250 = −2.0 pp
    assert check.check_variant("Q4_K_M", gguf, fp16, resamples=FAST)["criteria"]["tier2_accuracy_point_estimate"]["holds"]


def test_a_pooled_lower_bound_below_minus_two_points_rejects():
    gguf, fp16 = _systems()
    _flip(gguf[1]["rows"], 10, start=300)  # −1.8 pp in tier 1, −1.6 pp in tier 2: point estimates hold
    _flip(gguf[2]["rows"], 4, start=150)
    result = check.check_variant("Q8_0", gguf, fp16, resamples=FAST)
    assert result["criteria"]["tier1_accuracy_point_estimate"]["holds"]
    assert result["criteria"]["tier2_accuracy_point_estimate"]["holds"]
    assert not result["criteria"]["pooled_accuracy_lower_bound"]["holds"] and not result["accepted"]


def test_significantly_more_wrong_interventions_in_a_tier_rejects():
    gguf, fp16 = _systems()
    _flip(gguf[1]["rows"], 20, field="recoveries")  # 20 of 220 healthy tier 1 runs now intervene
    result = check.check_variant("Q4_K_M", gguf, fp16, resamples=FAST)
    assert result["criteria"]["tier1_wrong_interventions_not_worse"]["ci95"][0] > 0
    assert not result["criteria"]["tier1_wrong_interventions_not_worse"]["holds"] and not result["accepted"]


def test_pooled_pairing_is_by_tier_and_case_id():
    gguf, fp16 = _systems(n1=10, n2=10)  # every case ID occurs in both tiers
    _flip(gguf[2]["rows"], 10)
    pooled = check.check_variant("Q8_0", gguf, fp16, resamples=FAST)["pooled"]["bootstrap"]["decision_accuracy"]
    assert pooled["n"] == 20 and pooled["difference"] == -0.5


def test_episode_agreement_compares_each_calls_parsed_action_in_order():
    rows = [_row("a"), _row("b"), _row("c")]
    probe = '{"action": "probe", "verb": "history", "args": {"entity": "account", "id": "A-1"}}'
    decide = '{"action": "decide", "verb": "no_intervention", "args": {}}'
    fp16 = [{"case_id": "a", "call": 0, "text": probe}, {"case_id": "a", "call": 1, "text": decide},
            {"case_id": "b", "call": 0, "text": decide}, {"case_id": "c", "call": 0, "text": decide}]
    gguf = [{"case_id": "a", "call": 1, "text": decide}, {"case_id": "a", "call": 0, "text": " " + probe + "\n"},
            {"case_id": "b", "call": 0, "text": probe}, {"case_id": "b", "call": 1, "text": decide},
            {"case_id": "c", "call": 0, "text": "not json", "discarded": True}, {"case_id": "c", "call": 0, "text": decide}]
    result = check.episode_agreement(gguf, fp16, [r["case_id"] for r in rows])
    assert result == {"cases": 3, "agree": 2, "rate": 0.6667, "differing": ["b"]}


def test_generations_not_ending_on_the_models_end_tokens_are_counted_with_their_cases():
    calls = [{"case_id": "a", "token_ids": [5, 151645]}, {"case_id": "b", "token_ids": [5, 151643]},
             {"case_id": "c", "token_ids": [5, 128247]}, {"case_id": "d", "token_ids": []},
             {"case_id": "e", "token_ids": [5, 128247], "discarded": True}]
    assert check.unexpected_stops(calls, 2) == {"calls": 2, "cases": ["tier 2 c", "tier 2 d"], "last_tokens": [128247, None]}


def test_the_reported_stops_reach_the_result():
    gguf, fp16 = _systems(n1=20, n2=20)
    gguf[2]["calls"][3]["token_ids"] = [7, 128247]
    result = check.check_variant("Q8_0", gguf, fp16, resamples=FAST)
    assert result["unexpected_stops"] == 1
    assert result["tiers"]["tier2"]["unexpected_stops"]["cases"] == ["tier 2 case-0003"]


def test_shipping_rule():
    accepted = {"accepted": True, "tiers": {"tier1": {"bootstrap": {}}, "tier2": {"bootstrap": {}}},
                "pooled": {"bootstrap": {}}}
    rejected = {**accepted, "accepted": False}
    assert check.ship({"Q4_K_M": accepted, "Q8_0": accepted})["shipped"] == "Q4_K_M"
    assert check.ship({"Q4_K_M": rejected, "Q8_0": accepted})["shipped"] == "Q8_0"
    neither = check.ship({"Q4_K_M": rejected, "Q8_0": rejected})
    assert neither["shipped"] == "Q8_0" and neither["state_differences"] and neither["accepted"] == []

    with pytest.raises(ValueError, match="expected checks"):
        check.ship({"Q8_0": accepted})


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_fp16(tmp_path):
    hashes = {}

    for tier in (1, 2):
        d = tmp_path / check.FP16_DIR / f"tier{tier}"
        d.mkdir(parents=True)
        rows = _tier(5)
        (d / f"rows-tier{tier}-validation.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (d / "calls.jsonl").write_text("".join(json.dumps(c) + "\n" for c in _calls(rows, tier)))
        hashes[tier] = _sha(d / f"rows-tier{tier}-validation.jsonl")
        (d / f"validation-tier{tier}.json").write_text(json.dumps({"files": {
            f"rows-tier{tier}-validation.jsonl": hashes[tier], "calls.jsonl": _sha(d / "calls.jsonl")}}))

    return hashes


def test_fp16_inputs_must_have_the_pinned_and_recorded_hashes(tmp_path):
    hashes = _write_fp16(tmp_path)
    loaded = check.load_fp16(tmp_path, hashes)
    assert len(loaded[1]["rows"]) == 5 and len(loaded[2]["calls"]) == 5

    with pytest.raises(ValueError, match="is not the fp16 comparator"):
        check.load_fp16(tmp_path, {**hashes, 2: "0" * 64})

    with (tmp_path / check.FP16_DIR / "tier1" / "calls.jsonl").open("a") as calls:
        calls.write("{}\n")

    with pytest.raises(ValueError, match="calls.jsonl does not have the hash"):
        check.load_fp16(tmp_path, hashes)


@pytest.mark.skipif(not (ROOT / check.FP16_DIR).exists(), reason="the fp16 validation run is not downloaded")
def test_the_real_fp16_comparator_loads():
    loaded = check.load_fp16()
    assert {t: len(loaded[t]["rows"]) for t in (1, 2)} == {1: 550, 2: 250}
    assert {t: len(loaded[t]["calls"]) for t in (1, 2)} == {1: 743, 2: 703}


MANIFEST = {"gguf": {f"{STEM}-q4_k_m.gguf": {"sha256": "q4" * 32}, f"{STEM}-q8_0.gguf": {"sha256": "q8" * 32}}}


def _write_run(tmp_path, sizes=None, **metadata_changes):
    sizes = sizes or check.VALIDATION_SIZES

    for tier in (1, 2):
        d = tmp_path / "Q4_K_M" / f"tier{tier}"
        d.mkdir(parents=True)
        rows = _tier(sizes[tier])
        metadata = {"variant": "Q4_K_M", "gguf_sha256": "q4" * 32, "platform": "mac", "threads": 6,
                    "cache_prompt": True, "llama_cpp_commit": LLAMA_CPP_COMMIT, "tier": tier, **metadata_changes}
        (d / "metadata.json").write_text(json.dumps(metadata))
        (d / f"rows-tier{tier}-validation.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (d / "calls.jsonl").write_text("".join(json.dumps(c) + "\n" for c in _calls(rows, tier)))
        files = {p.name: _sha(p) for p in d.iterdir()}
        (d / f"validation-Q4_K_M-tier{tier}.json").write_text(json.dumps({"files": files}))


def test_the_gguf_run_must_be_complete_declared_and_unchanged(tmp_path):
    _write_run(tmp_path / "ok")
    loaded = check.load_gguf(tmp_path / "ok", "Q4_K_M", MANIFEST)
    assert len(loaded[1]["rows"]) == 550 and loaded[2]["metadata"]["tier"] == 2

    _write_run(tmp_path / "threads", threads=4)
    with pytest.raises(ValueError, match="not the declared run.*'threads': 4"):
        check.load_gguf(tmp_path / "threads", "Q4_K_M", MANIFEST)

    _write_run(tmp_path / "cache", cache_prompt=False)
    with pytest.raises(ValueError, match="not the declared run"):
        check.load_gguf(tmp_path / "cache", "Q4_K_M", MANIFEST)

    _write_run(tmp_path / "short", sizes={1: 550, 2: 249})
    with pytest.raises(ValueError, match="expected 250 cases once each, found 249"):
        check.load_gguf(tmp_path / "short", "Q4_K_M", MANIFEST)

    with pytest.raises(ValueError, match="Q8_0 tier 1 run is not complete"):
        check.load_gguf(tmp_path / "ok", "Q8_0", MANIFEST)

    with (tmp_path / "ok" / "Q4_K_M" / "tier2" / "calls.jsonl").open("a") as calls:
        calls.write("{}\n")

    with pytest.raises(ValueError, match="calls.jsonl does not have the hash"):
        check.load_gguf(tmp_path / "ok", "Q4_K_M", MANIFEST)
