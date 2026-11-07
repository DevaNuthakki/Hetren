"""Write docs/milestone-3/RESULTS.md from recorded rows, offline (no model call).

Follows ``milestone2_results``: summaries are recomputed and compared with
the run's stored summaries, and comparisons use ``metrics.paired_bootstrap``.
Input rows must match their logged hashes and the declared cases exactly.
Selection and validation tables also come from existing rows, never a new
evaluation. Fixed prose describes the logged training history and limitations.

``python -m packages.support_evaluator.milestone3_results`` writes the report;
``--check`` compares its UTF-8 bytes without writing. Raw artifacts are
gitignored, so full regeneration requires the operator's local artifacts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import sys

from packages.support_evaluator import milestone2_results as m2
from packages.support_evaluator.case_sources import load_source
from packages.support_evaluator.metrics import decision_metrics, paired_bootstrap, rate
from packages.support_evaluator.selection_subset import SUBSET_DIR, selection_score


REPO_ROOT = m2.REPO_ROOT
RESULTS = REPO_ROOT / "docs/milestone-3/RESULTS.md"
TEST_LOG = REPO_ROOT / "docs/milestone-2/TEST_RUN_LOG.md"
VALIDATION_LOG = REPO_ROOT / "docs/milestone-3/VALIDATION_LOG.md"
ARTIFACTS = REPO_ROOT / "artifacts/milestone-3"
SELECTION = ARTIFACTS / "selection-run-1/qlora-selection"
VALIDATION = ARTIFACTS / "validation-run-1/qlora-validation"
REFERENCE = m2.BASELINES / "qwen-untrained-validation/qwen-untrained"
FT = "Qwen fine-tuned"
SYSTEMS = (*m2.SYSTEMS, FT)
STEPS = (264, 528, 792, 1055)
NAMES = ("tier1-test_in_distribution", "tier1-test_held_out", "tier2-test_in_distribution",
         "tier2-test_held_out", "live")
ENDPOINTS = ("decision_accuracy", "wrong_interventions_on_healthy")
TIER2_SETS = ("Tier 2 in-distribution", "Tier 2 held-out")

HEAD = """\
# Milestone 3 results: fine-tuned diagnosis on the test splits

Results follow the frozen evaluation protocol (`docs/milestone-2/EVAL_PROTOCOL.md`, frozen 2026-11-02) and Amendment 1 (2026-11-03). Test runs #1–#6 are recorded in `docs/milestone-2/TEST_RUN_LOG.md`; training, checkpoint selection and full validation are recorded in `docs/milestone-3/VALIDATION_LOG.md`. Every declared system ran once per test set. Only checkpoint selection on validation determined the fine-tuned model; no test result changed a checkpoint, prompt, decoding setting or metric.

## Systems

| system | declared version | test runs | code | cost |
|---|---|---|---|---|
| rules v1 | `RULES_POLICY_VERSION = 1`, single recovery in both tiers | #1 | `31922b7` | $0 (offline) |
| GPT-4.1 | `gpt-4.1-2025-04-14`, prompt version 2, temperature 0, 128 output tokens | #2 | `54feb7b` (runner as of `31922b7`) | $15.63 |
| Qwen untrained | `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`, fp16, greedy, 128 new tokens | #3, #4 | bundle `31922b7` | $0 (Kaggle) |
| Qwen fine-tuned | same base, revision, prompt and decoding; QLoRA checkpoint `0792`, adapter merged into the fp16 base | #5, #6 | bundles `8007e69`, `7238a80` (evaluation code unchanged) | $0 (Kaggle) |

All model policies receive prompt version 2 and the same compact evidence, with one stateless call per step. Qwen evaluation uses one visible Tesla T4 per process and one generation at a time. Fine-tuned selection, validation and test used Python 3.13.16, torch 2.11.0+cu130, transformers 4.56.2, accelerate 1.10.1, tokenizers 0.22.2 and peft 0.17.1. Rules v1 was built for the training families and is frozen.

