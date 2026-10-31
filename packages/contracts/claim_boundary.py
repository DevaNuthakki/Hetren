"""Inert contract for an explicit scientific Claim Boundary.

A ClaimBoundary records the exact limit of what accumulated evidence is being
used to state.

It distinguishes:

- demonstrated properties,
- assumptions,
- unresolved uncertainty,
- unsupported generalizations,
- authorization status,
- deployment status.

The boundary is qualifier-reported. Construction validates structure,
provenance identities and canonical representation. Each demonstrated property
explicitly names the already-declared source artifacts used to support that
bounded positive statement. Validation can bind the boundary to one
GoalContract and SystemSnapshot.

The contract does not resolve or validate the truth of source artifacts, prove
that a demonstrated property is scientifically justified, infer a claim from a
Repair Contrast or Verifier Separation Profile, prove causal correctness,
perform verification, establish eligibility, grant authorization, authorize
deployment, or mutate lifecycle state.

This initial P09 contract intentionally has no positive AUTHORIZED or DEPLOYED
status. A future authority/deployment layer must earn a separate contract or
schema revision before such a claim can be represented.
"""

from dataclasses import dataclass, fields
from enum import StrEnum

from .execution import (
    _require_equal,
    _require_scope,
    _require_sha256,
    _require_type,
)
from .records import (
    ContractError,
    GoalContract,
    SystemSnapshot,
    _require_text,
    _require_tuple,
    canonical_sha256,
)


class ClaimBoundaryExternalStatus(StrEnum):
    """Non-authoritative status available to the P09 Claim Boundary."""

    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    UNKNOWN = "UNKNOWN"
    OUTSIDE_SCOPE = "OUTSIDE_SCOPE"


