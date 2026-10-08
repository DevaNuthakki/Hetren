"""Development harness for the four frozen P09.3B H1 arms.

The harness receives only:

- one treatment-visible H1PublicCase; and
- an experiment-execution callback.

It does not receive evaluator truth.

C0 performs no active intervention.
C1 performs the frozen deterministic seeded-random active policy.
C2 performs the frozen raw-information-gain active policy.
C3 delegates active choice to the existing Hetren lifecycle/planner.

The existing lifecycle remains authoritative for common terminal-state
semantics.
"""

import hashlib
import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from environments.agent.h1_controlled_active_diagnosis import (
    H1ObservedExperiment,
    H1PublicCase,
)
from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisStatus,
    Experiment,
    Observation,
    Verdict,
    canonical_sha256,
)
from packages.core.hetren_diagnosis.lifecycle import (
    remaining_budget_units,
    replay_observations,
    select_next_decision,
)
from packages.core.hetren_diagnosis.planner import (
    expected_information_gain,
    initial_posterior,
)


_EPSILON = 1e-12


class H1Arm(StrEnum):
    TRACE_ONLY = "trace_only"
    SEEDED_RANDOM_ACTIVE = "seeded_random_active"
    MAX_INFORMATION_GAIN_ACTIVE = "max_information_gain_active"
    HEAL_INFORMATION_GAIN_PER_COST = (
        "heal_information_gain_per_cost"
    )


ExperimentExecutor = Callable[
    [str],
    H1ObservedExperiment,
]


@dataclass(frozen=True)
class H1ArmRunResult:
    arm: H1Arm
    case_id: str
    status: DiagnosisStatus
    diagnosed_hypothesis_key: str | None
    posterior: tuple[tuple[str, float], ...]
    experiment_sequence: tuple[str, ...]
    verdict_sequence: tuple[Verdict, ...]
    evidence_references: tuple[str, ...]
    declared_cost_units: int
    actual_cost_units: int
    workflow_step_count: int
    problem_sha256: str

    @property
    def result_sha256(self) -> str:
        return canonical_sha256(
            {
                "record_type": "H1ArmRunResult",
                "schema_version": 1,
                "arm": self.arm.value,
                "case_id": self.case_id,
                "status": self.status.value,
                "diagnosed_hypothesis_key": (
                    self.diagnosed_hypothesis_key
                ),
                "posterior": [
                    [
                        key,
                        probability,
                    ]
                    for key, probability in self.posterior
                ],
                "experiment_sequence": (
                    self.experiment_sequence
                ),
                "verdict_sequence": [
                    verdict.value
                    for verdict in self.verdict_sequence
                ],
                "evidence_references": (
                    self.evidence_references
                ),
                "declared_cost_units": (
                    self.declared_cost_units
                ),
                "actual_cost_units": (
                    self.actual_cost_units
                ),
                "workflow_step_count": (
                    self.workflow_step_count
                ),
                "problem_sha256": (
                    self.problem_sha256
                ),
            }
        )


def _posterior_tuple(
    public_case: H1PublicCase,
    observations: tuple[Observation, ...],
) -> tuple[tuple[str, float], ...]:
    posterior = replay_observations(
        public_case.problem,
        observations,
    )

    return tuple(
        sorted(
            posterior.items()
        )
    )


def _diagnosed_key(
    posterior: tuple[tuple[str, float], ...],
) -> str | None:
    certain = tuple(
        key
        for key, probability in posterior
        if math.isclose(
            probability,
            1.0,
            rel_tol=0.0,
            abs_tol=_EPSILON,
        )
    )

    if len(certain) != 1:
        return None

    return certain[0]


def _eligible_experiments(
    public_case: H1PublicCase,
    observations: tuple[Observation, ...],
) -> tuple[Experiment, ...]:
    remaining = remaining_budget_units(
        public_case.problem,
        observations,
    )

    excluded = {
        observation.experiment_key
        for observation in observations
    }

    return tuple(
        sorted(
            (
                experiment
                for experiment
                in public_case.problem.experiments
                if experiment.key not in excluded
                and experiment.cost_units <= remaining
            ),
            key=lambda experiment: experiment.key,
        )
    )


