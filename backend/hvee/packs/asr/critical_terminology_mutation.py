"""Controlled mutation testing for Critical Terminology Fidelity v1.

These synthetic defects exist only inside the evaluator development
laboratory. They mutate already-produced observation values; the production
fidelity evaluator itself is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    Observation,
    ObservationStatus,
)
from hvee.laboratory.semantic.mutation import (
    replace_success_observation_value,
    run_semantic_evaluator_mutation,
    run_semantic_evaluator_mutation_suite,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_APPLICABLE_METRIC,
    CRITICAL_TERMINOLOGY_FINDINGS_METRIC,
    CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_OUTCOME_METRIC,
    CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    ASRCriticalTerminologyFidelityOutcome,
)
from hvee.packs.asr.critical_terminology_portfolio import (
    CRITICAL_TERMINOLOGY_PORTFOLIO_VOCABULARY_SHA256,
    ASRCriticalTerminologyPortfolioDefinition,
    compare_critical_terminology_portfolio_case,
    evaluate_critical_terminology_portfolio_case_observations,
)


CRITICAL_TERMINOLOGY_MUTATION_SUITE_KEY = (
    "hetren.asr.critical-terminology-evaluator-"
    "mutation-suite.en-us"
)
CRITICAL_TERMINOLOGY_MUTATION_SUITE_VERSION = "1.0.0"


class ASRCriticalTerminologyEvaluatorMutation(StrEnum):
    """Synthetic terminology-evaluator defects used for calibration."""

    OUTCOME_FALSE_PASS = "outcome_false_pass"
    PRESERVATION_FALSE_PASS = "preservation_false_pass"
    EQUIVALENCE_FALSE_FAILURE = "equivalence_false_failure"
    SUBSTITUTION_BLIND = "substitution_blind"
    OMISSION_BLIND = "omission_blind"
    INSERTION_BLIND = "insertion_blind"
    ORDERING_CHANGE_BLIND = "ordering_change_blind"
    NO_TERMINOLOGY_APPLICABILITY_BLIND = (
        "no_terminology_applicability_blind"
    )
    VOCABULARY_IDENTITY_BLIND = "vocabulary_identity_blind"
    DETAILED_FINDINGS_BLIND = "detailed_findings_blind"


CRITICAL_TERMINOLOGY_EVALUATOR_MUTATIONS_V1 = (
    ASRCriticalTerminologyEvaluatorMutation.OUTCOME_FALSE_PASS,
    (
        ASRCriticalTerminologyEvaluatorMutation
        .PRESERVATION_FALSE_PASS
    ),
    (
        ASRCriticalTerminologyEvaluatorMutation
        .EQUIVALENCE_FALSE_FAILURE
    ),
    ASRCriticalTerminologyEvaluatorMutation.SUBSTITUTION_BLIND,
    ASRCriticalTerminologyEvaluatorMutation.OMISSION_BLIND,
    ASRCriticalTerminologyEvaluatorMutation.INSERTION_BLIND,
    (
        ASRCriticalTerminologyEvaluatorMutation
        .ORDERING_CHANGE_BLIND
    ),
    (
        ASRCriticalTerminologyEvaluatorMutation
        .NO_TERMINOLOGY_APPLICABILITY_BLIND
    ),
    (
        ASRCriticalTerminologyEvaluatorMutation
        .VOCABULARY_IDENTITY_BLIND
    ),
    (
        ASRCriticalTerminologyEvaluatorMutation
        .DETAILED_FINDINGS_BLIND
    ),
)


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyMutationResult:
    mutation: ASRCriticalTerminologyEvaluatorMutation
    changed_case_ids: tuple[str, ...]
    detected_case_ids: tuple[str, ...]

    @property
    def changed_cases(self) -> int:
        return len(
            self.changed_case_ids
        )

    @property
    def detected_cases(self) -> int:
        return len(
            self.detected_case_ids
        )

    @property
    def killed(self) -> bool:
        return bool(
            self.detected_case_ids
        )


@dataclass(frozen=True, slots=True)
class ASRCriticalTerminologyMutationReport:
    portfolio_key: str
    portfolio_version: str
    suite_key: str
    suite_version: str
    results: tuple[
        ASRCriticalTerminologyMutationResult,
        ...,
    ]

    @property
    def total_mutants(self) -> int:
        return len(
            self.results
        )

    @property
    def killed_mutants(self) -> int:
        return sum(
            result.killed
            for result in self.results
        )

    @property
    def survived_mutants(self) -> int:
        return (
            self.total_mutants
            - self.killed_mutants
        )

    @property
    def mutation_score(self) -> float:
        if not self.results:
            return 0.0

        return (
            self.killed_mutants
            / self.total_mutants
        )


def _replace_success_value(
    observations: tuple[Observation, ...],
    *,
    metric_key: str,
    current_value: object,
    new_value: object,
) -> tuple[Observation, ...]:
    return replace_success_observation_value(
        observations,
        metric_key=metric_key,
        current_value=current_value,
        new_value=new_value,
    )


def apply_critical_terminology_evaluator_mutation(
    *,
    mutation: ASRCriticalTerminologyEvaluatorMutation,
    observations: tuple[Observation, ...],
) -> tuple[Observation, ...]:
    """Corrupt selected observation values without changing their contract."""

    if not isinstance(
        mutation,
        ASRCriticalTerminologyEvaluatorMutation,
    ):
        raise HveeContractError(
            "critical-terminology mutation must be "
            "ASRCriticalTerminologyEvaluatorMutation"
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
            "critical-terminology mutation requires "
            "Observation values"
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .OUTCOME_FALSE_PASS
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_OUTCOME_METRIC.key
            ),
            current_value=(
                ASRCriticalTerminologyFidelityOutcome
                .NOT_PRESERVED
                .value
            ),
            new_value=(
                ASRCriticalTerminologyFidelityOutcome
                .PRESERVED
                .value
            ),
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .PRESERVATION_FALSE_PASS
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_PRESERVED_METRIC.key
            ),
            current_value=False,
            new_value=True,
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .EQUIVALENCE_FALSE_FAILURE
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_PRESERVED_METRIC.key
            ),
            current_value=True,
            new_value=False,
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .SUBSTITUTION_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC
                .key
            ),
            current_value=1,
            new_value=0,
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .OMISSION_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC.key
            ),
            current_value=1,
            new_value=0,
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .INSERTION_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC.key
            ),
            current_value=1,
            new_value=0,
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .ORDERING_CHANGE_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC
                .key
            ),
            current_value=1,
            new_value=0,
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .NO_TERMINOLOGY_APPLICABILITY_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_APPLICABLE_METRIC.key
            ),
            current_value=False,
            new_value=True,
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .VOCABULARY_IDENTITY_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC
                .key
            ),
            current_value=(
                CRITICAL_TERMINOLOGY_PORTFOLIO_VOCABULARY_SHA256
            ),
            new_value=("0" * 64),
        )

    if mutation == (
        ASRCriticalTerminologyEvaluatorMutation
        .DETAILED_FINDINGS_BLIND
    ):
        return tuple(
            (
                replace(
                    observation,
                    value=[],
                )
                if (
                    observation.metric_key
                    == CRITICAL_TERMINOLOGY_FINDINGS_METRIC.key
                    and observation.status
                    == ObservationStatus.SUCCESS
                    and isinstance(
                        observation.value,
                        list,
                    )
                    and observation.value
                )
                else observation
            )
            for observation in observations
        )

    raise HveeContractError(
        "unsupported critical-terminology evaluator mutation"
    )


def run_critical_terminology_evaluator_mutation(
    *,
    portfolio: ASRCriticalTerminologyPortfolioDefinition,
    mutation: ASRCriticalTerminologyEvaluatorMutation,
) -> ASRCriticalTerminologyMutationResult:
    if not isinstance(
        portfolio,
        ASRCriticalTerminologyPortfolioDefinition,
    ):
        raise HveeContractError(
            "critical-terminology mutation testing "
            "requires a portfolio"
        )

    laboratory_result = run_semantic_evaluator_mutation(
        cases=portfolio.cases,
        mutation=mutation,
        evaluate_case=lambda case: (
            evaluate_critical_terminology_portfolio_case_observations(
                case,
                profile=portfolio.profile,
            )
        ),
        compare_case=lambda *, case, observations: (
            compare_critical_terminology_portfolio_case(
                case=case,
                observations=observations,
                profile=portfolio.profile,
            )
        ),
        apply_mutation=(
            apply_critical_terminology_evaluator_mutation
        ),
    )

    return ASRCriticalTerminologyMutationResult(
        mutation=laboratory_result.mutation,
        changed_case_ids=(
            laboratory_result.changed_case_ids
        ),
        detected_case_ids=(
            laboratory_result.detected_case_ids
        ),
    )


def run_critical_terminology_evaluator_mutation_suite(
    portfolio: ASRCriticalTerminologyPortfolioDefinition,
) -> ASRCriticalTerminologyMutationReport:
    if not isinstance(
        portfolio,
        ASRCriticalTerminologyPortfolioDefinition,
    ):
        raise HveeContractError(
            "critical-terminology mutation suite "
            "requires a portfolio"
        )

    laboratory_report = (
        run_semantic_evaluator_mutation_suite(
            portfolio_key=portfolio.key,
            portfolio_version=portfolio.version,
            suite_key=CRITICAL_TERMINOLOGY_MUTATION_SUITE_KEY,
            suite_version=(
                CRITICAL_TERMINOLOGY_MUTATION_SUITE_VERSION
            ),
            cases=portfolio.cases,
            mutations=(
                CRITICAL_TERMINOLOGY_EVALUATOR_MUTATIONS_V1
            ),
            evaluate_case=lambda case: (
                evaluate_critical_terminology_portfolio_case_observations(
                    case,
                    profile=portfolio.profile,
                )
            ),
            compare_case=lambda *, case, observations: (
                compare_critical_terminology_portfolio_case(
                    case=case,
                    observations=observations,
                    profile=portfolio.profile,
                )
            ),
            apply_mutation=(
                apply_critical_terminology_evaluator_mutation
            ),
        )
    )

    return ASRCriticalTerminologyMutationReport(
        portfolio_key=(
            laboratory_report.portfolio_key
        ),
        portfolio_version=(
            laboratory_report.portfolio_version
        ),
        suite_key=(
            laboratory_report.suite_key
        ),
        suite_version=(
            laboratory_report.suite_version
        ),
        results=tuple(
            ASRCriticalTerminologyMutationResult(
                mutation=result.mutation,
                changed_case_ids=(
                    result.changed_case_ids
                ),
                detected_case_ids=(
                    result.detected_case_ids
                ),
            )
            for result in (
                laboratory_report.results
            )
        ),
    )
