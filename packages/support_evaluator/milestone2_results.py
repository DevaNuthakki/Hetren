"""Write docs/milestone-2/RESULTS.md from the recorded test-split rows (offline, no model call).

Every table is recomputed from the ``rows-<set>.jsonl`` files of test runs
#1–#4 (``docs/milestone-2/TEST_RUN_LOG.md``) with ``Source.summarize`` and
``metrics.paired_bootstrap``; the run stops if a recomputed summary differs
from the ``summary-<set>.json`` the run wrote. The prose around the tables is
fixed text in this script. The rows are gitignored, so this runs on the
operator's machine.

``python -m packages.support_evaluator.milestone2_results`` rewrites the
document; ``--check`` only compares it with the committed file.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import sys

from packages.support_evaluator.case_sources import load_source
from packages.support_evaluator.metrics import paired_bootstrap


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "docs" / "milestone-2" / "RESULTS.md"
BASELINES = REPO_ROOT / "artifacts" / "milestone-2" / "baselines"
QWEN_A = BASELINES / "qwen-untrained-test" / "qwen-untrained-test-session-A"
QWEN_B = BASELINES / "qwen-untrained-test" / "qwen-untrained-test-session-B"
TIER1 = REPO_ROOT / "artifacts" / "milestone-2" / "dataset-v2", REPO_ROOT / "docs" / "milestone-2" / "splits-v1"
TIER2 = REPO_ROOT / "artifacts" / "milestone-2" / "dataset-v3", REPO_ROOT / "docs" / "milestone-2" / "splits-v2"
LIVE = REPO_ROOT / "artifacts" / "milestone-2" / "live-test-v1"

# (test set, load_source arguments, the Qwen session that ran it)
SETS = (
    ("Tier 1 in-distribution", {"dataset": TIER1[0], "split": TIER1[1] / "test_in_distribution.txt"}, QWEN_A),
    ("Tier 1 held-out", {"dataset": TIER1[0], "split": TIER1[1] / "test_held_out.txt"}, QWEN_A),
    ("Tier 2 in-distribution", {"dataset": TIER2[0], "split": TIER2[1] / "test_in_distribution.txt"}, QWEN_B),
    ("Tier 2 held-out", {"dataset": TIER2[0], "split": TIER2[1] / "test_held_out.txt"}, QWEN_B),
    ("Live", {"live": LIVE}, QWEN_B),
)
SYSTEMS = ("rules v1", "GPT-4.1", "Qwen untrained")


def system_dirs(qwen: Path) -> dict[str, Path]:
    return {"rules v1": BASELINES / "rules-v1-test", "GPT-4.1": BASELINES / "gpt41-test-prompt-v2", "Qwen untrained": qwen}


def row_files() -> list[Path]:
    """Every rows file the document is computed from (the source names follow ``case_sources``)."""
    names = ("tier1-test_in_distribution", "tier1-test_held_out", "tier2-test_in_distribution", "tier2-test_held_out", "live")
    return [d / f"rows-{name}.jsonl" for (_, _, qwen), name in zip(SETS, names) for d in system_dirs(qwen).values()]


HEAD = """\
# Milestone 2 results: baselines on the test splits