def _select_c1(
    public_case: H1PublicCase,
    observations: tuple[Observation, ...],
) -> Experiment:
    eligible = _eligible_experiments(
        public_case,
        observations,
    )

    if not eligible:
        raise ContractError(
            "C1 has no eligible experiment while lifecycle is ACTIVE"
        )

    candidate_keys = tuple(
        experiment.key
        for experiment in eligible
    )

    sequence = len(
        observations
    )

    seed_material = (
        "hetren-p09.3-h1-c1-v1|"
        + public_case.case_id
        + "|"
        + str(sequence)
    )

    seed_int = int(
        hashlib.sha256(
            seed_material.encode(
                "utf-8"
            )
        ).hexdigest(),
        16,
    )

    rng = random.Random(
        seed_int
    )

    selected_key = candidate_keys[
        rng.randrange(
            len(candidate_keys)
        )
    ]

    return next(
        experiment
        for experiment in eligible
        if experiment.key == selected_key
    )


def _select_c2(
    public_case: H1PublicCase,
    observations: tuple[Observation, ...],
) -> Experiment:
    eligible = _eligible_experiments(
        public_case,
        observations,
    )

    if not eligible:
        raise ContractError(
            "C2 has no eligible experiment while lifecycle is ACTIVE"
        )

    posterior = dict(
        _posterior_tuple(
            public_case,
            observations,
        )
    )

    ranked = tuple(
        sorted(
            eligible,
            key=lambda experiment: (
                -expected_information_gain(
                    posterior,
                    experiment,
                ),
                experiment.key,
            ),
        )
    )

    return ranked[0]


def _build_result(
    *,
    arm: H1Arm,
    public_case: H1PublicCase,
    observations: tuple[Observation, ...],
    status: DiagnosisStatus,
    experiment_sequence: tuple[str, ...],
    verdict_sequence: tuple[Verdict, ...],
    evidence_references: tuple[str, ...],
    declared_cost_units: int,
    actual_cost_units: int,
    workflow_step_count: int,
) -> H1ArmRunResult:
    posterior = _posterior_tuple(
        public_case,
        observations,
    )

    diagnosed = (
        _diagnosed_key(
            posterior
        )
        if status is DiagnosisStatus.DIAGNOSED
        else None
    )

    if (
        status is DiagnosisStatus.DIAGNOSED
        and diagnosed is None
    ):
        raise ContractError(
            "DIAGNOSED result lacks one certain hypothesis"
        )

    return H1ArmRunResult(
        arm=arm,
        case_id=public_case.case_id,
        status=status,
        diagnosed_hypothesis_key=diagnosed,
        posterior=posterior,
        experiment_sequence=experiment_sequence,
        verdict_sequence=verdict_sequence,
        evidence_references=evidence_references,
        declared_cost_units=declared_cost_units,
        actual_cost_units=actual_cost_units,
        workflow_step_count=workflow_step_count,
        problem_sha256=public_case.problem.problem_sha256,
    )


