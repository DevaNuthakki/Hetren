"""Offline demo: replay all three Milestone 1 examples from committed captures.

Usage::

    python -m packages.support_examples.demo

No API key is needed. Network access is blocked for the whole run, so every
model response comes from ``tests/fixtures/support_captures``. Each example
runs through the harness exactly as in the live recording: agent, Hetren
diagnosis and recovery, then the verifier.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import socket
import sys

from packages.integrations.openai_agents import RunProvenance
from packages.support_examples.harness import ExampleResult, ReplaySource, SupportHarness
from packages.verification.support_verification import recorded_replay_plan


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "support_captures"

LABELS = {
    "example_correct_run": "Correct run",
    "example_insufficient_evidence": "Insufficient evidence",
    "example_verified_recovery": "Verified recovery",
}

HEADERS = ("Example", "Runs", "Hetren outcome", "Verdict")


def _block_network() -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise RuntimeError("the offline demo does not use the network")

    socket.socket.connect = refuse  # type: ignore[method-assign]
    socket.create_connection = refuse  # type: ignore[assignment]


def replay_examples() -> list[ExampleResult]:
    results = []

    for entry in recorded_replay_plan():
        harness = SupportHarness(
            example_name=entry.example_name,
            first_run_number=entry.first_run_number,
            model_source=ReplaySource(
                root=FIXTURES,
                source_provenance=RunProvenance.LIVE,
                source_model_id=entry.source_model_id,
            ),
        )
        results.append(harness.run_example())

    return results


def _hetren_outcome(result: ExampleResult) -> str:
    outcome = result.frozen.outcome
    diagnosis = outcome.diagnosis

    if diagnosis.assessment.missing:
        return f"{diagnosis.outcome.value} ({len(diagnosis.assessment.missing)} items missing)"

    if outcome.claims_fix:
        changed = len(outcome.candidate.actions)
        return f"{diagnosis.outcome.value} -> {changed} mapping entries corrected"

    return diagnosis.outcome.value


def table_rows(results: Sequence[ExampleResult]) -> list[tuple[str, str, str, str]]:
    return [
        (
            LABELS.get(result.example_name, result.example_name),
            ", ".join(run.record.run_id for run in result.runs),
            _hetren_outcome(result),
            result.verification.evaluator_verdict.value,
        )
        for result in results
    ]


def render_table(rows: Sequence[tuple[str, ...]]) -> str:
    widths = [max(len(row[index]) for row in (HEADERS, *rows)) for index in range(len(HEADERS))]

    def line(row: Sequence[str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()

    return "\n".join(
        [line(HEADERS), line(["-" * width for width in widths]), *(line(row) for row in rows)]
    )


def main(argv: Sequence[str] | None = None) -> int:
    _block_network()
    results = replay_examples()

    print("Hetren Milestone 1: offline replay of recorded live runs")
    print(f"Model: {recorded_replay_plan()[0].source_model_id} (replayed; network blocked)")
    print()
    print(render_table(table_rows(results)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