@dataclass(frozen=True)
class ClaimBoundarySource:
    """Exact opaque artifact identity used as Claim Boundary provenance."""

    reference: str
    sha256: str

    def __post_init__(self) -> None:
        _require_text(
            self.reference,
            "reference",
        )

        _require_sha256(
            self.sha256,
            "sha256",
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "reference": self.reference,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class ClaimBoundaryDemonstration:
    """One bounded positive statement with explicit source provenance."""

    statement: str
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(
            self.statement,
            "statement",
        )

        _require_tuple(
            self.source_references,
            "source_references",
        )

        if not self.source_references:
            raise ContractError(
                "demonstrated property requires source references"
            )

        if len(
            self.source_references
        ) != len(
            set(self.source_references)
        ):
            raise ContractError(
                "demonstrated property source references must be unique"
            )

        if self.source_references != tuple(
            sorted(
                self.source_references
            )
        ):
            raise ContractError(
                "demonstrated property source references must be sorted"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "statement": self.statement,
            "source_references": self.source_references,
        }


@dataclass(frozen=True)
class ClaimBoundary:
    """Qualifier-reported bounded claim for one goal and system snapshot."""

    tenant_id: str
    project_id: str
    boundary_id: str

    goal_contract_id: str
    goal_contract_sha256: str

    system_snapshot_id: str
    system_snapshot_sha256: str

    qualifier_id: str
    qualifier_version: str

    protocol_reference: str
    protocol_sha256: str

    sources: tuple[
        ClaimBoundarySource,
        ...,
    ]

    demonstrated_properties: tuple[
        ClaimBoundaryDemonstration,
        ...,
    ]
    assumptions: tuple[str, ...]
    unresolved_uncertainty: tuple[str, ...]
    unsupported_generalizations: tuple[str, ...]

    authorization_status: ClaimBoundaryExternalStatus
    deployment_status: ClaimBoundaryExternalStatus

    rationale: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "boundary_id",
            "goal_contract_id",
            "system_snapshot_id",
            "qualifier_id",
            "qualifier_version",
            "protocol_reference",
            "rationale",
        ):
            _require_text(
                getattr(self, field),
                field,
            )

        for field in (
            "goal_contract_sha256",
            "system_snapshot_sha256",
            "protocol_sha256",
        ):
            _require_sha256(
                getattr(self, field),
                field,
            )

        if not isinstance(
            self.sources,
            tuple,
        ):
            raise ContractError(
                "sources must be a tuple"
            )

        for index, source in enumerate(
            self.sources
        ):
            if not isinstance(
                source,
                ClaimBoundarySource,
            ):
                raise ContractError(
                    f"sources[{index}] must be a ClaimBoundarySource"
                )

        source_references = tuple(
            source.reference
            for source in self.sources
        )

        if len(
            source_references
        ) != len(
            set(source_references)
        ):
            raise ContractError(
                "source references must be unique"
            )

        if source_references != tuple(
            sorted(
                source_references
            )
        ):
            raise ContractError(
                "sources must be sorted by reference"
            )

        if not isinstance(
            self.demonstrated_properties,
            tuple,
        ):
            raise ContractError(
                "demonstrated_properties must be a tuple"
            )

        for index, demonstration in enumerate(
            self.demonstrated_properties
        ):
            if not isinstance(
                demonstration,
                ClaimBoundaryDemonstration,
            ):
                raise ContractError(
                    "demonstrated_properties"
                    f"[{index}] must be a "
                    "ClaimBoundaryDemonstration"
                )

        if (
            self.demonstrated_properties
            and not self.sources
        ):
            raise ContractError(
                "demonstrated properties require source provenance"
            )

        declared_source_references = {
            source.reference
            for source in self.sources
        }

        for demonstration in self.demonstrated_properties:
            undeclared = (
                set(
                    demonstration.source_references
                )
                - declared_source_references
            )

            if undeclared:
                raise ContractError(
                    "demonstrated property references source "
                    "not declared by Claim Boundary"
                )

        for field in (
            "assumptions",
            "unresolved_uncertainty",
            "unsupported_generalizations",
            "limitations",
        ):
            _require_tuple(
                getattr(self, field),
                field,
            )

        _require_type(
            self.authorization_status,
            ClaimBoundaryExternalStatus,
            "authorization_status",
        )

        _require_type(
            self.deployment_status,
            ClaimBoundaryExternalStatus,
            "deployment_status",
        )

        if not any(
            (
                self.demonstrated_properties,
                self.assumptions,
                self.unresolved_uncertainty,
                self.unsupported_generalizations,
            )
        ):
            raise ContractError(
                "Claim Boundary must contain at least one "
                "claim-boundary statement"
            )

    def canonical_payload(self) -> dict[str, object]:
        payload = {
            field.name: getattr(
                self,
                field.name,
            )
            for field in fields(self)
        }

        payload["sources"] = tuple(
            source.canonical_payload()
            for source in self.sources
        )

        payload["demonstrated_properties"] = tuple(
            demonstration.canonical_payload()
            for demonstration in self.demonstrated_properties
        )

        payload[
            "authorization_status"
        ] = self.authorization_status.value

        payload[
            "deployment_status"
        ] = self.deployment_status.value

        return {
            "record_type": "ClaimBoundary",
            "schema_version": 1,
            **payload,
        }

    @property
    def boundary_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

    def validate_against(
        self,
        *,
        goal: GoalContract,
        snapshot: SystemSnapshot,
    ) -> None:
        """Validate exact goal/snapshot lineage without proving the claim."""

        _require_type(
            goal,
            GoalContract,
            "goal",
        )

        _require_type(
            snapshot,
            SystemSnapshot,
            "snapshot",
        )

        _require_scope(
            self,
            goal,
            "goal",
        )

        _require_scope(
            self,
            snapshot,
            "snapshot",
        )

        _require_equal(
            snapshot.system_id,
            goal.system_id,
            "snapshot.system_id",
        )

        for actual, expected, name in (
            (
                self.goal_contract_id,
                goal.contract_id,
                "goal_contract_id",
            ),
            (
                self.goal_contract_sha256,
                goal.contract_sha256,
                "goal_contract_sha256",
            ),
            (
                self.system_snapshot_id,
                snapshot.snapshot_id,
                "system_snapshot_id",
            ),
            (
                self.system_snapshot_sha256,
                snapshot.snapshot_sha256,
                "system_snapshot_sha256",
            ),
        ):
            _require_equal(
                actual,
                expected,
                name,
            )


__all__ = [
    "ClaimBoundary",
    "ClaimBoundaryDemonstration",
    "ClaimBoundaryExternalStatus",
    "ClaimBoundarySource",
]