## Training history

Training used only the train splits of dataset v2 (tier 1) and dataset v3 (tier 2), including contrast partners. Duplicate examples were deduplicated; 58 conflicting inputs (116 examples) were dropped. The initial file held 17,082 examples and 32,594,218 tokens. Loss applied only to assistant tokens, with Amendment 1's per-tier rare-verb weights (capped at 3).

QLoRA used a 4-bit NF4 base with double quantisation, fp16 compute, fp32 LoRA weights, rank 16, alpha 32, dropout 0.05, and all seven declared attention/MLP projections. Paged 8-bit AdamW used learning rate 1e-4, cosine decay, 3% warmup, clipping 1.0 and no weight decay; effective batch 16, sequence length 2,560 without truncation or packing, gradient checkpointing and seed 2029. The pinned training libraries included bitsandbytes 0.50.2; the custom loop did not use trl.

The train-only throughput pilot measured 337.9 tokens/s on one T4 and 638.9 on two. The faster configuration projected 14.17 hours per epoch, so the predeclared 14-hour rule kept every non-probe example and sampled probes at rate 0.9707. This retained 16,869 examples (213 probes dropped), giving 1,055 optimiser steps and candidates at 264, 528, 792 and 1,055. The last step contained five examples and divided its loss by five.

| training run | date (UTC) | steps | outcome |
|---|---|---|---|
| session 1, bundle `7e9089e` | 2026-11-03–04 | 1–528 | completed; checkpoints 264 and 528 saved |
| session 2, first attempt, same bundle | 2026-11-04 | resumed at 528; no step completed | failed on the first resumed optimiser step; paged optimiser buffers had loaded into ordinary memory |
| session 2 retry, bundle `846b0be` | 2026-11-04 | resume check 529, then training 529–1,055 | completed; paged buffers restored value for value; settings and learning-rate scale unchanged; checkpoints 792 and 1,055 saved |

No training loss was non-finite. Session 1's first optimiser update was skipped during fp16 loss-scale calibration; the scheduler and resume preserved that state. Pilot and resume-check weights were never selection candidates. Detailed times, losses, checkpoint hashes and the failed attempt remain in the validation log.

## Selection and full validation

Amendment 1 fixed the four candidates and the score before training: **S = ½(A₁ + A₂) − W**, with tier-specific decision accuracies A₁ and A₂ and the pooled wrong-intervention rate W on healthy subset runs. The subset contains 200 tier 1 and 100 tier 2 validation primaries, stratified by family with seed 2029; its lists were committed before candidate evaluation. Exact score ties favour the earlier checkpoint. Monitored rates never affect the choice.
"""

TAIL = """
## Limitations

- **Unseen escalation failed.** F6 was absent from training and validation. The risk of poor held-out F6 abstention was recorded before testing, and the chosen checkpoint remains fixed under Amendment 1.
- **Wrong interventions remain material.** Especially on healthy tier 2 held-out runs, higher decision accuracy does not imply dependable intervention behaviour. Zero observed errors on another set has a nonzero Wilson upper bound.
- **Synthetic scope.** These are generated support worlds and one OpenAI Agents SDK workflow with bounded probes and recoveries. The experiment does not establish diagnosis of arbitrary traces, production safety or general autonomous repair.
- **Baseline scope.** Rules v1 encodes training-family knowledge and stops after one recovery. GPT-4.1 and untrained Qwen use the shared zero-shot prompt; no few-shot strong-model baseline or contrast-partner ablation was tested. The comparisons establish performance against these specific baselines.
- **Selection uncertainty.** One training seed and four validation candidates were evaluated. The score rewards both accuracy and restraint; the selected checkpoint need not maximise either tier's accuracy alone. Full validation and test results do not reopen selection. The subset's recorded label-replay ceiling is S = 0.995 because one visible input has conflicting labels.
- **Live verification scope.** Live observations are fixed captures from `gpt-4.1-mini-2025-04-14`. Of 300 runs, 277 are proxy-matched, 17 final-label-only and six live-confirmed on the target ticket. Recovery re-runs and regression checks otherwise rely on scripted proxies; no tier 2 live split exists. Live F7 consists entirely of healthy runs.
- **Metric and action limits.** Undetermined cases remain in decision metrics and are excluded from probe-efficiency metrics. Tier 1 probe labels use small hypothesis sets; tier 2 adds richer hypotheses and distractors. Partial repair followed by escalation cannot score correct under the frozen action space.
- **Statistical limits.** Paired bootstrap intervals resample cases under the frozen protocol; they do not measure variation across training seeds or deployments. No multiple-comparison correction is applied. Every primary comparison is shown, including those with no significant difference.

