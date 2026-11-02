"""Metric formulas for scored episodes (task 12; defined in EVAL_PROTOCOL.md).

``summarize(rows, tags)`` takes the rows ``episodes.score`` writes for the
primary cases of one split and one tier. Every rate is reported as
``{"n", "k", "rate", "ci95"}`` with a Wilson 95% interval.

Decision metrics use every row, undetermined cases included (their final
labels come from execution). Probe-efficiency metrics use only determined
rows (``probe_label.determined``), and the undetermined count is reported
with them.

``python -m packages.support_evaluator.metrics --rows <rows.jsonl>
--dataset <dir> --out <summary.json>`` re-summarizes recorded rows: rows
written before a row carried ``determined`` and ``oracle_probes`` get them
from the dataset's evaluator records (and older tier 1 rows their ``tier``
and ``recoveries``), and slices use its ``tags.jsonl``.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from typing import Any


DECISIONS = ("insufficient_evidence", "abstain", "no_intervention")
# Families whose fault leaves no anomaly in the run (only a probe reveals it).
PROACTIVE_KINDS = ("stale_account_record", "queue_misconfiguration")
LENGTH_BINS = 10
Z95 = 1.959964


def wilson(k: int, n: int) -> list[float] | None:
    if not n:
        return None

    p = k / n
    centre = (p + Z95 ** 2 / (2 * n)) / (1 + Z95 ** 2 / n)
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95 ** 2 / (4 * n ** 2)) / (1 + Z95 ** 2 / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def rate(k: int, n: int) -> dict[str, object]:
    return {"n": n, "k": k, "rate": round(k / n, 4) if n else None, "ci95": wilson(k, n)}


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def label_kind(row: dict[str, Any]) -> tuple[str, str]:
    """The label's first non-probe action (tier 2: the first target)."""
    return row["label"]["action"], row["label"]["verb"]


def label_key(row: dict[str, Any]) -> str:
    """The whole label: its non-probe verbs in order (tier 2 sequences joined by ">")."""
    targets = row.get("label_targets") or [row["label"]]
    return ">".join(target["verb"] for target in targets)


def first_action(row: dict[str, Any]) -> dict[str, Any]:
    """The policy's first non-probe action (in tier 2 a stop after a recovery is not a decision)."""
    return row["recoveries"][0] if row["recoveries"] else (row["final"] or {})


def _healthy(row: dict[str, Any]) -> bool:
    return label_kind(row) == ("decide", "no_intervention")


def _determined(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("determined", True)]


def decision_metrics(rows: list[dict[str, Any]]) -> dict[str, object]:
    recover = [r for r in rows if r["label"]["action"] == "recover"]
    healthy = [r for r in rows if _healthy(r)]
    result: dict[str, object] = {
        "cases": len(rows),
        "decision_accuracy": rate(sum(r["correct"] for r in rows), len(rows)),
        "exact_match": rate(sum(r["exact"] for r in rows), len(rows)),
        "verified_recovery_rate": rate(sum(r["correct"] and bool(r["recoveries"]) for r in recover), len(recover)),
        "wrong_interventions_on_healthy": rate(sum(bool(r["recoveries"]) for r in healthy), len(healthy)),
        "invalid_actions": rate(sum((r["failure"] or "").startswith("invalid_action") for r in rows), len(rows)),
        "failed_recovery_calls": sum(bool(r.get("recovery_failures")) for r in rows),
        "failures": dict(Counter(r["failure"] for r in rows if r["failure"])),
    }

    for verb in DECISIONS:
        truth = [r for r in rows if label_kind(r) == ("decide", verb)]
        chosen = [r for r in rows if first_action(r).get("verb") == verb]
        result[verb] = {
            "recall": rate(sum(r["correct"] for r in truth), len(truth)),
            "precision": rate(sum(r["correct"] for r in chosen), len(chosen)),
        }

    return result


def probe_metrics(rows: list[dict[str, Any]]) -> dict[str, object]:
    determined = _determined(rows)
    healthy = [r for r in determined if _healthy(r)]
    with_oracle = [r for r in determined if r.get("oracle_probes") is not None]
    return {
        "undetermined": len(rows) - len(determined),
        "determined_cases": len(determined),
        "mean_probes": _mean([len(r["probes"]) for r in determined]),
        "mean_probes_on_healthy": _mean([len(r["probes"]) for r in healthy]),
        "oracle_mean_probes": _mean([r["oracle_probes"] for r in with_oracle]),
        "mean_excess_probes": _mean([len(r["probes"]) - r["oracle_probes"] for r in with_oracle]),
        "probe_budget_exceeded": rate(sum(r["failure"] == "probe_budget_exceeded" for r in rows), len(rows)),
    }


def sequence_metrics(rows: list[dict[str, Any]]) -> dict[str, object]:
    fixed = [r for r in rows if r["label_recoveries"] >= 1]
    two = [r for r in rows if r["label_recoveries"] == 2]
    return {
        "exact_sequence_match": rate(sum(r["exact"] for r in rows), len(rows)),
        "longer_than_label": rate(
            sum(r["correct"] and len(r["recoveries"]) > r["label_recoveries"] for r in fixed), len(fixed),
        ),
        "stopped_after_one_of_two": rate(
            sum(len(r["recoveries"]) == 1 and (r["final"] or {}).get("action") in ("decide", "recover") for r in two),
            len(two),
        ),
        "two_recovery_labels": rate(sum(r["correct"] for r in two), len(two)),
    }


