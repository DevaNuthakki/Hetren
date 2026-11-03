"""Reusable leakage scanner for agent- and Hetren-visible surfaces.

Callers pass named surfaces (prompts, tool outputs, stage records, traces,
run records, diagnosis inputs, ...) as JSON-compatible values, plus any
identifiers (run IDs, capture file names). The scanner reports:

- ``evaluator_field_name``: a mapping key that only evaluator records use;
- ``sensitive_token``: a fault ID, fault type, example name, verdict,
  evidence condition, or evaluator field name inside any string;
- ``answer_pair``: one string containing both a ticket and its expected
  queue or account;
- ``answer_mapping``: a mapping keyed by a ticket ID whose value is that
  ticket's expected queue or account;
- ``non_neutral_identifier``: an identifier that does not match its neutral
  pattern.

Ordinary environment observations are not flagged: a routed ticket's
``{"ticket_id": ..., "queue_id": ...}`` keeps the ticket and queue in
separate fields, and account or queue IDs on their own are not answers.

Scope of the answer checks
--------------------------
``answer_pair`` and ``answer_mapping`` apply to everything given TO the agent
or TO Hetren: prompts, tool definitions, tool outputs, stage records Hetren
reads, diagnosis inputs, and identifiers. Use ``scan_content`` for these.

The agent's own outputs (its tool-call arguments and final message) are its
decisions and may legitimately name a ticket together with a queue or
account. Scan them with ``scan_agent_outputs``, which skips the two answer
checks but still applies the evaluator field-name and sensitive-token checks.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re

from packages.support_evaluator.catalog import (
    EVALUATOR_FIELD_NAMES,
    answer_pairs,
    sensitive_tokens,
)
from packages.support_evaluator.cases import CaseTruth, case_answer_pairs
from packages.support_evaluator.registry import NEUTRAL_RUN_ID


NEUTRAL_FILE_NAME = re.compile(r"(run|capture)-[0-9]{4}\.json")


@dataclass(frozen=True)
class LeakFinding:
    surface: str
    path: str
    kind: str
    detail: str


def _scan_string(
    value: str,
    *,
    surface: str,
    path: str,
    tokens: frozenset[str],
    pairs: frozenset[tuple[str, str]],
) -> list[LeakFinding]:
    findings: list[LeakFinding] = []
    folded = value.casefold()

    for token in sorted(tokens):
        if token.casefold() in folded:
            findings.append(LeakFinding(surface, path, "sensitive_token", token))

    for ticket_id, expected in sorted(pairs):
        if ticket_id in value and expected in value:
            findings.append(
                LeakFinding(surface, path, "answer_pair", f"{ticket_id}->{expected}")
            )

    return findings


def _walk(
    value: object,
    *,
    surface: str,
    path: str,
    tokens: frozenset[str],
    pairs: frozenset[tuple[str, str]],
) -> list[LeakFinding]:
    if value is None or isinstance(value, (bool, int, float)):
        return []

    if isinstance(value, str):
        return _scan_string(
            value, surface=surface, path=path, tokens=tokens, pairs=pairs,
        )

    if isinstance(value, Mapping):
        findings: list[LeakFinding] = []

        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{surface}{path} has a non-string key")

            key_path = f"{path}.{key}"

            if key.casefold() in EVALUATOR_FIELD_NAMES:
                findings.append(
                    LeakFinding(surface, key_path, "evaluator_field_name", key)
                )

            findings.extend(
                _scan_string(
                    key, surface=surface, path=f"{key_path}<key>",
                    tokens=tokens, pairs=frozenset(),
                )
            )

            if isinstance(item, str) and (key, item) in pairs:
                findings.append(
                    LeakFinding(surface, key_path, "answer_mapping", f"{key}->{item}")
                )

            findings.extend(
                _walk(item, surface=surface, path=key_path, tokens=tokens, pairs=pairs)
            )

        return findings

    if isinstance(value, (list, tuple)):
        findings = []

        for index, item in enumerate(value):
            findings.extend(
                _walk(
                    item, surface=surface, path=f"{path}[{index}]",
                    tokens=tokens, pairs=pairs,
                )
            )

        return findings

    raise TypeError(
        f"{surface}{path} is not JSON-compatible: {type(value).__name__}"
    )


def scan_content(
    surfaces: Mapping[str, object],
    *,
    check_answers: bool = True,
    extra_pairs: frozenset[tuple[str, str]] = frozenset(),
) -> tuple[LeakFinding, ...]:
    """Scan named JSON-compatible surfaces for evaluator-only content.

    ``extra_pairs`` adds per-case answer pairs (see ``scan_case_content``).
    """
    tokens = sensitive_tokens()
    pairs = (answer_pairs() | extra_pairs) if check_answers else frozenset()
    findings: list[LeakFinding] = []

    for surface, value in surfaces.items():
        findings.extend(
            _walk(value, surface=surface, path="", tokens=tokens, pairs=pairs)
        )

    return tuple(findings)


def scan_case_content(
    surfaces: Mapping[str, object],
    truth: CaseTruth,
) -> tuple[LeakFinding, ...]:
    """Scan Hetren- or agent-visible surfaces of one generated case.

    Adds the case's own answer pairs (target ticket with its expected queue
    and account) to the standing checks.
    """
    return scan_content(surfaces, extra_pairs=case_answer_pairs(truth))


def scan_agent_outputs(
    surfaces: Mapping[str, object],
) -> tuple[LeakFinding, ...]:
    """Scan the agent's own decisions: no answer checks, all other checks."""
    return scan_content(surfaces, check_answers=False)


def scan_identifiers(
    surface: str,
    identifiers: Iterable[str],
    pattern: re.Pattern[str],
) -> tuple[LeakFinding, ...]:
    """Identifiers must match their neutral pattern and carry no tokens."""
    findings: list[LeakFinding] = []

    for identifier in identifiers:
        if not isinstance(identifier, str) or pattern.fullmatch(identifier) is None:
            findings.append(
                LeakFinding(surface, "", "non_neutral_identifier", str(identifier))
            )

    findings.extend(scan_content({surface: list(identifiers)}))
    return tuple(findings)


def assert_no_leaks(findings: Iterable[LeakFinding]) -> None:
    findings = tuple(findings)

    if findings:
        details = "\n".join(
            f"  {finding.kind}: {finding.surface}{finding.path} ({finding.detail})"
            for finding in findings
        )
        raise AssertionError(f"evaluator-only content leaked:\n{details}")


__all__ = [
    "LeakFinding",
    "NEUTRAL_FILE_NAME",
    "NEUTRAL_RUN_ID",
    "assert_no_leaks",
    "scan_agent_outputs",
    "scan_case_content",
    "scan_content",
    "scan_identifiers",
]