## Reproducing

Run `python -m packages.support_evaluator.milestone3_results` to write this document, or add `--check` to compare its exact UTF-8 bytes without writing. This is offline analysis of recorded rows, with no model generation, episode execution, live API call or GPU run. It does not rerun any test split.

The generator checks test-row hashes against their numbered entries in `docs/milestone-2/TEST_RUN_LOG.md`, checks selection and validation inputs against hashes in the validation log, requires exactly the declared cases once each, recomputes summaries with `case_sources.load_source(...).summarize`, and requires equality with the stored summaries. Selection scores and monitored rates are recomputed from the existing validation rows. All pairwise comparisons call `metrics.paired_bootstrap` with 10,000 resamples and seed 2026. Formatting helpers and source paths follow the Milestone 2 generator; its report and the protocol are unchanged.

Artifacts are gitignored. Baseline rows are under the directories recorded for runs #1–#4. Fine-tuned in-distribution and live rows come from `artifacts/milestone-3/test-session-A/qlora-test/<set>/`; held-out rows come from `artifacts/milestone-3/test-session-B/qlora-test/<set>/`. Session B's copies of session A results are not counted again. Selection inputs are under `artifacts/milestone-3/selection-run-1/qlora-selection/` and full validation under `artifacts/milestone-3/validation-run-1/qlora-validation/`. The exact regeneration test runs where those artifacts exist; CI always checks the committed document's fixed prose and structure.
"""


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _logged_bytes(path: Path, log: str, run: int | None = None) -> bytes:
    """Require the file's digest to be in its pre-existing log before using it."""
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if run is not None:
        entry = next((line for line in log.splitlines() if line.startswith(f"| {run} |")), "")
        matched = f"`{path.name}` `{digest}`" in entry
    else:
        matched = digest in log
    if not matched:
        raise ValueError(f"{path}: sha256 does not match the logged {'run #' + str(run) if run else 'validation record'}")
    return content


def _rows(path: Path, log: str, run: int | None = None) -> list[dict]:
    return [json.loads(line) for line in _logged_bytes(path, log, run).splitlines()]


def _require_cases(rows: list[dict], members, description: str) -> None:
    if sorted(r["case_id"] for r in rows) != sorted(members):
        raise ValueError(f"{description}: rows must contain exactly the declared cases once each")


def test_directories(index: int) -> dict[str, tuple[Path, int]]:
    _, _, qwen = m2.SETS[index]
    directories = {s: (d, 1 if s == "rules v1" else 2 if s == "GPT-4.1" else 3 if index < 2 else 4)
                   for s, d in m2.system_dirs(qwen).items()}
    held_out = index in (1, 3)
    session = "test-session-B" if held_out else "test-session-A"
    directories[FT] = (ARTIFACTS / session / "qlora-test" / NAMES[index], 6 if held_out else 5)
    return directories


def row_files() -> list[Path]:
    paths = [directory / f"rows-{name}.jsonl" for i, name in enumerate(NAMES)
             for directory, _ in test_directories(i).values()]
    paths += [SELECTION / f"checkpoint-{step:04d}" / f"rows-tier{tier}-tier{tier}.jsonl"
              for step in STEPS for tier in (1, 2)]
    paths += [VALIDATION / f"tier{tier}" / f"rows-tier{tier}-validation.jsonl" for tier in (1, 2)]
    return paths + [REFERENCE / f"rows-tier{tier}.jsonl" for tier in (1, 2)]


