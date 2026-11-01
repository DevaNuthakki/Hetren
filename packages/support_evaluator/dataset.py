"""Versioned, hashed dataset of labelled scripted runs (evaluator side).

Layout of one dataset directory::

    hetren_visible.jsonl     one line per record: case_id and its steps, each
                             a compact input and the target action. This is
                             the only file a model or Hetren ever reads.
    evaluator/cases.jsonl    one line per record: role (primary case or
                             counterfactual partner), the plan entry, case
                             truth, world hash, twin group, label provenance,
                             probe label and labeling time. Evaluator-side only.
    manifest.json            format and generator versions, plan parameters,
                             counts, and the SHA-256 of each file.

Twin cases also write their counterfactual partners (the other worlds whose
evidence is identical up to renaming) as their own records, tagged
evaluator-side with ``role: partner``, the primary's case ID and the shared
twin group ID. Evaluation metrics use primary records only.

Case IDs are neutral (``case-NNNNNN``) and assigned after a seeded shuffle
of all records, so their order says nothing about role, kind, variant or
behaviour. Records are written sorted by case ID. Labeling time is kept
only in the evaluator file and the data files are hashed; the visible file
is byte-identical for the same parameters.

Results are appended to ``<out>.partial.jsonl`` as each case finishes, so a
failure late in a long build does not lose finished work.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
import random

from environments.support.generator import GENERATOR_NAME, GENERATOR_VERSION, generate_world
from packages.support_evaluator.injectors import _recently_changed, inject
from packages.support_evaluator.labeler import label_case
from packages.support_evaluator.plan import PlannedCase, cross_plan


DATASET_FORMAT = "hetren-support-dataset"
DATASET_FORMAT_VERSION = 1


def _summary(sandbox: dict[str, object]) -> dict[str, object]:
    return {
        "action": sandbox["action"],
        "verified": sandbox["verified"],
        "failed_checks": sorted(name for name, ok in sandbox["checks"].items() if not ok),
        "regression_ok": sandbox["regression_ok"],
    }


def label_planned(planned: PlannedCase) -> dict[str, object]:
    """Label one case; returns its primary record and any partner records (no IDs)."""
    labelled = label_case(planned)
    provenance = labelled.provenance_payload()
    run = provenance["run_label"]
    run["sandboxes"] = [_summary(sandbox) for sandbox in run["sandboxes"]]
    twin = labelled.probe_label.twin_group_id

    primary = {
        "visible": {"steps": list(labelled.steps)},
        "evaluator": {
            "role": "primary",
            "planned": asdict(planned),
            "truth": labelled.case.truth.canonical_payload(),
            "world_sha256": labelled.case.spec.world_sha256,
            "twin_group_id": twin,
            "run_label": run,
            "probe_label": provenance["probe_label"],
        },
        "labeling_seconds": round(labelled.seconds, 3),
    }
    partners = [
        {
            "visible": {"steps": partner["steps"]},
            "evaluator": {
                "role": "partner",
                "planned": asdict(planned),
                "counterfactual": partner["counterfactual"],
                "truth": partner["truth"],
                "world_sha256": partner["world_sha256"],
                "twin_group_id": twin,
                "rule": partner["rule"],
            },
        }
        for partner in labelled.partners
    ]
    return {"primary": primary, "partners": partners}


def _label_indexed(item: tuple[int, PlannedCase]) -> tuple[int, dict[str, object]]:
    index, planned = item
    return index, label_planned(planned)


def preflight(plan: tuple[PlannedCase, ...]) -> None:
    """Inject every planned case before labeling (milliseconds each).

    Catches injection errors in seconds instead of after hours of labeling.
    """
    for planned in plan:
        inject(
            planned.case_kind, generate_world(planned.world_seed),
            random.Random(planned.case_seed), planned.case_variant,
        )


def record_line(record: dict[str, object]) -> str:
    """The exact JSONL line written for one record."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def flatten(results: list[dict[str, object]]) -> list[tuple[int, int, dict]]:
    """(plan index, position, record) for every record; position 0 is the primary."""
    return [
        (index, position, record)
        for index, result in enumerate(results)
        for position, record in enumerate([result["primary"], *result["partners"]])
    ]


def assign_case_ids(records: list[tuple[int, int, dict]], seed: int) -> list[str]:
    """Neutral case IDs from a seeded shuffle of all records."""
    order = list(range(len(records)))
    random.Random(f"{seed}:case-ids").shuffle(order)
    ids = [""] * len(records)

    for rank, row in enumerate(order):
        ids[row] = f"case-{rank + 1:06d}"

    return ids


