"""Dataset audits: leakage scans and trivial-feature shortcut classifiers.

``scan_dataset`` runs the leakage scanner (with each case's own answer
pairs) and the no-marker scan over every Hetren-visible record, and checks
that case IDs are neutral.

``shortcut_audit`` measures how well single trivial features predict the
final label, with 5-fold cross-validation against the majority-class
baseline. Numeric features use quantile-binned lookup tables; ticket text
uses multinomial naive Bayes. Features come from the first step's input
(what a model sees before probing) plus world timestamp features
reconstructed on the evaluator side.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import re

from environments.support.generator import parse_time
from packages.hetren_evidence import render_evidence
from packages.support_evaluator.cases import CaseTruth
from packages.support_evaluator.plan import PlannedCase
from packages.support_evaluator.leakage import scan_case_content


FAULT_MARKERS = (
    "fault", "swap", "identifier_mapping", "inject", "stale", "drift",
    "misconfig", "corrupt", "broken",
)
CASE_ID = re.compile(r"case-[0-9]{6}")


def primaries(visible: list[dict], evaluator: list[dict]) -> tuple[list[dict], list[dict]]:
    """Primary records only (metrics and audits never use counterfactual partners)."""
    pairs = [(v, e) for v, e in zip(visible, evaluator) if e.get("role", "primary") == "primary"]
    return [v for v, _ in pairs], [e for _, e in pairs]


def load_dataset(directory: Path) -> tuple[list[dict], list[dict]]:
    directory = Path(directory)
    visible = [json.loads(line) for line in (directory / "hetren_visible.jsonl").open(encoding="utf-8")]
    evaluator = [json.loads(line) for line in (directory / "evaluator" / "cases.jsonl").open(encoding="utf-8")]

    if [v["case_id"] for v in visible] != [e["case_id"] for e in evaluator]:
        raise ValueError("visible and evaluator records are not aligned")

    return visible, evaluator


def scan_dataset(visible: list[dict], evaluator: list[dict]) -> dict[str, object]:
    findings, markers, bad_ids, extra_keys = [], [], [], set()

    for record, case in zip(visible, evaluator):
        extra_keys |= set(record) - {"case_id", "steps"}

        for step in record["steps"]:
            extra_keys |= set(step) - {"input", "target"}

        if CASE_ID.fullmatch(record["case_id"]) is None:
            bad_ids.append(record["case_id"])

        truth = CaseTruth.from_payload(case["truth"])
        findings += [
            (record["case_id"], f.kind, f.detail)
            for f in scan_case_content({"steps": record["steps"]}, truth)
        ]
        text = json.dumps(record).lower()
        markers += [(record["case_id"], m) for m in FAULT_MARKERS if m in text]

    return {
        "records": len(visible),
        "leak_findings": findings,
        "marker_findings": markers,
        "non_neutral_ids": bad_ids,
        "unexpected_visible_keys": sorted(extra_keys),
    }


def label_of(record: dict) -> str:
    """The record's label: its non-probe actions in order (tier 2 can have two recoveries, then stop)."""
    return ">".join(s["target"]["verb"] for s in record["steps"] if s["target"]["action"] != "probe")


# Features


def _ticket_text(first_input: dict) -> str:
    for step in first_input["steps"]:
        if step["tool"] == "read_ticket" and step["outcome"] == "succeeded":
            observation = step["observation"]
            return f"{observation.get('subject', '')} {observation.get('body', '')}"

    return ""


def _timestamp_features(case: dict) -> dict[str, float]:
    # The world as the model sees it when probing: with the case's distractors (tier 2).
    from packages.support_evaluator.distractors import inject_planned

    spec = inject_planned(PlannedCase(**case["planned"]))[0].spec
    truth = case["truth"]
    directory = dict(spec.directory)
    ticket = next(t for t in spec.tickets if t.ticket_id == truth["target_ticket_id"])
    account_id = directory.get(ticket.customer_ref)
    account = next((a for a in spec.accounts if a.account_id == account_id), None)

    if account is None:
        return {"source_gap_hours": 0.0, "recency_days": -1.0, "history_events": 0.0}

    source = next((s for s in spec.account_sources if s.account_id == account_id), None)
    source_time = parse_time(source.updated_at) if source else parse_time(account.updated_at)
    working_time = parse_time(account.updated_at)

    return {
        "source_gap_hours": (source_time - working_time).total_seconds() / 3600,
        "recency_days": (parse_time(spec.as_of) - working_time).total_seconds() / 86400,
        "history_events": float(sum(e.account_id == account_id for e in spec.account_history)),
    }