All numbers here are test-split results under the frozen evaluation protocol (`docs/milestone-2/EVAL_PROTOCOL.md`, frozen 2026-11-02, no amendments). Every run behind them is logged in `docs/milestone-2/TEST_RUN_LOG.md` (runs #1–#4); each system ran once per test set, and no system or setting was chosen after seeing test results.

## Systems

| system | declared version | test runs | code | cost |
|---|---|---|---|---|
| rules v1 | `RULES_POLICY_VERSION = 1`, single-recovery policy in both tiers | #1 | `31922b7` | $0 (offline) |
| GPT-4.1 | `gpt-4.1-2025-04-14`, prompt version 2, temperature 0, 128 output tokens | #2 | `54feb7b` (runner as of `31922b7`) | $15.63 |
| Qwen untrained | `Qwen/Qwen3-4B-Instruct-2507` at revision `cdbee75f`, prompt version 2, fp16, greedy, 128 new tokens, one Tesla T4 | #3 (tier 1), #4 (tier 2, live) | bundle `31922b7` | $0 (Kaggle) |

GPT-4.1 and Qwen see the same system prompt (version 2) and the same compact evidence, one stateless call per step. Rules v1 is a hand-written policy built for the training families.

## Test sets

| test set | dataset and split | cases | healthy runs |
|---|---|---|---|
| Tier 1 in-distribution | dataset v2, splits v1 `test_in_distribution` | 560 | 176 |
| Tier 1 held-out | dataset v2, splits v1 `test_held_out` (F6 queue misconfiguration, F7 tier format drift) | 960 | 121 |
| Tier 2 in-distribution | dataset v3, splits v2 `test_in_distribution` (up to two recoveries, compounds, distractors) | 256 | 45 |
| Tier 2 held-out | dataset v3, splits v2 `test_held_out` (compounds with F6 or F7) | 400 | 56 |
| Live | live test v1: runs recorded from `gpt-4.1-mini` (tier 1 episodes) | 300 | 121 |

## Findings

Claims follow the protocol's claim rule: "better" means the paired bootstrap 95% interval of the difference excludes zero; every other result is "no significant difference". No correction for multiple comparisons is applied, and all 30 comparisons are reported below.

1. **Rules v1 has the highest decision accuracy on all five test sets**, significantly so against both models on every set (99.5%, 45.7%, 84.4%, 28.2% and 80.3%).
2. **Rules v1 does not transfer to held-out families.** Its accuracy falls from 99.5% to 45.7% (tier 1) and from 84.4% to 28.2% (tier 2), and it gets 1 of 60 live held-out runs right. It applies a recovery to nearly every healthy held-out run: 121 of 121 in tier 1, 52 of 56 in tier 2 and all 30 healthy live tier-format-drift runs. On wrong interventions in the held-out sets, both models are significantly better than rules v1.
3. **GPT-4.1 against untrained Qwen.**
   - Decision accuracy: GPT-4.1 is better on tier 1 held-out (+10.5 pp), tier 2 in-distribution (+4.3 pp) and tier 2 held-out (+4.0 pp). There is no significant difference on tier 1 in-distribution, and Qwen is better on live (+8.7 pp).
   - Wrong interventions: Qwen is better on four sets. On tier 1 held-out both are at 0 of 121.
4. **Untrained Qwen's 0% wrong interventions reflect a bias against acting, not good judgement.**
   - It never applied a recovery on a healthy run. Where it did not choose `no_intervention`, it chose `insufficient_evidence` (47 of 176, 20 of 45 and 27 of 121 healthy runs).
   - It rarely fixes faulty runs either (verified recovery 0–12%), and 10–26% of its episodes end on an invalid action.
   - GPT-4.1 intervenes wrongly on 33% (tier 1) and 51% (tier 2) of healthy in-distribution runs.
5. **No system fixes both faults of a two-recovery label** (0 of 26 in tier 2 in-distribution, 0 of 95 in tier 2 held-out). Rules v1 stops after one recovery by design; GPT-4.1 stops after one in 65–75% of these cases and Qwen in 19–36%.
6. **Proactive detection is near zero for both models.** On single-fault F2/F6 cases, which only a probe reveals, GPT-4.1 scores 0–10% and Qwen 0–5%.
7. **The models' best families are those the run text already shows.** Misleading ticket text and recent tier change score 44–100% for both models in tier 1, tier 2 and live. Families that need a probe or an exact recovery argument (mapping swap, stale account record, mishandled tool error) score 0–23%.

For Milestone 3, the bar is set by these numbers.
- **To beat:** untrained Qwen at 30.4% / 14.3% / 13.3% / 15.2% / 36.7%, and GPT-4.1 on the same sets.
- **To approach:** rules v1 in-distribution.
- **Constraints:** without giving up the near-zero wrong-intervention rate, and with held-out families reported separately.

## Results

Rates are k / n with Wilson 95% intervals in brackets. Decision metrics include undetermined cases; probe-efficiency metrics exclude them and report their count. Paired differences are A − B in percentage points, with the paired bootstrap 95% interval (10,000 resamples, seed 2026); for wrong interventions, a negative difference favours A.
"""

TAIL = """
The live split's held-out families (F6, F7) are 60 runs. All 30 tier-format-drift runs are healthy (the live agent handled the drift), and 29 of 30 queue-misconfiguration runs are labelled `abstain`.

## Reproducing

Every table above was recomputed from the recorded rows (`rows-<set>.jsonl` in the output directories listed in the test-run log) with `case_sources.load_source(...).summarize` and `metrics.paired_bootstrap`, with no model call. The recomputed summaries are identical to the `summary-<set>.json` files the runs wrote.
"""


def _interval(m) -> str:
    if m is None or m["n"] == 0:
        return "–"

    low, high = m["ci95"]
    return f"{100 * m['rate']:.1f}% ({m['k']}/{m['n']}) [{100 * low:.1f}, {100 * high:.1f}]"


def _rate(m) -> str:
    return "–" if m is None or m["n"] == 0 else f"{100 * m['rate']:.1f}% ({m['k']}/{m['n']})"


def _difference(e) -> str:
    if e["difference"] is None:
        return "–"

    low, high = e["ci95"]
    return f"{100 * e['difference']:+.1f} pp [{100 * low:+.1f}, {100 * high:+.1f}] (n={e['n']})"


def load() -> dict[tuple[str, str], tuple[list[dict], dict]]:
    """(test set, system) -> (rows, summary), every summary checked against the one the run wrote."""
    data = {}

    for set_name, arguments, qwen in SETS:
        source = load_source(**arguments)

        for system, directory in system_dirs(qwen).items():
            rows = [json.loads(line) for line in (directory / f"rows-{source.name}.jsonl").open(encoding="utf-8")]

            if sorted(r["case_id"] for r in rows) != sorted(c.case_id for c in source.cases):
                raise SystemExit(f"STOP: {system} on {set_name} was not scored on exactly the split's cases")

            summary = json.loads(json.dumps(source.summarize(rows)))

            if summary != json.loads((directory / f"summary-{source.name}.json").read_text(encoding="utf-8")):
                raise SystemExit(f"STOP: the recomputed summary of {system} on {set_name} differs from the stored one")

            data[set_name, system] = rows, summary

    return data


def tables(data) -> list[str]:
    sets = [name for name, _, _ in SETS]
    out = []
    p = out.append

    p("\n### Primary endpoints\n")
    p("| test set | system | decision accuracy | wrong interventions on healthy runs |")
    p("|---|---|---|---|")
    for set_name in sets:
        for system in SYSTEMS:
            s = data[set_name, system][1]
            p(f"| {set_name} | {system} | {_interval(s['decision_accuracy'])} | {_interval(s['wrong_interventions_on_healthy'])} |")

    p("\n### Paired comparisons\n")
    p("| test set | A − B | decision accuracy: difference [95% CI] | verdict | wrong interventions: difference [95% CI] | verdict |")
    p("|---|---|---|---|---|---|")
    for set_name in sets:
        for a, b in itertools.combinations(SYSTEMS, 2):
            result = paired_bootstrap(data[set_name, a][0], data[set_name, b][0])
            cells = []

            for endpoint in ("decision_accuracy", "wrong_interventions_on_healthy"):
                e = result[endpoint]
                verdict = e["verdict"].replace("A better", f"{a} better").replace("B better", f"{b} better")
                cells += [_difference(e), verdict]

            p(f"| {set_name} | {a} − {b} | " + " | ".join(cells) + " |")

    p("\n### Secondary metrics\n")
    p("| test set | system | exact match | verified recovery | invalid actions | failed recovery calls "
      "| `insufficient_evidence` recall | `abstain` recall | `no_intervention` recall | mean probes (oracle) | undetermined |")
    p("|---|---|---|---|---|---|---|---|---|---|---|")
    for set_name in sets:
        for system in SYSTEMS:
            s = data[set_name, system][1]
            probes = s["probes"]
            p(f"| {set_name} | {system} | {_rate(s['exact_match'])} | {_rate(s['verified_recovery_rate'])} "
              f"| {_rate(s['invalid_actions'])} | {s['failed_recovery_calls']} | {_rate(s['insufficient_evidence']['recall'])} "
              f"| {_rate(s['abstain']['recall'])} | {_rate(s['no_intervention']['recall'])} "
              f"| {probes['mean_probes']} ({probes['oracle_mean_probes']}) | {probes['undetermined']} |")

    p("\n### Tier 2 sequence metrics\n")
    p("| test set | system | exact sequence match | longer than label | stopped after one of two | two-recovery labels |")
    p("|---|---|---|---|---|---|")
    for set_name in sets[2:4]:
        for system in SYSTEMS:
            q = data[set_name, system][1]["sequence"]
            p(f"| {set_name} | {system} | {_rate(q['exact_sequence_match'])} | {_rate(q['longer_than_label'])} "
              f"| {_rate(q['stopped_after_one_of_two'])} | {_rate(q['two_recovery_labels'])} |")

    p("\n### Groups and slices (decision accuracy)\n")
    p("| test set | system | training families | held-out families | proactive detection | compound slice | length-reweighted |")
    p("|---|---|---|---|---|---|---|")
    for set_name in sets:
        for system in SYSTEMS:
            s = data[set_name, system][1]
            group = lambda key: _rate(s[key]["decision_accuracy"]) if s.get(key) else "–"
            slices = s.get("slices") or {}
            reweighted = slices.get("length_matched", {}).get("reweighted_accuracy")
            p(f"| {set_name} | {system} | {group('training_families')} | {group('held_out_families')} "
              f"| {group('proactive_detection')} | {_rate(slices['compound']) if slices else '–'} "
              f"| {'–' if reweighted is None else f'{100 * reweighted:.1f}%'} |")

    p("\n### Live split by label category (decision accuracy)\n")
    categories = sorted(data["Live", SYSTEMS[0]][1]["live_categories"])
    p("| system | " + " | ".join(categories) + " |")
    p("|---|" + "---|" * len(categories))
    for system in SYSTEMS:
        by_category = data["Live", system][1]["live_categories"]
        p(f"| {system} | " + " | ".join(_rate(by_category.get(c)) for c in categories) + " |")

    for set_name in sets:
        p(f"\n### Per family: {set_name}\n")
        families = data[set_name, SYSTEMS[0]][1]["by_family"]
        p("| family | held out | " + " | ".join(SYSTEMS) + " |")
        p("|---|---|" + "---|" * len(SYSTEMS))
        for family in sorted(families, key=lambda f: (families[f]["held_out"], f)):
            cells = [_rate(data[set_name, s][1]["by_family"][family]["decision_accuracy"]) for s in SYSTEMS]
            p(f"| `{family}` | {'yes' if families[family]['held_out'] else 'no'} | " + " | ".join(cells) + " |")

    return out


def render() -> str:
    return HEAD + "\n".join(tables(load())) + "\n" + TAIL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument("--check", action="store_true", help="compare with --out instead of writing it")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    missing = [str(p.relative_to(REPO_ROOT)) for p in row_files() if not p.exists()]

    if missing:
        print(f"STOP: recorded rows are missing: {', '.join(missing)}", file=sys.stderr)
        return 2

    text = render()

    if args.check:
        if args.out.read_text(encoding="utf-8") != text:
            print(f"STOP: {args.out} differs from the regenerated results", file=sys.stderr)
            return 1

        print(f"{args.out} matches the regenerated results")
        return 0

    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "load",
    "render",
    "row_files",
    "tables",
]
