"""Bounded recovery for identifier-mapping inconsistencies.

Hetren never touches the environment directly. The harness supplies plain
tools already bound to the environment (``GatedTool`` instances) and an
opaque ``state_sha256`` callable; Hetren builds its own gateways around them
with its own policies:

- probes: a read-only diagnostic gateway, ``AllowListPolicy`` over the
  diagnostic tools only; a probe that changes state is rejected;
- correction: a recovery gateway whose policy is
  ``AllOfPolicy(AllowListPolicy({recovery tool}), ExactCallsPolicy(calls))``,
  so the recovery permission is separate from the agent's tools and even the
  allowed tool can only make the calls in the frozen candidate;
- rollback: the same structure, scoped to the inverse calls.

A candidate changes only the mapping entries the diagnosis implicates, and
only where the probes show the directory disagreeing with the unique account
that names the reference. The candidate is frozen (content-addressed) before
it is applied, and the whole outcome is frozen before anyone verifies it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from packages.action_gateway import (
    AllOfPolicy,
    AllowListPolicy,
    ExactCallsPolicy,
    GatedTool,
    StageStatus,
    ToolGateway,
)
from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.support_recovery.diagnosis import (
    Diagnosis,
    DiagnosisOutcome,
    diagnose,
)


RESOLVE_TOOL = "resolve_customer_ref"
OWNERS_TOOL = "find_accounts_by_customer_ref"
CORRECTION_TOOL = "set_customer_mapping"
DIAGNOSTIC_TOOL_NAMES = frozenset({RESOLVE_TOOL, OWNERS_TOOL})


class CandidateStatus(StrEnum):
    PROPOSED = "proposed"
    NOT_NEEDED = "not_needed"
    UNDETERMINED = "undetermined"


class ApplicationStatus(StrEnum):
    APPLIED = "applied"
    FAILED = "failed"


@dataclass(frozen=True)
class CorrectionAction:
    customer_ref: str
    account_id: str

    def arguments(self) -> dict[str, object]:
        return {"customer_ref": self.customer_ref, "account_id": self.account_id}


@dataclass(frozen=True)
class RecoveryCandidate:
    """Content-addressed, immutable once created: this is the frozen candidate."""

    diagnosis_sha256: str
    probe_records_sha256: str
    status: CandidateStatus
    actions: tuple[CorrectionAction, ...]
    reasons: tuple[str, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "RecoveryCandidate",
            "schema_version": 1,
            "diagnosis_sha256": self.diagnosis_sha256,
            "probe_records_sha256": self.probe_records_sha256,
            "status": self.status.value,
            "actions": [action.arguments() for action in self.actions],
            "reasons": list(self.reasons),
        }

    @property
    def candidate_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class RecoveryApplication:
    candidate_sha256: str
    status: ApplicationStatus
    stage_records: tuple[dict[str, object], ...]
    state_before_sha256: str
    state_after_sha256: str
    rollback_actions: tuple[CorrectionAction, ...]

    @property
    def rollback_reference(self) -> str:
        return canonical_sha256(
            {
                "record_type": "RecoveryRollbackPlan",
                "candidate_sha256": self.candidate_sha256,
                "restore_state_sha256": self.state_before_sha256,
                "actions": [action.arguments() for action in self.rollback_actions],
            }
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "RecoveryApplication",
            "schema_version": 1,
            "candidate_sha256": self.candidate_sha256,
            "status": self.status.value,
            "stage_records": list(self.stage_records),
            "state_before_sha256": self.state_before_sha256,
            "state_after_sha256": self.state_after_sha256,
            "rollback_actions": [action.arguments() for action in self.rollback_actions],
            "rollback_reference": self.rollback_reference,
        }


def _require_tools(tools: Sequence[GatedTool], names: frozenset[str]) -> list[GatedTool]:
    selected = [tool for tool in tools if tool.name in names]

    if {tool.name for tool in selected} != names:
        raise ContractError(f"tools must include exactly {sorted(names)}")

    return selected


def run_probes(
    diagnosis: Diagnosis,
    *,
    diagnostic_tools: Sequence[GatedTool],
    state_sha256: Callable[[], str],
) -> tuple[dict[str, object], ...]:
    """Read-only probes for each implicated reference; returns stage records."""
    gateway = ToolGateway(
        tools=_require_tools(diagnostic_tools, DIAGNOSTIC_TOOL_NAMES),
        policy=AllowListPolicy(DIAGNOSTIC_TOOL_NAMES),
        state_sha256=state_sha256,
    )

    for customer_ref in diagnosis.implicated_customer_refs:
        gateway.invoke(RESOLVE_TOOL, {"customer_ref": customer_ref})
        gateway.invoke(OWNERS_TOOL, {"customer_ref": customer_ref})

    for record in gateway.records:
        if record.state_before_sha256 != record.state_after_sha256:
            raise ContractError("a diagnostic probe changed environment state")

    return tuple(record.canonical_payload() for record in gateway.records)


def _probe_observations(
    probe_records: tuple[dict[str, object], ...],
    tool_name: str,
) -> dict[str, dict[str, Any]]:
    observations: dict[str, dict[str, Any]] = {}

    for record in probe_records:
        if (
            record["tool_name"] == tool_name
            and record["stage"] == "observed"
            and record["status"] == "succeeded"
        ):
            observation = record["payload"]["observation"]
            observations[observation["customer_ref"]] = observation

    return observations


def propose_candidate(
    diagnosis: Diagnosis,
    probe_records: tuple[dict[str, object], ...],
) -> RecoveryCandidate:
    probes_sha256 = canonical_sha256(list(probe_records))

    def candidate(status, actions=(), reasons=()):
        return RecoveryCandidate(
            diagnosis.diagnosis_sha256, probes_sha256, status, tuple(actions), tuple(reasons),
        )

    if diagnosis.outcome is not DiagnosisOutcome.MAPPING_INCONSISTENCY:
        return candidate(CandidateStatus.NOT_NEEDED, reasons=(f"diagnosis_{diagnosis.outcome.value}",))

    resolved = _probe_observations(probe_records, RESOLVE_TOOL)
    owners = _probe_observations(probe_records, OWNERS_TOOL)
    actions: list[CorrectionAction] = []

    for customer_ref in diagnosis.implicated_customer_refs:
        if customer_ref not in resolved or customer_ref not in owners:
            return candidate(CandidateStatus.UNDETERMINED, reasons=("probe_observation_missing",))

        owner_ids = owners[customer_ref]["account_ids"]

        if len(owner_ids) != 1:
            return candidate(CandidateStatus.UNDETERMINED, reasons=("owner_not_unique",))

        if resolved[customer_ref]["account_id"] != owner_ids[0]:
            actions.append(CorrectionAction(customer_ref, owner_ids[0]))

    if not actions:
        return candidate(CandidateStatus.UNDETERMINED, reasons=("directory_agrees_with_owners",))

    return candidate(CandidateStatus.PROPOSED, actions, ("directory_disagrees_with_owner",))


def _scoped_gateway(
    recovery_tools: Sequence[GatedTool],
    state_sha256: Callable[[], str],
    actions: tuple[CorrectionAction, ...],
) -> ToolGateway:
    return ToolGateway(
        tools=_require_tools(recovery_tools, frozenset({CORRECTION_TOOL})),
        policy=AllOfPolicy(
            AllowListPolicy({CORRECTION_TOOL}),
            ExactCallsPolicy((CORRECTION_TOOL, action.arguments()) for action in actions),
        ),
        state_sha256=state_sha256,
    )


def apply_candidate(
    candidate: RecoveryCandidate,
    *,
    recovery_tools: Sequence[GatedTool],
    state_sha256: Callable[[], str],
) -> RecoveryApplication:
    if candidate.status is not CandidateStatus.PROPOSED:
        raise ContractError("only a proposed candidate can be applied")

    gateway = _scoped_gateway(recovery_tools, state_sha256, candidate.actions)
    state_before = state_sha256()
    rollback: list[CorrectionAction] = []
    status = ApplicationStatus.APPLIED

    for action in candidate.actions:
        result = gateway.invoke(CORRECTION_TOOL, action.arguments())

        if result.status is not StageStatus.SUCCEEDED:
            status = ApplicationStatus.FAILED
            break

        rollback.insert(
            0, CorrectionAction(action.customer_ref, result.observation["previous_account_id"]),
        )

    return RecoveryApplication(
        candidate_sha256=candidate.candidate_sha256,
        status=status,
        stage_records=tuple(record.canonical_payload() for record in gateway.records),
        state_before_sha256=state_before,
        state_after_sha256=state_sha256(),
        rollback_actions=tuple(rollback),
    )


def rollback_application(
    application: RecoveryApplication,
    *,
    recovery_tools: Sequence[GatedTool],
    state_sha256: Callable[[], str],
) -> tuple[dict[str, object], ...]:
    """Undo an application through a gateway scoped to the inverse calls."""
    gateway = _scoped_gateway(recovery_tools, state_sha256, application.rollback_actions)

    for action in application.rollback_actions:
        if gateway.invoke(CORRECTION_TOOL, action.arguments()).status is not StageStatus.SUCCEEDED:
            raise ContractError("rollback action failed")

    if state_sha256() != application.state_before_sha256:
        raise ContractError("rollback did not restore the recorded state")

    return tuple(record.canonical_payload() for record in gateway.records)


@dataclass(frozen=True)
class HetrenOutcome:
    run_id: str
    diagnosis: Diagnosis
    probe_records: tuple[dict[str, object], ...]
    candidate: RecoveryCandidate | None
    application: RecoveryApplication | None
    post_recovery_run_id: str | None
    post_recovery_diagnosis: Diagnosis | None

    @property
    def claims_fix(self) -> bool:
        return (
            self.application is not None
            and self.application.status is ApplicationStatus.APPLIED
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "HetrenSupportOutcome",
            "schema_version": 1,
            "run_id": self.run_id,
            "diagnosis": self.diagnosis.canonical_payload(),
            "probe_records": list(self.probe_records),
            "candidate": None if self.candidate is None else self.candidate.canonical_payload(),
            "application": (
                None if self.application is None else self.application.canonical_payload()
            ),
            "post_recovery_run_id": self.post_recovery_run_id,
            "post_recovery_diagnosis": (
                None if self.post_recovery_diagnosis is None
                else self.post_recovery_diagnosis.canonical_payload()
            ),
            "claims_fix": self.claims_fix,
        }


@dataclass(frozen=True)
class FrozenOutcome:
    outcome: HetrenOutcome
    frozen_sha256: str

    def verify_integrity(self) -> None:
        if canonical_sha256(self.outcome.canonical_payload()) != self.frozen_sha256:
            raise ContractError("frozen outcome does not match its digest")


def freeze_outcome(outcome: HetrenOutcome) -> FrozenOutcome:
    return FrozenOutcome(outcome, canonical_sha256(outcome.canonical_payload()))


RerunCallback = Callable[[], Mapping[str, Any]]


def recover(
    diagnosis_input: Mapping[str, Any],
    *,
    diagnostic_tools: Sequence[GatedTool],
    recovery_tools: Sequence[GatedTool],
    state_sha256: Callable[[], str],
    rerun: RerunCallback,
) -> FrozenOutcome:
    """Diagnose, and if implicated, probe, freeze a candidate, apply, re-run.

    ``rerun`` re-executes the original task after a correction and returns
    the new run's diagnosis input (its ``evidence_payload()``).
    """
    diagnosis = diagnose(diagnosis_input)
    run_id = str(diagnosis_input.get("run_id"))

    if diagnosis.outcome is not DiagnosisOutcome.MAPPING_INCONSISTENCY:
        return freeze_outcome(HetrenOutcome(run_id, diagnosis, (), None, None, None, None))

    probes = run_probes(
        diagnosis, diagnostic_tools=diagnostic_tools, state_sha256=state_sha256,
    )
    candidate = propose_candidate(diagnosis, probes)

    if candidate.status is not CandidateStatus.PROPOSED:
        return freeze_outcome(HetrenOutcome(run_id, diagnosis, probes, candidate, None, None, None))

    application = apply_candidate(
        candidate, recovery_tools=recovery_tools, state_sha256=state_sha256,
    )

    if application.status is not ApplicationStatus.APPLIED:
        return freeze_outcome(
            HetrenOutcome(run_id, diagnosis, probes, candidate, application, None, None)
        )

    post_input = rerun()
    post_diagnosis = diagnose(post_input)

    return freeze_outcome(
        HetrenOutcome(
            run_id, diagnosis, probes, candidate, application,
            str(post_input.get("run_id")), post_diagnosis,
        )
    )


__all__ = [
    "ApplicationStatus",
    "CORRECTION_TOOL",
    "CandidateStatus",
    "CorrectionAction",
    "DIAGNOSTIC_TOOL_NAMES",
    "FrozenOutcome",
    "HetrenOutcome",
    "RecoveryApplication",
    "RecoveryCandidate",
    "apply_candidate",
    "freeze_outcome",
    "propose_candidate",
    "recover",
    "rollback_application",
    "run_probes",
]
