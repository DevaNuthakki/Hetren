"""Build the fine-tuning data for Qwen3-4B (Milestone 3) from the train split only.

Implements ``EVAL_PROTOCOL.md``, Amendment 1, "Training data":

- every record of the ``train`` split (primaries and their contrast
  partners) of dataset v2 / splits v1 (tier 1) and dataset v3 / splits v2
  (tier 2);
- one example per labelled step: the user message is the step's compact
  evidence as the model baselines send it, the target is the step's action
  as JSON with its keys in the order ``action``, ``verb``, ``args`` (as in the
  prompt's examples); the system message is prompt version 2 for the tier,
  recorded in the manifest by its hash and rebuilt by the trainer;
- an example that occurs more than once is kept once; an input that occurs
  with more than one target is dropped entirely;
- each example's loss weight is min(3, max(1, sqrt(m / c))) for its target
  verb, with c the verb's count in the tier and m the median of the tier's
  per-verb counts.

The builder stops unless the counts are the ones Amendment 1 records.

Epoch budget (Amendment 1, "Epoch budget"): with ``--probe-rate R`` it also
writes ``train-budget.jsonl``, which keeps every non-probe example and, in
each tier, round(R × n) of the tier's n probe examples, drawn without
replacement by ``random.Random("2029:tier<N>:probes")`` from the probe
examples in file order; kept examples stay in file order. ``budget.json``
records the rate, the counts and every dropped example (tier, case ID, step).

``python -m packages.support_evaluator.training_data --out <dir>`` writes
``train.jsonl`` and ``manifest.json``; with ``--check <manifest>`` it stops
unless its manifest equals the committed one
(``docs/milestone-3/train-v1.manifest.json``), and with ``--check-budget``
unless ``budget.json`` equals ``docs/milestone-3/train-v1-budget.json``.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import median
import sys

from packages.hetren_baselines.prompt import system_prompt, user_message
from packages.hetren_evidence import render_evidence


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_VERSION = 2
WEIGHT_CAP = 3.0
SEED = 2029
SOURCES = {
    1: ("artifacts/milestone-2/dataset-v2", "docs/milestone-2/splits-v1/train.txt"),
    2: ("artifacts/milestone-2/dataset-v3", "docs/milestone-2/splits-v2/train.txt"),
}
# Amendment 1: raw examples per tier, and what deduplication leaves.
EXPECTED = {"raw": {1: 10_415, 2: 13_096}, "examples": {1: 6_981, 2: 10_101}, "conflicting_inputs": 58}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_text(action: dict) -> str:
    return json.dumps({"action": action["action"], "verb": action["verb"], "args": action["args"]})


def step_kind(step: dict) -> str:
    """probe, recover or decide; after a recovery (compact evidence v2) prefixed with ``post_recovery_``."""
    post = step["input"]["format"] == "compact-evidence-v2"
    return ("post_recovery_" if post else "") + step["target"]["action"]


def raw_examples(tier: int, root: Path = REPO_ROOT) -> list[dict]:
    """Every labelled step of every train-split record of the tier, in dataset order."""
    dataset, split = (root / p for p in SOURCES[tier])
    members = set(split.read_text(encoding="utf-8").split())
    visible = map(json.loads, (dataset / "hetren_visible.jsonl").open(encoding="utf-8"))
    evaluator = map(json.loads, (dataset / "evaluator" / "cases.jsonl").open(encoding="utf-8"))
    examples = []

    for v, e in zip(visible, evaluator):
        if v["case_id"] != e["case_id"]:
            raise ValueError(f"visible and evaluator records out of step at {v['case_id']}")

        if v["case_id"] not in members:
            continue

        for index, step in enumerate(v["steps"]):
            examples.append({
                "tier": tier, "case_id": v["case_id"], "role": e["role"], "step": index,
                "kind": step_kind(step), "verb": step["target"]["verb"],
                "user": user_message(render_evidence(step["input"])), "target": target_text(step["target"]),
            })

    return examples


def deduplicate(examples: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Examples kept once each, without conflicting inputs; and what was removed.

    Counts: ``duplicates`` (repeats of a kept example), ``conflicting_inputs``
    and ``conflicting_examples`` (the distinct examples on those inputs).
    """
    targets = defaultdict(set)

    for example in examples:
        targets[example["tier"], example["user"]].add(example["target"])

    conflicting = {key for key, found in targets.items() if len(found) > 1}
    seen, kept, duplicates = set(), [], 0

    for example in examples:
        key = example["tier"], example["user"]

        if key in conflicting:
            continue

        if key in seen:
            duplicates += 1
            continue

        seen.add(key)
        kept.append(example)

    removed = {
        "duplicates": duplicates,
        "conflicting_inputs": len(conflicting),
        "conflicting_examples": sum(len(targets[key]) for key in conflicting),
    }
    return kept, removed


def verb_weights(examples: list[dict]) -> dict[str, float]:
    counts = Counter(e["verb"] for e in examples)
    middle = median(counts.values())
    return {verb: min(WEIGHT_CAP, max(1.0, math.sqrt(middle / count))) for verb, count in sorted(counts.items())}


