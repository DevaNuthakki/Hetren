from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when a shared contract invariant is violated."""


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def _require_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")


def _require_optional_text(value: object, field: str) -> None:
    if value is not None:
        _require_text(value, field)


def _require_tuple(value: object, field: str) -> None:
    if not isinstance(value, tuple):
        raise ContractError(f"{field} must be a tuple")

    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ContractError(
                f"{field}[{index}] must be a non-empty string"
            )


def _require_non_empty_tuple(value: object, field: str) -> None:
    _require_tuple(value, field)

    if not value:
        raise ContractError(f"{field} must be non-empty")


@dataclass(frozen=True)
class GoalContract:
    """
    Canonical declaration of a governed objective.

    This record declares what is being attempted and under which
    constraints/evidence rules. It does not contain execution outcomes,
    evaluation results, authorization grants, or verification verdicts.
    """

    tenant_id: str
    project_id: str
    contract_id: str
    contract_version: str

    system_id: str
    system_version_id: str

    claim_scope: str
    objective: str
    metrics: tuple[str, ...]
    minimum_effect: str

    baseline_reference: str | None

    acceptance_predicates: tuple[str, ...]
    hard_constraints: tuple[str, ...]
    invariants: tuple[str, ...]
    eligible_changes: tuple[str, ...]
    budget_constraints: tuple[str, ...]

    reviewer_version: str
    evaluator_version: str

    evidence_requirements: tuple[str, ...]
    protected_evaluation_requirements: tuple[str, ...]

    uncertainty_policy: str
    failure_invalidity_policy: str

    verification_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "contract_id",
            "contract_version",
            "system_id",
            "system_version_id",
            "claim_scope",
            "objective",
            "minimum_effect",
            "reviewer_version",
            "evaluator_version",
            "uncertainty_policy",
            "failure_invalidity_policy",
        ):
            _require_text(getattr(self, field), field)

        _require_non_empty_tuple(self.metrics, "metrics")

        _require_optional_text(
            self.baseline_reference,
            "baseline_reference",
        )

        for field in (
            "acceptance_predicates",
            "hard_constraints",
            "invariants",
            "eligible_changes",
            "budget_constraints",
            "evidence_requirements",
            "protected_evaluation_requirements",
            "verification_requirements",
        ):
            _require_tuple(getattr(self, field), field)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "system_id": self.system_id,
            "system_version_id": self.system_version_id,
            "claim_scope": self.claim_scope,
            "objective": self.objective,
            "metrics": self.metrics,
            "minimum_effect": self.minimum_effect,
            "baseline_reference": self.baseline_reference,
            "acceptance_predicates": self.acceptance_predicates,
            "hard_constraints": self.hard_constraints,
            "invariants": self.invariants,
            "eligible_changes": self.eligible_changes,
            "budget_constraints": self.budget_constraints,
            "reviewer_version": self.reviewer_version,
            "evaluator_version": self.evaluator_version,
            "evidence_requirements": self.evidence_requirements,
            "protected_evaluation_requirements": (
                self.protected_evaluation_requirements
            ),
            "uncertainty_policy": self.uncertainty_policy,
            "failure_invalidity_policy": (
                self.failure_invalidity_policy
            ),
            "verification_requirements": self.verification_requirements,
        }

    @property
    def contract_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True)
class SystemSnapshot:
    """
    Canonical captured-state record for a target system.

    This record references immutable target/version/binding identities
    and material state. It does not itself declare capability support,
    success, authorization, or evaluation outcome.
    """

    tenant_id: str
    project_id: str

    snapshot_id: str

    system_id: str
    system_version_id: str

    environment_family: str

    component_version_ids: tuple[str, ...]
    provider_binding_ids: tuple[str, ...]
    adapter_binding_ids: tuple[str, ...]
    evaluator_binding_ids: tuple[str, ...]

    code_identity: str | None
    data_identity: str | None
    prompt_identity: str | None
    runtime_identity: str | None

    state_references: tuple[str, ...]
    artifact_references: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "snapshot_id",
            "system_id",
            "system_version_id",
            "environment_family",
        ):
            _require_text(getattr(self, field), field)

        for field in (
            "component_version_ids",
            "provider_binding_ids",
            "adapter_binding_ids",
            "evaluator_binding_ids",
            "state_references",
            "artifact_references",
        ):
            _require_tuple(getattr(self, field), field)

        for field in (
            "code_identity",
            "data_identity",
            "prompt_identity",
            "runtime_identity",
        ):
            _require_optional_text(getattr(self, field), field)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "snapshot_id": self.snapshot_id,
            "system_id": self.system_id,
            "system_version_id": self.system_version_id,
            "environment_family": self.environment_family,
            "component_version_ids": self.component_version_ids,
            "provider_binding_ids": self.provider_binding_ids,
            "adapter_binding_ids": self.adapter_binding_ids,
            "evaluator_binding_ids": self.evaluator_binding_ids,
            "code_identity": self.code_identity,
            "data_identity": self.data_identity,
            "prompt_identity": self.prompt_identity,
            "runtime_identity": self.runtime_identity,
            "state_references": self.state_references,
            "artifact_references": self.artifact_references,
        }

    @property
    def snapshot_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


__all__ = [
    "ContractError",
    "GoalContract",
    "SystemSnapshot",
    "canonical_sha256",
]