def _summary(source, rows: list[dict], directory: Path) -> dict:
    _require_cases(rows, (c.case_id for c in source.cases), str(directory))
    summary = json.loads(json.dumps(source.summarize(rows)))
    if summary != _json(directory / f"summary-{source.name}.json"):
        raise ValueError(f"{directory}: recomputed summary differs from the stored one")
    return summary


def load() -> dict:
    """Read and summarize test rows; no case's prepare/score callable is invoked."""
    log = TEST_LOG.read_text(encoding="utf-8")
    data = {}
    for index, (set_name, arguments, _) in enumerate(m2.SETS):
        source = load_source(**arguments)
        for system, (directory, run) in test_directories(index).items():
            rows = _rows(directory / f"rows-{source.name}.jsonl", log, run)
            data[set_name, system] = rows, _summary(source, rows, directory)
    return data


def history() -> tuple[list[dict], dict, dict, dict]:
    """Recompute existing selection/full-validation rows and check their records."""
    log = VALIDATION_LOG.read_text(encoding="utf-8")
    members = {tier: (SUBSET_DIR / f"tier{tier}.txt").read_text(encoding="utf-8").split() for tier in (1, 2)}
    sources = {tier: load_source(dataset=m2.TIER1[0] if tier == 1 else m2.TIER2[0],
                                 split=SUBSET_DIR / f"tier{tier}.txt") for tier in (1, 2)}
    candidates = []
    for step in STEPS:
        directory = SELECTION / f"checkpoint-{step:04d}"
        recorded = json.loads(_logged_bytes(directory / "selection.json", log))
        rows = {tier: _rows(directory / f"rows-tier{tier}-tier{tier}.jsonl", log) for tier in (1, 2)}
        for tier in (1, 2):
            _require_cases(rows[tier], members[tier], f"{directory}, tier {tier}")
            _summary(sources[tier], rows[tier], directory)
        score = selection_score(rows[1], rows[2])
        if any(score[key] != recorded[key] for key in score):
            raise ValueError(f"{directory}: recomputed selection score differs from the recorded one")
        candidates.append(recorded)

    choice = json.loads(_logged_bytes(SELECTION / "choice.json", log))
    best = max(candidates, key=lambda c: c["S"])  # candidates are in step order; ties keep the earlier
    if any(best[key] != choice[key] for key in ("step", "S", "state_sha256", "adapter_sha256")) or best["checkpoint"] != choice["chosen"]:
        raise ValueError("recomputed checkpoint choice differs from the logged choice")

    reference_rows = {}
    full = {}
    for tier in (1, 2):
        # Reference rows cover full validation: restrict them to the already committed subset.
        rows = _rows(REFERENCE / f"rows-tier{tier}.jsonl", log)
        source = load_source(dataset=m2.TIER1[0] if tier == 1 else m2.TIER2[0],
                             split=(m2.TIER1[1] if tier == 1 else m2.TIER2[1]) / "validation.txt")
        _require_cases(rows, (c.case_id for c in source.cases), f"untrained tier {tier}")
        reference_rows[tier] = [r for r in rows if r["case_id"] in members[tier]]
        directory = VALIDATION / f"tier{tier}"
        recorded = json.loads(_logged_bytes(directory / f"validation-tier{tier}.json", log))
        rows = _rows(directory / f"rows-tier{tier}-validation.jsonl", log)
        full[tier] = _summary(source, rows, directory)
        if recorded["summary"] != full[tier] or recorded["adapter_sha256"] != choice["adapter_sha256"]:
            raise ValueError(f"tier {tier}: full validation differs from its recorded result or chosen adapter")
    reference = selection_score(reference_rows[1], reference_rows[2])
    if reference["S"] != choice["reference_S"]:
        raise ValueError("recomputed untrained reference differs from the recorded reference")
    return candidates, choice, reference, full