def run_h1_arm(
    *,
    public_case: H1PublicCase,
    arm: H1Arm,
    execute_experiment: ExperimentExecutor | None,
) -> H1ArmRunResult:
    """Run one frozen H1 arm on one treatment-visible case."""

    if not isinstance(
        public_case,
        H1PublicCase,
    ):
        raise ContractError(
            "public_case must be an H1PublicCase"
        )

    if not isinstance(
        arm,
        H1Arm,
    ):
        raise ContractError(
            "arm must be an H1Arm"
        )

    if arm is H1Arm.TRACE_ONLY:
        posterior = tuple(
            sorted(
                initial_posterior(
                    public_case.problem
                ).items()
            )
        )

        diagnosed = _diagnosed_key(
            posterior
        )

        status = (
            DiagnosisStatus.DIAGNOSED
            if diagnosed is not None
            else DiagnosisStatus.INCONCLUSIVE
        )

        return H1ArmRunResult(
            arm=arm,
            case_id=public_case.case_id,
            status=status,
            diagnosed_hypothesis_key=diagnosed,
            posterior=posterior,
            experiment_sequence=(),
            verdict_sequence=(),
            evidence_references=(),
            declared_cost_units=0,
            actual_cost_units=0,
            workflow_step_count=0,
            problem_sha256=public_case.problem.problem_sha256,
        )

    if not callable(
        execute_experiment
    ):
        raise ContractError(
            "active H1 arms require an experiment executor"
        )

    observations: tuple[Observation, ...] = ()
    experiment_sequence: tuple[str, ...] = ()
    verdict_sequence: tuple[Verdict, ...] = ()
    evidence_references: tuple[str, ...] = ()

    declared_cost_units = 0
    actual_cost_units = 0
    workflow_step_count = 0

    experiments_by_key = {
        experiment.key: experiment
        for experiment in public_case.problem.experiments
    }

    while True:
        lifecycle_decision = select_next_decision(
            public_case.problem,
            observations,
        )

        if (
            lifecycle_decision.status
            is not DiagnosisStatus.ACTIVE
        ):
            return _build_result(
                arm=arm,
                public_case=public_case,
                observations=observations,
                status=lifecycle_decision.status,
                experiment_sequence=experiment_sequence,
                verdict_sequence=verdict_sequence,
                evidence_references=evidence_references,
                declared_cost_units=declared_cost_units,
                actual_cost_units=actual_cost_units,
                workflow_step_count=workflow_step_count,
            )

        if (
            arm
            is H1Arm.SEEDED_RANDOM_ACTIVE
        ):
            selected = _select_c1(
                public_case,
                observations,
            )

        elif (
            arm
            is H1Arm.MAX_INFORMATION_GAIN_ACTIVE
        ):
            selected = _select_c2(
                public_case,
                observations,
            )

        elif (
            arm
            is H1Arm.HEAL_INFORMATION_GAIN_PER_COST
        ):
            selected_key = (
                lifecycle_decision.experiment_key
            )

            if selected_key is None:
                raise ContractError(
                    "ACTIVE C3 lifecycle decision lacks experiment"
                )

            selected = experiments_by_key[
                selected_key
            ]

        else:
            raise ContractError(
                "unsupported active H1 arm"
            )

        execution = execute_experiment(
            selected.key
        )

        if not isinstance(
            execution,
            H1ObservedExperiment,
        ):
            raise ContractError(
                "experiment executor returned unexpected type"
            )

        if execution.case_id != public_case.case_id:
            raise ContractError(
                "experiment execution case ID mismatch"
            )

        if execution.experiment_key != selected.key:
            raise ContractError(
                "experiment executor returned wrong experiment"
            )

        if (
            execution.actual_cost_units
            != selected.cost_units
        ):
            raise ContractError(
                "experiment actual cost does not match "
                "registered synthetic cost"
            )

        observation = Observation(
            sequence=len(
                observations
            ),
            experiment_key=selected.key,
            experiment_sha256=selected.experiment_sha256,
            verdict=execution.verdict,
            actual_cost_units=execution.actual_cost_units,
            evidence_sha256=execution.evidence_sha256,
            counterexample_sha256=None,
        )

        observations = (
            *observations,
            observation,
        )

        experiment_sequence = (
            *experiment_sequence,
            selected.key,
        )

        verdict_sequence = (
            *verdict_sequence,
            execution.verdict,
        )

        evidence_references = (
            *evidence_references,
            execution.evidence_sha256,
        )

        declared_cost_units += (
            selected.cost_units
        )

        actual_cost_units += (
            execution.actual_cost_units
        )

        workflow_step_count += (
            execution.workflow_step_count
        )


def run_all_h1_arms(
    *,
    public_case: H1PublicCase,
    execute_experiment: ExperimentExecutor,
) -> tuple[H1ArmRunResult, ...]:
    return tuple(
        run_h1_arm(
            public_case=public_case,
            arm=arm,
            execute_experiment=(
                None
                if arm is H1Arm.TRACE_ONLY
                else execute_experiment
            ),
        )
        for arm in H1Arm
    )


__all__ = [
    "ExperimentExecutor",
    "H1Arm",
    "H1ArmRunResult",
    "run_all_h1_arms",
    "run_h1_arm",
]
