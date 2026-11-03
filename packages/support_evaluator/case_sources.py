"""The cases a baseline runner scores: a dataset split, or the live split.

``load_source(dataset=..., split=...)`` gives the split's primary cases;
``load_source(live=...)`` gives the scored live runs (``live_episodes``).
Every case carries how to prepare it and how to score its episode, so the
runners (``gpt41_baseline``, ``local_model_baseline``, ``rules_baseline``)
treat both the same way.

A source names its output files by tier and split (``tier1-test_held_out``)
or ``live``, so several splits can share an output directory, and it is
identified by the hash of its visible records (case IDs repeat across
datasets).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from packages.support_evaluator.episodes import PreparedCase, prepare, score
from packages.support_evaluator.live_episodes import live_cases, live_model_id, prepare_live, score_live
from packages.support_evaluator.metrics import summarize


@dataclass(frozen=True)
class Case:
    case_id: str
    prepare: Callable[[], PreparedCase]
    score: Callable[[PreparedCase, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Source:
    tier: int | str  # 1, 2 or "live"
    name: str  # output file stem: "tier<N>-<split>" or "live"
    dataset: dict[str, str]  # {"name", "visible_sha256"}
    recoveries: int  # the episodes' recovery limit (the live split is tier 1)
    tags_path: Path | None
    cases: tuple[Case, ...]

    def summarize(self, rows: list[dict[str, Any]]) -> dict[str, object]:
        tags = None

        if self.tags_path is not None:
            tags = {t["case_id"]: t for t in map(json.loads, self.tags_path.open(encoding="utf-8"))}

        summary = summarize(rows, tags)

        if self.tier == "live":
            summary["live_categories"] = {
                category: summarize([r for r in rows if r["live_category"] == category])["decision_accuracy"]
                for category in sorted({r["live_category"] for r in rows})
            }

        return summary


def _score_live(row: dict[str, Any], prepared: PreparedCase, episode: dict[str, Any]) -> dict[str, Any]:
    return score_live(prepared, row, episode)


def load_source(dataset: Path | None = None, split: Path | None = None, live: Path | None = None) -> Source:
    if live is not None and (dataset is not None or split is not None):
        raise ValueError("give either a dataset and a split, or the live directory")

    if live is None and (dataset is None or split is None):
        raise ValueError("give either a dataset and a split, or the live directory")

    if live is not None:
        live = Path(live)
        model_id = live_model_id(live)
        identity = {
            "name": live.name,
            "visible_sha256": hashlib.sha256((live / "hetren_visible_final.jsonl").read_bytes()).hexdigest(),
        }
        cases = tuple(
            Case(v["run_id"], partial(prepare_live, live, v, row, model_id), partial(_score_live, row))
            for v, row in live_cases(live)
        )
        return Source("live", "live", identity, 1, None, cases)

    dataset, split = Path(dataset), Path(split)
    identity = {
        "name": dataset.name,
        "visible_sha256": json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))["files"]["hetren_visible.jsonl"],
    }
    members = set(split.read_text(encoding="utf-8").split())
    visible = map(json.loads, (dataset / "hetren_visible.jsonl").open(encoding="utf-8"))
    evaluator = map(json.loads, (dataset / "evaluator" / "cases.jsonl").open(encoding="utf-8"))
    primaries = [(v, e) for v, e in zip(visible, evaluator) if v["case_id"] in members and e["role"] == "primary"]
    tier = 2 if primaries and primaries[0][1].get("tier", 1) == 2 else 1
    cases = tuple(Case(v["case_id"], partial(prepare, v, e), score) for v, e in primaries)
    return Source(tier, f"tier{tier}-{split.stem}", identity, tier, dataset / "evaluator" / "tags.jsonl", cases)


def add_source_arguments(parser) -> None:
    parser.add_argument("--dataset", type=Path, help="dataset directory (v2 for tier 1, v3 for tier 2)")
    parser.add_argument("--split", type=Path, help="split file, e.g. docs/milestone-2/splits-v1/test_held_out.txt")
    parser.add_argument("--live", type=Path, help="live test directory instead of --dataset and --split")


def source_arguments_error(args) -> str | None:
    """Why the source arguments cannot be used, or None."""
    if args.live is not None:
        if args.dataset is not None or args.split is not None:
            return "give either --dataset and --split, or --live"
    elif args.dataset is None or args.split is None:
        return "give either --dataset and --split, or --live"

    for path in (args.live,) if args.live is not None else (args.dataset, args.split):
        if not Path(path).exists():
            return f"{path} does not exist"

    return None


__all__ = [
    "Case",
    "Source",
    "add_source_arguments",
    "load_source",
    "source_arguments_error",
]