def comparisons(data) -> dict:
    return {(name, a, b): paired_bootstrap(data[name, a][0], data[name, b][0], resamples=10_000, seed=2026)
            for name, _, _ in m2.SETS for a, b in itertools.combinations(SYSTEMS, 2)}


def _table(headers, rows) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(map(str, row)) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def history_tables(candidates, choice, reference, full) -> str:
    out = ["\nRates and Wilson intervals below use the four-decimal metric values and display formatting of the Milestone 2 generator. "
           "Some displayed validation percentages or interval endpoints differ by 0.1 percentage points from the manually rounded validation log; "
           "the counts, metric values and selection scores are unchanged.\n\n### Checkpoint selection (2026-11-04)\n\n"]
    entries = [("Qwen untrained (existing rows)", reference)] + [(c["checkpoint"], c) for c in candidates]
    out.append(_table(("candidate", "S", "A₁", "A₂", "W (healthy, pooled)"),
                      [(name, f"{c['S']:.4f}", *(m2._interval(c[k]) for k in ("A1", "A2", "W"))) for name, c in entries]))
    out.append(f"\n**Chosen: `{choice['chosen']}`**, S = {choice['S']:.4f}, versus the untrained reference {reference['S']:.4f}. "
               f"The adapter sha256 is `{choice['adapter_sha256']}` and the checkpoint's `state.json` sha256 is `{choice['state_sha256']}`. "
               "All four candidates used the same platform, GPU type, libraries and bundle `1225d58`.\n\n")
    out.append(_table(("candidate", "tier 1 insufficient_evidence precision", "tier 1 abstain recall",
                       "tier 2 insufficient_evidence precision", "tier 2 abstain recall"),
                      [(name, *(m2._interval(c["monitoring"][f"tier{tier}"][key]) for tier in (1, 2)
                                for key in ("insufficient_evidence_precision", "abstain_recall"))) for name, c in entries]))
    out.append("\nThe F6 abstention risk was recorded **before any fine-tuned test run**: the chosen checkpoint's tier 1 "
               "abstain recall was 2/17 on the selection subset, against 15/17 for checkpoint 264. F6 was never used in training or validation.\n")
    out.append("\n### Full validation (2026-11-04; reporting only)\n\n")
    out.append(_table(("tier", "decision accuracy", "wrong interventions", "invalid actions", "insufficient_evidence precision", "abstain recall"),
                      [(tier, m2._interval(s["decision_accuracy"]), m2._interval(s["wrong_interventions_on_healthy"]),
                        m2._interval(s["invalid_actions"]), m2._interval(s["insufficient_evidence"]["precision"]),
                        m2._interval(s["abstain"]["recall"])) for tier, s in full.items()]))
    out.append("\nFull validation used bundle `edca36c`, reproduced all 300 selection-subset episodes exactly and did not change the choice. "
               "Selection and full-validation smoke tests passed; no generation was non-finite, empty or at the token limit.\n")
    return "".join(out)


def _sequence_counts(data, system: str, key: str, fmt=lambda m: f"{m['k']}/{m['n']}") -> str:
    """One tier 2 sequence metric of a system on both tier 2 sets, in set order."""
    return " and ".join(fmt(data[name, system][1]["sequence"][key]) for name in TIER2_SETS)


def two_step_finding(data) -> str:
    baselines = [s for s in SYSTEMS if s != FT]
    fixed = ", ".join(f"{s} {_sequence_counts(data, s, 'two_recovery_labels')}" for s in baselines)
    stopped = ", ".join(f"{s} {_sequence_counts(data, s, 'stopped_after_one_of_two')}" for s in baselines)
    return ("5. **Two-step recovery improved but remains limited.** On cases whose label needs two recoveries "
            "(tier 2 in-distribution and held-out), the fine-tuned model fixed both faults in "
            f"{_sequence_counts(data, FT, 'two_recovery_labels', m2._rate)}; the baselines fixed both in {fixed}. "
            f"It stopped after the first of the two recoveries in {_sequence_counts(data, FT, 'stopped_after_one_of_two')} "
            f"({stopped}; rules v1 stops after one recovery by design).\n")


