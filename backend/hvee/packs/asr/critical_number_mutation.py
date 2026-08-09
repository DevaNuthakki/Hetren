from __future__ import annotations

from dataclasses import dataclass, replace
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
    CRITICAL_NUMBER_INSERTION_COUNT_METRIC,
    CRITICAL_NUMBER_OMISSION_COUNT_METRIC,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
    ASRCriticalNumberFidelityOutcome,
)
from hvee.packs.asr.critical_number_portfolio import (
    ASRCriticalNumberPortfolioDefinition,
    compare_critical_number_portfolio_case,
    evaluate_critical_number_portfolio_case_observations,
)


CRITICAL_NUMBER_MUTATION_SUITE_KEY = (
    "hetren.asr.critical-number-evaluator-mutation-suite.en-us"
)
CRITICAL_NUMBER_MUTATION_SUITE_VERSION = "1.0.0"


class ASRCriticalNumberEvaluatorMutation(StrEnum):
    """Synthetic defects used only by the evaluator calibration laboratory."""

    OUTCOME_FALSE_PASS = "outcome_false_pass"
    PRESERVATION_FALSE_PASS = "preservation_false_pass"
    EQUIVALENCE_FALSE_FAILURE = "equivalence_false_failure"
    SUBSTITUTION_BLIND = "substitution_blind"
    OMISSION_BLIND = "omission_blind"
    INSERTION_BLIND = "insertion_blind"
    AMBIGUITY_BLIND = "ambiguity_blind"
    NO_NUMBER_APPLICABILITY_BLIND = "no_number_applicability_blind"
    DETAILED_FINDINGS_BLIND = "detailed_findings_blind"


CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1 = (
    ASRCriticalNumberEvaluatorMutation.OUTCOME_FALSE_PASS,
    ASRCriticalNumberEvaluatorMutation.PRESERVATION_FALSE_PASS,
    ASRCriticalNumberEvaluatorMutation.EQUIVALENCE_FALSE_FAILURE,
    ASRCriticalNumberEvaluatorMutation.SUBSTITUTION_BLIND,
    ASRCriticalNumberEvaluatorMutation.OMISSION_BLIND,
    ASRCriticalNumberEvaluatorMutation.INSERTION_BLIND,
    ASRCriticalNumberEvaluatorMutation.AMBIGUITY_BLIND,
    ASRCriticalNumberEvaluatorMutation.NO_NUMBER_APPLICABILITY_BLIND,
    ASRCriticalNumberEvaluatorMutation.DETAILED_FINDINGS_BLIND,
)


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberMutationResult:
    mutation: ASRCriticalNumberEvaluatorMutation
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
class ASRCriticalNumberMutationReport:
    portfolio_key: str
    portfolio_version: str
    suite_key: str
    suite_version: str
    results: tuple[ASRCriticalNumberMutationResult, ...]

    @property
    def total_mutants(self) -> int:
        return len(self.results)

    @property
    def killed_mutants(self) -> int:
        return sum(result.killed for result in self.results)

    @property
    def survived_mutants(self) -> int:
        return self.total_mutants - self.killed_mutants

    @property
    def mutation_score(self) -> float:
        if not self.results:
            return 0.0
        return self.killed_mutants / self.total_mutants


def _replace_success_value(
    observations: tuple[Observation, ...],
    *,
    metric_key: str,
    current_value: object,
    new_value: object,
) -> tuple[Observation, ...]:
    return tuple(
        replace(observation, value=new_value)
        if (
            observation.metric_key == metric_key
            and observation.status == ObservationStatus.SUCCESS
            and observation.value == current_value
        )
        else observation
        for observation in observations
    )


