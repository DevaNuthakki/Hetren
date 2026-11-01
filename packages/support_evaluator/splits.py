"""Frozen train / validation / held-out-test splits of a dataset (evaluator side).

Rules:

- Held-out families (F6 queue misconfiguration, F7 tier format drift) appear
  only in ``test_held_out``, which contains nothing else: their primary cases
  go there with all their partners, and any partner record of a held-out kind
  outside it is dropped. Metrics use primaries only.
- Splitting is by world seed. Seeds used by held-out primaries are reserved
  for ``test_held_out``; other cases on a reserved seed are dropped with their
  partners. Every other seed goes to validation, ``test_in_distribution`` or
  train by a seeded hash, so no world appears in two splits.
- A primary case and its twin partners always share a split.
- Validation is for tuning and baselines. ``test_in_distribution``,
  ``test_held_out`` and the live test split (recorded later, not built here)
  are for final evaluation only.

Each split file lists case IDs only (one per line, sorted). Dropped records
are listed with their reason. The manifest records the dataset it was built
from (by file hashes), the rules and parameters, every file's hash, and
per-split counts.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from packages.support_evaluator.cases import HELD_OUT_KINDS


SPLIT_FORMAT = "hetren-support-splits"
SPLIT_FORMAT_VERSION = 1
SPLITS = ("train", "validation", "test_in_distribution", "test_held_out")
DROPPED_FILE = "dropped.tsv"
HELD_OUT_PARTNER = "held-out partner outside test_held_out"
SEED_RESERVED = "seed reserved for held-out"


def _seed_bucket(world_seed: int, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{world_seed}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / 16 ** 12


def _kind_of(case: dict) -> str:
    if case["role"] == "partner":
        return case["counterfactual"].split("/")[0]

    return case["planned"]["case_kind"]


def assign_splits(
    evaluator: list[dict],
    *,
    seed: int,
    validation_fraction: float,
    test_fraction: float,
) -> tuple[dict[str, str], dict[str, str]]:
    """case_id -> split for every kept record, and case_id -> reason for dropped ones."""
    primaries = [c for c in evaluator if c["role"] == "primary"]
    reserved = {c["planned"]["world_seed"] for c in primaries if c["planned"]["case_kind"] in HELD_OUT_KINDS}

    def split_of_primary(case: dict) -> str | None:
        world_seed = case["planned"]["world_seed"]

        if case["planned"]["case_kind"] in HELD_OUT_KINDS:
            return "test_held_out"

        if world_seed in reserved:
            return None

        bucket = _seed_bucket(world_seed, seed)

        if bucket < validation_fraction:
            return "validation"

        return "test_in_distribution" if bucket < validation_fraction + test_fraction else "train"

    split_of: dict[str, str] = {}
    dropped: dict[str, str] = {}

    for case in primaries:
        split = split_of_primary(case)

        if split is None:
            dropped[case["case_id"]] = SEED_RESERVED
        else:
            split_of[case["case_id"]] = split

    for case in evaluator:
        if case["role"] != "partner":
            continue

        split = split_of.get(case["primary_case_id"])

        if split is None:
            dropped[case["case_id"]] = SEED_RESERVED
        elif split != "test_held_out" and _kind_of(case) in HELD_OUT_KINDS:
            dropped[case["case_id"]] = HELD_OUT_PARTNER
        else:
            split_of[case["case_id"]] = split

    return split_of, dict(sorted(dropped.items()))


def _counts(cases: list[dict], visible_by_id: dict[str, dict], tags: dict[str, dict]) -> dict[str, object]:
    def label(case):
        return visible_by_id[case["case_id"]]["steps"][-1]["target"]["verb"]

    primaries = [c for c in cases if c["role"] == "primary"]
    partners = [c for c in cases if c["role"] == "partner"]

    return {
        "primary_cases": len(primaries),
        "partner_records": len(partners),
        "by_kind": dict(sorted(Counter(_kind_of(c) for c in primaries).items())),
        "by_label": dict(sorted(Counter(label(c) for c in primaries).items())),
        "by_behaviour": dict(sorted(Counter(c["planned"]["behaviour"] for c in primaries).items())),
        "partners_by_kind": dict(sorted(Counter(_kind_of(c) for c in partners).items())),
        "world_seeds": len({c["planned"]["world_seed"] for c in primaries}),
        "twin_groups": len({c["twin_group_id"] for c in cases if c["twin_group_id"]}),
        "slices": {
            "compound": sum(tags[c["case_id"]]["compound"] for c in primaries),
            "target_recent": sum(tags[c["case_id"]]["target_recent"] for c in primaries),
        },
    }


def build_splits(
    dataset_dir: Path,
    out_dir: Path,
    *,
    seed: int,
    validation_fraction: float = 0.15,
    test_fraction: float = 0.15,
) -> dict[str, object]:
    dataset_dir, out_dir = Path(dataset_dir), Path(out_dir)

    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"{out_dir} must be empty or new")

    dataset_manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    visible = [json.loads(line) for line in (dataset_dir / "hetren_visible.jsonl").open(encoding="utf-8")]
    evaluator = [json.loads(line) for line in (dataset_dir / "evaluator" / "cases.jsonl").open(encoding="utf-8")]
    tags = {t["case_id"]: t for t in map(json.loads, (dataset_dir / "evaluator" / "tags.jsonl").open(encoding="utf-8"))}
    visible_by_id = {record["case_id"]: record for record in visible}

    split_of, dropped = assign_splits(
        evaluator, seed=seed, validation_fraction=validation_fraction, test_fraction=test_fraction,
    )
    members: dict[str, list[str]] = defaultdict(list)

    for case_id, split in split_of.items():
        members[split].append(case_id)

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    for split in SPLITS:
        lines = "".join(f"{case_id}\n" for case_id in sorted(members[split]))
        (out_dir / f"{split}.txt").write_text(lines, encoding="utf-8")
        files[f"{split}.txt"] = hashlib.sha256(lines.encode("utf-8")).hexdigest()

    dropped_lines = "".join(f"{case_id}\t{reason}\n" for case_id, reason in dropped.items())
    (out_dir / DROPPED_FILE).write_text(dropped_lines, encoding="utf-8")
    files[DROPPED_FILE] = hashlib.sha256(dropped_lines.encode("utf-8")).hexdigest()

    by_split = defaultdict(list)

    for case in evaluator:
        if case["case_id"] in split_of:
            by_split[split_of[case["case_id"]]].append(case)

    manifest = {
        "format": SPLIT_FORMAT,
        "format_version": SPLIT_FORMAT_VERSION,
        "dataset": {
            "generator": dataset_manifest["generator"],
            "plan": dataset_manifest["plan"],
            "files": dataset_manifest["files"],
        },
        "parameters": {"seed": seed, "validation_fraction": validation_fraction, "test_fraction": test_fraction},
        "regenerate": (
            f"python -m packages.support_evaluator.splits --dataset {dataset_dir.as_posix()} "
            f"--out {out_dir.as_posix()} --seed {seed} --validation-fraction {validation_fraction} "
            f"--test-fraction {test_fraction}"
        ),
        "rules": {
            "held_out_kinds": list(HELD_OUT_KINDS),
            "split_unit": "world_seed",
            "held_out_seeds_reserved_for": "test_held_out (other cases on them are dropped)",
            "twin_partners": "same split as their primary; held-out-kind partners dropped outside test_held_out",
            "agent_source": "scripted cases only; live runs form a separate test split",
            "use": {
                "train": "training",
                "validation": "tuning and baselines",
                "test_in_distribution": "final evaluation only",
                "test_held_out": "final evaluation only",
            },
        },
        "files": files,
        "counts": {split: _counts(by_split[split], visible_by_id, tags) for split in SPLITS},
        "dropped": dict(sorted(Counter(dropped.values()).items())),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build frozen splits of a Milestone 2 dataset.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--test-fraction", type=float, default=0.15)
    args = parser.parse_args(argv)

    manifest = build_splits(
        args.dataset, args.out, seed=args.seed,
        validation_fraction=args.validation_fraction, test_fraction=args.test_fraction,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


__all__ = [
    "DROPPED_FILE",
    "HELD_OUT_PARTNER",
    "SEED_RESERVED",
    "SPLITS",
    "SPLIT_FORMAT",
    "SPLIT_FORMAT_VERSION",
    "assign_splits",
    "build_splits",
]


if __name__ == "__main__":
    raise SystemExit(main())