def findings(data, paired) -> str:
    verdicts = Counter("FT better" if e["verdict"] == "B better" else "baseline better" if e["verdict"] == "A better"
                       else "no significant difference"
                       for (_, _, b), result in paired.items() if b == FT for e in result.values())
    rates = ", ".join(m2._rate(data[name, FT][1]["decision_accuracy"]) for name, _, _ in m2.SETS)
    return ("\n## Findings\n\n"
            f"1. **Fine-tuning improved decision accuracy against both model baselines on every set.** In table order, fine-tuned accuracy is {rates}. "
            "Every accuracy comparison with GPT-4.1 and untrained Qwen favours fine-tuning under the paired claim rule.\n"
            "2. **Rules retain an accuracy advantage on four sets.** Tier 2 held-out accuracy has no significant difference between rules and fine-tuning. "
            "Wrong interventions favour fine-tuning over rules on both held-out sets and live; on the two in-distribution sets there is no significant difference.\n"
            f"3. **Across the 30 endpoint comparisons involving fine-tuning**, it is better in {verdicts['FT better']}, "
            f"a baseline is better in {verdicts['baseline better']}, and {verdicts['no significant difference']} have no significant difference. "
            "The full report includes the 30 baseline-only comparisons too: six system pairs × five sets × two endpoints = **60 endpoint comparisons**.\n"
            "4. **Restraint did not transfer consistently.** Fine-tuning introduces wrong interventions relative to untrained Qwen, most visibly on tier 2 held-out. "
            "It has no invalid actions across the five sets, but failed recovery calls remain; valid JSON does not imply a valid or successful repair.\n"
            + two_step_finding(data) +
            "6. **Held-out transfer differs sharply by family.** F6 escalation failed, while F7 includes successful recoveries as well as correct healthy/withheld decisions. "
            "The breakdown below keeps those outcomes separate, including live F7's entirely healthy cases.\n")