def select_probes(rows: list[dict], probe_rate: float, seed: int = SEED) -> tuple[list[dict], dict[str, object]]:
    """Every non-probe example, and round(rate × n) of each tier's n probe examples; the record of what was dropped."""
    dropped, record = set(), {"probe_rate": probe_rate, "seed": seed, "tiers": {}}

    for tier in (1, 2):
        probes = [i for i, r in enumerate(rows) if r["tier"] == tier and r["kind"].endswith("probe")]
        keep = math.floor(probe_rate * len(probes) + 0.5)
        kept = set(random.Random(f"{seed}:tier{tier}:probes").sample(probes, keep))
        dropped |= set(probes) - kept
        record["tiers"][str(tier)] = {
            "examples": sum(r["tier"] == tier for r in rows), "probe_examples": len(probes),
            "probes_kept": keep, "probes_dropped": len(probes) - keep,
        }

    selected = [r for i, r in enumerate(rows) if i not in dropped]
    record["examples"] = len(selected)
    record["dropped"] = [[rows[i]["tier"], rows[i]["case_id"], rows[i]["step"]] for i in sorted(dropped)]
    return selected, record


def build(out: Path, root: Path = REPO_ROOT) -> dict[str, object]:
    out.mkdir(parents=True, exist_ok=True)
    rows, manifest = [], {
        "format": "hetren-train-v1",
        "protocol": "docs/milestone-2/EVAL_PROTOCOL.md, Amendment 1 (2026-11-03)",
        "prompt_version": PROMPT_VERSION,
        "system_prompt_sha256": {},
        "sources": {},
        "raw_examples": {},
        "removed": {},
        "examples": {},
        "by_kind": {},
        "by_verb": {},
        "by_role": {},
        "weights": {},
    }

    for tier in (1, 2):
        dataset, split = (root / p for p in SOURCES[tier])
        raw = raw_examples(tier, root)
        kept, removed = deduplicate(raw)
        weights = verb_weights(kept)
        system = system_prompt(tier, PROMPT_VERSION)
        key = str(tier)

        manifest["system_prompt_sha256"][key] = hashlib.sha256(system.encode("utf-8")).hexdigest()
        manifest["sources"][key] = {
            "dataset": dataset.name,
            "hetren_visible.jsonl": _sha256(dataset / "hetren_visible.jsonl"),
            "evaluator/cases.jsonl": _sha256(dataset / "evaluator" / "cases.jsonl"),
            "split": str(split.relative_to(root)),
            "split_sha256": _sha256(split),
        }
        manifest["raw_examples"][key] = len(raw)
        manifest["removed"][key] = removed
        manifest["examples"][key] = len(kept)
        manifest["by_kind"][key] = dict(sorted(Counter(e["kind"] for e in kept).items()))
        manifest["by_verb"][key] = dict(sorted(Counter(e["verb"] for e in kept).items()))
        manifest["by_role"][key] = dict(sorted(Counter(e["role"] for e in kept).items()))
        manifest["weights"][key] = {verb: round(w, 4) for verb, w in weights.items() if w != 1.0}
        rows += [{**e, "weight": weights[e["verb"]]} for e in kept]

    raw_counts = {t: manifest["raw_examples"][str(t)] for t in (1, 2)}
    counts = {t: manifest["examples"][str(t)] for t in (1, 2)}
    conflicting = sum(r["conflicting_inputs"] for r in manifest["removed"].values())

    if raw_counts != EXPECTED["raw"] or counts != EXPECTED["examples"] or conflicting != EXPECTED["conflicting_inputs"]:
        raise SystemExit(f"STOP: counts differ from Amendment 1: raw {raw_counts}, kept {counts}, "
                         f"conflicting inputs {conflicting}")

    path = out / "train.jsonl"

    with path.open("w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(row, sort_keys=True) + "\n" for row in rows)

    manifest["files"] = {"train.jsonl": _sha256(path)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def build_budget(out: Path, probe_rate: float) -> dict[str, object]:
    """``train-budget.jsonl`` from ``train.jsonl`` (written by ``build``) under the epoch budget, and its record."""
    rows = [json.loads(line) for line in (out / "train.jsonl").open(encoding="utf-8")]
    selected, record = select_probes(rows, probe_rate)
    path = out / "train-budget.jsonl"

    with path.open("w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(row, sort_keys=True) + "\n" for row in selected)

    record["files"] = {"train.jsonl": _sha256(out / "train.jsonl"), "train-budget.jsonl": _sha256(path)}
    (out / "budget.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return record


def _matches(path: Path | None, built: dict) -> bool:
    return path is None or json.loads(path.read_text(encoding="utf-8")) == built


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--check", type=Path, help="committed manifest the build must equal")
    parser.add_argument("--probe-rate", type=float, help="the epoch budget's probe rate (writes train-budget.jsonl)")
    parser.add_argument("--check-budget", type=Path, help="committed budget record the selection must equal")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    manifest = build(args.out)

    if not _matches(args.check, manifest):
        print(f"STOP: the built training data does not match {args.check}", file=sys.stderr)
        return 1

    print(f"wrote {args.out / 'train.jsonl'}: {sum(manifest['examples'].values())} examples "
          f"(tier 1 {manifest['examples']['1']}, tier 2 {manifest['examples']['2']})")

    if args.probe_rate is not None:
        record = build_budget(args.out, args.probe_rate)

        if not _matches(args.check_budget, record):
            print(f"STOP: the budget selection does not match {args.check_budget}", file=sys.stderr)
            return 1

        print(f"wrote {args.out / 'train-budget.jsonl'}: {record['examples']} examples "
              f"({len(record['dropped'])} probe examples dropped at rate {args.probe_rate})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build",
    "build_budget",
    "deduplicate",
    "raw_examples",
    "select_probes",
    "step_kind",
    "target_text",
    "verb_weights",
]
