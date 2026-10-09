from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib

from environments.agent.p09_4_multistep_incident import (
    expected_incident_ids,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    Observation,
    Verdict,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.lifecycle import (
    remaining_budget_units,
)
from packages.core.hetren_diagnosis.open_set import (
    OpenSetReason,
    select_next_open_set_decision,
)
from packages.core.hetren_diagnosis.planner import (
    expected_information_gain,
    initial_posterior,
)
from packages.engines.behavioral.p09_4_checkpoint_replay import (
    P094ReplayBaseline,
    execute_checkpoint_replay,
)
from packages.engines.behavioral.p09_4_multistep_diagnosis import (
    build_development_problem,
)


SCIENTIFIC_BUDGET_UNITS = 13

CALIBRATED_REPLAY_COSTS = {
    "p1-canonical-tool": 4,
    "p2-canonical-parameter": 4,
    "p3-canonical-prerequisite-order": 3,
    "p4-fresh-context": 3,
    "p5-environment-contract": 3,
}

_C1_DOMAIN = b"hetren:p09.4:c1-selection:v1"


class P094ScientificArm(str, Enum):
    TRACE_ONLY = "trace_only"
    SEEDED_RANDOM_ACTIVE = "seeded_random_active"
    MAX_INFORMATION_GAIN_ACTIVE = "max_information_gain_active"
    HEAL_INFORMATION_GAIN_PER_COST = (
        "heal_information_gain_per_cost"
    )


@dataclass(frozen=True)
class P094ScientificSelection:
    sequence: int
    phase: str
    candidate_experiment_keys: tuple[str, ...]
    experiment_key: str
    remaining_budget_before: int
    c1_selection_digest_sha256: str | None

    def __post_init__(
        self,
    ) -> None:
        if (
            isinstance(
                self.sequence,
                bool,
            )
            or not isinstance(
                self.sequence,
                int,
            )
            or self.sequence < 0
        ):
            raise ContractError(
                "selection sequence must be a non-negative integer"
            )

        if self.phase not in {
            "active",
            "confirmation",
        }:
            raise ContractError(
                "selection phase must be active or confirmation"
            )

        if (
            not isinstance(
                self.candidate_experiment_keys,
                tuple,
            )
            or not self.candidate_experiment_keys
        ):
            raise ContractError(
                "selection candidates are required"
            )

        if (
            not isinstance(
                self.experiment_key,
                str,
            )
            or not self.experiment_key
        ):
            raise ContractError(
                "selected experiment key is required"
            )

        if (
            self.experiment_key
            not in self.candidate_experiment_keys
        ):
            raise ContractError(
                "selected experiment must be an eligible candidate"
            )

        if (
            isinstance(
                self.remaining_budget_before,
                bool,
            )
            or not isinstance(
                self.remaining_budget_before,
                int,
            )
            or self.remaining_budget_before < 0
        ):
            raise ContractError(
                "remaining budget must be a non-negative integer"
            )

        if (
            self.c1_selection_digest_sha256
            is not None
            and (
                not isinstance(
                    self.c1_selection_digest_sha256,
                    str,
                )
                or len(
                    self.c1_selection_digest_sha256
                )
                != 64
            )
        ):
            raise ContractError(
                "C1 selection digest must be a SHA-256 hex digest"
            )


@dataclass(frozen=True)
class P094ScientificArmRun:
    arm: P094ScientificArm
    case_id: str
    status: DiagnosisStatus
    terminal_reason: str
    diagnosed_hypothesis_key: str | None
    posterior: tuple[tuple[str, float], ...]
    selections: tuple[P094ScientificSelection, ...]
    observations: tuple[Observation, ...]
    experiment_sequence: tuple[str, ...]
    verdict_sequence: tuple[Verdict, ...]
    evidence_references: tuple[str, ...]
    declared_cost_units: int
    actual_cost_units: int
    workflow_step_count: int
    budget_units: int
    problem_sha256: str
    baseline_trace_sha256: str

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.arm,
            P094ScientificArm,
        ):
            raise ContractError(
                "arm must be a P094ScientificArm"
            )

        if (
            not isinstance(
                self.case_id,
                str,
            )
            or not self.case_id
        ):
            raise ContractError(
                "case_id is required"
            )

        if not isinstance(
            self.status,
            DiagnosisStatus,
        ):
            raise ContractError(
                "status must be a DiagnosisStatus"
            )

        if self.status is DiagnosisStatus.ACTIVE:
            raise ContractError(
                "scientific arm result must be terminal"
            )

        if (
            not isinstance(
                self.terminal_reason,
                str,
            )
            or not self.terminal_reason
        ):
            raise ContractError(
                "terminal_reason is required"
            )

        lengths = {
            len(
                self.selections
            ),
            len(
                self.observations
            ),
            len(
                self.experiment_sequence
            ),
            len(
                self.verdict_sequence
            ),
            len(
                self.evidence_references
            ),
        }

        if len(
            lengths
        ) != 1:
            raise ContractError(
                "scientific arm execution records must align"
            )

        if tuple(
            observation.experiment_key
            for observation
            in self.observations
        ) != self.experiment_sequence:
            raise ContractError(
                "observation sequence does not match experiment sequence"
            )

        if tuple(
            observation.verdict
            for observation
            in self.observations
        ) != self.verdict_sequence:
            raise ContractError(
                "observation verdicts do not match verdict sequence"
            )

        if tuple(
            observation.evidence_sha256
            for observation
            in self.observations
        ) != self.evidence_references:
            raise ContractError(
                "observation evidence does not match evidence references"
            )

        if (
            self.declared_cost_units
            != self.actual_cost_units
        ):
            raise ContractError(
                "declared and actual replay cost must agree"
            )

        if (
            self.actual_cost_units
            != sum(
                observation.actual_cost_units
                for observation
                in self.observations
            )
        ):
            raise ContractError(
                "actual cost must equal observation cost sum"
            )

        if self.actual_cost_units > self.budget_units:
            raise ContractError(
                "scientific arm exceeded its budget"
            )

        if (
            self.arm
            is P094ScientificArm.TRACE_ONLY
            and (
                self.observations
                or self.actual_cost_units != 0
                or self.workflow_step_count != 0
            )
        ):
            raise ContractError(
                "trace-only arm cannot execute active replay work"
            )

    @property
    def remaining_budget_units(
        self,
    ) -> int:
        return (
            self.budget_units
            - self.actual_cost_units
        )

    @property
    def result_sha256(
        self,
    ) -> str:
        return canonical_sha256(
            {
                "arm":
                    self.arm.value,
                "case_id":
                    self.case_id,
                "status":
                    self.status.value,
                "terminal_reason":
                    self.terminal_reason,
                "diagnosed_hypothesis_key":
                    self.diagnosed_hypothesis_key,
                "posterior":
                    self.posterior,
                "selections":
                    tuple(
                        {
                            "sequence":
                                selection.sequence,
                            "phase":
                                selection.phase,
                            "candidate_experiment_keys":
                                selection.candidate_experiment_keys,
                            "experiment_key":
                                selection.experiment_key,
                            "remaining_budget_before":
                                selection.remaining_budget_before,
                            "c1_selection_digest_sha256":
                                selection.c1_selection_digest_sha256,
                        }
                        for selection
                        in self.selections
                    ),
                "experiment_sequence":
                    self.experiment_sequence,
                "verdict_sequence":
                    tuple(
                        verdict.value
                        for verdict
                        in self.verdict_sequence
                    ),
                "evidence_references":
                    self.evidence_references,
                "declared_cost_units":
                    self.declared_cost_units,
                "actual_cost_units":
                    self.actual_cost_units,
                "workflow_step_count":
                    self.workflow_step_count,
                "budget_units":
                    self.budget_units,
                "problem_sha256":
                    self.problem_sha256,
                "baseline_trace_sha256":
                    self.baseline_trace_sha256,
            }
        )


