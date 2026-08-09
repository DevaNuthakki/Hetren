from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_FINDINGS_METRIC,
    CRITICAL_NUMBER_GENERATED_COUNT_METRIC,
    CRITICAL_NUMBER_INSERTION_COUNT_METRIC,
    CRITICAL_NUMBER_OMISSION_COUNT_METRIC,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_NUMBER_REFERENCE_COUNT_METRIC,
    CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
    EN_US_CRITICAL_NUMBER_PROFILE,
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberReasonCode,
    ASRCriticalNumberType,
    build_critical_number_fidelity_observations,
    evaluate_critical_number_fidelity,
)


CRITICAL_NUMBER_PORTFOLIO_KEY = (
    "hetren.asr.critical-number-fidelity-portfolio.en-us"
)
CRITICAL_NUMBER_PORTFOLIO_VERSION = "1.0.0"


class ASRCriticalNumberPortfolioPartition(StrEnum):
    """Source-visible development partitions, not a private certification set."""

    CALIBRATION = "calibration"
    REGRESSION_HOLDOUT = "regression_holdout"


class ASRCriticalNumberPortfolioOperation(StrEnum):
    EQUIVALENCE = "equivalence"
    SUBSTITUTION = "substitution"
    OMISSION = "omission"
    INSERTION = "insertion"
    NOT_APPLICABLE = "not_applicable"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPortfolioCase:
    case_id: str
    partition: ASRCriticalNumberPortfolioPartition
    operation: ASRCriticalNumberPortfolioOperation
    numeric_type: ASRCriticalNumberType
    reference_text: str
    generated_text: str
    expected_outcome: ASRCriticalNumberFidelityOutcome
    expected_applicable: bool
    expected_preserved_status: ObservationStatus
    expected_preserved: bool | None
    expected_reference_count: int
    expected_generated_count: int
    expected_substitution_count: int
    expected_omission_count: int
    expected_insertion_count: int
    expected_ambiguity_count: int
    required_reason_codes: tuple[ASRCriticalNumberReasonCode, ...]
    description: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.case_id, str)
            or not self.case_id
            or self.case_id != self.case_id.strip()
        ):
            raise HveeContractError(
                "critical-number portfolio case id must be non-empty"
            )
        if not isinstance(self.partition, ASRCriticalNumberPortfolioPartition):
            raise HveeContractError(
                "critical-number portfolio case requires a partition"
            )
        if not isinstance(self.operation, ASRCriticalNumberPortfolioOperation):
            raise HveeContractError(
                "critical-number portfolio case requires an operation"
            )
        if not isinstance(self.numeric_type, ASRCriticalNumberType):
            raise HveeContractError(
                "critical-number portfolio case requires a numeric type"
            )
        if not isinstance(self.reference_text, str) or not isinstance(
            self.generated_text,
            str,
        ):
            raise HveeContractError(
                "critical-number portfolio transcripts must be strings"
            )
        if not isinstance(
            self.expected_outcome,
            ASRCriticalNumberFidelityOutcome,
        ):
            raise HveeContractError(
                "critical-number portfolio case requires an outcome"
            )
        if not isinstance(self.expected_applicable, bool):
            raise HveeContractError(
                "critical-number portfolio applicability must be bool"
            )
        if not isinstance(
            self.expected_preserved_status,
            ObservationStatus,
        ):
            raise HveeContractError(
                "critical-number portfolio requires a preserved status"
            )
        if self.expected_preserved_status == ObservationStatus.SUCCESS:
            if not isinstance(self.expected_preserved, bool):
                raise HveeContractError(
                    "successful preserved expectation requires bool"
                )
        elif self.expected_preserved is not None:
            raise HveeContractError(
                "non-success preserved expectation cannot contain a value"
            )
        for count in (
            self.expected_reference_count,
            self.expected_generated_count,
            self.expected_substitution_count,
            self.expected_omission_count,
            self.expected_insertion_count,
            self.expected_ambiguity_count,
        ):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise HveeContractError(
                    "critical-number portfolio counts must be non-negative"
                )
        if (
            not isinstance(self.required_reason_codes, tuple)
            or not all(
                isinstance(reason, ASRCriticalNumberReasonCode)
                for reason in self.required_reason_codes
            )
        ):
            raise HveeContractError(
                "critical-number portfolio reason codes must be versioned"
            )
        if not isinstance(self.description, str) or not self.description.strip():
            raise HveeContractError(
                "critical-number portfolio case requires a description"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPortfolioDefinition:
    key: str
    version: str
    cases: tuple[ASRCriticalNumberPortfolioCase, ...]

    def __post_init__(self) -> None:
        if self.key != CRITICAL_NUMBER_PORTFOLIO_KEY or (
            self.version != CRITICAL_NUMBER_PORTFOLIO_VERSION
        ):
            raise HveeContractError(
                "critical-number portfolio identity is unsupported"
            )
        if (
            not isinstance(self.cases, tuple)
            or not self.cases
            or not all(
                isinstance(case, ASRCriticalNumberPortfolioCase)
                for case in self.cases
            )
        ):
            raise HveeContractError(
                "critical-number portfolio requires cases"
            )
        case_ids = tuple(case.case_id for case in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise HveeContractError(
                "critical-number portfolio case ids must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPortfolioCaseResult:
    case_id: str
    partition: ASRCriticalNumberPortfolioPartition
    operation: ASRCriticalNumberPortfolioOperation
    passed: bool
    failed_checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPortfolioReport:
    portfolio_key: str
    portfolio_version: str
    case_results: tuple[ASRCriticalNumberPortfolioCaseResult, ...]

    @property
    def total_cases(self) -> int:
        return len(self.case_results)

    @property
    def passed_cases(self) -> int:
        return sum(result.passed for result in self.case_results)

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    @property
    def passed(self) -> bool:
        return self.total_cases > 0 and self.failed_cases == 0


def _case(
    *,
    case_id: str,
    partition: ASRCriticalNumberPortfolioPartition,
    operation: ASRCriticalNumberPortfolioOperation,
    numeric_type: ASRCriticalNumberType,
    reference_text: str,
    generated_text: str,
    outcome: ASRCriticalNumberFidelityOutcome,
    reference_count: int,
    generated_count: int,
    substitution_count: int = 0,
    omission_count: int = 0,
    insertion_count: int = 0,
    ambiguity_count: int = 0,
    required_reason_codes: tuple[ASRCriticalNumberReasonCode, ...] = (),
    description: str,
) -> ASRCriticalNumberPortfolioCase:
    if outcome == ASRCriticalNumberFidelityOutcome.PRESERVED:
        applicable = True
        preserved_status = ObservationStatus.SUCCESS
        preserved: bool | None = True
    elif outcome == ASRCriticalNumberFidelityOutcome.NOT_PRESERVED:
        applicable = True
        preserved_status = ObservationStatus.SUCCESS
        preserved = False
    elif outcome == ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE:
        applicable = False
        preserved_status = ObservationStatus.ABSTAINED
        preserved = None
    else:
        applicable = True
        preserved_status = (
            ObservationStatus.UNSUPPORTED
            if operation == ASRCriticalNumberPortfolioOperation.UNSUPPORTED
            else ObservationStatus.ABSTAINED
        )
        preserved = None
    return ASRCriticalNumberPortfolioCase(
        case_id=case_id,
        partition=partition,
        operation=operation,
        numeric_type=numeric_type,
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
        expected_ambiguity_count=ambiguity_count,
        required_reason_codes=required_reason_codes,
        description=description,
    )


def _supported_type_cases(
    *,
    label: str,
    numeric_type: ASRCriticalNumberType,
    match_reference: str,
    match_generated: str,
    substitution_generated: str,
    omission_generated: str,
    insertion_reference: str,
    insertion_generated: str,
) -> tuple[ASRCriticalNumberPortfolioCase, ...]:
    return (
        _case(
            case_id=f"calibration.{label}.equivalence",
            partition=ASRCriticalNumberPortfolioPartition.CALIBRATION,
            operation=ASRCriticalNumberPortfolioOperation.EQUIVALENCE,
            numeric_type=numeric_type,
            reference_text=match_reference,
            generated_text=match_generated,
            outcome=ASRCriticalNumberFidelityOutcome.PRESERVED,
            reference_count=1,
            generated_count=1,
            required_reason_codes=(
                ASRCriticalNumberReasonCode.FORMAT_EQUIVALENT,
            ),
            description=(
                f"Supported {label} surface forms are semantically equivalent."
            ),
        ),
        _case(
            case_id=f"calibration.{label}.substitution",
            partition=ASRCriticalNumberPortfolioPartition.CALIBRATION,
            operation=ASRCriticalNumberPortfolioOperation.SUBSTITUTION,
            numeric_type=numeric_type,
            reference_text=match_reference,
            generated_text=substitution_generated,
            outcome=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED,
            reference_count=1,
            generated_count=1,
            substitution_count=1,
            required_reason_codes=(
                ASRCriticalNumberReasonCode.VALUE_SUBSTITUTION,
            ),
            description=f"Controlled {label} value substitution.",
        ),
        _case(
            case_id=f"holdout.{label}.omission",
            partition=ASRCriticalNumberPortfolioPartition.REGRESSION_HOLDOUT,
            operation=ASRCriticalNumberPortfolioOperation.OMISSION,
            numeric_type=numeric_type,
            reference_text=match_reference,
            generated_text=omission_generated,
            outcome=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED,
            reference_count=1,
            generated_count=0,
            omission_count=1,
            required_reason_codes=(
                ASRCriticalNumberReasonCode.REFERENCE_ENTITY_OMITTED,
            ),
            description=f"Controlled {label} omission.",
        ),
        _case(
            case_id=f"holdout.{label}.insertion",
            partition=ASRCriticalNumberPortfolioPartition.REGRESSION_HOLDOUT,
            operation=ASRCriticalNumberPortfolioOperation.INSERTION,
            numeric_type=numeric_type,
            reference_text=insertion_reference,
            generated_text=insertion_generated,
            outcome=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED,
            reference_count=0,
            generated_count=1,
            insertion_count=1,
            required_reason_codes=(
                ASRCriticalNumberReasonCode.GENERATED_ENTITY_INSERTED,
            ),
            description=f"Controlled {label} insertion.",
        ),
    )


_SUPPORTED_CASES = (
    *_supported_type_cases(
        label="cardinal-decimal",
        numeric_type=ASRCriticalNumberType.CARDINAL_DECIMAL,
        match_reference="take five tablets now",
        match_generated="take 5 tablets now",
        substitution_generated="take 50 tablets now",
        omission_generated="take tablets now",
        insertion_reference="take tablets now",
        insertion_generated="take 5 tablets now",
    ),
    *_supported_type_cases(
        label="percentage",
        numeric_type=ASRCriticalNumberType.PERCENTAGE,
        match_reference="discount twenty percent today",
        match_generated="discount 20% today",
        substitution_generated="discount 2% today",
        omission_generated="discount today",
        insertion_reference="discount today",
        insertion_generated="discount 20% today",
    ),
    *_supported_type_cases(
        label="currency",
        numeric_type=ASRCriticalNumberType.CURRENCY,
        match_reference="pay $1,200 now",
        match_generated="pay 1,200 US dollars now",
        substitution_generated="pay 12,000 US dollars now",
        omission_generated="pay now",
        insertion_reference="pay now",
        insertion_generated="pay $1,200 now",
    ),
    *_supported_type_cases(
        label="measurement",
        numeric_type=ASRCriticalNumberType.MEASUREMENT,
        match_reference="dose five milligrams now",
        match_generated="dose 5 mg now",
        substitution_generated="dose 50 mg now",
        omission_generated="dose now",
        insertion_reference="dose now",
        insertion_generated="dose 5 mg now",
    ),
    *_supported_type_cases(
        label="clock-time",
        numeric_type=ASRCriticalNumberType.CLOCK_TIME,
        match_reference="meet at nine fifteen AM tomorrow",
        match_generated="meet at 9:15 AM tomorrow",
        substitution_generated="meet at 9:50 AM tomorrow",
        omission_generated="meet tomorrow",
        insertion_reference="meet tomorrow",
        insertion_generated="meet at 9:15 AM tomorrow",
    ),
    *_supported_type_cases(
        label="calendar-date",
        numeric_type=ASRCriticalNumberType.CALENDAR_DATE,
        match_reference="renew on August 9, 2026",
        match_generated="renew on 2026-08-09",
        substitution_generated="renew on 2026-08-19",
        omission_generated="renew soon",
        insertion_reference="renew soon",
        insertion_generated="renew on August 9, 2026",
    ),
)


CRITICAL_NUMBER_FIDELITY_PORTFOLIO_V1 = (
    ASRCriticalNumberPortfolioDefinition(
        key=CRITICAL_NUMBER_PORTFOLIO_KEY,
        version=CRITICAL_NUMBER_PORTFOLIO_VERSION,
        cases=(
            *_SUPPORTED_CASES,
            _case(
                case_id="calibration.no-number.not-applicable",
                partition=ASRCriticalNumberPortfolioPartition.CALIBRATION,
                operation=ASRCriticalNumberPortfolioOperation.NOT_APPLICABLE,
                numeric_type=ASRCriticalNumberType.UNKNOWN,
                reference_text="hello world",
                generated_text="hello there",
                outcome=ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE,
                reference_count=0,
                generated_count=0,
                description=(
                    "No-number transcripts abstain rather than claiming preservation."
                ),
            ),
            _case(
                case_id="holdout.ambiguous-date.insufficient",
                partition=(
                    ASRCriticalNumberPortfolioPartition.REGRESSION_HOLDOUT
                ),
                operation=ASRCriticalNumberPortfolioOperation.AMBIGUOUS,
                numeric_type=ASRCriticalNumberType.CALENDAR_DATE,
                reference_text="date 03/04/26",
                generated_text="date 03/04/26",
                outcome=(
                    ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
                ),
                reference_count=0,
                generated_count=0,
                ambiguity_count=2,
                required_reason_codes=(
                    ASRCriticalNumberReasonCode.REFERENCE_EXPRESSION_AMBIGUOUS,
                    ASRCriticalNumberReasonCode.GENERATED_EXPRESSION_AMBIGUOUS,
                ),
                description="Ambiguous numeric date ordering never silently passes.",
            ),
            _case(
                case_id="holdout.fraction.unsupported",
                partition=(
                    ASRCriticalNumberPortfolioPartition.REGRESSION_HOLDOUT
                ),
                operation=ASRCriticalNumberPortfolioOperation.UNSUPPORTED,
                numeric_type=ASRCriticalNumberType.UNKNOWN,
                reference_text="ratio 1/2",
                generated_text="ratio 1/2",
                outcome=(
                    ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
                ),
                reference_count=0,
                generated_count=0,
                required_reason_codes=(
                    ASRCriticalNumberReasonCode.REFERENCE_EXPRESSION_UNSUPPORTED,
                    ASRCriticalNumberReasonCode.GENERATED_EXPRESSION_UNSUPPORTED,
                ),
                description="Unsupported fraction evidence never silently passes.",
            ),
            _case(
                case_id="holdout.measurement.unit-substitution",
                partition=(
                    ASRCriticalNumberPortfolioPartition.REGRESSION_HOLDOUT
                ),
                operation=ASRCriticalNumberPortfolioOperation.SUBSTITUTION,
                numeric_type=ASRCriticalNumberType.MEASUREMENT,
                reference_text="dose 5 mg now",
                generated_text="dose 5 g now",
                outcome=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED,
                reference_count=1,
                generated_count=1,
                substitution_count=1,
                required_reason_codes=(
                    ASRCriticalNumberReasonCode.UNIT_SUBSTITUTION,
                ),
                description="A measurement-unit change is a proven substitution.",
            ),
            _case(
                case_id="holdout.type-substitution",
                partition=(
                    ASRCriticalNumberPortfolioPartition.REGRESSION_HOLDOUT
                ),
                operation=ASRCriticalNumberPortfolioOperation.SUBSTITUTION,
                numeric_type=ASRCriticalNumberType.CURRENCY,
                reference_text="send 5 dollars now",
                generated_text="send 5 mg now",
                outcome=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED,
                reference_count=1,
                generated_count=1,
                substitution_count=1,
                required_reason_codes=(
                    ASRCriticalNumberReasonCode.TYPE_SUBSTITUTION,
                ),
                description="A numeric semantic-type change cannot be a match.",
            ),
        ),
    )
)


def evaluate_critical_number_portfolio_case_observations(
    case: ASRCriticalNumberPortfolioCase,
) -> tuple[Observation, ...]:
    if not isinstance(case, ASRCriticalNumberPortfolioCase):
        raise HveeContractError(
            "critical-number portfolio evaluation requires a case"
        )
    evaluation = evaluate_critical_number_fidelity(
        reference_text=case.reference_text,
        generated_text=case.generated_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )
    return build_critical_number_fidelity_observations(evaluation)


def compare_critical_number_portfolio_case(
    *,
    case: ASRCriticalNumberPortfolioCase,
    observations: tuple[Observation, ...],
) -> ASRCriticalNumberPortfolioCaseResult:
    if not isinstance(case, ASRCriticalNumberPortfolioCase):
        raise HveeContractError(
            "critical-number portfolio comparison requires a case"
        )
    if not isinstance(observations, tuple) or not all(
        isinstance(observation, Observation) for observation in observations
    ):
        raise HveeContractError(
            "critical-number portfolio requires Observation values"
        )
    by_key: dict[str, Observation] = {}
    for observation in observations:
        if observation.metric_key in by_key:
            raise HveeContractError(
                "critical-number portfolio observations contain duplicates"
            )
        by_key[observation.metric_key] = observation

    required_keys = (
        CRITICAL_NUMBER_APPLICABLE_METRIC.key,
        CRITICAL_NUMBER_PRESERVED_METRIC.key,
        CRITICAL_NUMBER_OUTCOME_METRIC.key,
        CRITICAL_NUMBER_REFERENCE_COUNT_METRIC.key,
        CRITICAL_NUMBER_GENERATED_COUNT_METRIC.key,
        CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC.key,
        CRITICAL_NUMBER_OMISSION_COUNT_METRIC.key,
        CRITICAL_NUMBER_INSERTION_COUNT_METRIC.key,
        CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC.key,
        CRITICAL_NUMBER_FINDINGS_METRIC.key,
    )
    missing = tuple(key for key in required_keys if key not in by_key)
    if missing:
        raise HveeContractError(
            "critical-number portfolio observations are incomplete"
        )

    failed: list[str] = []

    def expect_value(key: str, expected: object, check: str) -> None:
        actual = by_key[key]
        if actual.status != ObservationStatus.SUCCESS or actual.value != expected:
            failed.append(check)

    expect_value(
        CRITICAL_NUMBER_APPLICABLE_METRIC.key,
        case.expected_applicable,
        "applicable",
    )
    expect_value(
        CRITICAL_NUMBER_OUTCOME_METRIC.key,
        case.expected_outcome.value,
        "outcome",
    )
    expect_value(
        CRITICAL_NUMBER_REFERENCE_COUNT_METRIC.key,
        case.expected_reference_count,
        "reference_count",
    )
    expect_value(
        CRITICAL_NUMBER_GENERATED_COUNT_METRIC.key,
        case.expected_generated_count,
        "generated_count",
    )
    expect_value(
        CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC.key,
        case.expected_substitution_count,
        "substitution_count",
    )
    expect_value(
        CRITICAL_NUMBER_OMISSION_COUNT_METRIC.key,
        case.expected_omission_count,
        "omission_count",
    )
    expect_value(
        CRITICAL_NUMBER_INSERTION_COUNT_METRIC.key,
        case.expected_insertion_count,
        "insertion_count",
    )
    expect_value(
        CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC.key,
        case.expected_ambiguity_count,
        "ambiguity_count",
    )

    preserved = by_key[CRITICAL_NUMBER_PRESERVED_METRIC.key]
    if preserved.status != case.expected_preserved_status:
        failed.append("preserved_status")
    if preserved.value != case.expected_preserved:
        failed.append("preserved_value")

    findings = by_key[CRITICAL_NUMBER_FINDINGS_METRIC.key]
    if findings.status != ObservationStatus.SUCCESS or not isinstance(
        findings.value,
        list,
    ):
        failed.append("findings")
    else:
        actual_reason_codes = tuple(
            item.get("reason_code")
            for item in findings.value
            if isinstance(item, dict)
        )
        for reason_code in case.required_reason_codes:
            if reason_code.value not in actual_reason_codes:
                failed.append(f"reason:{reason_code.value}")

    failed_tuple = tuple(failed)
    return ASRCriticalNumberPortfolioCaseResult(
        case_id=case.case_id,
        partition=case.partition,
        operation=case.operation,
        passed=not failed_tuple,
        failed_checks=failed_tuple,
    )


def run_critical_number_portfolio_case(
    case: ASRCriticalNumberPortfolioCase,
) -> ASRCriticalNumberPortfolioCaseResult:
    return compare_critical_number_portfolio_case(
        case=case,
        observations=evaluate_critical_number_portfolio_case_observations(case),
    )


def run_critical_number_portfolio(
    portfolio: ASRCriticalNumberPortfolioDefinition,
) -> ASRCriticalNumberPortfolioReport:
    if not isinstance(portfolio, ASRCriticalNumberPortfolioDefinition):
        raise HveeContractError(
            "critical-number portfolio runner requires a definition"
        )
    return ASRCriticalNumberPortfolioReport(
        portfolio_key=portfolio.key,
        portfolio_version=portfolio.version,
        case_results=tuple(
            run_critical_number_portfolio_case(case)
            for case in portfolio.cases
        ),
    )