def _group(rows: list[dict[str, Any]]) -> dict[str, object]:
    probes = probe_metrics(rows)
    return {
        "decision_accuracy": rate(sum(r["correct"] for r in rows), len(rows)),
        "mean_probes": probes["mean_probes"],
        "undetermined": probes["undetermined"],
    }


def length_metrics(rows: list[dict[str, Any]], tokens: dict[str, int]) -> dict[str, object]:
    """Accuracy within first-input token deciles, and reweighted so every label has the same length distribution.

    A row of label L in bin b gets weight P(b) / P(b | L).
    """
    values = sorted(tokens[r["case_id"]] for r in rows)
    edges = [values[len(values) * i // LENGTH_BINS] for i in range(1, LENGTH_BINS)]
    bin_of = {r["case_id"]: bisect_right(edges, tokens[r["case_id"]]) for r in rows}
    overall = Counter(bin_of.values())
    by_label = defaultdict(Counter)

    for r in rows:
        by_label[label_key(r)][bin_of[r["case_id"]]] += 1

    weight = {
        r["case_id"]: (overall[bin_of[r["case_id"]]] / len(rows))
        / (by_label[label_key(r)][bin_of[r["case_id"]]] / sum(by_label[label_key(r)].values()))
        for r in rows
    }
    total = sum(weight.values())
    deciles = defaultdict(list)

    for r in rows:
        deciles[bin_of[r["case_id"]]].append(r)

    return {
        "edges": edges,
        "deciles": {b: rate(sum(r["correct"] for r in group), len(group)) for b, group in sorted(deciles.items())},
        "reweighted_accuracy": round(sum(weight[r["case_id"]] * r["correct"] for r in rows) / total, 4),
    }


def summarize(rows: list[dict[str, Any]], tags: dict[str, dict] | None = None) -> dict[str, object]:
    """Every metric of the protocol for the rows of one split and one tier."""
    result = decision_metrics(rows)
    result["probes"] = probe_metrics(rows)
    tier2 = [r for r in rows if r["tier"] == 2]

    if tier2:
        result["sequence"] = sequence_metrics(tier2)

    by_family = defaultdict(list)

    for row in rows:
        by_family[row["case_kind"]].append(row)

    result["by_family"] = {
        kind: {"held_out": group[0]["held_out"], **_group(group)} for kind, group in sorted(by_family.items())
    }
    result["training_families"] = _group([r for r in rows if not r["held_out"]]) if any(not r["held_out"] for r in rows) else None
    result["held_out_families"] = _group([r for r in rows if r["held_out"]]) if any(r["held_out"] for r in rows) else None
    proactive = [r for r in rows if r["case_kind"] in PROACTIVE_KINDS]
    result["proactive_detection"] = _group(proactive) if proactive else None

    if tags is not None:
        slices = {
            "compound": [r for r in rows if tags[r["case_id"]]["compound"]],
            "target_recent_faulty": [r for r in rows if tags[r["case_id"]]["target_recent"] and not _healthy(r)],
        }

        if tier2:
            slices["compound_pair"] = [r for r in rows if tags[r["case_id"]]["compound_pair"]]

        result["slices"] = {name: rate(sum(r["correct"] for r in group), len(group)) for name, group in slices.items()}
        result["slices"]["length_matched"] = length_metrics(
            rows, {r["case_id"]: tags[r["case_id"]]["first_input_tokens"] for r in rows},
        )

    return result


def attach_case_facts(rows: list[dict[str, Any]], dataset_dir: Path) -> list[dict[str, Any]]:
    """Rows with ``determined`` and ``oracle_probes`` from the dataset's evaluator records.

    Tier 1 rows written before rows carried ``tier`` and ``recoveries`` get
    them from their final action (the only action a tier 1 episode applies).
    """
    facts = {}

    for line in (Path(dataset_dir) / "evaluator" / "cases.jsonl").open(encoding="utf-8"):
        case = json.loads(line)

        if case["role"] == "primary":
            facts[case["case_id"]] = {
                "determined": case["probe_label"]["determined"],
                "oracle_probes": len(case["probe_label"]["probes"]),
            }

    def legacy(row):
        final = row["final"]
        return {"tier": 1, "recoveries": [final] if final and final["action"] == "recover" else []}

    return [{**legacy(r), **facts[r["case_id"]], **r} for r in rows]


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Summarize recorded episode rows with the protocol's metrics.")
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    rows = attach_case_facts([json.loads(line) for line in args.rows.open(encoding="utf-8")], args.dataset)
    tags = {t["case_id"]: t for t in map(json.loads, (args.dataset / "evaluator" / "tags.jsonl").open(encoding="utf-8"))}
    args.out.write_text(json.dumps(summarize(rows, tags), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "attach_case_facts",
    "decision_metrics",
    "first_action",
    "label_key",
    "label_kind",
    "length_metrics",
    "probe_metrics",
    "rate",
    "sequence_metrics",
    "summarize",
    "wilson",
]
