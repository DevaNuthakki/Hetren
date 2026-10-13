"""Development-only adaptive diagnosis for paired binary interventions.

Applies to a validated two-hypothesis, two-experiment reference design.
The caller supplies real probe execution and evidence through a callback.

The policy is intentionally conservative after a failing first probe.
It does not establish safety for arbitrary agent systems, perform repair,
grant authorization, or provide independent evidence attestation.

Pilot-derived heuristic: a first-probe PASS can close with confirmed
reference-set support; a first-probe FAIL requires a complementary probe.
This heuristic has known out-of-reference-set and masking limitations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from packages.core.hetren_diagnosis.contracts import (
    ContractError,
    DiagnosisProblem,
    DiagnosisStatus,
    Experiment,
    Observation,
    Verdict,
)
from packages.core.hetren_diagnosis.open_set import (
    OpenSetDecision,
    OpenSetReason,
    select_next_open_set_decision,
)


@dataclass(frozen=True)
class AdaptiveTwoProbeDevelopmentResult:
    initial_decision: OpenSetDecision
    first_probe_decision: OpenSetDecision
    final_open_set_decision: OpenSetDecision | None
    observations: tuple[Observation, ...]
    diagnostic_runs: tuple[object, ...]
    policy_status: DiagnosisStatus
    policy_reason: str
    diagnosed_hypothesis_key: str | None

    @property
    def experiment_count(self) -> int:
        return len(self.observations)

    @property
    def experiment_cost_units(self) -> int:
        return sum(
            item.actual_cost_units
            for item in self.observations
        )


def _validate_design(problem: DiagnosisProblem) -> None:
    """Require a complementary, two-hypothesis binary probe design."""
    if not isinstance(problem, DiagnosisProblem):
        raise ContractError("problem must be a DiagnosisProblem")

    if (
        len(problem.hypotheses) != 2
        or len(problem.experiments) != 2
    ):
        raise ContractError(
            "adaptive development protocol requires exactly "
            "two hypotheses and two experiments"
        )

    keys = {item.key for item in problem.hypotheses}

    if len(keys) != 2:
        raise ContractError("hypothesis keys must be distinct")

    experiment_predictions = []

    for experiment in problem.experiments:
        predictions = dict(experiment.predicted_verdicts)

        if (
            set(predictions) != keys
            or set(predictions.values())
            != {Verdict.PASS, Verdict.FAIL}
            or experiment.cost_units < 1
        ):
            raise ContractError(
                "each probe must distinguish the two hypotheses"
            )

        experiment_predictions.append(predictions)

    first, second = experiment_predictions

    if any(
        first[key] is second[key]
        for key in keys
    ):
        raise ContractError(
            "experiments must have complementary predictions"
        )

    if (
        sum(item.cost_units for item in problem.experiments)
        > problem.budget_units
    ):
        raise ContractError(
            "reference design lacks budget for both probes"
        )


def run_adaptive_two_probe_development(
    problem: DiagnosisProblem,
    *,
    execute_probe: Callable[
        [Experiment, int],
        tuple[Observation, object],
    ],
    budget_units: int = 2,
) -> AdaptiveTwoProbeDevelopmentResult:
    """Execute at most two validated probes against a caller's agent.

    The callback receives the selected experiment and observation
    sequence number, and returns the actual observation and agent run.

    The returned evidence is checked for internal consistency.
    These checks cannot establish external provenance or authenticity.
    """
    _validate_design(problem)

    if not callable(execute_probe):
        raise ContractError("execute_probe must be callable")

    if (
        type(budget_units) is not int
        or budget_units < 1
        or budget_units > problem.budget_units
    ):
        raise ContractError("invalid adaptive investigation budget")

    initial = select_next_open_set_decision(problem)

    if (
        initial.status is not DiagnosisStatus.ACTIVE
        or initial.experiment_key is None
    ):
        raise ContractError(
            "initial open-set diagnosis must select an experiment"
        )

    experiments_by_key = {
        item.key: item
        for item in problem.experiments
    }

    first = experiments_by_key.get(initial.experiment_key)

    if first is None:
        raise ContractError("initial experiment is unknown")

    if first.cost_units > budget_units:
        raise ContractError(
            "cannot afford the initial diagnostic experiment"
        )

    observations: list[Observation] = []
    runs: list[object] = []
    run_ids: set[str] = set()

    def execute(experiment: Experiment) -> None:
        sequence = len(observations)

        payload = execute_probe(experiment, sequence)

        if (
            not isinstance(payload, tuple)
            or len(payload) != 2
        ):
            raise ContractError(
                "probe callback must return (observation, agent_run)"
            )

        observation, run = payload

        if not isinstance(observation, Observation):
            raise ContractError(
                "probe callback returned an invalid observation"
            )

        run_id = getattr(run, "run_id", None)
        passed = getattr(run, "passed", None)
        evidence = getattr(
            run, "execution_evidence_sha256", None
        )
        trace = getattr(run, "trace", None)

        if (
            not isinstance(run_id, str)
            or not run_id
            or run_id in run_ids
            or type(passed) is not bool
            or not isinstance(evidence, str)
            or not evidence
            or trace is None
            or not getattr(trace, "events", ())
        ):
            raise ContractError(
                "probe run has missing or reused execution evidence"
            )

        expected_verdict = (
            Verdict.PASS if passed else Verdict.FAIL
        )

        if (
            observation.sequence != sequence
            or observation.experiment_key != experiment.key
            or observation.experiment_sha256
            != experiment.experiment_sha256
            or observation.actual_cost_units
            != experiment.cost_units
            or observation.verdict is not expected_verdict
            or observation.evidence_sha256 != evidence
        ):
            raise ContractError(
                "probe observation does not match the executed run"
            )

        if (
            expected_verdict is Verdict.FAIL
            and observation.counterexample_sha256 is None
        ):
            raise ContractError(
                "failed execution requires counterexample evidence"
            )

        if (
            expected_verdict is Verdict.PASS
            and observation.counterexample_sha256 is not None
        ):
            raise ContractError(
                "passing execution cannot claim a counterexample"
            )

        run_ids.add(run_id)
        runs.append(run)
        observations.append(observation)

    def finish(
        status: DiagnosisStatus,
        reason: str,
        hypothesis: str | None,
        final: OpenSetDecision | None,
        first_decision: OpenSetDecision,
    ) -> AdaptiveTwoProbeDevelopmentResult:
        return AdaptiveTwoProbeDevelopmentResult(
            initial_decision=initial,
            first_probe_decision=first_decision,
            final_open_set_decision=final,
            observations=tuple(observations),
            diagnostic_runs=tuple(runs),
            policy_status=status,
            policy_reason=reason,
            diagnosed_hypothesis_key=hypothesis,
        )

    execute(first)

    first_decision = select_next_open_set_decision(
        problem,
        tuple(observations),
    )

    if observations[0].verdict is Verdict.PASS:
        if (
            first_decision.status is not DiagnosisStatus.DIAGNOSED
            or first_decision.reason
            is not OpenSetReason.RFS_UNIQUE_CONFIRMATION
            or first_decision.diagnosed_hypothesis_key is None
        ):
            raise ContractError(
                "passing probe lacks unique confirmed diagnosis"
            )

        return finish(
            first_decision.status,
            first_decision.reason.value,
            first_decision.diagnosed_hypothesis_key,
            first_decision,
            first_decision,
        )

    # A first-probe FAIL is not accepted as final in this
    # development policy, even if the underlying reference-set
    # lifecycle has already returned DIAGNOSED.
    second = next(
        item for item in problem.experiments
        if item.key != first.key
    )

    spent = observations[0].actual_cost_units

    if spent + second.cost_units > budget_units:
        return finish(
            DiagnosisStatus.BUDGET_EXHAUSTED,
            "falsification_budget_exhausted",
            None,
            None,
            first_decision,
        )

    execute(second)

    final = select_next_open_set_decision(
        problem,
        tuple(observations),
    )

    if (
        final.status is DiagnosisStatus.DIAGNOSED
        and final.reason is OpenSetReason.RFS_UNIQUE_CONFIRMATION
        and final.diagnosed_hypothesis_key is not None
        and observations[-1].verdict is Verdict.PASS
    ):
        return finish(
            final.status,
            final.reason.value,
            final.diagnosed_hypothesis_key,
            final,
            first_decision,
        )

    if (
        final.status is DiagnosisStatus.INCONCLUSIVE
        and final.reason is OpenSetReason.EVIDENCE_CONTRADICTION
        and final.diagnosed_hypothesis_key is None
    ):
        return finish(
            final.status,
            final.reason.value,
            None,
            final,
            first_decision,
        )

    raise ContractError(
        "two-probe policy encountered unsupported evidence"
    )
