"""The checkpoint-selection subset and score of Amendment 1 (validation only).

The subset is 300 validation primary cases: 200 tier 1 (dataset v2, splits v1
``validation``) and 100 tier 2 (dataset v3, splits v2 ``validation``). Within
each tier the cases are stratified by case kind, a compound by its pair
(``compound:<kind>+<kind>``, the protocol's family key): each kind gets
``count × size ÷ tier total`` cases rounded down, and the remaining places go
to the kinds with the largest remainders (ties by kind name). Within a kind,
cases are drawn without replacement from the sorted case IDs by
``random.Random("2029:tier<N>")``, kinds in name order.

The score of a set of rows on the subset is S = ½(A₁ + A₂) − W, with A₁ and A₂
the tier 1 and tier 2 decision accuracy and W the wrong-intervention rate on
the healthy runs of both tiers pooled. ``insufficient_evidence`` precision
and ``abstain`` recall per tier are reported with it (monitoring only).

``python -m packages.support_evaluator.selection_subset write`` writes the
lists and their manifest to ``docs/milestone-3/selection-subset-v1/``
(``--check`` compares instead); ``score --tier1 <rows> --tier2 <rows>``
scores recorded rows on the subset.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import sys

from packages.support_evaluator.cases import COMPOUND_KIND, component_kinds
from packages.support_evaluator.metrics import decision_metrics, rate


REPO_ROOT = Path(__file__).resolve().parents[2]
SEED = 2029
SIZES = {1: 200, 2: 100}
SOURCES = {
    1: ("artifacts/milestone-2/dataset-v2", "docs/milestone-2/splits-v1/validation.txt"),
    2: ("artifacts/milestone-2/dataset-v3", "docs/milestone-2/splits-v2/validation.txt"),
}
SUBSET_DIR = REPO_ROOT / "docs" / "milestone-3" / "selection-subset-v1"


def family(truth: dict) -> str:
    """The protocol's family key: the case kind, a compound as ``compound:<kind>+<kind>``."""
    if truth["case_kind"] == COMPOUND_KIND:
        return f"{COMPOUND_KIND}:" + "+".join(component_kinds(truth["case_kind"], truth["case_variant"]))

    return truth["case_kind"]


def validation_primaries(tier: int, root: Path = REPO_ROOT) -> dict[str, str]:
    """case ID -> family for the tier's validation primaries."""
    dataset, split = (root / p for p in SOURCES[tier])
    members = set(split.read_text(encoding="utf-8").split())
    kinds = {}

    for line in (dataset / "evaluator" / "cases.jsonl").open(encoding="utf-8"):
        case = json.loads(line)

        if case["case_id"] in members and case["role"] == "primary":
            kinds[case["case_id"]] = family(case["truth"])

    return kinds


def allocate(counts: dict[str, int], size: int) -> dict[str, int]:
    """Proportional allocation with largest remainders (ties by kind name)."""
    total = sum(counts.values())
    exact = {kind: count * size / total for kind, count in counts.items()}
    quota = {kind: int(value) for kind, value in exact.items()}
    order = sorted(counts, key=lambda kind: (-(exact[kind] - quota[kind]), kind))

    for kind in order[:size - sum(quota.values())]:
        quota[kind] += 1

    return dict(sorted(quota.items()))


def draw(kinds: dict[str, str], size: int, tier: int, seed: int = SEED) -> tuple[list[str], dict[str, int]]:
    by_kind = defaultdict(list)

    for case_id, kind in kinds.items():
        by_kind[kind].append(case_id)

    quota = allocate({kind: len(ids) for kind, ids in by_kind.items()}, size)
    rng = random.Random(f"{seed}:tier{tier}")
    chosen = []

    for kind in sorted(by_kind):
        chosen += rng.sample(sorted(by_kind[kind]), quota[kind])

    return sorted(chosen), quota


