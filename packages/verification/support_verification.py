"""Evaluator-side verification for the Milestone 1 support examples.

This is the only module allowed to import ``packages.support_evaluator``.
It is not exported from ``packages.verification`` so that importing that
package never loads the evaluator.

The trusted harness:

1. registers each run (``register_run``) with the example it belongs to and
   the fault payload it actually injected;
2. lets Hetren finish and freeze its outcome;
3. calls ``verify`` with the frozen outcome, the environment, and a callback
   that runs the agent on a given ticket.

``verify`` checks the frozen outcome's integrity, the target ticket's final
account and queue against the expected values, and, where the example has
regression expectations, runs the agent on each regression ticket after the
recovery and checks its queue. It records a verdict. Nothing it produces is
passed back to Hetren.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from environments.support.fixtures import SupportEnvironment
from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.integrations.openai_agents import RunRecord, RunStatus
from packages.support_evaluator import (
    RunRegistry,
    SupportVerdict,
)
from packages.support_evaluator.recordings import (
    RECORDED_RUNS,
    RECORDING_SOURCE_MODEL_ID,
    example_run_ids,
    first_run_number,
)
from packages.support_recovery import (
    ApplicationStatus,
    DiagnosisOutcome,
    FrozenOutcome,
)


RegressionRunner = Callable[[str], RunRecord]


@dataclass(frozen=True)
class ReplayPlanEntry:
    """Where an example's committed recording starts, for offline replay."""

    example_name: str
    first_run_number: int
    run_ids: tuple[str, ...]
    source_model_id: str


def recorded_replay_plan() -> tuple[ReplayPlanEntry, ...]:
    """Read-only view of the evaluator's recordings map for the harness."""
    return tuple(
        ReplayPlanEntry(
            example_name=example_name,
            first_run_number=first_run_number(example_name),
            run_ids=example_run_ids(example_name),
            source_model_id=RECORDING_SOURCE_MODEL_ID,
        )
        for example_name in sorted(
            {run.example_name for run in RECORDED_RUNS.values()},
            key=lambda name: first_run_number(name),
        )
    )


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    subject: str | None = None

    def canonical_payload(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "subject": self.subject}


@dataclass(frozen=True)
class SupportVerification:
    run_id: str
    example_name: str
    frozen_sha256: str
    checks: tuple[VerificationCheck, ...]
    regression_run_ids: tuple[str, ...]
    evaluator_verdict: SupportVerdict

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "SupportVerification",
            "schema_version": 1,
            "run_id": self.run_id,
            "example_name": self.example_name,
            "frozen_sha256": self.frozen_sha256,
            "checks": [check.canonical_payload() for check in self.checks],
            "regression_run_ids": list(self.regression_run_ids),
            "evaluator_verdict": self.evaluator_verdict.value,
        }

    @property
    def verification_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


class SupportVerifier:
    def __init__(self) -> None:
        self._registry = RunRegistry()
        self._verified: set[str] = set()

    def register_run(
        self,
        *,
        run_id: str,
        example_name: str,
        fault_payload: dict[str, object] | None,
    ) -> None:
        self._registry.register(
            run_id=run_id, example_name=example_name, fault_payload=fault_payload,
        )

    def verify(
        self,
        *,
        frozen: FrozenOutcome,
        environment: SupportEnvironment,
        regression_runner: RegressionRunner,
    ) -> SupportVerification:
        if not isinstance(frozen, FrozenOutcome):
            raise ContractError("verify requires a frozen Hetren outcome")

        frozen.verify_integrity()
        outcome = frozen.outcome

        if outcome.run_id in self._verified:
            raise ContractError("run has already been verified")

        registration = self._registry.lookup(outcome.run_id)
        spec = registration.spec
        checks = [VerificationCheck("outcome_integrity", True)]

        target = environment.get_ticket(spec.target_ticket_id)
        target_account_ok = (
            environment.resolve_customer(target.customer_ref) == spec.expected_account_id
        )
        target_queue_ok = target.queue_id == spec.expected_queue_id
        checks.append(VerificationCheck("target_account", target_account_ok, spec.target_ticket_id))
        checks.append(VerificationCheck("target_queue", target_queue_ok, spec.target_ticket_id))

        regression_run_ids: list[str] = []
        regression_ok = True

        for ticket_id, queue_id in sorted(spec.regression_expectations.items()):
            record = regression_runner(ticket_id)
            regression_run_ids.append(record.run_id)
            passed = (
                record.status is RunStatus.COMPLETED
                and environment.get_ticket(ticket_id).queue_id == queue_id
            )
            regression_ok = regression_ok and passed
            checks.append(VerificationCheck("regression_queue", passed, ticket_id))

        diagnosed = outcome.diagnosis.outcome
        no_candidate_applied = outcome.application is None
        expected = spec.expected_verdict

        if expected is SupportVerdict.NO_INTERVENTION_CORRECT:
            ok = (
                diagnosed is DiagnosisOutcome.HEALTHY
                and outcome.candidate is None
                and target_account_ok
                and target_queue_ok
            )
            verdict = expected if ok else SupportVerdict.INCORRECT_OUTCOME
        elif expected is SupportVerdict.RECOVERY_VERIFIED:
            if not outcome.claims_fix:
                verdict = SupportVerdict.INCORRECT_OUTCOME
            elif target_account_ok and target_queue_ok and regression_ok:
                verdict = SupportVerdict.RECOVERY_VERIFIED
            else:
                verdict = SupportVerdict.RECOVERY_REJECTED
        elif expected is SupportVerdict.INSUFFICIENT_EVIDENCE_CORRECT:
            ok = (
                diagnosed is DiagnosisOutcome.INSUFFICIENT_EVIDENCE
                and outcome.candidate is None
                and no_candidate_applied
            )
            verdict = expected if ok else SupportVerdict.INCORRECT_OUTCOME
        else:
            raise ContractError("example has an unsupported expected verdict")

        checks.append(
            VerificationCheck(
                "application_status",
                outcome.application is None
                or outcome.application.status is ApplicationStatus.APPLIED,
            )
        )

        self._verified.add(outcome.run_id)

        return SupportVerification(
            run_id=outcome.run_id,
            example_name=spec.example_name,
            frozen_sha256=frozen.frozen_sha256,
            checks=tuple(checks),
            regression_run_ids=tuple(regression_run_ids),
            evaluator_verdict=verdict,
        )


__all__ = [
    "RegressionRunner",
    "ReplayPlanEntry",
    "SupportVerification",
    "SupportVerifier",
    "VerificationCheck",
    "recorded_replay_plan",
]
