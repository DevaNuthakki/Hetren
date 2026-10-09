"""Opt-in open-set diagnosis lifecycle.

Historical closed-world diagnosis semantics remain in lifecycle.py.

This module adds a treatment-visible safety layer that:

1. detects evidence contradiction before all-zero posterior normalization;
2. requires RFS-unique evidence before emitting a specific diagnosis;
3. requests deterministic singleton confirmation when needed;
4. keeps budget exhaustion distinct from evidence contradiction.

It does not consume evaluator truth, repair authority, verification authority,
eligibility state, or protected-result metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    Observation,
    Verdict,
)

from packages.core.hetren_diagnosis.lifecycle import (
    remaining_budget_units,
    select_next_decision,
)

from packages.core.hetren_diagnosis.planner import (
    apply_observation,
    initial_posterior,
)


class OpenSetReason(StrEnum):
    """Auditable reason for one open-set lifecycle decision."""

    BASE_LIFECYCLE = "base_lifecycle"
    RFS_UNIQUE_CONFIRMATION = "rfs_unique_confirmation"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CONFIRMATION_BUDGET_EXHAUSTED = "confirmation_budget_exhausted"
    CONFIRMATION_UNAVAILABLE = "confirmation_unavailable"
    EVIDENCE_CONTRADICTION = "evidence_contradiction"


@dataclass(frozen=True)
class OpenSetReplayResult:
    """Posterior replay plus contradiction metadata."""

    posterior: tuple[
        tuple[
            str,
            float,
        ],
        ...,
    ]

    contradiction_sequence: int | None = None
    contradiction_experiment_key: str | None = None
    contradiction_verdict: Verdict | None = None

    @property
    def contradicted(
        self,
    ) -> bool:
        return (
            self.contradiction_sequence
            is not None
        )

    def posterior_mapping(
        self,
    ) -> dict[str, float]:
        return dict(
            self.posterior
        )


@dataclass(frozen=True)
class OpenSetDecision:
    """One opt-in open-set diagnosis decision."""

    status: DiagnosisStatus
    reason: OpenSetReason

    candidate_experiment_keys: tuple[str, ...]
    experiment_key: str | None
    diagnosed_hypothesis_key: str | None

    replay: OpenSetReplayResult

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.status,
            DiagnosisStatus,
        ):
            raise ContractError(
                "status must be a DiagnosisStatus"
            )

        if not isinstance(
            self.reason,
            OpenSetReason,
        ):
            raise ContractError(
                "reason must be an OpenSetReason"
            )

        if not isinstance(
            self.candidate_experiment_keys,
            tuple,
        ):
            raise ContractError(
                "candidate_experiment_keys must be a tuple"
            )

        if self.status is DiagnosisStatus.ACTIVE:
            if not isinstance(
                self.experiment_key,
                str,
            ) or not self.experiment_key:
                raise ContractError(
                    "ACTIVE open-set decision requires an experiment"
                )

            if (
                self.diagnosed_hypothesis_key
                is not None
            ):
                raise ContractError(
                    "ACTIVE open-set decision cannot diagnose a hypothesis"
                )

        elif self.status is DiagnosisStatus.DIAGNOSED:
            if self.experiment_key is not None:
                raise ContractError(
                    "DIAGNOSED open-set decision cannot select an experiment"
                )

            if not isinstance(
                self.diagnosed_hypothesis_key,
                str,
            ) or not self.diagnosed_hypothesis_key:
                raise ContractError(
                    "DIAGNOSED open-set decision requires a hypothesis"
                )

        else:
            if self.experiment_key is not None:
                raise ContractError(
                    "terminal open-set decision cannot select an experiment"
                )

            if (
                self.diagnosed_hypothesis_key
                is not None
            ):
                raise ContractError(
                    "non-diagnosed terminal decision cannot diagnose a hypothesis"
                )


def _posterior_tuple(
    posterior: dict[str, float],
) -> tuple[
    tuple[
        str,
        float,
    ],
    ...,
]:
    return tuple(
        sorted(
            posterior.items()
        )
    )


def _experiment_by_key(
    problem: DiagnosisProblem,
) -> dict[str, object]:
    return {
        experiment.key:
            experiment
        for experiment
        in problem.experiments
    }


def replay_open_set_observations(
    problem: DiagnosisProblem,
    observations: Sequence[Observation] = (),
) -> OpenSetReplayResult:
    """Replay observations without normalizing an impossible open-set verdict."""
    if not isinstance(
        problem,
        DiagnosisProblem,
    ):
        raise ContractError(
            "problem must be a DiagnosisProblem"
        )

    observations = tuple(
        observations
    )

    posterior = initial_posterior(
        problem
    )

    experiments_by_key = (
        _experiment_by_key(
            problem
        )
    )

    seen_experiments: set[str] = set()

    spent_cost_units = 0

    for (
        expected_sequence,
        observation,
    ) in enumerate(
        observations
    ):
        if not isinstance(
            observation,
            Observation,
        ):
            raise ContractError(
                "observations must contain Observation instances"
            )

        if (
            observation.sequence
            != expected_sequence
        ):
            raise ContractError(
                "observation sequences must be contiguous starting at zero"
            )

        experiment = (
            experiments_by_key.get(
                observation.experiment_key
            )
        )

        if experiment is None:
            raise ContractError(
                "observation references an unknown experiment"
            )

        if (
            observation.experiment_key
            in seen_experiments
        ):
            raise ContractError(
                "an experiment cannot be observed more than once"
            )

        if (
            observation.experiment_sha256
            != experiment.experiment_sha256
        ):
            raise ContractError(
                "observation experiment digest does not match experiment"
            )

        spent_cost_units += (
            observation.actual_cost_units
        )

        if (
            spent_cost_units
            > problem.budget_units
        ):
            raise ContractError(
                "observation costs exceed diagnosis budget"
            )

        predictions = dict(
            experiment.predicted_verdicts
        )

        supported_hypotheses = tuple(
            hypothesis_key
            for (
                hypothesis_key,
                probability,
            )
            in posterior.items()
            if (
                probability > 0.0
                and predictions[
                    hypothesis_key
                ]
                is observation.verdict
            )
        )

        if not supported_hypotheses:
            return OpenSetReplayResult(
                posterior=(
                    _posterior_tuple(
                        posterior
                    )
                ),
                contradiction_sequence=(
                    observation.sequence
                ),
                contradiction_experiment_key=(
                    observation.experiment_key
                ),
                contradiction_verdict=(
                    observation.verdict
                ),
            )

        posterior = apply_observation(
            posterior,
            experiment,
            observation,
        )

        seen_experiments.add(
            observation.experiment_key
        )

    return OpenSetReplayResult(
        posterior=(
            _posterior_tuple(
                posterior
            )
        ),
    )


def _surviving_hypotheses(
    replay: OpenSetReplayResult,
) -> tuple[str, ...]:
    return tuple(
        key
        for (
            key,
            probability,
        )
        in replay.posterior
        if probability > 0.0
    )


def _has_rfs_unique_support(
    problem: DiagnosisProblem,
    observations: tuple[Observation, ...],
    hypothesis_key: str,
) -> bool:
    experiments_by_key = (
        _experiment_by_key(
            problem
        )
    )

    original_hypothesis_keys = tuple(
        hypothesis.key
        for hypothesis
        in problem.hypotheses
    )

    for observation in observations:
        experiment = experiments_by_key[
            observation.experiment_key
        ]

        predictions = dict(
            experiment.predicted_verdicts
        )

        if (
            predictions[
                hypothesis_key
            ]
            is not observation.verdict
        ):
            continue

        matching_original_hypotheses = tuple(
            key
            for key
            in original_hypothesis_keys
            if (
                predictions[
                    key
                ]
                is observation.verdict
            )
        )

        if (
            matching_original_hypotheses
            == (
                hypothesis_key,
            )
        ):
            return True

    return False


def _confirmation_candidates(
    problem: DiagnosisProblem,
    observations: tuple[Observation, ...],
    hypothesis_key: str,
) -> tuple[object, ...]:
    original_hypothesis_keys = tuple(
        hypothesis.key
        for hypothesis
        in problem.hypotheses
    )

    executed = frozenset(
        observation.experiment_key
        for observation
        in observations
    )

    candidates = []

    for experiment in problem.experiments:
        if experiment.key in executed:
            continue

        predictions = dict(
            experiment.predicted_verdicts
        )

        candidate_verdict = predictions[
            hypothesis_key
        ]

        matching_original_hypotheses = tuple(
            key
            for key
            in original_hypothesis_keys
            if (
                predictions[
                    key
                ]
                is candidate_verdict
            )
        )

        if (
            matching_original_hypotheses
            != (
                hypothesis_key,
            )
        ):
            continue

        candidates.append(
            experiment
        )

    candidates.sort(
        key=lambda experiment: (
            experiment.cost_units,
            experiment.key,
        )
    )

    return tuple(
        candidates
    )


def select_next_open_set_decision(
    problem: DiagnosisProblem,
    observations: Sequence[Observation] = (),
) -> OpenSetDecision:
    """Produce the next opt-in contradiction-aware diagnosis decision."""
    if not isinstance(
        problem,
        DiagnosisProblem,
    ):
        raise ContractError(
            "problem must be a DiagnosisProblem"
        )

    observations = tuple(
        observations
    )

    replay = replay_open_set_observations(
        problem,
        observations,
    )

    if replay.contradicted:
        return OpenSetDecision(
            status=DiagnosisStatus.INCONCLUSIVE,
            reason=(
                OpenSetReason.EVIDENCE_CONTRADICTION
            ),
            candidate_experiment_keys=(),
            experiment_key=None,
            diagnosed_hypothesis_key=None,
            replay=replay,
        )

    survivors = _surviving_hypotheses(
        replay
    )

    if not survivors:
        raise ContractError(
            "open-set replay produced no surviving hypothesis without contradiction"
        )

    if len(
        survivors
    ) == 1:
        hypothesis_key = survivors[
            0
        ]

        if _has_rfs_unique_support(
            problem,
            observations,
            hypothesis_key,
        ):
            return OpenSetDecision(
                status=(
                    DiagnosisStatus.DIAGNOSED
                ),
                reason=(
                    OpenSetReason.RFS_UNIQUE_CONFIRMATION
                ),
                candidate_experiment_keys=(),
                experiment_key=None,
                diagnosed_hypothesis_key=(
                    hypothesis_key
                ),
                replay=replay,
            )

        confirmation_candidates = (
            _confirmation_candidates(
                problem,
                observations,
                hypothesis_key,
            )
        )

        if not confirmation_candidates:
            return OpenSetDecision(
                status=(
                    DiagnosisStatus.INCONCLUSIVE
                ),
                reason=(
                    OpenSetReason.CONFIRMATION_UNAVAILABLE
                ),
                candidate_experiment_keys=(),
                experiment_key=None,
                diagnosed_hypothesis_key=None,
                replay=replay,
            )

        remaining_budget = (
            remaining_budget_units(
                problem,
                observations,
            )
        )

        affordable = tuple(
            experiment
            for experiment
            in confirmation_candidates
            if (
                experiment.cost_units
                <= remaining_budget
            )
        )

        if not affordable:
            return OpenSetDecision(
                status=(
                    DiagnosisStatus.BUDGET_EXHAUSTED
                ),
                reason=(
                    OpenSetReason.CONFIRMATION_BUDGET_EXHAUSTED
                ),
                candidate_experiment_keys=tuple(
                    experiment.key
                    for experiment
                    in confirmation_candidates
                ),
                experiment_key=None,
                diagnosed_hypothesis_key=None,
                replay=replay,
            )

        selected = affordable[
            0
        ]

        return OpenSetDecision(
            status=DiagnosisStatus.ACTIVE,
            reason=(
                OpenSetReason.CONFIRMATION_REQUIRED
            ),
            candidate_experiment_keys=tuple(
                experiment.key
                for experiment
                in affordable
            ),
            experiment_key=selected.key,
            diagnosed_hypothesis_key=None,
            replay=replay,
        )

    base_decision = (
        select_next_decision(
            problem,
            observations,
        )
    )

    if (
        base_decision.status
        is DiagnosisStatus.DIAGNOSED
    ):
        raise ContractError(
            "closed-world lifecycle diagnosed before open-set singleton handling"
        )

    return OpenSetDecision(
        status=base_decision.status,
        reason=OpenSetReason.BASE_LIFECYCLE,
        candidate_experiment_keys=(
            base_decision.candidate_experiment_keys
        ),
        experiment_key=(
            base_decision.experiment_key
        ),
        diagnosed_hypothesis_key=None,
        replay=replay,
    )


__all__ = [
    "OpenSetDecision",
    "OpenSetReason",
    "OpenSetReplayResult",
    "replay_open_set_observations",
    "select_next_open_set_decision",
]