def case_features(record: dict, case: dict, encoding) -> dict[str, object]:
    first = record["steps"][0]["input"]
    steps = first["steps"]
    features: dict[str, object] = {
        "step_count": float(len(steps)),
        "error_present": float(any(s["outcome"] == "failed" for s in steps)),
        "denied_present": float(any(s["outcome"] == "denied" for s in steps)),
        "input_tokens": float(len(encoding.encode(render_evidence(first)))),
        "ticket_text": _ticket_text(first),
    }
    features.update(_timestamp_features(case))
    return features


# Classifiers


def _folds(n: int, k: int, seed: int) -> list[list[int]]:
    order = list(range(n))
    random.Random(seed).shuffle(order)
    return [order[i::k] for i in range(k)]


def _bin_edges(values: list[float], bins: int = 10) -> list[float]:
    ordered = sorted(values)
    return sorted({ordered[int(len(ordered) * q / bins)] for q in range(1, bins)})


def _bin(value: float, edges: list[float]) -> int:
    return sum(value > edge for edge in edges)


def _lookup_accuracy(values: list[float], labels: list[str], k: int = 5, seed: int = 0) -> float:
    correct = 0

    for fold in _folds(len(values), k, seed):
        test = set(fold)
        train = [i for i in range(len(values)) if i not in test]
        edges = _bin_edges([values[i] for i in train])
        table: dict[int, Counter] = defaultdict(Counter)

        for i in train:
            table[_bin(values[i], edges)][labels[i]] += 1

        fallback = Counter(labels[i] for i in train).most_common(1)[0][0]

        for i in fold:
            counts = table.get(_bin(values[i], edges))
            correct += (counts.most_common(1)[0][0] if counts else fallback) == labels[i]

    return correct / len(values)


_WORD = re.compile(r"[a-z]+")


def _naive_bayes_accuracy(texts: list[str], labels: list[str], k: int = 5, seed: int = 0) -> float:
    tokens = [_WORD.findall(text.lower()) for text in texts]
    correct = 0

    for fold in _folds(len(texts), k, seed):
        test = set(fold)
        train = [i for i in range(len(texts)) if i not in test]
        priors = Counter(labels[i] for i in train)
        words: dict[str, Counter] = defaultdict(Counter)
        vocabulary = set()

        for i in train:
            words[labels[i]].update(tokens[i])
            vocabulary.update(tokens[i])

        totals = {label: sum(counts.values()) for label, counts in words.items()}

        for i in fold:
            scores = {
                label: math.log(priors[label] / len(train)) + sum(
                    math.log((words[label][w] + 1) / (totals.get(label, 0) + len(vocabulary)))
                    for w in tokens[i]
                )
                for label in priors
            }
            correct += max(scores, key=scores.get) == labels[i]

    return correct / len(texts)


@dataclass(frozen=True)
class FeatureResult:
    feature: str
    accuracy: float
    baseline: float
    kind: str

    @property
    def lift(self) -> float:
        return self.accuracy - self.baseline


# Features that legitimately describe what went wrong in the run, versus
# features that should carry no information about the correct action.
EVIDENCE_FEATURES = ("step_count", "error_present", "denied_present", "input_tokens", "source_gap_hours")
SPURIOUS_FEATURES = ("ticket_text", "recency_days", "history_events")


def shortcut_audit(visible: list[dict], evaluator: list[dict], encoding) -> list[FeatureResult]:
    visible, evaluator = primaries(visible, evaluator)
    labels = [label_of(record) for record in visible]
    features = [case_features(r, c, encoding) for r, c in zip(visible, evaluator)]
    baseline = Counter(labels).most_common(1)[0][1] / len(labels)
    results = []

    for name in EVIDENCE_FEATURES + SPURIOUS_FEATURES:
        if name == "ticket_text":
            accuracy = _naive_bayes_accuracy([f[name] for f in features], labels)
        else:
            accuracy = _lookup_accuracy([float(f[name]) for f in features], labels)

        kind = "evidence" if name in EVIDENCE_FEATURES else "should_be_uninformative"
        results.append(FeatureResult(name, accuracy, baseline, kind))

    return results


__all__ = [
    "EVIDENCE_FEATURES",
    "FeatureResult",
    "SPURIOUS_FEATURES",
    "case_features",
    "label_of",
    "load_dataset",
    "primaries",
    "scan_dataset",
    "shortcut_audit",
]
