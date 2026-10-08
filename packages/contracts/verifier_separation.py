"""Inert multidimensional Verifier Separation Profile contract.

A VerifierSeparationProfile records how a named profiler reports that one
VerificationReport differs from its source evaluation lineage across several
preregistered dimensions.

The profile is categorical and multidimensional. It deliberately contains no
numeric independence score, no overall independence grade, and no boolean
"is_independent" conclusion.

SAME and SEPARATE are evidence-bearing assertions. UNKNOWN exists so missing
knowledge is preserved rather than converted into manufactured separation.
NOT_APPLICABLE exists for dimensions that genuinely do not apply to a frozen
scenario.

Construction and validation do not resolve evidence, prove that a separation
claim is true, prove verifier independence, change VerificationReport.outcome,
establish eligibility, authorize a repair, authorize deployment, or advance a
lifecycle.
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
    _require_text,
    _require_tuple,
    canonical_sha256,
)
from .verification import VerificationReport


class VerifierSeparationDimension(StrEnum):
    EXECUTION_ATTEMPT = "EXECUTION_ATTEMPT"
    EVALUATOR = "EVALUATOR"
    TEST_OR_EVIDENCE_ORIGIN = "TEST_OR_EVIDENCE_ORIGIN"
    RUNTIME_ENVIRONMENT = "RUNTIME_ENVIRONMENT"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    ORGANIZATION = "ORGANIZATION"


class VerifierSeparationState(StrEnum):
    SAME = "SAME"
    SEPARATE = "SEPARATE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


_REQUIRED_DIMENSIONS = (
    VerifierSeparationDimension.EXECUTION_ATTEMPT,
    VerifierSeparationDimension.EVALUATOR,
    VerifierSeparationDimension.TEST_OR_EVIDENCE_ORIGIN,
    VerifierSeparationDimension.RUNTIME_ENVIRONMENT,
    VerifierSeparationDimension.INFRASTRUCTURE,
    VerifierSeparationDimension.ORGANIZATION,
)


@dataclass(frozen=True)
class VerifierSeparationAssessment:
    """One evidence-qualified categorical separation assessment."""

    dimension: VerifierSeparationDimension
    state: VerifierSeparationState
    evidence_references: tuple[str, ...]
    rationale: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_type(
            self.dimension,
            VerifierSeparationDimension,
            "dimension",
        )

        _require_type(
            self.state,
            VerifierSeparationState,
            "state",
        )

        _require_tuple(
            self.evidence_references,
            "evidence_references",
        )

        _require_text(
            self.rationale,
            "rationale",
        )

        _require_tuple(
            self.limitations,
            "limitations",
        )

        if len(
            self.evidence_references
        ) != len(
            set(self.evidence_references)
        ):
            raise ContractError(
                "evidence_references must be unique"
            )

        if self.evidence_references != tuple(
            sorted(
                self.evidence_references
            )
        ):
            raise ContractError(
                "evidence_references must be sorted"
            )

        if (
            self.state
            in (
                VerifierSeparationState.SAME,
                VerifierSeparationState.SEPARATE,
            )
            and not self.evidence_references
        ):
            raise ContractError(
                f"{self.state.value} requires evidence references"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_type": "VerifierSeparationAssessment",
            "schema_version": 1,
            "dimension": self.dimension.value,
            "state": self.state.value,
            "evidence_references": self.evidence_references,
            "rationale": self.rationale,
            "limitations": self.limitations,
        }


@dataclass(frozen=True)
class VerifierSeparationProfile:
    """Profiler-reported separation properties for one verification report."""

    tenant_id: str
    project_id: str
    profile_id: str

    verification_id: str
    verification_sha256: str

    profiler_id: str
    profiler_version: str

    protocol_reference: str
    protocol_sha256: str

    assessments: tuple[
        VerifierSeparationAssessment,
        ...,
    ]

    rationale: str
    uncertainty: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "project_id",
            "profile_id",
            "verification_id",
            "profiler_id",
            "profiler_version",
            "protocol_reference",
            "rationale",
            "uncertainty",
        ):
            _require_text(
                getattr(self, field),
                field,
            )

        for field in (
            "verification_sha256",
            "protocol_sha256",
        ):
            _require_sha256(
                getattr(self, field),
                field,
            )

        if not isinstance(
            self.assessments,
            tuple,
        ):
            raise ContractError(
                "assessments must be a tuple"
            )

        _require_tuple(
            self.limitations,
            "limitations",
        )

        for index, assessment in enumerate(
            self.assessments
        ):
            if not isinstance(
                assessment,
                VerifierSeparationAssessment,
            ):
                raise ContractError(
                    "assessments"
                    f"[{index}] must be a "
                    "VerifierSeparationAssessment"
                )

        dimensions = tuple(
            assessment.dimension
            for assessment in self.assessments
        )

        if dimensions != _REQUIRED_DIMENSIONS:
            raise ContractError(
                "assessments must contain each required "
                "separation dimension exactly once in "
                "canonical order"
            )

    def canonical_payload(self) -> dict[str, object]:
        payload = {
            field.name: getattr(
                self,
                field.name,
            )
            for field in fields(self)
        }

        payload["assessments"] = tuple(
            assessment.canonical_payload()
            for assessment in self.assessments
        )

        return {
            "record_type": "VerifierSeparationProfile",
            "schema_version": 1,
            **payload,
        }

    @property
    def profile_sha256(self) -> str:
        return canonical_sha256(
            self.canonical_payload()
        )

    def validate_against(
        self,
        *,
        verification: VerificationReport,
    ) -> None:
        """Validate linkage and declared separation evidence provenance."""

        _require_type(
            verification,
            VerificationReport,
            "verification",
        )

        _require_scope(
            self,
            verification,
            "verification",
        )

        for actual, expected, name in (
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
        ):
            _require_equal(
                actual,
                expected,
                name,
            )

        declared = set(
            verification.independence_references
        )

        for assessment in self.assessments:
            undeclared = (
                set(
                    assessment.evidence_references
                )
                - declared
            )

            if undeclared:
                raise ContractError(
                    "separation assessment references evidence "
                    "not declared by VerificationReport"
                )


__all__ = [
    "VerifierSeparationAssessment",
    "VerifierSeparationDimension",
    "VerifierSeparationProfile",
    "VerifierSeparationState",
]
