"""Controlled mutation testing for Critical Identifier Fidelity v1.

These mutations exist only inside the evaluator calibration laboratory.
They do not modify the production evaluator and do not grant certification,
qualification, runtime eligibility, or release authority.
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
from hvee.packs.asr.critical_identifier_fidelity import (
    CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_IDENTIFIER_APPLICABLE_METRIC,
    CRITICAL_IDENTIFIER_FINDINGS_METRIC,
    CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_OUTCOME_METRIC,
    CRITICAL_IDENTIFIER_PRESERVED_METRIC,
    CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC,
    ASRCriticalIdentifierFidelityOutcome,
)
from hvee.packs.asr.critical_identifier_portfolio import (
    ASRCriticalIdentifierPortfolioDefinition,
    compare_critical_identifier_portfolio_case,
    evaluate_critical_identifier_portfolio_case_observations,
)


CRITICAL_IDENTIFIER_MUTATION_SUITE_KEY = (
    "hetren.asr.critical-identifier-evaluator-mutation-suite.en-us"
)
CRITICAL_IDENTIFIER_MUTATION_SUITE_VERSION = "1.0.0"


class ASRCriticalIdentifierEvaluatorMutation(StrEnum):
    """Synthetic evaluator defects used only for controlled calibration."""

    OUTCOME_FALSE_PASS = "outcome_false_pass"
    PRESERVATION_FALSE_PASS = "preservation_false_pass"
    EQUIVALENCE_FALSE_FAILURE = "equivalence_false_failure"
    SUBSTITUTION_BLIND = "substitution_blind"
    OMISSION_BLIND = "omission_blind"
    INSERTION_BLIND = "insertion_blind"
    ORDERING_CHANGE_BLIND = "ordering_change_blind"
    AMBIGUITY_BLIND = "ambiguity_blind"
    NO_IDENTIFIER_APPLICABILITY_BLIND = (
        "no_identifier_applicability_blind"
    )
    DETAILED_FINDINGS_BLIND = "detailed_findings_blind"


CRITICAL_IDENTIFIER_EVALUATOR_MUTATIONS_V1 = (
    ASRCriticalIdentifierEvaluatorMutation.OUTCOME_FALSE_PASS,
    ASRCriticalIdentifierEvaluatorMutation.PRESERVATION_FALSE_PASS,
    ASRCriticalIdentifierEvaluatorMutation.EQUIVALENCE_FALSE_FAILURE,
    ASRCriticalIdentifierEvaluatorMutation.SUBSTITUTION_BLIND,
    ASRCriticalIdentifierEvaluatorMutation.OMISSION_BLIND,
    ASRCriticalIdentifierEvaluatorMutation.INSERTION_BLIND,
    ASRCriticalIdentifierEvaluatorMutation.ORDERING_CHANGE_BLIND,
    ASRCriticalIdentifierEvaluatorMutation.AMBIGUITY_BLIND,
    (
        ASRCriticalIdentifierEvaluatorMutation
        .NO_IDENTIFIER_APPLICABILITY_BLIND
    ),
    ASRCriticalIdentifierEvaluatorMutation.DETAILED_FINDINGS_BLIND,
)


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierMutationResult:
    mutation: ASRCriticalIdentifierEvaluatorMutation
    changed_case_ids: tuple[str, ...]
    detected_case_ids: tuple[str, ...]

    @property
    def changed_cases(self) -> int:
        return len(self.changed_case_ids)

    @property
    def detected_cases(self) -> int:
        return len(self.detected_case_ids)

    @property
    def killed(self) -> bool:
        return bool(self.detected_case_ids)


@dataclass(frozen=True, slots=True)
class ASRCriticalIdentifierMutationReport:
    portfolio_key: str
    portfolio_version: str
    suite_key: str
    suite_version: str
    results: tuple[
        ASRCriticalIdentifierMutationResult,
        ...,
    ]

    @property
    def total_mutants(self) -> int:
        return len(self.results)

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


def apply_critical_identifier_evaluator_mutation(
    *,
    mutation: ASRCriticalIdentifierEvaluatorMutation,
    observations: tuple[Observation, ...],
) -> tuple[Observation, ...]:
    """
    Corrupt selected successful observation values without changing identity.

    The real evaluator is never modified. Mutation testing operates only on
    its already-produced observations.
    """

    if not isinstance(
        mutation,
        ASRCriticalIdentifierEvaluatorMutation,
    ):
        raise HveeContractError(
            "critical-identifier mutation must be "
            "ASRCriticalIdentifierEvaluatorMutation"
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
            "critical-identifier mutation requires "
            "Observation values"
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .OUTCOME_FALSE_PASS
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_OUTCOME_METRIC.key
            ),
            current_value=(
                ASRCriticalIdentifierFidelityOutcome
                .NOT_PRESERVED
                .value
            ),
            new_value=(
                ASRCriticalIdentifierFidelityOutcome
                .PRESERVED
                .value
            ),
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .PRESERVATION_FALSE_PASS
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_PRESERVED_METRIC.key
            ),
            current_value=False,
            new_value=True,
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .EQUIVALENCE_FALSE_FAILURE
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_PRESERVED_METRIC.key
            ),
            current_value=True,
            new_value=False,
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .SUBSTITUTION_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC
                .key
            ),
            current_value=1,
            new_value=0,
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .OMISSION_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC
                .key
            ),
            current_value=1,
            new_value=0,
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .INSERTION_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC
                .key
            ),
            current_value=1,
            new_value=0,
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .ORDERING_CHANGE_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC
                .key
            ),
            current_value=1,
            new_value=0,
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .AMBIGUITY_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC
                .key
            ),
            current_value=2,
            new_value=0,
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
        .NO_IDENTIFIER_APPLICABILITY_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=(
                CRITICAL_IDENTIFIER_APPLICABLE_METRIC.key
            ),
            current_value=False,
            new_value=True,
        )

    if mutation == (
        ASRCriticalIdentifierEvaluatorMutation
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
                    == CRITICAL_IDENTIFIER_FINDINGS_METRIC.key
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
        "unsupported critical-identifier evaluator mutation"
    )


def run_critical_identifier_evaluator_mutation(
    *,
    portfolio: ASRCriticalIdentifierPortfolioDefinition,
    mutation: ASRCriticalIdentifierEvaluatorMutation,
) -> ASRCriticalIdentifierMutationResult:
    if not isinstance(
        portfolio,
        ASRCriticalIdentifierPortfolioDefinition,
    ):
        raise HveeContractError(
            "critical-identifier mutation testing "
            "requires a portfolio"
        )

    laboratory_result = run_semantic_evaluator_mutation(
        cases=portfolio.cases,
        mutation=mutation,
        evaluate_case=(
            evaluate_critical_identifier_portfolio_case_observations
        ),
        compare_case=compare_critical_identifier_portfolio_case,
        apply_mutation=apply_critical_identifier_evaluator_mutation,
    )

    return ASRCriticalIdentifierMutationResult(
        mutation=laboratory_result.mutation,
        changed_case_ids=laboratory_result.changed_case_ids,
        detected_case_ids=laboratory_result.detected_case_ids,
    )


def run_critical_identifier_evaluator_mutation_suite(
    portfolio: ASRCriticalIdentifierPortfolioDefinition,
) -> ASRCriticalIdentifierMutationReport:
    if not isinstance(
        portfolio,
        ASRCriticalIdentifierPortfolioDefinition,
    ):
        raise HveeContractError(
            "critical-identifier mutation suite "
            "requires a portfolio"
        )

    laboratory_report = (
        run_semantic_evaluator_mutation_suite(
            portfolio_key=portfolio.key,
            portfolio_version=portfolio.version,
            suite_key=CRITICAL_IDENTIFIER_MUTATION_SUITE_KEY,
            suite_version=(
                CRITICAL_IDENTIFIER_MUTATION_SUITE_VERSION
            ),
            cases=portfolio.cases,
            mutations=(
                CRITICAL_IDENTIFIER_EVALUATOR_MUTATIONS_V1
            ),
            evaluate_case=(
                evaluate_critical_identifier_portfolio_case_observations
            ),
            compare_case=(
                compare_critical_identifier_portfolio_case
            ),
            apply_mutation=(
                apply_critical_identifier_evaluator_mutation
            ),
        )
    )

    return ASRCriticalIdentifierMutationReport(
        portfolio_key=laboratory_report.portfolio_key,
        portfolio_version=laboratory_report.portfolio_version,
        suite_key=laboratory_report.suite_key,
        suite_version=laboratory_report.suite_version,
        results=tuple(
            ASRCriticalIdentifierMutationResult(
                mutation=result.mutation,
                changed_case_ids=result.changed_case_ids,
                detected_case_ids=result.detected_case_ids,
            )
            for result in laboratory_report.results
        ),
    )
