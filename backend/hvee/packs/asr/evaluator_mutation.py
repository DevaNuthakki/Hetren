from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from hvee.core.contracts import (
    HveeContractError,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.normalized_evaluation import (
    NORMALIZED_DELETIONS_METRIC,
    NORMALIZED_INSERTIONS_METRIC,
    NORMALIZED_SUBSTITUTIONS_METRIC,
)
from hvee.packs.asr.numeric_preservation import (
    GENERATED_NUMERIC_TOKEN_COUNT_METRIC,
    MISSING_NUMERIC_TOKEN_COUNT_METRIC,
    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC,
    REFERENCE_NUMERIC_TOKEN_COUNT_METRIC,
    UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC,
)
from hvee.packs.asr.portfolio import (
    ASRPortfolioDefinition,
)
from hvee.packs.asr.portfolio_runner import (
    compare_asr_portfolio_case,
    evaluate_asr_portfolio_case_observations,
)
from hvee.packs.asr.transcript_integrity import (
    MISSING_OUTPUT_METRIC,
    UNEXPECTED_OUTPUT_METRIC,
)


class ASREvaluatorMutation(StrEnum):
    """
    Synthetic evaluator defects used to test Portfolio v1.

    These mutations do not replace or modify production evaluators.
    They deliberately corrupt evaluator observations inside the
    calibration laboratory so the portfolio's defect-detection
    capability can be measured.
    """

    WORD_SUBSTITUTION_BLIND = (
        "word_substitution_blind"
    )
    WORD_DELETION_BLIND = (
        "word_deletion_blind"
    )
    WORD_INSERTION_BLIND = (
        "word_insertion_blind"
    )

    MISSING_OUTPUT_BLIND = (
        "missing_output_blind"
    )
    UNEXPECTED_OUTPUT_BLIND = (
        "unexpected_output_blind"
    )

    NUMERIC_ORDER_INSENSITIVE = (
        "numeric_order_insensitive"
    )
    NUMERIC_MISSING_BLIND = (
        "numeric_missing_blind"
    )
    NUMERIC_UNEXPECTED_BLIND = (
        "numeric_unexpected_blind"
    )


ASR_EVALUATOR_MUTATION_SUITE_KEY = (
    "hetren.asr.evaluator-mutation-suite"
)
ASR_EVALUATOR_MUTATION_SUITE_VERSION = "1.0.0"


ASR_EVALUATOR_MUTATIONS_V1 = (
    ASREvaluatorMutation.WORD_SUBSTITUTION_BLIND,
    ASREvaluatorMutation.WORD_DELETION_BLIND,
    ASREvaluatorMutation.WORD_INSERTION_BLIND,
    ASREvaluatorMutation.MISSING_OUTPUT_BLIND,
    ASREvaluatorMutation.UNEXPECTED_OUTPUT_BLIND,
    ASREvaluatorMutation.NUMERIC_ORDER_INSENSITIVE,
    ASREvaluatorMutation.NUMERIC_MISSING_BLIND,
    ASREvaluatorMutation.NUMERIC_UNEXPECTED_BLIND,
)


@dataclass(frozen=True, slots=True)
class ASREvaluatorMutationResult:
    mutation: ASREvaluatorMutation
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
        """
        Whether at least one controlled portfolio case detected
        the synthetic evaluator defect.
        """

        return bool(self.detected_case_ids)


@dataclass(frozen=True, slots=True)
class ASREvaluatorMutationReport:
    portfolio_key: str
    portfolio_version: str
    results: tuple[
        ASREvaluatorMutationResult,
        ...,
    ]

    @property
    def total_mutants(self) -> int:
        return len(self.results)

    @property
    def killed_mutants(self) -> int:
        return sum(
            result.killed
            for result
            in self.results
        )

    @property
    def survived_mutants(self) -> int:
        return (
            self.total_mutants
            - self.killed_mutants
        )

    @property
    def mutation_score(self) -> float:
        """
        Fraction of this explicitly defined synthetic mutation set
        detected by this portfolio.

        This is not a general evaluator-accuracy score.
        """

        if self.total_mutants == 0:
            return 0.0

        return (
            self.killed_mutants
            / self.total_mutants
        )


def _successful_metric_value(
    observations: tuple[Observation, ...],
    metric_key: str,
) -> object | None:
    matches = [
        observation
        for observation
        in observations
        if observation.metric_key == metric_key
        and observation.status
        == ObservationStatus.SUCCESS
    ]

    if len(matches) > 1:
        raise HveeContractError(
            "evaluator mutation input contains "
            "duplicate metric observations"
        )

    if not matches:
        return None

    return matches[0].value


def _replace_metric_value(
    observations: tuple[Observation, ...],
    *,
    metric_key: str,
    value: int | bool,
) -> tuple[Observation, ...]:
    return tuple(
        (
            replace(
                observation,
                value=value,
            )
            if (
                observation.metric_key
                == metric_key
                and observation.status
                == ObservationStatus.SUCCESS
            )
            else observation
        )
        for observation
        in observations
    )


def apply_asr_evaluator_mutation(
    *,
    mutation: ASREvaluatorMutation,
    observations: tuple[Observation, ...],
) -> tuple[Observation, ...]:
    """
    Apply one controlled synthetic defect to evaluator output.

    Scientific identities, versions, statuses, and value types remain
    unchanged. Only the selected successful observation value may be
    corrupted.
    """

    if not isinstance(
        mutation,
        ASREvaluatorMutation,
    ):
        raise HveeContractError(
            "ASR evaluator mutation must be "
            "ASREvaluatorMutation"
        )

    if (
        not isinstance(observations, tuple)
        or not all(
            isinstance(
                observation,
                Observation,
            )
            for observation
            in observations
        )
    ):
        raise HveeContractError(
            "ASR evaluator mutation requires "
            "a tuple of Observation values"
        )

    if mutation == (
        ASREvaluatorMutation
        .WORD_SUBSTITUTION_BLIND
    ):
        return _replace_metric_value(
            observations,
            metric_key=(
                NORMALIZED_SUBSTITUTIONS_METRIC.key
            ),
            value=0,
        )

    if mutation == (
        ASREvaluatorMutation
        .WORD_DELETION_BLIND
    ):
        return _replace_metric_value(
            observations,
            metric_key=(
                NORMALIZED_DELETIONS_METRIC.key
            ),
            value=0,
        )

    if mutation == (
        ASREvaluatorMutation
        .WORD_INSERTION_BLIND
    ):
        return _replace_metric_value(
            observations,
            metric_key=(
                NORMALIZED_INSERTIONS_METRIC.key
            ),
            value=0,
        )

    if mutation == (
        ASREvaluatorMutation
        .MISSING_OUTPUT_BLIND
    ):
        return _replace_metric_value(
            observations,
            metric_key=MISSING_OUTPUT_METRIC.key,
            value=False,
        )

    if mutation == (
        ASREvaluatorMutation
        .UNEXPECTED_OUTPUT_BLIND
    ):
        return _replace_metric_value(
            observations,
            metric_key=UNEXPECTED_OUTPUT_METRIC.key,
            value=False,
        )

    if mutation == (
        ASREvaluatorMutation
        .NUMERIC_MISSING_BLIND
    ):
        return _replace_metric_value(
            observations,
            metric_key=(
                MISSING_NUMERIC_TOKEN_COUNT_METRIC.key
            ),
            value=0,
        )

    if mutation == (
        ASREvaluatorMutation
        .NUMERIC_UNEXPECTED_BLIND
    ):
        return _replace_metric_value(
            observations,
            metric_key=(
                UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.key
            ),
            value=0,
        )

    if mutation == (
        ASREvaluatorMutation
        .NUMERIC_ORDER_INSENSITIVE
    ):
        reference_count = _successful_metric_value(
            observations,
            REFERENCE_NUMERIC_TOKEN_COUNT_METRIC.key,
        )
        generated_count = _successful_metric_value(
            observations,
            GENERATED_NUMERIC_TOKEN_COUNT_METRIC.key,
        )
        missing_count = _successful_metric_value(
            observations,
            MISSING_NUMERIC_TOKEN_COUNT_METRIC.key,
        )
        unexpected_count = _successful_metric_value(
            observations,
            UNEXPECTED_NUMERIC_TOKEN_COUNT_METRIC.key,
        )

        if (
            isinstance(reference_count, int)
            and not isinstance(
                reference_count,
                bool,
            )
            and isinstance(generated_count, int)
            and not isinstance(
                generated_count,
                bool,
            )
            and isinstance(missing_count, int)
            and not isinstance(
                missing_count,
                bool,
            )
            and isinstance(unexpected_count, int)
            and not isinstance(
                unexpected_count,
                bool,
            )
            and reference_count == generated_count
            and missing_count == 0
            and unexpected_count == 0
        ):
            return _replace_metric_value(
                observations,
                metric_key=(
                    NUMERIC_TOKEN_SEQUENCE_MATCH_METRIC.key
                ),
                value=True,
            )

        return observations

    raise HveeContractError(
        "unsupported ASR evaluator mutation"
    )


def run_asr_evaluator_mutation(
    *,
    portfolio: ASRPortfolioDefinition,
    mutation: ASREvaluatorMutation,
) -> ASREvaluatorMutationResult:
    if not isinstance(
        portfolio,
        ASRPortfolioDefinition,
    ):
        raise HveeContractError(
            "ASR evaluator mutation testing requires "
            "ASRPortfolioDefinition"
        )

    changed_case_ids: list[str] = []
    detected_case_ids: list[str] = []

    for case in portfolio.cases:
        observations = (
            evaluate_asr_portfolio_case_observations(
                case
            )
        )

        baseline = compare_asr_portfolio_case(
            case=case,
            observations=observations,
        )

        if not baseline.passed:
            raise HveeContractError(
                "ASR evaluator mutation testing requires "
                "the baseline portfolio to pass first"
            )

        mutated = apply_asr_evaluator_mutation(
            mutation=mutation,
            observations=observations,
        )

        if mutated != observations:
            changed_case_ids.append(
                case.case_id
            )

        mutated_result = compare_asr_portfolio_case(
            case=case,
            observations=mutated,
        )

        if not mutated_result.passed:
            detected_case_ids.append(
                case.case_id
            )

    if not changed_case_ids:
        raise HveeContractError(
            "ASR evaluator mutation had no effect "
            "on the portfolio"
        )

    return ASREvaluatorMutationResult(
        mutation=mutation,
        changed_case_ids=tuple(
            changed_case_ids
        ),
        detected_case_ids=tuple(
            detected_case_ids
        ),
    )


def run_asr_evaluator_mutation_suite(
    portfolio: ASRPortfolioDefinition,
) -> ASREvaluatorMutationReport:
    if not isinstance(
        portfolio,
        ASRPortfolioDefinition,
    ):
        raise HveeContractError(
            "ASR evaluator mutation suite requires "
            "ASRPortfolioDefinition"
        )

    results = tuple(
        run_asr_evaluator_mutation(
            portfolio=portfolio,
            mutation=mutation,
        )
        for mutation
        in ASR_EVALUATOR_MUTATIONS_V1
    )

    return ASREvaluatorMutationReport(
        portfolio_key=portfolio.key,
        portfolio_version=portfolio.version,
        results=results,
    )