def build_scientific_development_problem(
    trace,
) -> DiagnosisProblem:
    historical = build_development_problem(
        trace
    )

    historical_keys = tuple(
        experiment.key
        for experiment
        in historical.experiments
    )

    if historical_keys != tuple(
        CALIBRATED_REPLAY_COSTS
    ):
        raise ContractError(
            "historical experiment catalogue differs from frozen K1/K2 catalogue"
        )

    experiments = tuple(
        replace(
            experiment,
            cost_units=(
                CALIBRATED_REPLAY_COSTS[
                    experiment.key
                ]
            ),
        )
        for experiment
        in historical.experiments
    )

    return replace(
        historical,
        experiments=experiments,
        budget_units=SCIENTIFIC_BUDGET_UNITS,
    )


def _require_c1_seed(
    raw_seed: bytes,
) -> None:
    if (
        not isinstance(
            raw_seed,
            bytes,
        )
        or len(
            raw_seed
        )
        != 32
    ):
        raise ContractError(
            "C1 raw seed must be exactly 32 bytes"
        )


def _length_prefix(
    value: bytes,
) -> bytes:
    return (
        len(
            value
        ).to_bytes(
            4,
            "big",
        )
        + value
    )


def c1_selection_digest_sha256(
    *,
    raw_seed: bytes,
    case_id: str,
    sequence: int,
    eligible_experiment_keys: tuple[str, ...],
) -> str:
    _require_c1_seed(
        raw_seed
    )

    if (
        not isinstance(
            case_id,
            str,
        )
        or not case_id
    ):
        raise ContractError(
            "case_id is required"
        )

    if (
        isinstance(
            sequence,
            bool,
        )
        or not isinstance(
            sequence,
            int,
        )
        or sequence < 0
    ):
        raise ContractError(
            "C1 selection sequence must be a non-negative integer"
        )

    if (
        not isinstance(
            eligible_experiment_keys,
            tuple,
        )
        or not eligible_experiment_keys
    ):
        raise ContractError(
            "C1 eligible experiment keys are required"
        )

    if (
        eligible_experiment_keys
        != tuple(
            sorted(
                eligible_experiment_keys
            )
        )
        or len(
            set(
                eligible_experiment_keys
            )
        )
        != len(
            eligible_experiment_keys
        )
    ):
        raise ContractError(
            "C1 eligible experiment keys must be unique and lexicographically sorted"
        )

    payload = bytearray(
        _C1_DOMAIN
    )

    payload.extend(
        _length_prefix(
            raw_seed
        )
    )

    payload.extend(
        _length_prefix(
            case_id.encode(
                "utf-8"
            )
        )
    )

    payload.extend(
        sequence.to_bytes(
            8,
            "big",
        )
    )

    payload.extend(
        len(
            eligible_experiment_keys
        ).to_bytes(
            4,
            "big",
        )
    )

    for key in eligible_experiment_keys:
        if (
            not isinstance(
                key,
                str,
            )
            or not key
        ):
            raise ContractError(
                "C1 experiment keys must be non-empty strings"
            )

        payload.extend(
            _length_prefix(
                key.encode(
                    "utf-8"
                )
            )
        )

    return hashlib.sha256(
        bytes(
            payload
        )
    ).hexdigest()


