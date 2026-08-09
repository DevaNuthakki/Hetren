from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.normalized_evaluation import (
    build_normalized_error_observations,
    evaluate_normalized_transcript_pair,
)
from hvee.packs.asr.numeric_preservation import (
    build_numeric_preservation_observations,
    evaluate_numeric_preservation,
)
from hvee.packs.asr.portfolio import (
    ASRPortfolioCase,
    ASRPortfolioDefinition,
    ASRPortfolioExpectedObservation,
    ASRPortfolioMutation,
)
from hvee.packs.asr.transcript_integrity import (
    build_transcript_integrity_observations,
    evaluate_transcript_integrity,
)


ObservationIdentity = tuple[
    str,
    str,
    str,
    str,
]


@dataclass(frozen=True, slots=True)
class ASRPortfolioExpectationResult:
    expectation: ASRPortfolioExpectedObservation
    actual_status: ObservationStatus
    actual_value: int | float | bool | None
    matched: bool


@dataclass(frozen=True, slots=True)
class ASRPortfolioCaseResult:
    case_id: str
    mutation: ASRPortfolioMutation
    passed: bool
    expectation_results: tuple[
        ASRPortfolioExpectationResult,
        ...,
    ]

    @property
    def total_expectations(self) -> int:
        return len(self.expectation_results)

    @property
    def matched_expectations(self) -> int:
        return sum(
            result.matched
            for result
            in self.expectation_results
        )

    @property
    def mismatched_expectations(self) -> int:
        return (
            self.total_expectations
            - self.matched_expectations
        )


@dataclass(frozen=True, slots=True)
class ASRPortfolioReport:
    portfolio_key: str
    portfolio_version: str
    case_results: tuple[
        ASRPortfolioCaseResult,
        ...,
    ]

    @property
    def total_cases(self) -> int:
        return len(self.case_results)

    @property
    def passed_cases(self) -> int:
        return sum(
            result.passed
            for result
            in self.case_results
        )

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    @property
    def total_expectations(self) -> int:
        return sum(
            result.total_expectations
            for result
            in self.case_results
        )

    @property
    def matched_expectations(self) -> int:
        return sum(
            result.matched_expectations
            for result
            in self.case_results
        )

    @property
    def mismatched_expectations(self) -> int:
        return (
            self.total_expectations
            - self.matched_expectations
        )

    @property
    def passed(self) -> bool:
        return (
            self.total_cases > 0
            and self.failed_cases == 0
        )


def _observation_identity(
    observation: Observation,
) -> ObservationIdentity:
    return (
        observation.metric_key,
        observation.metric_version,
        observation.evaluator_key,
        observation.evaluator_version,
    )


def evaluate_asr_portfolio_case_observations(
    case: ASRPortfolioCase,
) -> tuple[Observation, ...]:
    """
    Execute the current pure Hetren ASR evaluators for one case.

    Portfolio v1 evaluates only transcript-grounded signals:
    normalized text errors, transcript integrity, and strict
    digit-form numeric preservation.

    This function does not make acoustic, hallucination, accent,
    noise, or other audio-grounded claims.
    """

    if not isinstance(
        case,
        ASRPortfolioCase,
    ):
        raise HveeContractError(
            "ASR portfolio evaluation requires "
            "ASRPortfolioCase"
        )

    normalized_evaluation = (
        evaluate_normalized_transcript_pair(
            reference_text=case.reference_text,
            generated_text=case.generated_text,
        )
    )

    transcript_integrity_evaluation = (
        evaluate_transcript_integrity(
            normalized_evaluation
        )
    )

    numeric_preservation_evaluation = (
        evaluate_numeric_preservation(
            reference_text=case.reference_text,
            generated_text=case.generated_text,
        )
    )

    observations = (
        *build_normalized_error_observations(
            normalized_evaluation
        ),
        *build_transcript_integrity_observations(
            transcript_integrity_evaluation
        ),
        *build_numeric_preservation_observations(
            numeric_preservation_evaluation
        ),
    )

    identities = tuple(
        _observation_identity(observation)
        for observation
        in observations
    )

    if len(identities) != len(
        set(identities)
    ):
        raise HveeContractError(
            "ASR portfolio evaluator output contains "
            "duplicate scientific identities"
        )

    return observations


