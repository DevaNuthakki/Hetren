"""Inert contract for assigning bounded semantic roles to evidence.

EvidenceRoleAssignment records what a named qualifier reports that one exact
piece of evidence may support.

Construction validates structure, provenance identifiers, role membership,
canonical ordering and evidence identity. It does not resolve the referenced
evidence, prove that the evidence is true, prove that a role assignment is
scientifically justified, establish causal correctness, perform verification,
prove verifier independence, authorize a repair, establish eligibility, or
grant deployment authority.

In particular, assigning INDEPENDENT_VERIFICATION is only a semantic label.
It is not proof of independence. VerificationReport and later HEAL assurance
contracts remain responsible for their own lineage and claim boundaries.
"""

from dataclasses import dataclass, fields
from enum import StrEnum

from .execution import _require_sha256
from .records import (
    ContractError,
    _require_text,
    _require_tuple,
    canonical_sha256,
)


class EvidenceRole(StrEnum):
    """Preregistered P09 evidence roles."""

    OBSERVATION = "OBSERVATION"
    REPRODUCTION = "REPRODUCTION"
    CAUSE_DISCRIMINATING = "CAUSE_DISCRIMINATING"
    REPAIR_DISCRIMINATING = "REPAIR_DISCRIMINATING"
    REGRESSION = "REGRESSION"
    INDEPENDENT_VERIFICATION = "INDEPENDENT_VERIFICATION"


@dataclass(frozen=True)
class EvidenceRoleAssignment:
    """Qualifier-reported roles for one exact evidence artifact.

    evidence_reference is an opaque provenance reference.

    evidence_sha256 binds the assignment to exact evidence bytes or to the
    canonical payload chosen by the producer. This contract does not fetch or
    independently recompute that referenced evidence.

    qualification_reference and qualification_sha256 bind the assignment to
    the exact declared qualification protocol or rule set used by the
    qualifier. Their presence does not prove that the protocol is scientifically
    adequate or that the qualifier applied it correctly.

    roles may contain more than one EvidenceRole because one artifact can
    legitimately support multiple bounded uses. Roles are required to be
    unique and sorted by enum value so semantically identical assignments do
    not receive different hashes merely because role order changed.

    rationale and uncertainty remain qualifier-reported statements.

    limitations are explicit claim boundaries. Their presence does not make a
    role assignment correct.
    """

    tenant_id: str
    project_id: str
    assignment_id: str

    evidence_reference: str
    evidence_sha256: str

    qualifier_id: str
    qualifier_version: str

    qualification_reference: str
    qualification_sha256: str

    roles: tuple[EvidenceRole, ...]

    rationale: str
    uncertainty: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "assignment_id",
            "evidence_reference",
            "qualifier_id",
            "qualifier_version",
            "qualification_reference",
            "rationale",
            "uncertainty",
        ):
            _require_text(
                getattr(self, field),
                field,
            )

        _require_sha256(
            self.evidence_sha256,
            "evidence_sha256",
        )

        _require_sha256(
            self.qualification_sha256,
            "qualification_sha256",
        )

        _require_tuple(
            self.roles,
            "roles",
        )

        _require_tuple(
            self.limitations,
            "limitations",
        )

        if not self.roles:
            raise ContractError(
                "roles must contain at least one EvidenceRole"
            )

        for role in self.roles:
            if not isinstance(
                role,
                EvidenceRole,
            ):
                raise ContractError(
                    "roles must contain only EvidenceRole values"
                )

        if len(self.roles) != len(
            set(self.roles)
        ):
            raise ContractError(
                "roles must be unique"
            )

        expected_order = tuple(
            sorted(
                self.roles,
                key=lambda role: role.value,
            )
        )

        if self.roles != expected_order:
            raise ContractError(
                "roles must be sorted by EvidenceRole value"
            )

    def canonical_payload(self) -> dict[str, object]:
        payload = {
            field.name: getattr(
                self,
                field.name,
            )
            for field in fields(self)
        }

        payload["roles"] = tuple(
            role.value
            for role in self.roles
        )

        return {
            "record_type": "EvidenceRoleAssignment",
            "schema_version": 1,
            **payload,
        }

    @property
    def assignment_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )


__all__ = [
    "EvidenceRole",
    "EvidenceRoleAssignment",
]
