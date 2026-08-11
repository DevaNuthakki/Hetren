"""Development portfolio for Critical Identifier Fidelity v1.

This is source-visible calibration and regression evidence. It is not a
private holdout, certification set, production qualification, or release
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.critical_identifier_fidelity import (
    CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_IDENTIFIER_APPLICABLE_METRIC,
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    CRITICAL_IDENTIFIER_FINDINGS_METRIC,
    CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC,
    CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_METRICS,
    CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_OUTCOME_METRIC,
    CRITICAL_IDENTIFIER_PRESERVED_METRIC,
    CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC,
    EN_US_CRITICAL_IDENTIFIER_PROFILE,
    ASRCriticalIdentifierFidelityOutcome,
    ASRCriticalIdentifierReasonCode,
    ASRCriticalIdentifierType,
    build_critical_identifier_fidelity_observations,
    evaluate_critical_identifier_fidelity,
)
from hvee.packs.asr.evaluation import ASR_EVALUATION_TYPE


CRITICAL_IDENTIFIER_PORTFOLIO_KEY = (
    "hetren.asr.critical-identifier-fidelity-portfolio.en-us"
)
CRITICAL_IDENTIFIER_PORTFOLIO_VERSION = "1.0.0"


class ASRCriticalIdentifierPortfolioPartition(StrEnum):
    """Source-visible development partitions."""

    CALIBRATION = "calibration"
    REGRESSION_HOLDOUT = "regression_holdout"


class ASRCriticalIdentifierPortfolioOperation(StrEnum):
    EQUIVALENCE = "equivalence"
    SUBSTITUTION = "substitution"
    OMISSION = "omission"
    INSERTION = "insertion"
    ORDERING_CHANGE = "ordering_change"
    DUPLICATE_CONTROL = "duplicate_control"
    DUPLICATE_OMISSION = "duplicate_omission"
    TYPE_MISMATCH = "type_mismatch"
    NOT_APPLICABLE = "not_applicable"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierPortfolioCase:
    case_id: str
    partition: ASRCriticalIdentifierPortfolioPartition
    operation: ASRCriticalIdentifierPortfolioOperation
    identifier_type: ASRCriticalIdentifierType | None
    reference_text: str
    generated_text: str
    expected_outcome: ASRCriticalIdentifierFidelityOutcome
    expected_applicable: bool
    expected_preserved_status: ObservationStatus
    expected_preserved: bool | None
    expected_reference_count: int
    expected_generated_count: int
    expected_substitution_count: int
    expected_omission_count: int
    expected_insertion_count: int
    expected_ordering_change_count: int
    expected_ambiguity_count: int
    required_reason_codes: tuple[
        ASRCriticalIdentifierReasonCode,
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
                "critical-identifier portfolio case id "
                "must be non-empty"
            )

        if not isinstance(
            self.partition,
            ASRCriticalIdentifierPortfolioPartition,
        ):
            raise HveeContractError(
                "critical-identifier portfolio case "
                "requires a partition"
            )

        if not isinstance(
            self.operation,
            ASRCriticalIdentifierPortfolioOperation,
        ):
            raise HveeContractError(
                "critical-identifier portfolio case "
                "requires an operation"
            )

        if self.operation == (
            ASRCriticalIdentifierPortfolioOperation
            .NOT_APPLICABLE
        ):
            if self.identifier_type is not None:
                raise HveeContractError(
                    "not-applicable identifier case "
                    "cannot declare an identifier type"
                )
        elif not isinstance(
            self.identifier_type,
            ASRCriticalIdentifierType,
        ):
            raise HveeContractError(
                "applicable identifier case requires "
                "an identifier type"
            )

        if (
            not isinstance(self.reference_text, str)
            or not isinstance(self.generated_text, str)
        ):
            raise HveeContractError(
                "critical-identifier portfolio transcripts "
                "must be strings"
            )

        if not isinstance(
            self.expected_outcome,
            ASRCriticalIdentifierFidelityOutcome,
        ):
            raise HveeContractError(
                "critical-identifier portfolio requires "
                "a versioned outcome"
            )

        if not isinstance(
            self.expected_applicable,
            bool,
        ):
            raise HveeContractError(
                "critical-identifier portfolio applicability "
                "must be bool"
            )

        if not isinstance(
            self.expected_preserved_status,
            ObservationStatus,
        ):
            raise HveeContractError(
                "critical-identifier portfolio requires "
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
                    "successful preserved expectation "
                    "requires bool"
                )
        elif self.expected_preserved is not None:
            raise HveeContractError(
                "non-success preserved expectation "
                "cannot contain a value"
            )

        for count in (
            self.expected_reference_count,
            self.expected_generated_count,
            self.expected_substitution_count,
            self.expected_omission_count,
            self.expected_insertion_count,
            self.expected_ordering_change_count,
            self.expected_ambiguity_count,
        ):
            if (
                isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise HveeContractError(
                    "critical-identifier portfolio counts "
                    "must be non-negative integers"
                )

        if (
            not isinstance(
                self.required_reason_codes,
                tuple,
            )
            or not all(
                isinstance(
                    reason,
                    ASRCriticalIdentifierReasonCode,
                )
                for reason in self.required_reason_codes
            )
        ):
            raise HveeContractError(
                "critical-identifier portfolio reason codes "
                "must be versioned"
            )

        if len(self.required_reason_codes) != len(
            set(self.required_reason_codes)
        ):
            raise HveeContractError(
                "critical-identifier portfolio reason codes "
                "must be unique"
            )

        if (
            not isinstance(self.description, str)
            or not self.description.strip()
        ):
            raise HveeContractError(
                "critical-identifier portfolio case "
                "requires a description"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierPortfolioDefinition:
    key: str
    version: str
    cases: tuple[
        ASRCriticalIdentifierPortfolioCase,
        ...,
    ]

    def __post_init__(self) -> None:
        if (
            self.key != CRITICAL_IDENTIFIER_PORTFOLIO_KEY
            or self.version
            != CRITICAL_IDENTIFIER_PORTFOLIO_VERSION
        ):
            raise HveeContractError(
                "critical-identifier portfolio identity "
                "is unsupported"
            )

        if (
            not isinstance(self.cases, tuple)
            or not self.cases
            or not all(
                isinstance(
                    case,
                    ASRCriticalIdentifierPortfolioCase,
                )
                for case in self.cases
            )
        ):
            raise HveeContractError(
                "critical-identifier portfolio "
                "requires cases"
            )

        case_ids = tuple(
            case.case_id
            for case in self.cases
        )

        if len(case_ids) != len(set(case_ids)):
            raise HveeContractError(
                "critical-identifier portfolio "
                "case ids must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierPortfolioCaseResult:
    case_id: str
    partition: ASRCriticalIdentifierPortfolioPartition
    operation: ASRCriticalIdentifierPortfolioOperation
    passed: bool
    failed_checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierPortfolioReport:
    portfolio_key: str
    portfolio_version: str
    case_results: tuple[
        ASRCriticalIdentifierPortfolioCaseResult,
        ...,
    ]

    @property
    def total_cases(self) -> int:
        return len(self.case_results)

    @property
    def passed_cases(self) -> int:
        return sum(
            result.passed
            for result in self.case_results
        )

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    @property
    def passed(self) -> bool:
        return (
            self.total_cases > 0
            and self.failed_cases == 0
        )


def _case(
    *,
    case_id: str,
    partition: ASRCriticalIdentifierPortfolioPartition,
    operation: ASRCriticalIdentifierPortfolioOperation,
    identifier_type: ASRCriticalIdentifierType | None,
    reference_text: str,
    generated_text: str,
    outcome: ASRCriticalIdentifierFidelityOutcome,
    reference_count: int,
    generated_count: int,
    substitution_count: int = 0,
    omission_count: int = 0,
    insertion_count: int = 0,
    ordering_change_count: int = 0,
    ambiguity_count: int = 0,
    required_reason_codes: tuple[
        ASRCriticalIdentifierReasonCode,
        ...,
    ] = (),
    description: str,
) -> ASRCriticalIdentifierPortfolioCase:
    if outcome == (
        ASRCriticalIdentifierFidelityOutcome.PRESERVED
    ):
        applicable = True
        preserved_status = ObservationStatus.SUCCESS
        preserved: bool | None = True
    elif outcome == (
        ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED
    ):
        applicable = True
        preserved_status = ObservationStatus.SUCCESS
        preserved = False
    elif outcome == (
        ASRCriticalIdentifierFidelityOutcome.NOT_APPLICABLE
    ):
        applicable = False
        preserved_status = ObservationStatus.ABSTAINED
        preserved = None
    else:
        applicable = True
        preserved_status = ObservationStatus.ABSTAINED
        preserved = None

    return ASRCriticalIdentifierPortfolioCase(
        case_id=case_id,
        partition=partition,
        operation=operation,
        identifier_type=identifier_type,
        reference_text=reference_text,
        generated_text=generated_text,
        expected_outcome=outcome,
        expected_applicable=applicable,
        expected_preserved_status=preserved_status,
        expected_preserved=preserved,
        expected_reference_count=reference_count,
        expected_generated_count=generated_count,
        expected_substitution_count=substitution_count,
        expected_omission_count=omission_count,
        expected_insertion_count=insertion_count,
        expected_ordering_change_count=ordering_change_count,
        expected_ambiguity_count=ambiguity_count,
        required_reason_codes=required_reason_codes,
        description=description,
    )


def _supported_type_cases(
    *,
    label: str,
    identifier_type: ASRCriticalIdentifierType,
    cue: str,
    reference_value: str,
    equivalent_value: str,
    equivalent_reason: ASRCriticalIdentifierReasonCode,
    substituted_value: str,
) -> tuple[
    ASRCriticalIdentifierPortfolioCase,
    ...,
]:
    reference = f"{cue} {reference_value}"

    return (
        _case(
            case_id=f"calibration.{label}.equivalence",
            partition=(
                ASRCriticalIdentifierPortfolioPartition
                .CALIBRATION
            ),
            operation=(
                ASRCriticalIdentifierPortfolioOperation
                .EQUIVALENCE
            ),
            identifier_type=identifier_type,
            reference_text=reference,
            generated_text=f"{cue} {equivalent_value}",
            outcome=(
                ASRCriticalIdentifierFidelityOutcome.PRESERVED
            ),
            reference_count=1,
            generated_count=1,
            required_reason_codes=(
                equivalent_reason,
            ),
            description=(
                f"Supported {label} identifier "
                "equivalence."
            ),
        ),
        _case(
            case_id=f"calibration.{label}.substitution",
            partition=(
                ASRCriticalIdentifierPortfolioPartition
                .CALIBRATION
            ),
            operation=(
                ASRCriticalIdentifierPortfolioOperation
                .SUBSTITUTION
            ),
            identifier_type=identifier_type,
            reference_text=reference,
            generated_text=f"{cue} {substituted_value}",
            outcome=(
                ASRCriticalIdentifierFidelityOutcome
                .NOT_PRESERVED
            ),
            reference_count=1,
            generated_count=1,
            substitution_count=1,
            required_reason_codes=(
                ASRCriticalIdentifierReasonCode
                .VALUE_SUBSTITUTION,
            ),
            description=(
                f"Controlled {label} value substitution."
            ),
        ),
        _case(
            case_id=f"holdout.{label}.omission",
            partition=(
                ASRCriticalIdentifierPortfolioPartition
                .REGRESSION_HOLDOUT
            ),
            operation=(
                ASRCriticalIdentifierPortfolioOperation
                .OMISSION
            ),
            identifier_type=identifier_type,
            reference_text=reference,
            generated_text=(
                "The interaction completed without "
                "an identifier."
            ),
            outcome=(
                ASRCriticalIdentifierFidelityOutcome
                .NOT_PRESERVED
            ),
            reference_count=1,
            generated_count=0,
            omission_count=1,
            required_reason_codes=(
                ASRCriticalIdentifierReasonCode
                .REFERENCE_IDENTIFIER_OMITTED,
            ),
            description=(
                f"Controlled {label} identifier omission."
            ),
        ),
        _case(
            case_id=f"holdout.{label}.insertion",
            partition=(
                ASRCriticalIdentifierPortfolioPartition
                .REGRESSION_HOLDOUT
            ),
            operation=(
                ASRCriticalIdentifierPortfolioOperation
                .INSERTION
            ),
            identifier_type=identifier_type,
            reference_text=(
                "The interaction completed without "
                "an identifier."
            ),
            generated_text=reference,
            outcome=(
                ASRCriticalIdentifierFidelityOutcome
                .NOT_PRESERVED
            ),
            reference_count=0,
            generated_count=1,
            insertion_count=1,
            required_reason_codes=(
                ASRCriticalIdentifierReasonCode
                .GENERATED_IDENTIFIER_INSERTED,
            ),
            description=(
                f"Controlled {label} identifier insertion."
            ),
        ),
    )


_TYPE_MATRIX = (
    (
        "confirmation-code",
        ASRCriticalIdentifierType.CONFIRMATION_CODE,
        "confirmation code",
        "AB7K92",
        "ab-7k-92",
        ASRCriticalIdentifierReasonCode.FORMAT_EQUIVALENT,
        "AB7K29",
    ),
    (
        "reference-id",
        ASRCriticalIdentifierType.REFERENCE_ID,
        "reference id",
        "QF2841",
        "QF2841",
        ASRCriticalIdentifierReasonCode.EXACT_MATCH,
        "QF2849",
    ),
    (
        "ticket-id",
        ASRCriticalIdentifierType.TICKET_ID,
        "ticket id",
        "93BZK",
        "93BZK",
        ASRCriticalIdentifierReasonCode.EXACT_MATCH,
        "93BZQ",
    ),
    (
        "case-id",
        ASRCriticalIdentifierType.CASE_ID,
        "case id",
        "A71K",
        "A71K",
        ASRCriticalIdentifierReasonCode.EXACT_MATCH,
        "A72K",
    ),
    (
        "order-id",
        ASRCriticalIdentifierType.ORDER_ID,
        "order id",
        "49218",
        "49218",
        ASRCriticalIdentifierReasonCode.EXACT_MATCH,
        "49281",
    ),
    (
        "account-id",
        ASRCriticalIdentifierType.ACCOUNT_ID,
        "account id",
        "AX93K",
        "AX93K",
        ASRCriticalIdentifierReasonCode.EXACT_MATCH,
        "AX39K",
    ),
    (
        "serial-number",
        ASRCriticalIdentifierType.SERIAL_NUMBER,
        "serial number",
        "R7-42-X",
        "r742x",
        ASRCriticalIdentifierReasonCode.FORMAT_EQUIVALENT,
        "R7-42-Y",
    ),
    (
        "booking-reference",
        ASRCriticalIdentifierType.BOOKING_REFERENCE,
        "booking reference",
        "PK8D6",
        "P K 8 D 6",
        ASRCriticalIdentifierReasonCode.FORMAT_EQUIVALENT,
        "PK8D9",
    ),
)


_TYPE_CASES = tuple(
    case
    for (
        label,
        identifier_type,
        cue,
        reference_value,
        equivalent_value,
        equivalent_reason,
        substituted_value,
    ) in _TYPE_MATRIX
    for case in _supported_type_cases(
        label=label,
        identifier_type=identifier_type,
        cue=cue,
        reference_value=reference_value,
        equivalent_value=equivalent_value,
        equivalent_reason=equivalent_reason,
        substituted_value=substituted_value,
    )
)


_EDGE_CASES = (
    _case(
        case_id="holdout.ticket-id.ordering-change",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation
            .ORDERING_CHANGE
        ),
        identifier_type=ASRCriticalIdentifierType.TICKET_ID,
        reference_text=(
            "ticket id A12 then ticket id B34"
        ),
        generated_text=(
            "ticket id B34 then ticket id A12"
        ),
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .NOT_PRESERVED
        ),
        reference_count=2,
        generated_count=2,
        ordering_change_count=1,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode
            .IDENTIFIER_ORDER_CHANGED,
        ),
        description=(
            "Reordering equal identifier multisets "
            "must not silently pass."
        ),
    ),
    _case(
        case_id="calibration.ticket-id.duplicate-control",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .CALIBRATION
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation
            .DUPLICATE_CONTROL
        ),
        identifier_type=ASRCriticalIdentifierType.TICKET_ID,
        reference_text=(
            "ticket id A12 then ticket id A12"
        ),
        generated_text=(
            "ticket id A12 then ticket id A12"
        ),
        outcome=(
            ASRCriticalIdentifierFidelityOutcome.PRESERVED
        ),
        reference_count=2,
        generated_count=2,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode.EXACT_MATCH,
        ),
        description=(
            "Duplicate identifiers remain preserved "
            "when multiplicity is unchanged."
        ),
    ),
    _case(
        case_id="holdout.ticket-id.duplicate-omission",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation
            .DUPLICATE_OMISSION
        ),
        identifier_type=ASRCriticalIdentifierType.TICKET_ID,
        reference_text=(
            "ticket id A12 then ticket id A12"
        ),
        generated_text="ticket id A12",
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .NOT_PRESERVED
        ),
        reference_count=2,
        generated_count=1,
        omission_count=1,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode
            .REFERENCE_IDENTIFIER_OMITTED,
        ),
        description=(
            "Duplicate multiplicity loss is a proven omission."
        ),
    ),
    _case(
        case_id="calibration.no-identifier.not-applicable",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .CALIBRATION
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation
            .NOT_APPLICABLE
        ),
        identifier_type=None,
        reference_text="The request succeeded.",
        generated_text="The request succeeded.",
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .NOT_APPLICABLE
        ),
        reference_count=0,
        generated_count=0,
        description=(
            "Ordinary text without supported cues "
            "must not create identifier evidence."
        ),
    ),
    _case(
        case_id="holdout.reference-id.ambiguous",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation.AMBIGUOUS
        ),
        identifier_type=ASRCriticalIdentifierType.REFERENCE_ID,
        reference_text="reference id AB7K or CD92",
        generated_text="reference id AB7K or CD92",
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        ),
        reference_count=0,
        generated_count=0,
        ambiguity_count=2,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode
            .REFERENCE_EXTRACTION_AMBIGUOUS,
            ASRCriticalIdentifierReasonCode
            .GENERATED_EXTRACTION_AMBIGUOUS,
        ),
        description=(
            "Alternative identifier candidates require abstention."
        ),
    ),
    _case(
        case_id="holdout.reference-id.grouped-unsupported",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation.UNSUPPORTED
        ),
        identifier_type=ASRCriticalIdentifierType.REFERENCE_ID,
        reference_text="reference id QF 2841",
        generated_text="reference id QF 2841",
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        ),
        reference_count=0,
        generated_count=0,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode
            .REFERENCE_SURFACE_UNSUPPORTED,
            ASRCriticalIdentifierReasonCode
            .GENERATED_SURFACE_UNSUPPORTED,
        ),
        description=(
            "Grouped multi-token identifier surfaces "
            "remain unsupported in v1."
        ),
    ),
    _case(
        case_id="holdout.confirmation-code.spoken-unsupported",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation.UNSUPPORTED
        ),
        identifier_type=(
            ASRCriticalIdentifierType.CONFIRMATION_CODE
        ),
        reference_text=(
            "confirmation code alpha bravo seven kilo"
        ),
        generated_text=(
            "confirmation code alpha bravo seven kilo"
        ),
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        ),
        reference_count=0,
        generated_count=0,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode
            .REFERENCE_SURFACE_UNSUPPORTED,
            ASRCriticalIdentifierReasonCode
            .GENERATED_SURFACE_UNSUPPORTED,
        ),
        description=(
            "Spoken alphabet interpretation is outside v1."
        ),
    ),
    _case(
        case_id="holdout.reference-id.underscore-unsupported",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation.UNSUPPORTED
        ),
        identifier_type=ASRCriticalIdentifierType.REFERENCE_ID,
        reference_text="reference id AB_7K_92",
        generated_text="reference id AB_7K_92",
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        ),
        reference_count=0,
        generated_count=0,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode
            .REFERENCE_SURFACE_UNSUPPORTED,
            ASRCriticalIdentifierReasonCode
            .GENERATED_SURFACE_UNSUPPORTED,
        ),
        description=(
            "Underscore-separated identifiers "
            "remain unsupported in v1."
        ),
    ),
    _case(
        case_id="holdout.reference-id.malformed-hyphen",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation.UNSUPPORTED
        ),
        identifier_type=ASRCriticalIdentifierType.REFERENCE_ID,
        reference_text="reference id AB--12",
        generated_text="reference id AB--12",
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        ),
        reference_count=0,
        generated_count=0,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode
            .REFERENCE_SURFACE_UNSUPPORTED,
            ASRCriticalIdentifierReasonCode
            .GENERATED_SURFACE_UNSUPPORTED,
        ),
        description=(
            "Malformed hyphen surfaces must not "
            "silently truncate into false passes."
        ),
    ),
    _case(
        case_id="holdout.identifier-type.mismatch",
        partition=(
            ASRCriticalIdentifierPortfolioPartition
            .REGRESSION_HOLDOUT
        ),
        operation=(
            ASRCriticalIdentifierPortfolioOperation
            .TYPE_MISMATCH
        ),
        identifier_type=ASRCriticalIdentifierType.TICKET_ID,
        reference_text="ticket id A12",
        generated_text="case id A12",
        outcome=(
            ASRCriticalIdentifierFidelityOutcome
            .NOT_PRESERVED
        ),
        reference_count=1,
        generated_count=1,
        omission_count=1,
        insertion_count=1,
        required_reason_codes=(
            ASRCriticalIdentifierReasonCode
            .REFERENCE_IDENTIFIER_OMITTED,
            ASRCriticalIdentifierReasonCode
            .GENERATED_IDENTIFIER_INSERTED,
        ),
        description=(
            "Equal symbol values under different identifier "
            "types cannot be treated as a match."
        ),
    ),
)


CRITICAL_IDENTIFIER_FIDELITY_PORTFOLIO_V1 = (
    ASRCriticalIdentifierPortfolioDefinition(
        key=CRITICAL_IDENTIFIER_PORTFOLIO_KEY,
        version=CRITICAL_IDENTIFIER_PORTFOLIO_VERSION,
        cases=(
            *_TYPE_CASES,
            *_EDGE_CASES,
        ),
    )
)


def evaluate_critical_identifier_portfolio_case_observations(
    case: ASRCriticalIdentifierPortfolioCase,
) -> tuple[Observation, ...]:
    if not isinstance(
        case,
        ASRCriticalIdentifierPortfolioCase,
    ):
        raise HveeContractError(
            "critical-identifier portfolio evaluation "
            "requires a case"
        )

    evaluation = evaluate_critical_identifier_fidelity(
        reference_text=case.reference_text,
        generated_text=case.generated_text,
        profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
    )

    return (
        build_critical_identifier_fidelity_observations(
            evaluation
        )
    )


def compare_critical_identifier_portfolio_case(
    *,
    case: ASRCriticalIdentifierPortfolioCase,
    observations: tuple[Observation, ...],
) -> ASRCriticalIdentifierPortfolioCaseResult:
    if not isinstance(
        case,
        ASRCriticalIdentifierPortfolioCase,
    ):
        raise HveeContractError(
            "critical-identifier portfolio comparison "
            "requires a case"
        )

    if (
        not isinstance(observations, tuple)
        or not all(
            isinstance(observation, Observation)
            for observation in observations
        )
    ):
        raise HveeContractError(
            "critical-identifier portfolio requires "
            "Observation values"
        )

    by_key: dict[str, Observation] = {}

    for observation in observations:
        if observation.metric_key in by_key:
            raise HveeContractError(
                "critical-identifier portfolio observations "
                "contain duplicate metric keys"
            )

        by_key[observation.metric_key] = observation

    metric_by_key = {
        metric.key: metric
        for metric in CRITICAL_IDENTIFIER_METRICS
    }

    missing = tuple(
        key
        for key in metric_by_key
        if key not in by_key
    )

    if missing:
        raise HveeContractError(
            "critical-identifier portfolio observations "
            "are incomplete"
        )

    for key, metric in metric_by_key.items():
        observation = by_key[key]

        if (
            observation.metric_version != metric.version
            or observation.evaluator_key
            != CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.key
            or observation.evaluator_version
            != CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.version
            or observation.evaluation_type
            != ASR_EVALUATION_TYPE
            or observation.value_type != metric.value_type
        ):
            raise HveeContractError(
                "critical-identifier portfolio scientific "
                "identity changed without a versioned contract"
            )

    failed: list[str] = []

    def expect_value(
        key: str,
        expected: object,
        check: str,
    ) -> None:
        actual = by_key[key]

        if (
            actual.status != ObservationStatus.SUCCESS
            or actual.value != expected
        ):
            failed.append(check)

    expect_value(
        CRITICAL_IDENTIFIER_APPLICABLE_METRIC.key,
        case.expected_applicable,
        "applicable",
    )
    expect_value(
        CRITICAL_IDENTIFIER_OUTCOME_METRIC.key,
        case.expected_outcome.value,
        "outcome",
    )
    expect_value(
        CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC.key,
        case.expected_reference_count,
        "reference_count",
    )
    expect_value(
        CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC.key,
        case.expected_generated_count,
        "generated_count",
    )
    expect_value(
        CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC.key,
        case.expected_substitution_count,
        "substitution_count",
    )
    expect_value(
        CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC.key,
        case.expected_omission_count,
        "omission_count",
    )
    expect_value(
        CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC.key,
        case.expected_insertion_count,
        "insertion_count",
    )
    expect_value(
        CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC.key,
        case.expected_ordering_change_count,
        "ordering_change_count",
    )
    expect_value(
        CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC.key,
        case.expected_ambiguity_count,
        "ambiguity_count",
    )

    preserved = by_key[
        CRITICAL_IDENTIFIER_PRESERVED_METRIC.key
    ]

    if (
        preserved.status
        != case.expected_preserved_status
    ):
        failed.append("preserved_status")

    if preserved.value != case.expected_preserved:
        failed.append("preserved_value")

    findings = by_key[
        CRITICAL_IDENTIFIER_FINDINGS_METRIC.key
    ]

    if (
        findings.status != ObservationStatus.SUCCESS
        or not isinstance(findings.value, list)
    ):
        failed.append("findings")
    else:
        actual_reason_codes = tuple(
            item.get("reason_code")
            for item in findings.value
            if isinstance(item, dict)
        )

        for reason_code in case.required_reason_codes:
            if (
                reason_code.value
                not in actual_reason_codes
            ):
                failed.append(
                    f"reason:{reason_code.value}"
                )

    failed_tuple = tuple(failed)

    return ASRCriticalIdentifierPortfolioCaseResult(
        case_id=case.case_id,
        partition=case.partition,
        operation=case.operation,
        passed=not failed_tuple,
        failed_checks=failed_tuple,
    )


def run_critical_identifier_portfolio_case(
    case: ASRCriticalIdentifierPortfolioCase,
) -> ASRCriticalIdentifierPortfolioCaseResult:
    return compare_critical_identifier_portfolio_case(
        case=case,
        observations=(
            evaluate_critical_identifier_portfolio_case_observations(
                case
            )
        ),
    )


def run_critical_identifier_portfolio(
    portfolio: ASRCriticalIdentifierPortfolioDefinition,
) -> ASRCriticalIdentifierPortfolioReport:
    if not isinstance(
        portfolio,
        ASRCriticalIdentifierPortfolioDefinition,
    ):
        raise HveeContractError(
            "critical-identifier portfolio runner "
            "requires a definition"
        )

    return ASRCriticalIdentifierPortfolioReport(
        portfolio_key=portfolio.key,
        portfolio_version=portfolio.version,
        case_results=tuple(
            run_critical_identifier_portfolio_case(case)
            for case in portfolio.cases
        ),
    )
