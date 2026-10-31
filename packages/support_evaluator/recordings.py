"""Evaluator-side map of the committed live recordings.

``tests/fixtures/support_captures/<run-id>/`` holds one recorded run per
directory and nothing else. This module is the only record of which example
and role each run belongs to. Like the rest of the evaluator, only
``packages/verification/support_verification.py`` may import it.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts import ContractError
from packages.support_evaluator.catalog import EXAMPLES


RECORDING_SOURCE_MODEL_ID = "gpt-4.1-mini-2025-04-14"


@dataclass(frozen=True)
class RecordedRun:
    run_id: str
    example_name: str
    role: str


RECORDED_RUNS: dict[str, RecordedRun] = {
    run.run_id: run
    for run in (
        RecordedRun("run-0001", "example_correct_run", "initial"),
        RecordedRun("run-0002", "example_insufficient_evidence", "initial"),
        RecordedRun("run-0003", "example_verified_recovery", "initial"),
        RecordedRun("run-0004", "example_verified_recovery", "rerun"),
        RecordedRun("run-0005", "example_verified_recovery", "regression"),
    )
}


def example_run_ids(example_name: str) -> tuple[str, ...]:
    if example_name not in EXAMPLES:
        raise ContractError("unknown example_name")

    return tuple(
        sorted(run.run_id for run in RECORDED_RUNS.values() if run.example_name == example_name)
    )


def first_run_number(example_name: str) -> int:
    run_ids = example_run_ids(example_name)

    if not run_ids:
        raise ContractError("example has no recorded runs")

    return int(run_ids[0].removeprefix("run-"))


__all__ = [
    "RECORDED_RUNS",
    "RECORDING_SOURCE_MODEL_ID",
    "RecordedRun",
    "example_run_ids",
    "first_run_number",
]
