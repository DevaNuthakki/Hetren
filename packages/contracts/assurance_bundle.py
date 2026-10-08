"""Machine-readable packaging contract for bounded HEAL assurance evidence.

An AssuranceBundle binds exact existing records into one deterministic package.

The bundle does not create new evidence. It does not reinterpret an
EvidenceRoleAssignment, promote a RepairContrastRecord, strengthen a
VerificationReport, manufacture verifier independence from a
VerifierSeparationProfile, or widen a ClaimBoundary.

Its purpose is provenance and reproducibility:

- identify the exact goal and candidate snapshot;
- identify exact Evidence Role assignments, when present;
- identify one exact Repair Contrast;
- identify one exact Verification Report;
- identify one exact Verifier Separation Profile;
- identify one exact Claim Boundary;
- preserve bundle-level provenance and limitations.

A valid bundle means that the declared record identities and their core lineage
are structurally consistent. It does not mean that the underlying evidence is
true, that the repair is generally correct, that verification is independent,
that the candidate is eligible, or that execution/deployment is authorized.
"""

from dataclasses import dataclass, fields

from .claim_boundary import ClaimBoundary
from .evidence import EvidenceRoleAssignment
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
from .repair_contrast import RepairContrastRecord
from .verification import VerificationReport
from .verifier_separation import VerifierSeparationProfile


@dataclass(frozen=True)
class AssuranceBundleEvidenceRoleReference:
    """Exact identity of one EvidenceRoleAssignment packaged by the bundle."""

    assignment_id: str
    assignment_sha256: str

    def __post_init__(self) -> None:
        _require_text(
            self.assignment_id,
            "assignment_id",
        )

        _require_sha256(
            self.assignment_sha256,
            "assignment_sha256",
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "assignment_id": self.assignment_id,
            "assignment_sha256": self.assignment_sha256,
        }