def build(root: Path = REPO_ROOT) -> tuple[dict[int, list[str]], dict[str, object]]:
    lists, manifest = {}, {"seed": SEED, "protocol": "docs/milestone-2/EVAL_PROTOCOL.md, Amendment 1 (2026-11-03)",
                           "tiers": {}}

    for tier, size in SIZES.items():
        kinds = validation_primaries(tier, root)
        chosen, quota = draw(kinds, size, tier)
        dataset, split = (root / p for p in SOURCES[tier])
        text = "".join(f"{case_id}\n" for case_id in chosen)
        lists[tier] = chosen
        manifest["tiers"][str(tier)] = {
            "dataset": dataset.name,
            "split": str(split.relative_to(root)),
            "split_sha256": hashlib.sha256(split.read_bytes()).hexdigest(),
            "validation_primaries": len(kinds),
            "cases": len(chosen),
            "per_kind": quota,
            "list_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }

    return lists, manifest


def selection_score(tier1_rows: list[dict], tier2_rows: list[dict]) -> dict[str, object]:
    """S = ½(A₁ + A₂) − W on rows already restricted to the subset, with the monitored rates."""
    tiers = {1: decision_metrics(tier1_rows), 2: decision_metrics(tier2_rows)}
    wrong = sum(tiers[t]["wrong_interventions_on_healthy"]["k"] for t in tiers)
    healthy = sum(tiers[t]["wrong_interventions_on_healthy"]["n"] for t in tiers)
    a1, a2 = (tiers[t]["decision_accuracy"]["rate"] for t in (1, 2))
    w = rate(wrong, healthy)
    return {
        "S": round((a1 + a2) / 2 - w["rate"], 4),
        "A1": tiers[1]["decision_accuracy"],
        "A2": tiers[2]["decision_accuracy"],
        "W": w,
        "monitoring": {
            f"tier{t}": {"insufficient_evidence_precision": tiers[t]["insufficient_evidence"]["precision"],
                         "abstain_recall": tiers[t]["abstain"]["recall"]}
            for t in tiers
        },
    }


def subset_rows(rows_path: Path, tier: int, directory: Path = SUBSET_DIR) -> list[dict]:
    members = (directory / f"tier{tier}.txt").read_text(encoding="utf-8").split()
    rows = {r["case_id"]: r for r in map(json.loads, Path(rows_path).open(encoding="utf-8"))}
    missing = [case_id for case_id in members if case_id not in rows]

    if missing:
        raise SystemExit(f"STOP: {len(missing)} subset cases have no row in {rows_path}")

    return [rows[case_id] for case_id in members]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write", help="write (or --check) the subset lists and manifest")
    write.add_argument("--out", type=Path, default=SUBSET_DIR)
    write.add_argument("--check", action="store_true")
    score = commands.add_parser("score", help="score recorded rows on the subset")
    score.add_argument("--tier1", required=True, type=Path)
    score.add_argument("--tier2", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "score":
        result = selection_score(subset_rows(args.tier1, 1), subset_rows(args.tier2, 2))
        print(json.dumps(result, indent=2))
        return 0

    lists, manifest = build()
    files = {f"tier{t}.txt": "".join(f"{c}\n" for c in ids) for t, ids in lists.items()}
    files["manifest.json"] = json.dumps(manifest, indent=2) + "\n"

    if args.check:
        differing = [name for name, text in files.items()
                     if not (args.out / name).exists() or (args.out / name).read_text(encoding="utf-8") != text]

        if differing:
            print(f"STOP: {', '.join(differing)} differ from a fresh draw", file=sys.stderr)
            return 1

        print(f"{args.out} matches a fresh draw")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)

    for name, text in files.items():
        (args.out / name).write_text(text, encoding="utf-8")

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SEED",
    "SIZES",
    "allocate",
    "build",
    "draw",
    "selection_score",
    "subset_rows",
    "validation_primaries",
]
