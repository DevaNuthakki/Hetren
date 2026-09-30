from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import math
import re


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when a diagnosis contract is violated."""


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class DiagnosisStatus(StrEnum):
    ACTIVE = "active"
    DIAGNOSED = "diagnosed"
    INCONCLUSIVE = "inconclusive"
    BUDGET_EXHAUSTED = "budget_exhausted"


class EventKind(StrEnum):
    DECISION = "decision"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE_TRANSITION = "state_transition"
    TERMINATION = "termination"


class InterventionKind(StrEnum):
    REPLAY = "replay"
    REPLACE_TOOL = "replace_tool"
    OVERRIDE_PARAMETER = "override_parameter"
    REMOVE_STEP = "remove_step"


class RationaleCode(StrEnum):
    BOOTSTRAP = "bootstrap"
    INFORMATION_GAIN_PER_COST = "information_gain_per_cost"
    COMPLETE = "complete"
    BUDGET_EXHAUSTED = "budget_exhausted"


def _require_sha(value: object, field: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ContractError(
            f"{field} must be a lowercase SHA-256 digest"
        )


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class TraceEvent:
    sequence: int
    kind: EventKind
    component: str
    operation: str
    input_sha256: str
    output_sha256: str
    state_before_sha256: str
    state_after_sha256: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ContractError(
                "event sequence must be a non-negative integer"
            )

        if not isinstance(self.kind, EventKind):
            raise ContractError("event kind must be an EventKind")

        if not self.component or not self.operation:
            raise ContractError(
                "event component and operation are required"
            )

        for field in (
            "input_sha256",
            "output_sha256",
            "state_before_sha256",
            "state_after_sha256",
        ):
            _require_sha(getattr(self, field), field)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "kind": self.kind.value,
            "component": self.component,
            "operation": self.operation,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "state_before_sha256": self.state_before_sha256,
            "state_after_sha256": self.state_after_sha256,
        }


@dataclass(frozen=True)
class AgentTrace:
    run_id: str
    events: tuple[TraceEvent, ...]

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ContractError("run_id is required")

        if not isinstance(self.events, tuple):
            raise ContractError("events must be a tuple")

        expected = tuple(range(len(self.events)))
        actual = tuple(event.sequence for event in self.events)

        if actual != expected:
            raise ContractError(
                "trace event sequences must be contiguous from zero"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "events": [
                event.canonical_payload()
                for event in self.events
            ],
        }

    @property
    def trace_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class Hypothesis:
    key: str
    description: str
    prior_probability: float

    def __post_init__(self) -> None:
        if not self.key or not self.description:
            raise ContractError(
                "hypothesis key and description are required"
            )

        if (
            isinstance(self.prior_probability, bool)
            or not isinstance(
                self.prior_probability,
                (int, float),
            )
            or not math.isfinite(self.prior_probability)
            or self.prior_probability <= 0.0
        ):
            raise ContractError(
                "hypothesis prior_probability must be "
                "finite and positive"
            )


@dataclass(frozen=True)
class Experiment:
    key: str
    intervention_kind: InterventionKind
    intervention_target: str
    cost_units: int
    predicted_verdicts: tuple[tuple[str, Verdict], ...]

    def __post_init__(self) -> None:
        if not self.key:
            raise ContractError("experiment key is required")

        if not self.intervention_target:
            raise ContractError(
                "experiment intervention target is required"
            )

        if not isinstance(
            self.intervention_kind,
            InterventionKind,
        ):
            raise ContractError(
                "intervention_kind must be an InterventionKind"
            )

        if (
            isinstance(self.cost_units, bool)
            or not isinstance(self.cost_units, int)
            or self.cost_units <= 0
        ):
            raise ContractError(
                "experiment cost_units must be a positive integer"
            )

        if not isinstance(self.predicted_verdicts, tuple):
            raise ContractError(
                "predicted_verdicts must be a tuple"
            )

        keys = tuple(
            key for key, _ in self.predicted_verdicts
        )

        if len(keys) != len(set(keys)):
            raise ContractError(
                "experiment hypothesis predictions must be unique"
            )

        if keys != tuple(sorted(keys)):
            raise ContractError(
                "experiment hypothesis predictions must be key-sorted"
            )

        for _, verdict in self.predicted_verdicts:
            if not isinstance(verdict, Verdict):
                raise ContractError(
                    "experiment predictions must use Verdict"
                )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "intervention_kind": self.intervention_kind.value,
            "intervention_target": self.intervention_target,
            "cost_units": self.cost_units,
            "predicted_verdicts": [
                [key, verdict.value]
                for key, verdict in self.predicted_verdicts
            ],
        }

    @property
    def experiment_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class DiagnosisProblem:
    trace: AgentTrace
    hypotheses: tuple[Hypothesis, ...]
    experiments: tuple[Experiment, ...]
    budget_units: int

    def __post_init__(self) -> None:
        if not isinstance(self.hypotheses, tuple):
            raise ContractError("hypotheses must be a tuple")

        if not self.hypotheses:
            raise ContractError("hypotheses must be non-empty")

        if not isinstance(self.experiments, tuple):
            raise ContractError("experiments must be a tuple")

        if (
            isinstance(self.budget_units, bool)
            or not isinstance(self.budget_units, int)
            or self.budget_units <= 0
        ):
            raise ContractError(
                "budget_units must be a positive integer"
            )

        hypothesis_keys = tuple(
            hypothesis.key
            for hypothesis in self.hypotheses
        )

        if len(hypothesis_keys) != len(set(hypothesis_keys)):
            raise ContractError(
                "hypothesis keys must be unique"
            )

        prior_total = sum(
            hypothesis.prior_probability
            for hypothesis in self.hypotheses
        )

        if not math.isclose(
            prior_total,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ContractError(
                "hypothesis priors must sum to one"
            )

        experiment_keys = tuple(
            experiment.key
            for experiment in self.experiments
        )

        if len(experiment_keys) != len(set(experiment_keys)):
            raise ContractError(
                "experiment keys must be unique"
            )

        expected = set(hypothesis_keys)

        for experiment in self.experiments:
            actual = {
                key
                for key, _ in experiment.predicted_verdicts
            }

            if actual != expected:
                raise ContractError(
                    f"experiment {experiment.key} must predict "
                    "one verdict for every hypothesis"
                )

    @property
    def problem_sha256(self) -> str:
        return canonical_sha256(
            {
                "trace": self.trace.canonical_payload(),
                "hypotheses": [
                    {
                        "key": hypothesis.key,
                        "description": hypothesis.description,
                        "prior_probability": hypothesis.prior_probability,
                    }
                    for hypothesis in sorted(
                        self.hypotheses,
                        key=lambda item: item.key,
                    )
                ],
                "experiments": [
                    experiment.canonical_payload()
                    for experiment in sorted(
                        self.experiments,
                        key=lambda item: item.key,
                    )
                ],
                "budget_units": self.budget_units,
            }
        )


@dataclass(frozen=True)
class Observation:
    sequence: int
    experiment_key: str
    experiment_sha256: str
    verdict: Verdict
    actual_cost_units: int
    evidence_sha256: str
    counterexample_sha256: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ContractError(
                "observation sequence must be a non-negative integer"
            )

        if not self.experiment_key:
            raise ContractError(
                "observation experiment_key is required"
            )

        _require_sha(
            self.experiment_sha256,
            "experiment_sha256",
        )

        if not isinstance(self.verdict, Verdict):
            raise ContractError(
                "observation verdict must be a Verdict"
            )

        if (
            isinstance(self.actual_cost_units, bool)
            or not isinstance(self.actual_cost_units, int)
            or self.actual_cost_units <= 0
        ):
            raise ContractError(
                "observation actual_cost_units must be positive"
            )

        _require_sha(
            self.evidence_sha256,
            "evidence_sha256",
        )

        if self.counterexample_sha256 is not None:
            _require_sha(
                self.counterexample_sha256,
                "counterexample_sha256",
            )


@dataclass(frozen=True)
class PlannerDecision:
    planner_key: str
    planner_version: str
    candidate_experiment_keys: tuple[str, ...]
    experiment_key: str | None
    expected_information_gain: float
    score_per_cost: float
    rationale: RationaleCode
    status: DiagnosisStatus
    problem_sha256: str

    def __post_init__(self) -> None:
        if not self.planner_key:
            raise ContractError(
                "planner_key is required"
            )

        if not self.planner_version:
            raise ContractError(
                "planner_version is required"
            )

        if not isinstance(
            self.candidate_experiment_keys,
            tuple,
        ):
            raise ContractError(
                "candidate_experiment_keys must be a tuple"
            )

        if len(self.candidate_experiment_keys) != len(
            set(self.candidate_experiment_keys)
        ):
            raise ContractError(
                "candidate experiment keys must be unique"
            )

        if self.candidate_experiment_keys != tuple(
            sorted(self.candidate_experiment_keys)
        ):
            raise ContractError(
                "candidate experiment keys must be sorted"
            )

        if (
            self.experiment_key is not None
            and self.experiment_key
            not in self.candidate_experiment_keys
        ):
            raise ContractError(
                "selected experiment must be in candidate set"
            )

        _require_sha(
            self.problem_sha256,
            "problem_sha256",
        )

        for field in (
            "expected_information_gain",
            "score_per_cost",
        ):
            value = getattr(self, field)

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0.0
            ):
                raise ContractError(
                    f"{field} must be finite and non-negative"
                )

        if not isinstance(
            self.rationale,
            RationaleCode,
        ):
            raise ContractError(
                "rationale must be a RationaleCode"
            )

        if not isinstance(
            self.status,
            DiagnosisStatus,
        ):
            raise ContractError(
                "status must be a DiagnosisStatus"
            )

        if (
            self.status is DiagnosisStatus.ACTIVE
            and self.experiment_key is None
        ):
            raise ContractError(
                "active planner decisions require an experiment"
            )

        if (
            self.status is not DiagnosisStatus.ACTIVE
            and self.experiment_key is not None
        ):
            raise ContractError(
                "terminal planner decisions cannot select an experiment"
            )