@dataclass(frozen=True)
class AssuranceBundle:
    """Exact record package for one bounded HEAL candidate lineage."""

    tenant_id: str
    project_id: str
    bundle_id: str

    goal_contract_id: str
    goal_contract_sha256: str

    system_snapshot_id: str
    system_snapshot_sha256: str

    assembler_id: str
    assembler_version: str

    protocol_reference: str
    protocol_sha256: str

    evidence_role_assignments: tuple[
        AssuranceBundleEvidenceRoleReference,
        ...,
    ]

    repair_contrast_id: str
    repair_contrast_sha256: str

    verification_id: str
    verification_sha256: str

    verifier_separation_profile_id: str
    verifier_separation_profile_sha256: str

    claim_boundary_id: str
    claim_boundary_sha256: str

    provenance_references: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "bundle_id",
            "goal_contract_id",
            "system_snapshot_id",
            "assembler_id",
            "assembler_version",
            "protocol_reference",
            "repair_contrast_id",
            "verification_id",
            "verifier_separation_profile_id",
            "claim_boundary_id",
        ):
            _require_text(
                getattr(self, field),
                field,
            )

        for field in (
            "goal_contract_sha256",
            "system_snapshot_sha256",
            "protocol_sha256",
            "repair_contrast_sha256",
            "verification_sha256",
            "verifier_separation_profile_sha256",
            "claim_boundary_sha256",
        ):
            _require_sha256(
                getattr(self, field),
                field,
            )

        if not isinstance(
            self.evidence_role_assignments,
            tuple,
        ):
            raise ContractError(
                "evidence_role_assignments must be a tuple"
            )

        for index, reference in enumerate(
            self.evidence_role_assignments
        ):
            if not isinstance(
                reference,
                AssuranceBundleEvidenceRoleReference,
            ):
                raise ContractError(
                    "evidence_role_assignments"
                    f"[{index}] must be an "
                    "AssuranceBundleEvidenceRoleReference"
                )

        assignment_ids = tuple(
            reference.assignment_id
            for reference in self.evidence_role_assignments
        )

        if len(
            assignment_ids
        ) != len(
            set(assignment_ids)
        ):
            raise ContractError(
                "Evidence Role assignment IDs must be unique"
            )

        if assignment_ids != tuple(
            sorted(
                assignment_ids
            )
        ):
            raise ContractError(
                "Evidence Role assignments must be sorted by assignment_id"
            )

        _require_tuple(
            self.provenance_references,
            "provenance_references",
        )

        _require_tuple(
            self.limitations,
            "limitations",
        )

        if not self.provenance_references:
            raise ContractError(
                "Assurance Bundle requires provenance references"
            )

        if not self.limitations:
            raise ContractError(
                "Assurance Bundle requires explicit limitations"
            )

        if len(
            self.provenance_references
        ) != len(
            set(self.provenance_references)
        ):
            raise ContractError(
                "provenance_references must be unique"
            )

        if self.provenance_references != tuple(
            sorted(
                self.provenance_references
            )
        ):
            raise ContractError(
                "provenance_references must be sorted"
            )

    def canonical_payload(self) -> dict[str, object]:
        payload = {
            field.name: getattr(
                self,
                field.name,
            )
            for field in fields(self)
        }

        payload["evidence_role_assignments"] = tuple(
            reference.canonical_payload()
            for reference in self.evidence_role_assignments
        )

        return {
            "record_type": "AssuranceBundle",
            "schema_version": 1,
            **payload,
        }

    @property
    def bundle_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

    def validate_against(
        self,
        *,
        goal: GoalContract,
        snapshot: SystemSnapshot,
        evidence_role_assignments: tuple[
            EvidenceRoleAssignment,
            ...,
        ],
        repair_contrast: RepairContrastRecord,
        verification: VerificationReport,
        verifier_separation_profile: VerifierSeparationProfile,
        claim_boundary: ClaimBoundary,
    ) -> None:
        """Validate packaged record identities and core lineage only."""

        for value, kind, name in (
            (
                goal,
                GoalContract,
                "goal",
            ),
            (
                snapshot,
                SystemSnapshot,
                "snapshot",
            ),
            (
                repair_contrast,
                RepairContrastRecord,
                "repair_contrast",
            ),
            (
                verification,
                VerificationReport,
                "verification",
            ),
            (
                verifier_separation_profile,
                VerifierSeparationProfile,
                "verifier_separation_profile",
            ),
            (
                claim_boundary,
                ClaimBoundary,
                "claim_boundary",
            ),
        ):
            _require_type(
                value,
                kind,
                name,
            )

            _require_scope(
                self,
                value,
                name,
            )

        if not isinstance(
            evidence_role_assignments,
            tuple,
        ):
            raise ContractError(
                "evidence_role_assignments argument must be a tuple"
            )

        for index, assignment in enumerate(
            evidence_role_assignments
        ):
            _require_type(
                assignment,
                EvidenceRoleAssignment,
                f"evidence_role_assignments[{index}]",
            )

            _require_scope(
                self,
                assignment,
                f"evidence_role_assignments[{index}]",
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
            (
                self.repair_contrast_id,
                repair_contrast.contrast_id,
                "repair_contrast_id",
            ),
            (
                self.repair_contrast_sha256,
                repair_contrast.contrast_sha256,
                "repair_contrast_sha256",
            ),
            (
                self.verification_id,
                verification.verification_id,
                "verification_id",
            ),
            (
                self.verification_sha256,
                verification.verification_sha256,
                "verification_sha256",
            ),
            (
                self.verifier_separation_profile_id,
                verifier_separation_profile.profile_id,
                "verifier_separation_profile_id",
            ),
            (
                self.verifier_separation_profile_sha256,
                verifier_separation_profile.profile_sha256,
                "verifier_separation_profile_sha256",
            ),
            (
                self.claim_boundary_id,
                claim_boundary.boundary_id,
                "claim_boundary_id",
            ),
            (
                self.claim_boundary_sha256,
                claim_boundary.boundary_sha256,
                "claim_boundary_sha256",
            ),
        ):
            _require_equal(
                actual,
                expected,
                name,
            )

        for actual, expected, name in (
            (
                repair_contrast.goal_contract_id,
                goal.contract_id,
                "repair_contrast.goal_contract_id",
            ),
            (
                repair_contrast.goal_contract_sha256,
                goal.contract_sha256,
                "repair_contrast.goal_contract_sha256",
            ),
            (
                repair_contrast.candidate_snapshot_id,
                snapshot.snapshot_id,
                "repair_contrast.candidate_snapshot_id",
            ),
            (
                repair_contrast.candidate_snapshot_sha256,
                snapshot.snapshot_sha256,
                "repair_contrast.candidate_snapshot_sha256",
            ),
            (
                verification.goal_contract_id,
                goal.contract_id,
                "verification.goal_contract_id",
            ),
            (
                verification.goal_contract_sha256,
                goal.contract_sha256,
                "verification.goal_contract_sha256",
            ),
            (
                verification.system_snapshot_id,
                snapshot.snapshot_id,
                "verification.system_snapshot_id",
            ),
            (
                verification.system_snapshot_sha256,
                snapshot.snapshot_sha256,
                "verification.system_snapshot_sha256",
            ),
            (
                verifier_separation_profile.verification_id,
                verification.verification_id,
                "verifier_separation_profile.verification_id",
            ),
            (
                verifier_separation_profile.verification_sha256,
                verification.verification_sha256,
                "verifier_separation_profile.verification_sha256",
            ),
            (
                claim_boundary.goal_contract_id,
                goal.contract_id,
                "claim_boundary.goal_contract_id",
            ),
            (
                claim_boundary.goal_contract_sha256,
                goal.contract_sha256,
                "claim_boundary.goal_contract_sha256",
            ),
            (
                claim_boundary.system_snapshot_id,
                snapshot.snapshot_id,
                "claim_boundary.system_snapshot_id",
            ),
            (
                claim_boundary.system_snapshot_sha256,
                snapshot.snapshot_sha256,
                "claim_boundary.system_snapshot_sha256",
            ),
        ):
            _require_equal(
                actual,
                expected,
                name,
            )

        expected_assignments = tuple(
            sorted(
                (
                    AssuranceBundleEvidenceRoleReference(
                        assignment_id=assignment.assignment_id,
                        assignment_sha256=assignment.assignment_sha256,
                    )
                    for assignment in evidence_role_assignments
                ),
                key=lambda reference: reference.assignment_id,
            )
        )

        if (
            self.evidence_role_assignments
            != expected_assignments
        ):
            raise ContractError(
                "packaged Evidence Role assignments do not "
                "match supplied assignments"
            )

        verifier_separation_profile.validate_against(
            verification=verification,
        )

        claim_boundary.validate_against(
            goal=goal,
            snapshot=snapshot,
        )


__all__ = [
    "AssuranceBundle",
    "AssuranceBundleEvidenceRoleReference",
]