def _write_jsonl(path: Path, records: Iterable[dict[str, object]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()

    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            line = record_line(record)
            handle.write(line)
            digest.update(line.encode("utf-8"))

    return digest.hexdigest()


def build_dataset(
    out_dir: Path,
    *,
    per_cell: int,
    seed: int,
    withheld_per_cell: int = 0,
    processes: int = 1,
    kinds: tuple[str, ...] | None = None,
    progress: bool = False,
) -> dict[str, object]:
    out_dir = Path(out_dir)
    partial = out_dir.with_name(out_dir.name + ".partial.jsonl")

    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"{out_dir} must be empty or new")

    if partial.exists():
        raise FileExistsError(f"{partial} already exists")

    plan = cross_plan(per_cell, seed, kinds=kinds, withheld_per_cell=withheld_per_cell)
    preflight(plan)

    indexed = list(enumerate(plan))
    results: list = [None] * len(plan)
    partial.parent.mkdir(parents=True, exist_ok=True)

    with partial.open("w", encoding="utf-8") as sink:
        def record(index, result, done):
            results[index] = result
            sink.write(record_line({"plan_index": index, **result}))
            sink.flush()

            if progress and (done % 200 == 0 or done == len(plan)):
                print(f"labelled {done}/{len(plan)}", flush=True)

        if processes > 1:
            with get_context("spawn").Pool(processes) as pool:
                # Results stream back as they finish; the first error stops the run.
                for done, (index, result) in enumerate(
                    pool.imap_unordered(_label_indexed, indexed, chunksize=4), start=1,
                ):
                    record(index, result, done)
        else:
            for done, (index, planned) in enumerate(indexed, start=1):
                record(index, label_planned(planned), done)

    records = flatten(results)
    ids = assign_case_ids(records, seed)
    ranked = sorted(range(len(records)), key=lambda row: ids[row])

    visible_sha = _write_jsonl(
        out_dir / "hetren_visible.jsonl",
        ({"case_id": ids[row], **records[row][2]["visible"]} for row in ranked),
    )

    primary_id = {records[row][0]: ids[row] for row in range(len(records)) if records[row][1] == 0}

    def evaluator_record(row):
        index, position, record = records[row]
        extra = {} if position == 0 else {"primary_case_id": primary_id[index]}
        return {"case_id": ids[row], **record["evaluator"], **extra}

    evaluator_sha = _write_jsonl(
        out_dir / "evaluator" / "cases.jsonl", (evaluator_record(row) for row in ranked),
    )
    timing_sha = _write_jsonl(
        out_dir / "evaluator" / "labeling_time.jsonl",
        (
            {"case_id": ids[row], "labeling_seconds": records[row][2]["labeling_seconds"]}
            for row in ranked if records[row][1] == 0
        ),
    )

    roles = [record[2]["evaluator"]["role"] for record in records]
    manifest = {
        "format": DATASET_FORMAT,
        "format_version": DATASET_FORMAT_VERSION,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "plan": {
            "per_cell": per_cell, "seed": seed, "withheld_per_cell": withheld_per_cell,
            "kinds": list(kinds) if kinds else "default",
        },
        "counts": {
            "primary_cases": roles.count("primary"),
            "partner_records": roles.count("partner"),
            "records": len(records),
            "steps": sum(len(record[2]["visible"]["steps"]) for record in records),
        },
        "files": {
            "hetren_visible.jsonl": visible_sha,
            "evaluator/cases.jsonl": evaluator_sha,
        },
        # Wall-clock timing differs between builds; hashed but not reproducible.
        "timing_file": {"evaluator/labeling_time.jsonl": timing_sha},
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    write_tags(out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

    seconds = [result["primary"]["labeling_seconds"] for result in results]
    return {"manifest": manifest, "seconds": seconds}


def is_compound(truth: dict[str, object], label: dict[str, object]) -> bool:
    """A recovery or abstain label that differs from the case's own remedy.

    Another problem in the run (for example a now-false claim that a
    text-following agent obeys) prevented the intended single fix.
    """
    if label["action"] == "decide" and label["verb"] in ("no_intervention", "insufficient_evidence"):
        return False

    return label["verb"] != truth["remedy_if_wrong"]


def _target_recent(case: dict[str, object]) -> bool:
    planned = case["planned"]
    spec = inject(
        planned["case_kind"], generate_world(planned["world_seed"]),
        random.Random(planned["case_seed"]), planned["case_variant"],
    ).spec
    ticket = next(t for t in spec.tickets if t.ticket_id == case["truth"]["target_ticket_id"])
    account_id = dict(spec.directory).get(ticket.customer_ref)
    account = next((a for a in spec.accounts if a.account_id == account_id), None)
    return account is not None and _recently_changed(spec, account)


def write_tags(out_dir: Path) -> str:
    """Evaluator-side slice tags for primary records (deterministic, hashed).

    ``compound``: see ``is_compound``. ``target_recent``: the target account
    had a recent tier change (recent-target stress slice).
    ``first_input_tokens``: o200k_base tokens of the first step's input
    (length-matched slice).
    """
    import tiktoken

    from packages.hetren_evidence import render_evidence

    out_dir = Path(out_dir)
    encoding = tiktoken.get_encoding("o200k_base")
    visible = [json.loads(line) for line in (out_dir / "hetren_visible.jsonl").open(encoding="utf-8")]
    evaluator = [json.loads(line) for line in (out_dir / "evaluator" / "cases.jsonl").open(encoding="utf-8")]
    tags = []

    for record, case in zip(visible, evaluator):
        if case["role"] != "primary":
            continue

        tags.append(
            {
                "case_id": case["case_id"],
                "compound": is_compound(case["truth"], record["steps"][-1]["target"]),
                "target_recent": _target_recent(case),
                "first_input_tokens": len(encoding.encode(render_evidence(record["steps"][0]["input"]))),
            }
        )

    digest = _write_jsonl(out_dir / "evaluator" / "tags.jsonl", tags)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["evaluator/tags.jsonl"] = digest
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return digest


def committed_manifest(out_dir: Path, primaries: int = 8, partners: int = 2) -> dict[str, object]:
    """Manifest plus per-record hashes for a seeded sample of records.

    The data files are too large to commit or to regenerate in CI; the sample
    lets a test re-label a few cases from the plan and check every line. Each
    sample entry records its plan index and position (0 = primary).
    """
    out_dir = Path(out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    partial = out_dir.with_name(out_dir.name + ".partial.jsonl")
    results: dict[int, dict] = {}

    for line in partial.open(encoding="utf-8"):
        row = json.loads(line)
        results[row.pop("plan_index")] = row

    records = flatten([results[index] for index in range(len(results))])
    ids = assign_case_ids(records, manifest["plan"]["seed"])
    row_of = {case_id: row for row, case_id in enumerate(ids)}
    visible = {
        json.loads(line)["case_id"]: line
        for line in (out_dir / "hetren_visible.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)
    }
    evaluator = {
        json.loads(line)["case_id"]: line
        for line in (out_dir / "evaluator" / "cases.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)
    }
    rng = random.Random(f"{manifest['plan']['seed']}:sample")
    primary_ids = sorted(case_id for case_id in ids if records[row_of[case_id]][1] == 0)
    partner_ids = sorted(case_id for case_id in ids if records[row_of[case_id]][1] > 0)
    chosen = sorted(rng.sample(primary_ids, primaries) + rng.sample(partner_ids, min(partners, len(partner_ids))))
    sample = []

    for case_id in chosen:
        index, position, _ = records[row_of[case_id]]
        entry = {
            "case_id": case_id,
            "plan_index": index,
            "position": position,
            "visible_line_sha256": hashlib.sha256(visible[case_id].encode("utf-8")).hexdigest(),
            "evaluator_line_sha256": hashlib.sha256(evaluator[case_id].encode("utf-8")).hexdigest(),
        }

        if position > 0:
            entry["primary_case_id"] = json.loads(evaluator[case_id])["primary_case_id"]

        sample.append(entry)

    return {
        **manifest,
        "data_location": f"artifacts/milestone-2/{out_dir.name} (gitignored)",
        "regenerate": (
            "python -m packages.support_evaluator.dataset --out <dir> "
            f"--per-cell {manifest['plan']['per_cell']} --seed {manifest['plan']['seed']} "
            f"--withheld-per-cell {manifest['plan']['withheld_per_cell']} --processes <n>"
        ),
        "sample": sample,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import time

    parser = argparse.ArgumentParser(description="Build a labelled Milestone 2 dataset.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--per-cell", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--withheld-per-cell", type=int, default=0)
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--kinds", nargs="*")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = build_dataset(
        args.out, per_cell=args.per_cell, seed=args.seed,
        withheld_per_cell=args.withheld_per_cell, processes=args.processes,
        kinds=tuple(args.kinds) if args.kinds else None, progress=True,
    )
    seconds = result["seconds"]
    print(json.dumps(result["manifest"], indent=2, sort_keys=True))
    print(f"wall seconds: {time.perf_counter() - started:.1f}")
    print(f"labeling seconds per case: mean {sum(seconds) / len(seconds):.2f}, max {max(seconds):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
