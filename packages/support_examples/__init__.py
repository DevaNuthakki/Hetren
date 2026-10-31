"""Trusted harness for the Milestone 1 support examples.

Calls the verifier; never imports the evaluator directly and never passes
anything but run-record evidence to Hetren.
"""

from .harness import (
    ExampleResult,
    HarnessRun,
    MAX_RUNS_PER_EXAMPLE,
    ModelSource,
    RecordingSource,
    ReplaySource,
    ScriptedSource,
    SupportHarness,
    live_recording_source,
    withhold_account_observation,
)
from .scenarios import ExampleScenario, SCENARIOS


__all__ = [
    "ExampleResult",
    "ExampleScenario",
    "HarnessRun",
    "MAX_RUNS_PER_EXAMPLE",
    "ModelSource",
    "RecordingSource",
    "ReplaySource",
    "SCENARIOS",
    "ScriptedSource",
    "SupportHarness",
    "live_recording_source",
    "withhold_account_observation",
]
