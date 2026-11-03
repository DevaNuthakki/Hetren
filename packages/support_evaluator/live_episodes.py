"""Episodes on the live test split (EVAL_PROTOCOL.md, "Live test split").

A live run's world is rebuilt from the evaluator's plan, checked against
its exported spec, and its recorded captures are replayed exactly (no API
call), so a policy starts from the live run's own end state and evidence.
The first input must equal the live record's (``hetren_visible_final.jsonl``).

Live episodes are tier 1. Scoring follows the run's label category
(``evaluator/live_labels_final.jsonl``):

- ``proxy_matched``: verified by execution as for scripted cases, with a
  matching scripted behaviour standing in for the live agent when a
  recovery re-runs the task (all matching behaviours give the same label);
- ``final_label_only``: the label is ``no_intervention`` or
  ``insufficient_evidence``, which ``verify_label`` settles without any
  re-run, so no stand-in is needed (none is set: a re-run would fail);
- ``live_confirmed_target``: no scripted behaviour matches, and the label
  is the recovery confirmed by one live re-run; only that exact recovery
  is scored correct;
- ``excluded``: never scored (headline metrics never include it).

Runs without a probe-sequence label count as undetermined for the
probe-efficiency metrics.

``live_manifest`` pins the live split for the protocol freeze: the export
manifest plus the hashes of every capture, the confirmation files and the
final labels and records (the data itself is gitignored). Run
``python -m packages.support_evaluator.live_episodes --live-dir <dir> --out <manifest.json>``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

from packages.contracts import ContractError
from packages.hetren_evidence import compact_evidence
from packages.support_evaluator.episodes import PreparedCase, score
from packages.support_evaluator.live_labels import _rebuild, replay_live_run


SCORED_CATEGORIES = ("proxy_matched", "final_label_only", "live_confirmed_target")
LIVE_BEHAVIOUR = "live"


def live_model_id(live_dir: Path) -> str:
    return json.loads((Path(live_dir) / "captures" / "ledger.json").read_text(encoding="utf-8"))["model"]


def live_cases(live_dir: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(visible record, final label row) for every scored live run, in run order."""
    live_dir = Path(live_dir)
    visible = {r["run_id"]: r for r in map(json.loads, (live_dir / "hetren_visible_final.jsonl").open(encoding="utf-8"))}
    labels = map(json.loads, (live_dir / "evaluator" / "live_labels_final.jsonl").open(encoding="utf-8"))
    return [(visible[row["run_id"]], row) for row in labels if row["category"] in SCORED_CATEGORIES]


def prepare_live(live_dir: Path, visible: dict[str, Any], label_row: dict[str, Any], model_id: str) -> PreparedCase:
    live_dir = Path(live_dir)
    run_id = visible["run_id"]
    spec, planned, case = _rebuild(live_dir, run_id)
    environment, record = replay_live_run(spec, case.spec, live_dir / "captures" / run_id, model_id)
    evidence = record.evidence_payload()

    if compact_evidence(evidence) != visible["steps"][0]["input"]:
        raise ContractError(f"{run_id}: replayed live input differs from the live record")

    stand_in = label_row["matching_behaviours"][0] if label_row["category"] == "proxy_matched" else LIVE_BEHAVIOUR
    probes = label_row.get("probes")
    return PreparedCase(
        run_id, replace(planned, behaviour=stand_in), case, environment, evidence, label_row["label"],
        determined=bool(label_row.get("determined")), oracle_probes=len(probes) if probes is not None else None,
    )


def score_live(prepared: PreparedCase, label_row: dict[str, Any], episode: dict[str, Any]) -> dict[str, Any]:
    category = label_row["category"]

    if category not in SCORED_CATEGORIES:
        raise ContractError(f"{prepared.case_id}: {category} runs are never scored")

    confirmed = (lambda final: final == prepared.label) if category == "live_confirmed_target" else None
    row = score(prepared, episode, verify=confirmed)
    return {**row, "behaviour": LIVE_BEHAVIOUR, "live_category": category,
            "proxy_behaviour": prepared.planned.behaviour if category == "proxy_matched" else None}


FINAL_FILES = (
    "hetren_visible_final.jsonl",
    "evaluator/live_labels_final.jsonl",
    "evaluator/confirmations.jsonl",
    "evaluator/confirmation_results.jsonl",
)
RECORDED_DIRS = ("captures", "confirm", "confirm-captures")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def directory_digest(directory: Path) -> str:
    """One hash over every file below ``directory``: sha256 of the sorted "<relative path> <sha256>" lines."""
    lines = sorted(f"{p.relative_to(directory).as_posix()} {_sha256(p)}\n" for p in directory.rglob("*") if p.is_file())
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def live_manifest(live_dir: Path) -> dict[str, Any]:
    live_dir = Path(live_dir)
    export = json.loads((live_dir / "manifest.json").read_text(encoding="utf-8"))
    labels = [json.loads(line) for line in (live_dir / "evaluator" / "live_labels_final.jsonl").open(encoding="utf-8")]
    return {
        **export,
        "data_location": f"artifacts/milestone-2/{live_dir.name} (gitignored)",
        "model": live_model_id(live_dir),
        "categories": dict(sorted(Counter(row["category"] for row in labels).items())),
        "files": {
            **export["files"],
            **{name: _sha256(live_dir / name) for name in FINAL_FILES},
            **{f"{name}/": directory_digest(live_dir / name) for name in RECORDED_DIRS},
        },
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Write the live split's manifest for the protocol freeze.")
    parser.add_argument("--live-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    args.out.write_text(json.dumps(live_manifest(args.live_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LIVE_BEHAVIOUR",
    "SCORED_CATEGORIES",
    "directory_digest",
    "live_cases",
    "live_manifest",
    "live_model_id",
    "prepare_live",
    "score_live",
]