def result_tables(data, paired) -> str:
    out = ["\n## Test results\n\nRates are k / n with Wilson 95% intervals. Decision metrics include undetermined cases; "
           "probe-efficiency metrics exclude them. All other metrics are secondary and descriptive. Paired differences are A − B in percentage points "
           "with paired bootstrap 95% intervals (10,000 resamples, seed 2026); lower wrong-intervention rates are better. "
           "A 'better' verdict requires the interval to exclude zero in its favour; otherwise it is 'no significant difference'. "
           "No correction for multiple comparisons is applied.\n"]
    sets = [name for name, _, _ in m2.SETS]
    entries = [(name, system, data[name, system][1]) for name in sets for system in SYSTEMS]
    out.append("\n### Test sets\n\n")
    descriptions = ("dataset v2, splits v1 test_in_distribution", "dataset v2, splits v1 test_held_out (F6/F7)",
                    "dataset v3, splits v2 test_in_distribution (up to two recoveries)",
                    "dataset v3, splits v2 test_held_out (F6/F7 compounds)", "live test v1 (tier 1 episodes)")
    out.append(_table(("test set", "source", "cases", "healthy runs"),
                      [(n, description, data[n, SYSTEMS[0]][1]["cases"],
                        data[n, SYSTEMS[0]][1]["wrong_interventions_on_healthy"]["n"])
                       for n, description in zip(sets, descriptions)]))
    out.append("\n### Primary endpoints\n\n")
    out.append(_table(("test set", "system", "decision accuracy", "wrong interventions on healthy runs"),
                      [(n, s, *(m2._interval(v[k]) for k in ENDPOINTS)) for n, s, v in entries]))
    out.append("\n### All paired comparisons\n\n")
    rows = []
    for (name, a, b), result in paired.items():
        cells = []
        for endpoint in ENDPOINTS:
            e = result[endpoint]
            cells += [m2._difference(e), e["verdict"].replace("A better", f"{a} better").replace("B better", f"{b} better")]
        rows.append((name, f"{a} − {b}", *cells))
    out.append(_table(("test set", "A − B", "decision accuracy: difference [95% CI]", "verdict",
                       "wrong interventions: difference [95% CI]", "verdict"), rows))
    out.append("\n### Secondary decision metrics\n\n")
    out.append(_table(("test set", "system", "exact match", "verified recovery", "invalid actions", "failed recovery calls"),
                      [(n, s, *(m2._interval(v[k]) for k in ("exact_match", "verified_recovery_rate", "invalid_actions")),
                        v["failed_recovery_calls"]) for n, s, v in entries]))
    out.append("\n### Decision recall and precision\n\n")
    out.append(_table(("test set", "system", "insufficient_evidence recall", "insufficient_evidence precision", "abstain recall",
                       "abstain precision", "no_intervention recall", "no_intervention precision"),
                      [(n, s, *(m2._interval(v[d][k]) for d in ("insufficient_evidence", "abstain", "no_intervention")
                                for k in ("recall", "precision"))) for n, s, v in entries]))
    out.append("\n### Probe efficiency\n\n")
    out.append(_table(("test set", "system", "mean probes", "healthy mean", "oracle mean", "mean excess", "budget exceeded", "undetermined"),
                      [(n, s, *(v["probes"][k] for k in ("mean_probes", "mean_probes_on_healthy", "oracle_mean_probes", "mean_excess_probes")),
                        m2._interval(v["probes"]["probe_budget_exceeded"]), v["probes"]["undetermined"]) for n, s, v in entries]))
    out.append("\n### Tier 2 sequence metrics\n\n")
    out.append(_table(("test set", "system", "exact sequence match", "longer than label", "stopped after one of two", "two-recovery labels"),
                      [(n, s, *(m2._interval(v["sequence"][k]) for k in ("exact_sequence_match", "longer_than_label",
                                "stopped_after_one_of_two", "two_recovery_labels"))) for n, s, v in entries if "sequence" in v]))
    out.append("\n### Groups and slices (decision accuracy)\n\n")
    rows = []
    for n, s, v in entries:
        groups = [m2._interval(v[k]["decision_accuracy"]) if v[k] else "–"
                  for k in ("training_families", "held_out_families", "proactive_detection")]
        slices = v.get("slices", {})
        reweighted = slices.get("length_matched", {}).get("reweighted_accuracy")
        rows.append((n, s, *groups, *(m2._interval(slices.get(k)) for k in ("compound", "compound_pair", "target_recent_faulty")),
                     "–" if reweighted is None else f"{100 * reweighted:.1f}%"))
    out.append(_table(("test set", "system", "training families", "held-out families", "proactive detection", "compound slice",
                       "compound pairs", "recent-target faulty", "length-reweighted"), rows))
    out.append("\n### Live split by label category (decision accuracy)\n\n")
    categories = sorted(data["Live", SYSTEMS[0]][1]["live_categories"])
    out.append(_table(("system", *categories),
                      [(s, *(m2._interval(data["Live", s][1]["live_categories"][c]) for c in categories)) for s in SYSTEMS]))
    for name in sets:
        out.append(f"\n### Per family: {name}\n\n")
        families = data[name, SYSTEMS[0]][1]["by_family"]
        out.append(_table(("family", "held out", *SYSTEMS),
                          [(f"`{f}`", "yes" if families[f]["held_out"] else "no",
                            *(m2._interval(data[name, s][1]["by_family"][f]["decision_accuracy"]) for s in SYSTEMS))
                           for f in sorted(families, key=lambda f: (families[f]["held_out"], f))]))
    return "".join(out)