def select_c1_experiment_key(
    *,
    raw_seed: bytes,
    case_id: str,
    sequence: int,
    eligible_experiment_keys: tuple[str, ...],
) -> tuple[str, str]:
    digest = c1_selection_digest_sha256(
        raw_seed=raw_seed,
        case_id=case_id,
        sequence=sequence,
        eligible_experiment_keys=(
            eligible_experiment_keys
        ),
    )

    index = (
        int(
            digest,
            16,
        )
        % len(
            eligible_experiment_keys
        )
    )

    return (
        eligible_experiment_keys[
            index
        ],
        digest,
    )


def _experiment_by_key(
    problem: DiagnosisProblem,
    experiment_key: str,
):
    experiment = next(
        (
            item
            for item
            in problem.experiments
            if item.key
            == experiment_key
        ),
        None,
    )

    if experiment is None:
        raise ContractError(
            "scientific arm selected an unknown experiment"
        )

    return experiment


def _reason_value(
    reason,
) -> str:
    value = getattr(
        reason,
        "value",
        None,
    )

    if isinstance(
        value,
        str,
    ) and value:
        return value

    return str(
        reason
    )


def _posterior_tuple(
    replay,
) -> tuple[tuple[str, float], ...]:
    return tuple(
        sorted(
            dict(
                replay.posterior
            ).items()
        )
    )


def _build_terminal_result(
    *,
    arm: P094ScientificArm,
    case_id: str,
    problem: DiagnosisProblem,
    baseline: P094ReplayBaseline,
    decision,
    selections: tuple[P094ScientificSelection, ...],
    observations: tuple[Observation, ...],
    experiment_sequence: tuple[str, ...],
    verdict_sequence: tuple[Verdict, ...],
    evidence_references: tuple[str, ...],
    declared_cost_units: int,
    actual_cost_units: int,
    workflow_step_count: int,
) -> P094ScientificArmRun:
    return P094ScientificArmRun(
        arm=arm,
        case_id=case_id,
        status=decision.status,
        terminal_reason=(
            _reason_value(
                decision.reason
            )
        ),
        diagnosed_hypothesis_key=(
            decision.diagnosed_hypothesis_key
        ),
        posterior=(
            _posterior_tuple(
                decision.replay
            )
        ),
        selections=selections,
        observations=observations,
        experiment_sequence=(
            experiment_sequence
        ),
        verdict_sequence=verdict_sequence,
        evidence_references=(
            evidence_references
        ),
        declared_cost_units=(
            declared_cost_units
        ),
        actual_cost_units=actual_cost_units,
        workflow_step_count=(
            workflow_step_count
        ),
        budget_units=problem.budget_units,
        problem_sha256=(
            problem.problem_sha256
        ),
        baseline_trace_sha256=(
            baseline.run.trace.trace_sha256
        ),
    )