def apply_critical_number_evaluator_mutation(
    *,
    mutation: ASRCriticalNumberEvaluatorMutation,
    observations: tuple[Observation, ...],
) -> tuple[Observation, ...]:
    """
    Corrupt selected successful observations without changing identity.

    Production evaluators never call this function. It exists solely to
    measure whether the portfolio detects known evaluator failure modes.
    """

    if not isinstance(mutation, ASRCriticalNumberEvaluatorMutation):
        raise HveeContractError(
            "critical-number mutation must be "
            "ASRCriticalNumberEvaluatorMutation"
        )
    if not isinstance(observations, tuple) or not all(
        isinstance(observation, Observation) for observation in observations
    ):
        raise HveeContractError(
            "critical-number mutation requires Observation values"
        )

    if mutation == ASRCriticalNumberEvaluatorMutation.OUTCOME_FALSE_PASS:
        return _replace_success_value(
            observations,
            metric_key=CRITICAL_NUMBER_OUTCOME_METRIC.key,
            current_value=ASRCriticalNumberFidelityOutcome.NOT_PRESERVED.value,
            new_value=ASRCriticalNumberFidelityOutcome.PRESERVED.value,
        )
    if mutation == ASRCriticalNumberEvaluatorMutation.PRESERVATION_FALSE_PASS:
        return _replace_success_value(
            observations,
            metric_key=CRITICAL_NUMBER_PRESERVED_METRIC.key,
            current_value=False,
            new_value=True,
        )
    if mutation == ASRCriticalNumberEvaluatorMutation.EQUIVALENCE_FALSE_FAILURE:
        return _replace_success_value(
            observations,
            metric_key=CRITICAL_NUMBER_PRESERVED_METRIC.key,
            current_value=True,
            new_value=False,
        )
    if mutation == ASRCriticalNumberEvaluatorMutation.SUBSTITUTION_BLIND:
        return _replace_success_value(
            observations,
            metric_key=CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC.key,
            current_value=1,
            new_value=0,
        )
    if mutation == ASRCriticalNumberEvaluatorMutation.OMISSION_BLIND:
        return _replace_success_value(
            observations,
            metric_key=CRITICAL_NUMBER_OMISSION_COUNT_METRIC.key,
            current_value=1,
            new_value=0,
        )
    if mutation == ASRCriticalNumberEvaluatorMutation.INSERTION_BLIND:
        return _replace_success_value(
            observations,
            metric_key=CRITICAL_NUMBER_INSERTION_COUNT_METRIC.key,
            current_value=1,
            new_value=0,
        )
    if mutation == ASRCriticalNumberEvaluatorMutation.AMBIGUITY_BLIND:
        return _replace_success_value(
            observations,
            metric_key=CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC.key,
            current_value=2,
            new_value=0,
        )
    if mutation == (
        ASRCriticalNumberEvaluatorMutation.NO_NUMBER_APPLICABILITY_BLIND
    ):
        return _replace_success_value(
            observations,
            metric_key=CRITICAL_NUMBER_APPLICABLE_METRIC.key,
            current_value=False,
            new_value=True,
        )
    if mutation == ASRCriticalNumberEvaluatorMutation.DETAILED_FINDINGS_BLIND:
        return tuple(
            replace(observation, value=[])
            if (
                observation.metric_key == CRITICAL_NUMBER_FINDINGS_METRIC.key
                and observation.status == ObservationStatus.SUCCESS
                and isinstance(observation.value, list)
                and observation.value
            )
            else observation
            for observation in observations
        )
    raise HveeContractError("unsupported critical-number evaluator mutation")


def run_critical_number_evaluator_mutation(
    *,
    portfolio: ASRCriticalNumberPortfolioDefinition,
    mutation: ASRCriticalNumberEvaluatorMutation,
) -> ASRCriticalNumberMutationResult:
    if not isinstance(portfolio, ASRCriticalNumberPortfolioDefinition):
        raise HveeContractError(
            "critical-number mutation testing requires a portfolio"
        )
    changed: list[str] = []
    detected: list[str] = []
    for case in portfolio.cases:
        observations = evaluate_critical_number_portfolio_case_observations(case)
        baseline = compare_critical_number_portfolio_case(
            case=case,
            observations=observations,
        )
        if not baseline.passed:
            raise HveeContractError(
                "critical-number mutation testing requires a passing baseline"
            )
        mutated = apply_critical_number_evaluator_mutation(
            mutation=mutation,
            observations=observations,
        )
        if mutated != observations:
            changed.append(case.case_id)
        result = compare_critical_number_portfolio_case(
            case=case,
            observations=mutated,
        )
        if not result.passed:
            detected.append(case.case_id)
    if not changed:
        raise HveeContractError(
            "critical-number evaluator mutation had no portfolio effect"
        )
    return ASRCriticalNumberMutationResult(
        mutation=mutation,
        changed_case_ids=tuple(changed),
        detected_case_ids=tuple(detected),
    )


def run_critical_number_evaluator_mutation_suite(
    portfolio: ASRCriticalNumberPortfolioDefinition,
) -> ASRCriticalNumberMutationReport:
    if not isinstance(portfolio, ASRCriticalNumberPortfolioDefinition):
        raise HveeContractError(
            "critical-number mutation suite requires a portfolio"
        )
    return ASRCriticalNumberMutationReport(
        portfolio_key=portfolio.key,
        portfolio_version=portfolio.version,
        suite_key=CRITICAL_NUMBER_MUTATION_SUITE_KEY,
        suite_version=CRITICAL_NUMBER_MUTATION_SUITE_VERSION,
        results=tuple(
            run_critical_number_evaluator_mutation(
                portfolio=portfolio,
                mutation=mutation,
            )
            for mutation in CRITICAL_NUMBER_EVALUATOR_MUTATIONS_V1
        ),
    )
