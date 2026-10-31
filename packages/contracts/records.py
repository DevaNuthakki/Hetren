from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
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




class CapabilitySupportState(StrEnum):
    QUALIFIED_SUPPORTED = "qualified_supported"
    UNQUALIFIED = "unqualified"
    UNSUPPORTED = "unsupported"
    INCOMPATIBLE = "incompatible"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


def _require_contract_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(
            f"{field} must be non-empty text"
        )


def _require_contract_tuple(
    value: object,
    field: str,
) -> None:
    if not isinstance(value, tuple):
        raise ContractError(
            f"{field} must be a tuple"
        )

    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ContractError(
                f"{field} must contain only non-empty text"
            )


@dataclass(frozen=True)
class CapabilityProfile:
    tenant_id: str
    project_id: str
    profile_id: str
    profile_version: str
    system_id: str
    system_version_id: str

    declared_scope: str
    environment_family: str
    capability_kind: str
    investigation_surface: str
    mvp_requirement: str
    support_state: CapabilitySupportState

    action_semantics: tuple[str, ...]
    required_access: tuple[str, ...]
    schema_reference: str | None

    system_form_constraints: tuple[str, ...]
    adapter_requirements: tuple[str, ...]
    evaluator_requirements: tuple[str, ...]
    provider_constraints: tuple[str, ...]
    target_component_constraints: tuple[str, ...]
    compatibility_requirements: tuple[str, ...]
    authorization_prerequisites: tuple[str, ...]

    qualification_evidence_references: tuple[str, ...]
    known_limitations: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    requalification_conditions: tuple[str, ...]

    cost: tuple[str, ...]
    limits: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "profile_id",
            "profile_version",
            "system_id",
            "system_version_id",
            "declared_scope",
            "environment_family",
            "capability_kind",
            "investigation_surface",
            "mvp_requirement",
        ):
            _require_contract_text(
                getattr(self, field),
                field,
            )

        if not isinstance(
            self.support_state,
            CapabilitySupportState,
        ):
            raise ContractError(
                "support_state must be a "
                "CapabilitySupportState"
            )

        for field in (
            "action_semantics",
            "required_access",
            "system_form_constraints",
            "adapter_requirements",
            "evaluator_requirements",
            "provider_constraints",
            "target_component_constraints",
            "compatibility_requirements",
            "authorization_prerequisites",
            "qualification_evidence_references",
            "known_limitations",
            "invalidation_conditions",
            "requalification_conditions",
            "cost",
            "limits",
        ):
            _require_contract_tuple(
                getattr(self, field),
                field,
            )

        if (
            self.schema_reference is not None
            and (
                not isinstance(
                    self.schema_reference,
                    str,
                )
                or not self.schema_reference.strip()
            )
        ):
            raise ContractError(
                "schema_reference must be non-empty "
                "text or None"
            )

        if (
            self.support_state
            is CapabilitySupportState.QUALIFIED_SUPPORTED
            and not self.qualification_evidence_references
        ):
            raise ContractError(
                "qualified_supported requires "
                "qualification evidence"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "system_id": self.system_id,
            "system_version_id": self.system_version_id,
            "declared_scope": self.declared_scope,
            "environment_family": self.environment_family,
            "capability_kind": self.capability_kind,
            "investigation_surface": self.investigation_surface,
            "mvp_requirement": self.mvp_requirement,
            "support_state": self.support_state.value,
            "action_semantics": self.action_semantics,
            "required_access": self.required_access,
            "schema_reference": self.schema_reference,
            "system_form_constraints": (
                self.system_form_constraints
            ),
            "adapter_requirements": (
                self.adapter_requirements
            ),
            "evaluator_requirements": (
                self.evaluator_requirements
            ),
            "provider_constraints": (
                self.provider_constraints
            ),
            "target_component_constraints": (
                self.target_component_constraints
            ),
            "compatibility_requirements": (
                self.compatibility_requirements
            ),
            "authorization_prerequisites": (
                self.authorization_prerequisites
            ),
            "qualification_evidence_references": (
                self.qualification_evidence_references
            ),
            "known_limitations": self.known_limitations,
            "invalidation_conditions": (
                self.invalidation_conditions
            ),
            "requalification_conditions": (
                self.requalification_conditions
            ),
            "cost": self.cost,
            "limits": self.limits,
        }

    @property
    def profile_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class MethodProposal:
    tenant_id: str
    project_id: str
    proposal_id: str
    proposal_version: str

    goal_contract_id: str
    system_snapshot_id: str

    question: str
    alternatives: tuple[str, ...]
    expected_outcomes: tuple[str, ...]
    controls: tuple[str, ...]
    generated_program: str
    dependencies: tuple[str, ...]
    stopping_rule: str

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "proposal_id",
            "proposal_version",
            "goal_contract_id",
            "system_snapshot_id",
            "question",
            "generated_program",
            "stopping_rule",
        ):
            _require_contract_text(
                getattr(self, field),
                field,
            )

        for field in (
            "alternatives",
            "expected_outcomes",
            "controls",
            "dependencies",
        ):
            _require_contract_tuple(
                getattr(self, field),
                field,
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "proposal_id": self.proposal_id,
            "proposal_version": self.proposal_version,
            "goal_contract_id": self.goal_contract_id,
            "system_snapshot_id": self.system_snapshot_id,
            "question": self.question,
            "alternatives": self.alternatives,
            "expected_outcomes": (
                self.expected_outcomes
            ),
            "controls": self.controls,
            "generated_program": (
                self.generated_program
            ),
            "dependencies": self.dependencies,
            "stopping_rule": self.stopping_rule,
        }

    @property
    def proposal_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

__all__ = [
    "ContractError",
    "GoalContract",
    "SystemSnapshot",
    "canonical_sha256",
    "CapabilityProfile",
    "CapabilitySupportState",
    "MethodProposal",
]