def compare_asr_portfolio_case(
    *,
    case: ASRPortfolioCase,
    observations: tuple[Observation, ...],
) -> ASRPortfolioCaseResult:
    """
    Compare actual evaluator observations with pinned expectations.

    Missing or duplicate scientific identities are contract failures.
    A non-success observation is a valid evaluator outcome but does
    not satisfy a Portfolio v1 expected-value assertion.

    Extra observations are allowed. Expectations define exactly which
    evaluator signals the case is asserting.
    """

    if not isinstance(
        case,
        ASRPortfolioCase,
    ):
        raise HveeContractError(
            "ASR portfolio comparison requires "
            "ASRPortfolioCase"
        )

    if not isinstance(
        observations,
        tuple,
    ) or not all(
        isinstance(
            observation,
            Observation,
        )
        for observation
        in observations
    ):
        raise HveeContractError(
            "ASR portfolio observations must be "
            "a tuple of Observation values"
        )

    by_identity: dict[
        ObservationIdentity,
        Observation,
    ] = {}

    for observation in observations:
        identity = _observation_identity(
            observation
        )

        if identity in by_identity:
            raise HveeContractError(
                "ASR portfolio observations contain "
                "duplicate scientific identity "
                f"{identity!r}"
            )

        by_identity[identity] = observation

    results: list[
        ASRPortfolioExpectationResult
    ] = []

    for expectation in case.expectations:
        actual = by_identity.get(
            expectation.identity
        )

        if actual is None:
            raise HveeContractError(
                "ASR portfolio expected scientific "
                "identity was not produced: "
                f"{expectation.identity!r}"
            )

        if (
            actual.value_type
            != expectation.value_type
        ):
            raise HveeContractError(
                "ASR portfolio scientific identity "
                "changed value type without changing "
                "its version"
            )

        matched = (
            actual.status
            == ObservationStatus.SUCCESS
            and actual.value
            == expectation.expected_value
        )

        actual_value: (
            int | float | bool | None
        )

        if actual.status == ObservationStatus.SUCCESS:
            if actual.value_type == MetricValueType.BOOLEAN:
                actual_value = bool(actual.value)
            elif actual.value_type == MetricValueType.INTEGER:
                actual_value = int(actual.value)
            elif actual.value_type == MetricValueType.NUMBER:
                actual_value = float(actual.value)
            else:
                raise HveeContractError(
                    "Portfolio v1 received an unsupported "
                    "successful observation value type"
                )
        else:
            actual_value = None

        results.append(
            ASRPortfolioExpectationResult(
                expectation=expectation,
                actual_status=actual.status,
                actual_value=actual_value,
                matched=matched,
            )
        )

    result_tuple = tuple(results)

    return ASRPortfolioCaseResult(
        case_id=case.case_id,
        mutation=case.mutation,
        passed=all(
            result.matched
            for result
            in result_tuple
        ),
        expectation_results=result_tuple,
    )


def run_asr_portfolio_case(
    case: ASRPortfolioCase,
) -> ASRPortfolioCaseResult:
    observations = (
        evaluate_asr_portfolio_case_observations(
            case
        )
    )

    return compare_asr_portfolio_case(
        case=case,
        observations=observations,
    )


def run_asr_portfolio(
    portfolio: ASRPortfolioDefinition,
) -> ASRPortfolioReport:
    if not isinstance(
        portfolio,
        ASRPortfolioDefinition,
    ):
        raise HveeContractError(
            "ASR portfolio runner requires "
            "ASRPortfolioDefinition"
        )

    results = tuple(
        run_asr_portfolio_case(case)
        for case
        in portfolio.cases
    )

    return ASRPortfolioReport(
        portfolio_key=portfolio.key,
        portfolio_version=portfolio.version,
        case_results=results,
    )