def transfer_tables(data) -> str:
    out = ["\n## F6 and F7: held-out findings\n\nThe F6/F7 rows below are tier 1 single-family cases and live cases. "
           "Tier 2 contains compounds, whose pair-level accuracies are reported above. 'Recovery' below counts cases labelled with a recovery, "
           "not all family cases; the healthy and withheld columns use their own label denominators.\n\n"]
    rows = []
    for name in ("Tier 1 held-out", "Live"):
        for kind in ("queue_misconfiguration", "tier_format_drift"):
            for system in SYSTEMS:
                group = [r for r in data[name, system][0] if r["case_kind"] == kind]
                s = decision_metrics(group)
                rows.append((name, kind, system, m2._interval(s["decision_accuracy"]),
                             m2._interval(s["abstain"]["recall"]), m2._interval(s["verified_recovery_rate"]),
                             m2._interval(s["no_intervention"]["recall"]), m2._interval(s["insufficient_evidence"]["recall"])))
    out.append(_table(("test set", "family", "system", "decision accuracy", "abstain recall", "verified recovery",
                       "healthy recall", "withheld recall"), rows))
    f6 = decision_metrics([r for r in data["Tier 1 held-out", FT][0] if r["case_kind"] == "queue_misconfiguration"])
    f7 = decision_metrics([r for r in data["Tier 1 held-out", FT][0] if r["case_kind"] == "tier_format_drift"])
    out.append(f"\n**F6:** fine-tuned abstain recall is {m2._interval(f6['abstain']['recall'])}. "
               "The pre-test risk materialized: complete-evidence F6 escalation was never correct. Withheld-evidence decisions contribute to family accuracy "
               "without showing successful escalation. Live F6 has 29 abstain labels and one healthy run; live abstain recall over all families is 0/44.\n")
    out.append(f"\n**F7:** fine-tuned family accuracy is {m2._interval(f7['decision_accuracy'])}, while verified recovery on the repair-labelled cases is "
               f"{m2._interval(f7['verified_recovery_rate'])}. Family accuracy also includes healthy and withheld-evidence decisions. "
               "On live F7 the fine-tuned model scores 29/30; **all 30 are healthy**, and both model baselines already score 30/30. "
               "Live F7 demonstrates correct non-intervention in most cases, not new evidence of successful repair.\n")
    out.append("\n### Held-out variants (decision accuracy)\n\n")
    rows = []
    for name in ("Tier 1 held-out", "Live"):
        keys = sorted({(r["case_kind"], r["case_variant"]) for r in data[name, SYSTEMS[0]][0] if r["held_out"]})
        for kind, variant in keys:
            cells = []
            for system in SYSTEMS:
                group = [r for r in data[name, system][0] if (r["case_kind"], r["case_variant"]) == (kind, variant)]
                cells.append(m2._interval(rate(sum(r["correct"] for r in group), len(group))))
            rows.append((name, kind, variant, *cells))
    out.append(_table(("test set", "family", "variant", *SYSTEMS), rows))
    return "".join(out)


def render() -> str:
    data = load()
    candidates, choice, reference, full = history()
    paired = comparisons(data)
    return (HEAD + history_tables(candidates, choice, reference, full) + findings(data, paired)
            + result_tables(data, paired) + transfer_tables(data) + TAIL)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument("--check", action="store_true", help="compare exact bytes with --out instead of writing")
    args = parser.parse_args(argv)
    try:
        missing = [str(p.relative_to(REPO_ROOT)) for p in row_files() if not p.is_file()]
        if missing:
            raise ValueError("recorded rows are missing: " + ", ".join(missing))
        content = render().encode("utf-8")
        if args.check:
            if not args.out.is_file() or args.out.read_bytes() != content:
                print(f"STOP: {args.out} differs from the regenerated results", file=sys.stderr)
                return 1
            print(f"{args.out} matches the regenerated results")
            return 0
        args.out.write_bytes(content)
    except (OSError, ValueError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
