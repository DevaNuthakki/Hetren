"""Development portfolio for Critical Terminology Fidelity v1.

This portfolio is source-visible calibration and regression evidence. It is
not a private holdout, certification set, production qualification, runtime
eligibility decision, or release authority.

The portfolio owns one pinned development vocabulary. Individual cases do not
silently substitute alternative vocabularies. The exact vocabulary SHA-256 is
part of the scientific comparison contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    Observation,
    ObservationStatus,
)
from hvee.laboratory.semantic.portfolio import (
    run_semantic_portfolio,
    validate_semantic_cases,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_APPLICABLE_METRIC,
    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
    CRITICAL_TERMINOLOGY_FINDINGS_METRIC,
    CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_METRICS,
    CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_OUTCOME_METRIC,
    CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    ASRCriticalTerminologyFidelityOutcome,
    ASRCriticalTerminologyFindingType,
    ASRCriticalTerminologyProfile,
    ASRCriticalTerminologyReasonCode,
    ASRCriticalTerminologyTerm,
    build_critical_terminology_fidelity_observations,
    calculate_critical_terminology_vocabulary_sha256,
    evaluate_critical_terminology_fidelity,
)
from hvee.packs.asr.evaluation import (
    ASR_EVALUATION_TYPE,
)


CRITICAL_TERMINOLOGY_PORTFOLIO_KEY = (
    "hetren.asr.critical-terminology-fidelity-portfolio.en-us"
)
CRITICAL_TERMINOLOGY_PORTFOLIO_VERSION = "1.0.0"


CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1 = (
    ASRCriticalTerminologyProfile(
        key=(
            "hetren.asr.critical-terminology-"
            "portfolio-profile.en-us"
        ),
        version="1.0.0",
        language="en",
        locale="en-US",
        terms=(
            ASRCriticalTerminologyTerm(
                term_key="database.postgresql",
                canonical_text="PostgreSQL",
                accepted_surfaces=(
                    "PostgreSQL",
                    "Postgres",
                ),
            ),
            ASRCriticalTerminologyTerm(
                term_key="database.mysql",
                canonical_text="MySQL",
                accepted_surfaces=(
                    "MySQL",
                ),
            ),
            ASRCriticalTerminologyTerm(
                term_key="platform.kubernetes",
                canonical_text="Kubernetes",
                accepted_surfaces=(
                    "Kubernetes",
                    "K8s",
                ),
            ),
            ASRCriticalTerminologyTerm(
                term_key="runtime.node-js",
                canonical_text="Node.js",
                accepted_surfaces=(
                    "Node.js",
                ),
            ),
            ASRCriticalTerminologyTerm(
                term_key="language.c-sharp",
                canonical_text="C#",
                accepted_surfaces=(
                    "C#",
                ),
            ),
            ASRCriticalTerminologyTerm(
                term_key="concept.machine-learning",
                canonical_text="machine learning",
                accepted_surfaces=(
                    "machine learning",
                ),
            ),
            ASRCriticalTerminologyTerm(
                term_key="concept.learning",
                canonical_text="learning",
                accepted_surfaces=(
                    "learning",
                ),
            ),
            ASRCriticalTerminologyTerm(
                term_key="algorithm.naive-bayes",
                canonical_text="naïve Bayes",
                accepted_surfaces=(
                    "naïve Bayes",
                ),
            ),
        ),
    )
)


CRITICAL_TERMINOLOGY_PORTFOLIO_VOCABULARY_SHA256 = (
    calculate_critical_terminology_vocabulary_sha256(
        CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1
    )
)


class ASRCriticalTerminologyPortfolioPartition(StrEnum):
    """Source-visible development partitions."""

    CALIBRATION = "calibration"
    REGRESSION_HOLDOUT = "regression_holdout"


class ASRCriticalTerminologyPortfolioOperation(StrEnum):
    EQUIVALENCE = "equivalence"
    SUBSTITUTION = "substitution"
    OMISSION = "omission"
    INSERTION = "insertion"
    ORDERING_CHANGE = "ordering_change"
    DUPLICATE_CONTROL = "duplicate_control"
    DUPLICATE_OMISSION = "duplicate_omission"
    PUNCTUATION_CONTROL = "punctuation_control"
    OVERLAP_CONTROL = "overlap_control"
    BOUNDARY_CONTROL = "boundary_control"
    UNREGISTERED_RENDERING = "unregistered_rendering"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyFindingExpectation:
    finding_type: ASRCriticalTerminologyFindingType
    reason_code: ASRCriticalTerminologyReasonCode
    reference_term_key: str | None
    generated_term_key: str | None

    def __post_init__(self) -> None:
        if not isinstance(
            self.finding_type,
            ASRCriticalTerminologyFindingType,
        ):
            raise HveeContractError(
                "terminology portfolio finding expectation "
                "requires a finding type"
            )

        if not isinstance(
            self.reason_code,
            ASRCriticalTerminologyReasonCode,
        ):
            raise HveeContractError(
                "terminology portfolio finding expectation "
                "requires a reason code"
            )

        for name, value in (
            (
                "reference term key",
                self.reference_term_key,
            ),
            (
                "generated term key",
                self.generated_term_key,
            ),
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or value != value.strip()
            ):
                raise HveeContractError(
                    f"terminology portfolio {name} "
                    "must be non-empty when supplied"
                )


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyPortfolioCase:
    case_id: str
    partition: ASRCriticalTerminologyPortfolioPartition
    operation: ASRCriticalTerminologyPortfolioOperation
    reference_text: str
    generated_text: str
    expected_outcome: ASRCriticalTerminologyFidelityOutcome
    expected_applicable: bool
    expected_preserved_status: ObservationStatus
    expected_preserved: bool | None
    expected_reference_count: int
    expected_generated_count: int
    expected_substitution_count: int
    expected_omission_count: int
    expected_insertion_count: int
    expected_ordering_change_count: int
    expected_findings: tuple[
        ASRCriticalTerminologyFindingExpectation,
        ...,
    ]
    description: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or self.case_id != self.case_id.strip()
        ):
            raise HveeContractError(
                "critical-terminology portfolio case id "
                "must be non-empty"
            )

        if not isinstance(
            self.partition,
            ASRCriticalTerminologyPortfolioPartition,
        ):
            raise HveeContractError(
                "critical-terminology portfolio case "
                "requires a partition"
            )

        if not isinstance(
            self.operation,
            ASRCriticalTerminologyPortfolioOperation,
        ):
            raise HveeContractError(
                "critical-terminology portfolio case "
                "requires an operation"
            )

        if (
            not isinstance(self.reference_text, str)
            or not isinstance(self.generated_text, str)
        ):
            raise HveeContractError(
                "critical-terminology portfolio transcripts "
                "must be strings"
            )

        if not isinstance(
            self.expected_outcome,
            ASRCriticalTerminologyFidelityOutcome,
        ):
            raise HveeContractError(
                "critical-terminology portfolio requires "
                "a versioned outcome"
            )

        if not isinstance(
            self.expected_applicable,
            bool,
        ):
            raise HveeContractError(
                "critical-terminology portfolio applicability "
                "must be bool"
            )

        if not isinstance(
            self.expected_preserved_status,
            ObservationStatus,
        ):
            raise HveeContractError(
                "critical-terminology portfolio requires "
                "a preserved status"
            )

        if (
            self.expected_preserved_status
            == ObservationStatus.SUCCESS
        ):
            if not isinstance(
                self.expected_preserved,
                bool,
            ):
                raise HveeContractError(
                    "successful terminology preserved "
                    "expectation requires bool"
                )
        elif self.expected_preserved is not None:
            raise HveeContractError(
                "non-success terminology preserved "
                "expectation cannot contain a value"
            )

        for count in (
            self.expected_reference_count,
            self.expected_generated_count,
            self.expected_substitution_count,
            self.expected_omission_count,
            self.expected_insertion_count,
            self.expected_ordering_change_count,
        ):
            if (
                isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise HveeContractError(
                    "critical-terminology portfolio counts "
                    "must be non-negative integers"
                )

        if (
            not isinstance(
                self.expected_findings,
                tuple,
            )
            or not all(
                isinstance(
                    finding,
                    ASRCriticalTerminologyFindingExpectation,
                )
                for finding in self.expected_findings
            )
        ):
            raise HveeContractError(
                "critical-terminology portfolio findings "
                "must be a tuple of expectations"
            )

        if (
            not isinstance(self.description, str)
            or not self.description.strip()
        ):
            raise HveeContractError(
                "critical-terminology portfolio case "
                "requires a description"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyPortfolioDefinition:
    key: str
    version: str
    profile: ASRCriticalTerminologyProfile
    cases: tuple[
        ASRCriticalTerminologyPortfolioCase,
        ...,
    ]

    def __post_init__(self) -> None:
        if self.key != CRITICAL_TERMINOLOGY_PORTFOLIO_KEY:
            raise HveeContractError(
                "critical-terminology portfolio key "
                "does not match v1"
            )

        if self.version != (
            CRITICAL_TERMINOLOGY_PORTFOLIO_VERSION
        ):
            raise HveeContractError(
                "critical-terminology portfolio version "
                "does not match v1"
            )

        if self.profile != (
            CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1
        ):
            raise HveeContractError(
                "critical-terminology portfolio requires "
                "the exact pinned v1 vocabulary"
            )

        validate_semantic_cases(
            self.cases
        )

    @property
    def vocabulary_sha256(self) -> str:
        return (
            calculate_critical_terminology_vocabulary_sha256(
                self.profile
            )
        )


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyPortfolioCaseResult:
    case_id: str
    partition: ASRCriticalTerminologyPortfolioPartition
    operation: ASRCriticalTerminologyPortfolioOperation
    passed: bool
    failed_checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyPortfolioReport:
    portfolio_key: str
    portfolio_version: str
    vocabulary_sha256: str
    case_results: tuple[
        ASRCriticalTerminologyPortfolioCaseResult,
        ...,
    ]

    @property
    def total_cases(self) -> int:
        return len(
            self.case_results
        )

    @property
    def passed_cases(self) -> int:
        return sum(
            result.passed
            for result in self.case_results
        )

    @property
    def failed_cases(self) -> int:
        return (
            self.total_cases
            - self.passed_cases
        )

    @property
    def passed(self) -> bool:
        return (
            self.total_cases > 0
            and self.failed_cases == 0
        )


def _finding(
    finding_type: ASRCriticalTerminologyFindingType,
    reason_code: ASRCriticalTerminologyReasonCode,
    reference_term_key: str | None,
    generated_term_key: str | None,
) -> ASRCriticalTerminologyFindingExpectation:
    return ASRCriticalTerminologyFindingExpectation(
        finding_type=finding_type,
        reason_code=reason_code,
        reference_term_key=reference_term_key,
        generated_term_key=generated_term_key,
    )


def _case(
    *,
    case_id: str,
    partition: ASRCriticalTerminologyPortfolioPartition,
    operation: ASRCriticalTerminologyPortfolioOperation,
    reference_text: str,
    generated_text: str,
    expected_outcome: ASRCriticalTerminologyFidelityOutcome,
    expected_reference_count: int,
    expected_generated_count: int,
    expected_substitution_count: int = 0,
    expected_omission_count: int = 0,
    expected_insertion_count: int = 0,
    expected_ordering_change_count: int = 0,
    expected_findings: tuple[
        ASRCriticalTerminologyFindingExpectation,
        ...,
    ] = (),
    description: str,
) -> ASRCriticalTerminologyPortfolioCase:
    applicable = (
        expected_outcome
        != ASRCriticalTerminologyFidelityOutcome.NOT_APPLICABLE
    )

    if applicable:
        preserved_status = ObservationStatus.SUCCESS
        preserved = (
            expected_outcome
            == ASRCriticalTerminologyFidelityOutcome.PRESERVED
        )
    else:
        preserved_status = ObservationStatus.ABSTAINED
        preserved = None

    return ASRCriticalTerminologyPortfolioCase(
        case_id=case_id,
        partition=partition,
        operation=operation,
        reference_text=reference_text,
        generated_text=generated_text,
        expected_outcome=expected_outcome,
        expected_applicable=applicable,
        expected_preserved_status=preserved_status,
        expected_preserved=preserved,
        expected_reference_count=expected_reference_count,
        expected_generated_count=expected_generated_count,
        expected_substitution_count=expected_substitution_count,
        expected_omission_count=expected_omission_count,
        expected_insertion_count=expected_insertion_count,
        expected_ordering_change_count=(
            expected_ordering_change_count
        ),
        expected_findings=expected_findings,
        description=description,
    )


P = ASRCriticalTerminologyPortfolioPartition
O = ASRCriticalTerminologyPortfolioOperation
FO = ASRCriticalTerminologyFidelityOutcome
FT = ASRCriticalTerminologyFindingType
RC = ASRCriticalTerminologyReasonCode


CRITICAL_TERMINOLOGY_FIDELITY_PORTFOLIO_V1 = (
    ASRCriticalTerminologyPortfolioDefinition(
        key=CRITICAL_TERMINOLOGY_PORTFOLIO_KEY,
        version=CRITICAL_TERMINOLOGY_PORTFOLIO_VERSION,
        profile=CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1,
        cases=(
            _case(
                case_id="calibration.exact-postgresql",
                partition=P.CALIBRATION,
                operation=O.EQUIVALENCE,
                reference_text="Use PostgreSQL",
                generated_text="Use PostgreSQL",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "database.postgresql",
                        "database.postgresql",
                    ),
                ),
                description=(
                    "Exact registered terminology is preserved."
                ),
            ),
            _case(
                case_id="calibration.accepted-postgres-alias",
                partition=P.CALIBRATION,
                operation=O.EQUIVALENCE,
                reference_text="Use PostgreSQL",
                generated_text="Use Postgres",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.ACCEPTED_ALIAS_EQUIVALENT,
                        "database.postgresql",
                        "database.postgresql",
                    ),
                ),
                description=(
                    "Explicitly registered Postgres alias is equivalent."
                ),
            ),
            _case(
                case_id="calibration.casefold-equivalence",
                partition=P.CALIBRATION,
                operation=O.EQUIVALENCE,
                reference_text="Use PostgreSQL",
                generated_text="Use POSTGRESQL",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "database.postgresql",
                        "database.postgresql",
                    ),
                ),
                description=(
                    "Case folding does not create a false terminology error."
                ),
            ),
            _case(
                case_id="calibration.whitespace-equivalence",
                partition=P.CALIBRATION,
                operation=O.EQUIVALENCE,
                reference_text="Use machine learning",
                generated_text="Use machine   learning",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "concept.machine-learning",
                        "concept.machine-learning",
                    ),
                ),
                description=(
                    "Whitespace collapse preserves a registered phrase."
                ),
            ),
            _case(
                case_id="calibration.nfkc-equivalence",
                partition=P.CALIBRATION,
                operation=O.EQUIVALENCE,
                reference_text="Use PostgreSQL",
                generated_text="Use ＰｏｓｔｇｒｅＳＱＬ",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "database.postgresql",
                        "database.postgresql",
                    ),
                ),
                description=(
                    "Unicode compatibility forms normalize deterministically."
                ),
            ),
            _case(
                case_id="calibration.decomposed-unicode-equivalence",
                partition=P.CALIBRATION,
                operation=O.EQUIVALENCE,
                reference_text="Use naïve Bayes",
                generated_text="Use nai\u0308ve Bayes",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "algorithm.naive-bayes",
                        "algorithm.naive-bayes",
                    ),
                ),
                description=(
                    "Composed and decomposed Unicode remain equivalent."
                ),
            ),
            _case(
                case_id="calibration.k8s-alias-equivalence",
                partition=P.CALIBRATION,
                operation=O.EQUIVALENCE,
                reference_text="Deploy Kubernetes",
                generated_text="Deploy K8s",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.ACCEPTED_ALIAS_EQUIVALENT,
                        "platform.kubernetes",
                        "platform.kubernetes",
                    ),
                ),
                description=(
                    "Explicit K8s alias is accepted for Kubernetes."
                ),
            ),
            _case(
                case_id="calibration.registered-term-substitution",
                partition=P.CALIBRATION,
                operation=O.SUBSTITUTION,
                reference_text="Use PostgreSQL",
                generated_text="Use MySQL",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_substitution_count=1,
                expected_findings=(
                    _finding(
                        FT.SUBSTITUTION,
                        RC.TERM_SUBSTITUTION,
                        "database.postgresql",
                        "database.mysql",
                    ),
                ),
                description=(
                    "Different registered concepts are a proven substitution."
                ),
            ),
            _case(
                case_id="calibration.reference-omission",
                partition=P.CALIBRATION,
                operation=O.OMISSION,
                reference_text="Deploy Kubernetes",
                generated_text="Deploy the platform",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=1,
                expected_generated_count=0,
                expected_omission_count=1,
                expected_findings=(
                    _finding(
                        FT.OMISSION,
                        RC.REFERENCE_TERM_OMITTED,
                        "platform.kubernetes",
                        None,
                    ),
                ),
                description=(
                    "Missing reference terminology is an omission."
                ),
            ),
            _case(
                case_id="calibration.generated-insertion",
                partition=P.CALIBRATION,
                operation=O.INSERTION,
                reference_text="Deploy the database",
                generated_text="Deploy PostgreSQL",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=0,
                expected_generated_count=1,
                expected_insertion_count=1,
                expected_findings=(
                    _finding(
                        FT.INSERTION,
                        RC.GENERATED_TERM_INSERTED,
                        None,
                        "database.postgresql",
                    ),
                ),
                description=(
                    "Generated-only registered terminology is an insertion."
                ),
            ),
            _case(
                case_id="calibration.ordering-change",
                partition=P.CALIBRATION,
                operation=O.ORDERING_CHANGE,
                reference_text="PostgreSQL then Kubernetes",
                generated_text="Kubernetes then PostgreSQL",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=2,
                expected_generated_count=2,
                expected_ordering_change_count=1,
                expected_findings=(
                    _finding(
                        FT.ORDERING_CHANGE,
                        RC.TERM_ORDER_CHANGED,
                        "database.postgresql",
                        "platform.kubernetes",
                    ),
                ),
                description=(
                    "Same terminology multiset in a new order is detected."
                ),
            ),
            _case(
                case_id="calibration.duplicate-control",
                partition=P.CALIBRATION,
                operation=O.DUPLICATE_CONTROL,
                reference_text="Postgres talks to Postgres",
                generated_text="Postgres talks to Postgres",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=2,
                expected_generated_count=2,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "database.postgresql",
                        "database.postgresql",
                    ),
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "database.postgresql",
                        "database.postgresql",
                    ),
                ),
                description=(
                    "Duplicate terminology occurrences remain distinct."
                ),
            ),
            _case(
                case_id="regression.duplicate-omission",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.DUPLICATE_OMISSION,
                reference_text="Postgres talks to Postgres",
                generated_text="Postgres",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=2,
                expected_generated_count=1,
                expected_omission_count=1,
                expected_findings=(
                    _finding(
                        FT.OMISSION,
                        RC.REFERENCE_TERM_OMITTED,
                        "database.postgresql",
                        None,
                    ),
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "database.postgresql",
                        "database.postgresql",
                    ),
                ),
                description=(
                    "Dropping one duplicate occurrence remains observable."
                ),
            ),
            _case(
                case_id="regression.node-js-punctuation-control",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.PUNCTUATION_CONTROL,
                reference_text="Use Node.js",
                generated_text="Use Node.js",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "runtime.node-js",
                        "runtime.node-js",
                    ),
                ),
                description=(
                    "Meaningful Node.js punctuation is retained."
                ),
            ),
            _case(
                case_id="regression.node-js-punctuation-loss",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.PUNCTUATION_CONTROL,
                reference_text="Use Node.js",
                generated_text="Use Node js",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=1,
                expected_generated_count=0,
                expected_omission_count=1,
                expected_findings=(
                    _finding(
                        FT.OMISSION,
                        RC.REFERENCE_TERM_OMITTED,
                        "runtime.node-js",
                        None,
                    ),
                ),
                description=(
                    "Removing meaningful punctuation is not silently accepted."
                ),
            ),
            _case(
                case_id="regression.c-sharp-symbol-control",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.PUNCTUATION_CONTROL,
                reference_text="Use C#",
                generated_text="Use C#",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "language.c-sharp",
                        "language.c-sharp",
                    ),
                ),
                description=(
                    "Critical symbol-bearing terminology is preserved."
                ),
            ),
            _case(
                case_id="regression.c-sharp-symbol-loss",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.PUNCTUATION_CONTROL,
                reference_text="Use C#",
                generated_text="Use C",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=1,
                expected_generated_count=0,
                expected_omission_count=1,
                expected_findings=(
                    _finding(
                        FT.OMISSION,
                        RC.REFERENCE_TERM_OMITTED,
                        "language.c-sharp",
                        None,
                    ),
                ),
                description=(
                    "C# cannot silently collapse to plain C."
                ),
            ),
            _case(
                case_id="regression.longest-overlap-control",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.OVERLAP_CONTROL,
                reference_text="Use machine learning",
                generated_text="Use machine learning",
                expected_outcome=FO.PRESERVED,
                expected_reference_count=1,
                expected_generated_count=1,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "concept.machine-learning",
                        "concept.machine-learning",
                    ),
                ),
                description=(
                    "Longest registered phrase wins over nested learning."
                ),
            ),
            _case(
                case_id="regression.token-boundary-control",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.BOUNDARY_CONTROL,
                reference_text="PostgreSQLish",
                generated_text="PostgreSQLish",
                expected_outcome=FO.NOT_APPLICABLE,
                expected_reference_count=0,
                expected_generated_count=0,
                description=(
                    "Registered terms do not match inside larger tokens."
                ),
            ),
            _case(
                case_id="regression.unregistered-phonetic-rendering",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.UNREGISTERED_RENDERING,
                reference_text="Deploy Kubernetes",
                generated_text="Deploy Cooper Netties",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=1,
                expected_generated_count=0,
                expected_omission_count=1,
                expected_findings=(
                    _finding(
                        FT.OMISSION,
                        RC.REFERENCE_TERM_OMITTED,
                        "platform.kubernetes",
                        None,
                    ),
                ),
                description=(
                    "Unregistered phonetic guesses are never equivalence."
                ),
            ),
            _case(
                case_id="regression.no-critical-terminology",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.NOT_APPLICABLE,
                reference_text="Deploy the service",
                generated_text="Deploy the service",
                expected_outcome=FO.NOT_APPLICABLE,
                expected_reference_count=0,
                expected_generated_count=0,
                description=(
                    "Ordinary transcripts without vocabulary terms abstain."
                ),
            ),
            _case(
                case_id="regression.generated-only-k8s",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.INSERTION,
                reference_text="Deploy the platform",
                generated_text="Deploy K8s",
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=0,
                expected_generated_count=1,
                expected_insertion_count=1,
                expected_findings=(
                    _finding(
                        FT.INSERTION,
                        RC.GENERATED_TERM_INSERTED,
                        None,
                        "platform.kubernetes",
                    ),
                ),
                description=(
                    "Generated-only aliases remain critical insertions."
                ),
            ),
            _case(
                case_id="regression.multi-term-alias-preservation",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.EQUIVALENCE,
                reference_text=(
                    "Use PostgreSQL on Kubernetes"
                ),
                generated_text=(
                    "Use Postgres on K8s"
                ),
                expected_outcome=FO.PRESERVED,
                expected_reference_count=2,
                expected_generated_count=2,
                expected_findings=(
                    _finding(
                        FT.MATCH,
                        RC.ACCEPTED_ALIAS_EQUIVALENT,
                        "database.postgresql",
                        "database.postgresql",
                    ),
                    _finding(
                        FT.MATCH,
                        RC.ACCEPTED_ALIAS_EQUIVALENT,
                        "platform.kubernetes",
                        "platform.kubernetes",
                    ),
                ),
                description=(
                    "Multiple explicitly registered aliases preserve identity."
                ),
            ),
            _case(
                case_id="regression.mixed-substitution-and-match",
                partition=P.REGRESSION_HOLDOUT,
                operation=O.SUBSTITUTION,
                reference_text=(
                    "Use PostgreSQL on Kubernetes"
                ),
                generated_text=(
                    "Use MySQL on Kubernetes"
                ),
                expected_outcome=FO.NOT_PRESERVED,
                expected_reference_count=2,
                expected_generated_count=2,
                expected_substitution_count=1,
                expected_findings=(
                    _finding(
                        FT.SUBSTITUTION,
                        RC.TERM_SUBSTITUTION,
                        "database.postgresql",
                        "database.mysql",
                    ),
                    _finding(
                        FT.MATCH,
                        RC.EXACT_SURFACE_MATCH,
                        "platform.kubernetes",
                        "platform.kubernetes",
                    ),
                ),
                description=(
                    "A changed critical term is detected beside a preserved one."
                ),
            ),
        ),
    )
)


def evaluate_critical_terminology_portfolio_case_observations(
    case: ASRCriticalTerminologyPortfolioCase,
    *,
    profile: ASRCriticalTerminologyProfile,
) -> tuple[Observation, ...]:
    if not isinstance(
        case,
        ASRCriticalTerminologyPortfolioCase,
    ):
        raise HveeContractError(
            "critical-terminology portfolio evaluation "
            "requires a case"
        )

    if profile != (
        CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1
    ):
        raise HveeContractError(
            "critical-terminology portfolio evaluation "
            "requires the exact pinned v1 vocabulary"
        )

    evaluation = evaluate_critical_terminology_fidelity(
        reference_text=case.reference_text,
        generated_text=case.generated_text,
        profile=profile,
    )

    return (
        build_critical_terminology_fidelity_observations(
            evaluation,
            profile=profile,
        )
    )


def _finding_signature(
    value: object,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
]:
    if not isinstance(
        value,
        dict,
    ):
        raise HveeContractError(
            "critical-terminology portfolio finding "
            "must be an object"
        )

    reference = value.get(
        "reference"
    )
    generated = value.get(
        "generated"
    )

    if (
        reference is not None
        and not isinstance(reference, dict)
    ):
        raise HveeContractError(
            "critical-terminology portfolio reference finding "
            "must be an object when present"
        )

    if (
        generated is not None
        and not isinstance(generated, dict)
    ):
        raise HveeContractError(
            "critical-terminology portfolio generated finding "
            "must be an object when present"
        )

    return (
        value.get("finding_type"),
        value.get("reason_code"),
        (
            reference.get("term_key")
            if isinstance(reference, dict)
            else None
        ),
        (
            generated.get("term_key")
            if isinstance(generated, dict)
            else None
        ),
    )


def compare_critical_terminology_portfolio_case(
    *,
    case: ASRCriticalTerminologyPortfolioCase,
    observations: tuple[Observation, ...],
    profile: ASRCriticalTerminologyProfile,
) -> ASRCriticalTerminologyPortfolioCaseResult:
    if not isinstance(
        case,
        ASRCriticalTerminologyPortfolioCase,
    ):
        raise HveeContractError(
            "critical-terminology portfolio comparison "
            "requires a case"
        )

    if profile != (
        CRITICAL_TERMINOLOGY_PORTFOLIO_PROFILE_V1
    ):
        raise HveeContractError(
            "critical-terminology portfolio comparison "
            "requires the exact pinned v1 vocabulary"
        )

    if (
        not isinstance(observations, tuple)
        or not all(
            isinstance(
                observation,
                Observation,
            )
            for observation in observations
        )
    ):
        raise HveeContractError(
            "critical-terminology portfolio requires "
            "Observation values"
        )

    by_key: dict[
        str,
        Observation,
    ] = {}

    for observation in observations:
        if observation.metric_key in by_key:
            raise HveeContractError(
                "critical-terminology portfolio observations "
                "contain duplicate metric keys"
            )

        by_key[
            observation.metric_key
        ] = observation

    metric_by_key = {
        metric.key: metric
        for metric in CRITICAL_TERMINOLOGY_METRICS
    }

    if set(by_key) != set(
        metric_by_key
    ):
        raise HveeContractError(
            "critical-terminology portfolio observations "
            "do not match the complete metric contract"
        )

    for key, metric in metric_by_key.items():
        observation = by_key[
            key
        ]

        if (
            observation.metric_version
            != metric.version
            or observation.evaluator_key
            != CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR.key
            or observation.evaluator_version
            != CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR.version
            or observation.evaluation_type
            != ASR_EVALUATION_TYPE
            or observation.value_type
            != metric.value_type
        ):
            raise HveeContractError(
                "critical-terminology portfolio scientific "
                "identity changed without a versioned contract"
            )

    failed: list[str] = []

    def expect_value(
        key: str,
        expected: object,
        check: str,
    ) -> None:
        observation = by_key[
            key
        ]

        if (
            observation.status
            != ObservationStatus.SUCCESS
            or observation.value
            != expected
        ):
            failed.append(
                check
            )

    expect_value(
        CRITICAL_TERMINOLOGY_APPLICABLE_METRIC.key,
        case.expected_applicable,
        "applicable",
    )

    expect_value(
        CRITICAL_TERMINOLOGY_OUTCOME_METRIC.key,
        case.expected_outcome.value,
        "outcome",
    )

    expect_value(
        (
            CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC
            .key
        ),
        calculate_critical_terminology_vocabulary_sha256(
            profile
        ),
        "vocabulary_sha256",
    )

    expect_value(
        CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC.key,
        case.expected_reference_count,
        "reference_count",
    )

    expect_value(
        CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC.key,
        case.expected_generated_count,
        "generated_count",
    )

    expect_value(
        CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC.key,
        case.expected_substitution_count,
        "substitution_count",
    )

    expect_value(
        CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC.key,
        case.expected_omission_count,
        "omission_count",
    )

    expect_value(
        CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC.key,
        case.expected_insertion_count,
        "insertion_count",
    )

    expect_value(
        (
            CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC
            .key
        ),
        case.expected_ordering_change_count,
        "ordering_change_count",
    )

    preserved = by_key[
        CRITICAL_TERMINOLOGY_PRESERVED_METRIC.key
    ]

    if (
        preserved.status
        != case.expected_preserved_status
    ):
        failed.append(
            "preserved_status"
        )

    if preserved.value != (
        case.expected_preserved
    ):
        failed.append(
            "preserved_value"
        )

    findings_observation = by_key[
        CRITICAL_TERMINOLOGY_FINDINGS_METRIC.key
    ]

    if (
        findings_observation.status
        != ObservationStatus.SUCCESS
        or not isinstance(
            findings_observation.value,
            list,
        )
    ):
        failed.append(
            "findings"
        )
    else:
        actual_signatures = tuple(
            _finding_signature(
                value
            )
            for value in (
                findings_observation.value
            )
        )

        expected_signatures = tuple(
            (
                finding.finding_type.value,
                finding.reason_code.value,
                finding.reference_term_key,
                finding.generated_term_key,
            )
            for finding in (
                case.expected_findings
            )
        )

        if actual_signatures != (
            expected_signatures
        ):
            failed.append(
                "findings"
            )

        expected_sha256 = (
            calculate_critical_terminology_vocabulary_sha256(
                profile
            )
        )

        for value in (
            findings_observation.value
        ):
            if not isinstance(
                value,
                dict,
            ):
                continue

            if (
                value.get("profile_key")
                != profile.key
                or value.get("profile_version")
                != profile.version
                or value.get("vocabulary_sha256")
                != expected_sha256
            ):
                failed.append(
                    "finding_provenance"
                )
                break

    failed_tuple = tuple(
        failed
    )

    return (
        ASRCriticalTerminologyPortfolioCaseResult(
            case_id=case.case_id,
            partition=case.partition,
            operation=case.operation,
            passed=not failed_tuple,
            failed_checks=failed_tuple,
        )
    )


def run_critical_terminology_portfolio_case(
    case: ASRCriticalTerminologyPortfolioCase,
    *,
    profile: ASRCriticalTerminologyProfile,
) -> ASRCriticalTerminologyPortfolioCaseResult:
    return (
        compare_critical_terminology_portfolio_case(
            case=case,
            observations=(
                evaluate_critical_terminology_portfolio_case_observations(
                    case,
                    profile=profile,
                )
            ),
            profile=profile,
        )
    )


def run_critical_terminology_portfolio(
    portfolio: ASRCriticalTerminologyPortfolioDefinition,
) -> ASRCriticalTerminologyPortfolioReport:
    if not isinstance(
        portfolio,
        ASRCriticalTerminologyPortfolioDefinition,
    ):
        raise HveeContractError(
            "critical-terminology portfolio runner "
            "requires a definition"
        )

    laboratory_report = run_semantic_portfolio(
        portfolio_key=portfolio.key,
        portfolio_version=portfolio.version,
        cases=portfolio.cases,
        run_case=lambda case: (
            run_critical_terminology_portfolio_case(
                case,
                profile=portfolio.profile,
            )
        ),
    )

    return (
        ASRCriticalTerminologyPortfolioReport(
            portfolio_key=(
                laboratory_report.portfolio_key
            ),
            portfolio_version=(
                laboratory_report.portfolio_version
            ),
            vocabulary_sha256=(
                portfolio.vocabulary_sha256
            ),
            case_results=(
                laboratory_report.case_results
            ),
        )
    )
