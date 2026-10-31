"""Trusted harness for the Milestone 1 support examples.

One harness instance runs one example end to end in one process:

1. set up the environment (inject the scenario's fault, if any);
2. register the run with the verifier (example name and injected fault);
3. run the agent; pass Hetren only the run record's evidence payload
   (with the scenario's evidence withheld, if any);
4. let Hetren diagnose, probe, recover, re-run, and freeze its outcome;
5. call the verifier with the frozen outcome; the verifier asks the harness
   to run the agent on each regression ticket.

Every agent run gets the next neutral run ID and, when recording or
replaying, its own capture directory named after that run ID. The harness
writes nothing else to disk: the run-ID-to-example mapping exists only in
the verifier's in-memory registry.

Model sources decide where model output comes from: scripted, recording
(scripted or live inner model), or replay. ``preflight`` checks every
directory a recording could need before the first model call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
import json
from pathlib import Path
from typing import Any

from agents import Model, OpenAIResponsesModel

from environments.support.faults import IdentifierMappingSwap, inject_fault
from environments.support.fixtures import SupportEnvironment
from environments.support.tools import (
    DIAGNOSTIC_TOOLS,
    MAINTENANCE_TOOL_DESCRIPTIONS,
    MAINTENANCE_TOOL_SCHEMAS,
    RECOVERY_TOOLS,
    SUPPORT_TOOL_DESCRIPTIONS,
    SUPPORT_TOOL_SCHEMAS,
    SUPPORT_TOOLS,
)
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.contracts import ContractError
from packages.integrations.openai_agents import (
    CaptureStore,
    RecordingModel,
    ReplayModel,
    RunProvenance,
    RunRecord,
    gateway_function_tools,
    run_agent,
)
from packages.integrations.run_ids import RunIdAllocator
from packages.support_agent import ScriptedSupportModel, build_support_agent, task_message
from packages.support_examples.scenarios import SCENARIOS, ExampleScenario
from packages.support_recovery import FrozenOutcome, recover
from packages.verification.support_verification import SupportVerification, SupportVerifier


AGENT_TOOL_NAMES = tuple(SUPPORT_TOOLS)
MAX_RUNS_PER_EXAMPLE = 3


class ModelSource(ABC):
    provenance: RunProvenance

    @abstractmethod
    def model_for(self, run_id: str) -> Model: ...

    def preflight(self, run_ids: list[str]) -> None:
        return None


class ScriptedSource(ModelSource):
    provenance = RunProvenance.SCRIPTED

    def model_for(self, run_id: str) -> Model:
        return ScriptedSupportModel()


class RecordingSource(ModelSource):
    """Records each run into ``root/<run_id>``, which must be absent or empty."""

    def __init__(
        self,
        *,
        root: Path,
        inner_factory: Any,
        source_provenance: RunProvenance,
        source_model_id: str | None = None,
    ) -> None:
        self._root = Path(root)
        self._inner_factory = inner_factory
        self._source_model_id = source_model_id
        self.provenance = source_provenance

    def preflight(self, run_ids: list[str]) -> None:
        for run_id in run_ids:
            directory = self._root / run_id

            if directory.exists() and any(directory.iterdir()):
                raise ContractError(f"capture directory {directory} is not empty")

    def model_for(self, run_id: str) -> Model:
        return RecordingModel(
            inner=self._inner_factory(),
            store=CaptureStore(self._root / run_id),
            source_provenance=self.provenance,
            source_model_id=self._source_model_id,
        )


class ReplaySource(ModelSource):
    provenance = RunProvenance.REPLAY

    def __init__(self, *, root: Path, source_provenance: RunProvenance, source_model_id: str) -> None:
        self._root = Path(root)
        self._source_provenance = source_provenance
        self._source_model_id = source_model_id

    def model_for(self, run_id: str) -> Model:
        return ReplayModel(
            store=CaptureStore(self._root / run_id),
            source_provenance=self._source_provenance,
            source_model_id=self._source_model_id,
        )


def live_recording_source(*, root: Path, model: str, client: Any) -> RecordingSource:
    """Live inner model; ``store=False`` comes from the agent definition."""
    return RecordingSource(
        root=root,
        inner_factory=lambda: OpenAIResponsesModel(model=model, openai_client=client),
        source_provenance=RunProvenance.LIVE,
        source_model_id=model,
    )


def withhold_account_observation(diagnosis_input: dict[str, Any]) -> dict[str, Any]:
    """Drop the account call's execution records from Hetren's input."""
    withheld = json.loads(json.dumps(diagnosis_input))
    lookups = [
        record["invocation_id"] for record in withheld["stage_records"]
        if record["tool_name"] == "lookup_account"
    ]

    if lookups:
        withheld["stage_records"] = [
            record for record in withheld["stage_records"]
            if not (
                record["invocation_id"] == lookups[0]
                and record["stage"] in ("attempted", "observed")
            )
        ]

    return withheld


def _gated(environment, registry, descriptions, schemas) -> list[GatedTool]:
    return [
        GatedTool(name, partial(function, environment), schemas[name], descriptions[name])
        for name, function in registry.items()
    ]


@dataclass(frozen=True)
class HarnessRun:
    role: str
    record: RunRecord


@dataclass(frozen=True)
class ExampleResult:
    example_name: str
    runs: tuple[HarnessRun, ...]
    diagnosis_inputs: tuple[dict[str, Any], ...]
    frozen: FrozenOutcome
    verification: SupportVerification


class SupportHarness:
    def __init__(
        self,
        *,
        example_name: str,
        model_source: ModelSource,
        first_run_number: int = 1,
        verifier: SupportVerifier | None = None,
    ) -> None:
        try:
            self.scenario: ExampleScenario = SCENARIOS[example_name]
        except KeyError:
            raise ContractError("unknown example") from None

        self.model_source = model_source
        self.verifier = verifier or SupportVerifier()
        self._first_run_number = first_run_number
        self._run_ids = RunIdAllocator(start=first_run_number)
        self.environment = SupportEnvironment()
        self.runs: list[HarnessRun] = []
        self.diagnosis_inputs: list[dict[str, Any]] = []

        if self.scenario.swap is not None:
            inject_fault(self.environment, IdentifierMappingSwap(*self.scenario.swap))

    def planned_run_ids(self) -> list[str]:
        return [
            f"run-{number:04d}"
            for number in range(self._first_run_number, self._first_run_number + MAX_RUNS_PER_EXAMPLE)
        ]

    def run_agent_on(self, ticket_id: str, role: str) -> RunRecord:
        run_id = self._run_ids.allocate()
        gateway = ToolGateway(
            tools=_gated(self.environment, SUPPORT_TOOLS, SUPPORT_TOOL_DESCRIPTIONS, SUPPORT_TOOL_SCHEMAS),
            policy=AllowListPolicy(AGENT_TOOL_NAMES),
            state_sha256=self.environment.state_sha256,
        )
        agent = build_support_agent(
            environment=self.environment,
            tools=gateway_function_tools(gateway),
            model=self.model_source.model_for(run_id),
        )
        record = run_agent(
            agent=agent,
            task_input=task_message(ticket_id),
            gateway=gateway,
            run_id=run_id,
            provenance=self.model_source.provenance,
        )
        self.runs.append(HarnessRun(role, record))
        return record

    def _diagnosis_input(self, record: RunRecord) -> dict[str, Any]:
        diagnosis_input = record.evidence_payload()

        if self.scenario.withhold_account_observation and not self.diagnosis_inputs:
            diagnosis_input = withhold_account_observation(diagnosis_input)

        self.diagnosis_inputs.append(diagnosis_input)
        return diagnosis_input

    def run_example(self) -> ExampleResult:
        self.model_source.preflight(self.planned_run_ids())

        initial = self.run_agent_on(self.scenario.ticket_id, "initial")
        self.verifier.register_run(
            run_id=initial.run_id,
            example_name=self.scenario.example_name,
            fault_payload=(
                None if self.scenario.swap is None
                else IdentifierMappingSwap(*self.scenario.swap).canonical_payload()
            ),
        )

        frozen = recover(
            self._diagnosis_input(initial),
            diagnostic_tools=_gated(
                self.environment, DIAGNOSTIC_TOOLS,
                MAINTENANCE_TOOL_DESCRIPTIONS, MAINTENANCE_TOOL_SCHEMAS,
            ),
            recovery_tools=_gated(
                self.environment, RECOVERY_TOOLS,
                MAINTENANCE_TOOL_DESCRIPTIONS, MAINTENANCE_TOOL_SCHEMAS,
            ),
            state_sha256=self.environment.state_sha256,
            rerun=lambda: self._diagnosis_input(
                self.run_agent_on(self.scenario.ticket_id, "rerun")
            ),
        )

        verification = self.verifier.verify(
            frozen=frozen,
            environment=self.environment,
            regression_runner=lambda ticket_id: self.run_agent_on(ticket_id, "regression"),
        )

        return ExampleResult(
            example_name=self.scenario.example_name,
            runs=tuple(self.runs),
            diagnosis_inputs=tuple(self.diagnosis_inputs),
            frozen=frozen,
            verification=verification,
        )


__all__ = [
    "ExampleResult",
    "HarnessRun",
    "MAX_RUNS_PER_EXAMPLE",
    "ModelSource",
    "RecordingSource",
    "ReplaySource",
    "ScriptedSource",
    "SupportHarness",
    "live_recording_source",
    "withhold_account_observation",
]