def run_scientific_arm(
    *,
    arm: P094ScientificArm,
    case_id: str,
    baseline: P094ReplayBaseline,
    c1_raw_seed: bytes | None = None,
) -> P094ScientificArmRun:
    if not isinstance(
        arm,
        P094ScientificArm,
    ):
        raise ContractError(
            "arm must be a P094ScientificArm"
        )

    if (
        not isinstance(
            case_id,
            str,
        )
        or not case_id
    ):
        raise ContractError(
            "case_id is required"
        )

    if not isinstance(
        baseline,
        P094ReplayBaseline,
    ):
        raise ContractError(
            "baseline must be a P094ReplayBaseline"
        )

    if baseline.run.passed:
        raise ContractError(
            "scientific diagnosis requires a failing baseline"
        )

    if (
        arm
        is P094ScientificArm.SEEDED_RANDOM_ACTIVE
    ):
        if c1_raw_seed is None:
            raise ContractError(
                "C1 requires caller-supplied development or committed seed bytes"
            )

        _require_c1_seed(
            c1_raw_seed
        )

    elif c1_raw_seed is not None:
        raise ContractError(
            "C1 seed bytes may only be supplied to the C1 arm"
        )

    problem = (
        build_scientific_development_problem(
            baseline.run.trace
        )
    )

    if (
        arm
        is P094ScientificArm.TRACE_ONLY
    ):
        posterior = tuple(
            sorted(
                initial_posterior(
                    problem
                ).items()
            )
        )

        return P094ScientificArmRun(
            arm=arm,
            case_id=case_id,
            status=(
                DiagnosisStatus.INCONCLUSIVE
            ),
            terminal_reason="trace_only",
            diagnosed_hypothesis_key=None,
            posterior=posterior,
            selections=(),
            observations=(),
            experiment_sequence=(),
            verdict_sequence=(),
            evidence_references=(),
            declared_cost_units=0,
            actual_cost_units=0,
            workflow_step_count=0,
            budget_units=(
                problem.budget_units
            ),
            problem_sha256=(
                problem.problem_sha256
            ),
            baseline_trace_sha256=(
                baseline.run.trace.trace_sha256
            ),
        )

    observations: tuple[
        Observation,
        ...,
    ] = ()

    selections: tuple[
        P094ScientificSelection,
        ...,
    ] = ()

    experiment_sequence: tuple[
        str,
        ...,
    ] = ()

    verdict_sequence: tuple[
        Verdict,
        ...,
    ] = ()

    evidence_references: tuple[
        str,
        ...,
    ] = ()

    declared_cost_units = 0
    actual_cost_units = 0
    workflow_step_count = 0

    while True:
        decision = (
            select_next_open_set_decision(
                problem,
                observations,
            )
        )

        if (
            decision.status
            is not DiagnosisStatus.ACTIVE
        ):
            return _build_terminal_result(
                arm=arm,
                case_id=case_id,
                problem=problem,
                baseline=baseline,
                decision=decision,
                selections=selections,
                observations=observations,
                experiment_sequence=(
                    experiment_sequence
                ),
                verdict_sequence=(
                    verdict_sequence
                ),
                evidence_references=(
                    evidence_references
                ),
                declared_cost_units=(
                    declared_cost_units
                ),
                actual_cost_units=(
                    actual_cost_units
                ),
                workflow_step_count=(
                    workflow_step_count
                ),
            )

        remaining_budget = (
            remaining_budget_units(
                problem,
                observations,
            )
        )

        candidate_keys = tuple(
            sorted(
                decision.candidate_experiment_keys
            )
        )

        if not candidate_keys:
            raise ContractError(
                "ACTIVE open-set decision must expose eligible candidates"
            )

        selection_digest = None

        if (
            decision.reason
            is OpenSetReason.CONFIRMATION_REQUIRED
        ):
            phase = "confirmation"

            selected_key = (
                decision.experiment_key
            )

            if selected_key is None:
                raise ContractError(
                    "confirmation decision lacks experiment"
                )

        elif (
            decision.reason
            is OpenSetReason.BASE_LIFECYCLE
        ):
            phase = "active"

            if (
                arm
                is P094ScientificArm.SEEDED_RANDOM_ACTIVE
            ):
                if c1_raw_seed is None:
                    raise ContractError(
                        "C1 seed unexpectedly unavailable"
                    )

                (
                    selected_key,
                    selection_digest,
                ) = (
                    select_c1_experiment_key(
                        raw_seed=c1_raw_seed,
                        case_id=case_id,
                        sequence=len(
                            observations
                        ),
                        eligible_experiment_keys=(
                            candidate_keys
                        ),
                    )
                )

            elif (
                arm
                is P094ScientificArm.MAX_INFORMATION_GAIN_ACTIVE
            ):
                posterior = dict(
                    decision.replay.posterior
                )

                selected_key = sorted(
                    candidate_keys,
                    key=lambda key: (
                        -expected_information_gain(
                            posterior,
                            _experiment_by_key(
                                problem,
                                key,
                            ),
                        ),
                        key,
                    ),
                )[
                    0
                ]

            elif (
                arm
                is P094ScientificArm.HEAL_INFORMATION_GAIN_PER_COST
            ):
                selected_key = (
                    decision.experiment_key
                )

                if selected_key is None:
                    raise ContractError(
                        "ACTIVE C3 decision lacks experiment"
                    )

            else:
                raise ContractError(
                    "unsupported active scientific arm"
                )

        else:
            raise ContractError(
                "unexpected ACTIVE open-set decision reason"
            )

        if selected_key not in candidate_keys:
            raise ContractError(
                "scientific policy selected an ineligible experiment"
            )

        experiment = _experiment_by_key(
            problem,
            selected_key,
        )

        replay = execute_checkpoint_replay(
            baseline=baseline,
            problem=problem,
            experiment_key=(
                experiment.key
            ),
            sequence=len(
                observations
            ),
        )

        if (
            replay.experiment_sha256
            != experiment.experiment_sha256
        ):
            raise ContractError(
                "replay experiment digest mismatch"
            )

        actual_cost = (
            replay.tool_interaction_count
        )

        if (
            actual_cost
            != experiment.cost_units
        ):
            raise ContractError(
                "executed replay interaction count differs from calibrated experiment cost"
            )

        verdict = (
            Verdict.PASS
            if replay.passed
            else Verdict.FAIL
        )

        counterexample_sha256 = None

        if verdict is Verdict.FAIL:
            counterexample_sha256 = (
                canonical_sha256(
                    {
                        "expected_report": {
                            "incident_ids":
                                expected_incident_ids(),
                        },
                        "actual_report":
                            replay.report.canonical_payload(),
                    }
                )
            )

        observation = Observation(
            sequence=len(
                observations
            ),
            experiment_key=(
                experiment.key
            ),
            experiment_sha256=(
                experiment.experiment_sha256
            ),
            verdict=verdict,
            actual_cost_units=actual_cost,
            evidence_sha256=(
                replay.execution_evidence_sha256
            ),
            counterexample_sha256=(
                counterexample_sha256
            ),
        )

        selection = (
            P094ScientificSelection(
                sequence=len(
                    observations
                ),
                phase=phase,
                candidate_experiment_keys=(
                    candidate_keys
                ),
                experiment_key=(
                    experiment.key
                ),
                remaining_budget_before=(
                    remaining_budget
                ),
                c1_selection_digest_sha256=(
                    selection_digest
                ),
            )
        )

        observations = (
            *observations,
            observation,
        )

        selections = (
            *selections,
            selection,
        )

        experiment_sequence = (
            *experiment_sequence,
            experiment.key,
        )

        verdict_sequence = (
            *verdict_sequence,
            verdict,
        )

        evidence_references = (
            *evidence_references,
            replay.execution_evidence_sha256,
        )

        declared_cost_units += (
            experiment.cost_units
        )

        actual_cost_units += (
            actual_cost
        )

        workflow_step_count += (
            replay.workflow_step_count
        )


__all__ = [
    "CALIBRATED_REPLAY_COSTS",
    "P094ScientificArm",
    "P094ScientificArmRun",
    "P094ScientificSelection",
    "SCIENTIFIC_BUDGET_UNITS",
    "build_scientific_development_problem",
    "c1_selection_digest_sha256",
    "run_scientific_arm",
    "select_c1_experiment_key",
]
