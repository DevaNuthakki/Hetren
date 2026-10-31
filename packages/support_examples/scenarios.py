"""Scenario setup for the Milestone 1 support examples (harness side).

A scenario says how to set an example up: which ticket the agent handles,
which fault (if any) the environment gets, and whether the harness withholds
part of the evidence from Hetren. It holds no expected values or verdicts;
those live only in the evaluator. ``SupportVerifier.register_run`` rejects a
fault payload that does not match the evaluator's definition, so the two
cannot drift silently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExampleScenario:
    example_name: str
    ticket_id: str
    swap: tuple[str, str] | None
    withhold_account_observation: bool


SCENARIOS: dict[str, ExampleScenario] = {
    "example_correct_run": ExampleScenario(
        example_name="example_correct_run",
        ticket_id="T-1003",
        swap=None,
        withhold_account_observation=False,
    ),
    "example_verified_recovery": ExampleScenario(
        example_name="example_verified_recovery",
        ticket_id="T-1003",
        swap=("C-3103", "C-3104"),
        withhold_account_observation=False,
    ),
    "example_insufficient_evidence": ExampleScenario(
        example_name="example_insufficient_evidence",
        ticket_id="T-1003",
        swap=("C-3103", "C-3104"),
        withhold_account_observation=True,
    ),
}


__all__ = [
    "ExampleScenario",
    "SCENARIOS",
]
