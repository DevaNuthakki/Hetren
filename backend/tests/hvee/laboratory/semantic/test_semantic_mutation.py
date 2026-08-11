from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.laboratory.semantic.mutation import (
    SemanticMutationResult,
    replace_success_observation_value,
    run_semantic_evaluator_mutation,
    run_semantic_evaluator_mutation_suite,
)


METRIC_KEY = "synthetic.semantic.preserved"


@dataclass(frozen=True, slots=True)
class SyntheticCase:
    case_id: str
    expected: bool


@dataclass(frozen=True, slots=True)
class SyntheticResult:
    case_id: str
    passed: bool


class SyntheticMutation(StrEnum):
    FALSE_TO_TRUE = "false_to_true"
    TRUE_TO_FALSE = "true_to_false"
    NO_EFFECT = "no_effect"


def _observation(
    value: bool,
) -> Observation:
    return Observation(
        metric_key=METRIC_KEY,
        metric_version="1.0.0",
        evaluator_key="synthetic.semantic.evaluator",
        evaluator_version="1.0.0",
        evaluation_type="synthetic",
        status=ObservationStatus.SUCCESS,
        value_type=MetricValueType.BOOLEAN,
        value=value,
    )


def _evaluate_case(
    case: SyntheticCase,
) -> tuple[Observation, ...]:
    return (
        _observation(case.expected),
    )


def _compare_case(
    *,
    case: SyntheticCase,
    observations: tuple[Observation, ...],
) -> SyntheticResult:
    return SyntheticResult(
        case_id=case.case_id,
        passed=(
            len(observations) == 1
            and observations[0].value
            == case.expected
        ),
    )


def _apply_mutation(
    *,
    mutation: SyntheticMutation,
    observations: tuple[Observation, ...],
) -> tuple[Observation, ...]:
    if mutation == SyntheticMutation.FALSE_TO_TRUE:
        return replace_success_observation_value(
            observations,
            metric_key=METRIC_KEY,
            current_value=False,
            new_value=True,
        )

    if mutation == SyntheticMutation.TRUE_TO_FALSE:
        return replace_success_observation_value(
            observations,
            metric_key=METRIC_KEY,
            current_value=True,
            new_value=False,
        )

    if mutation == SyntheticMutation.NO_EFFECT:
        return observations

    raise AssertionError("unexpected synthetic mutation")


CASES = (
    SyntheticCase(
        case_id="case.false",
        expected=False,
    ),
    SyntheticCase(
        case_id="case.true",
        expected=True,
    ),
)


def test_semantic_mutation_tracks_changed_and_detected_cases():
    result = run_semantic_evaluator_mutation(
        cases=CASES,
        mutation=SyntheticMutation.FALSE_TO_TRUE,
        evaluate_case=_evaluate_case,
        compare_case=_compare_case,
        apply_mutation=_apply_mutation,
    )

    assert result.changed_case_ids == (
        "case.false",
    )
    assert result.detected_case_ids == (
        "case.false",
    )
    assert result.changed_cases == 1
    assert result.detected_cases == 1
    assert result.killed is True


def test_semantic_mutation_suite_reports_complete_detection():
    report = run_semantic_evaluator_mutation_suite(
        portfolio_key="synthetic.semantic.portfolio",
        portfolio_version="1.0.0",
        suite_key="synthetic.semantic.mutation-suite",
        suite_version="1.0.0",
        cases=CASES,
        mutations=(
            SyntheticMutation.FALSE_TO_TRUE,
            SyntheticMutation.TRUE_TO_FALSE,
        ),
        evaluate_case=_evaluate_case,
        compare_case=_compare_case,
        apply_mutation=_apply_mutation,
    )

    assert report.total_mutants == 2
    assert report.killed_mutants == 2
    assert report.survived_mutants == 0
    assert report.mutation_score == 1.0


def test_semantic_mutation_requires_passing_baseline():
    forged_case = (
        SyntheticCase(
            case_id="case.false",
            expected=False,
        ),
    )

    def failing_compare(
        *,
        case: SyntheticCase,
        observations: tuple[Observation, ...],
    ) -> SyntheticResult:
        return SyntheticResult(
            case_id=case.case_id,
            passed=False,
        )

    with pytest.raises(
        HveeContractError,
        match="requires a passing baseline",
    ):
        run_semantic_evaluator_mutation(
            cases=forged_case,
            mutation=SyntheticMutation.FALSE_TO_TRUE,
            evaluate_case=_evaluate_case,
            compare_case=failing_compare,
            apply_mutation=_apply_mutation,
        )


def test_semantic_mutation_requires_a_portfolio_effect():
    with pytest.raises(
        HveeContractError,
        match="had no portfolio effect",
    ):
        run_semantic_evaluator_mutation(
            cases=CASES,
            mutation=SyntheticMutation.NO_EFFECT,
            evaluate_case=_evaluate_case,
            compare_case=_compare_case,
            apply_mutation=_apply_mutation,
        )


def test_semantic_mutation_rejects_identity_drift():
    def identity_mutation(
        *,
        mutation: SyntheticMutation,
        observations: tuple[Observation, ...],
    ) -> tuple[Observation, ...]:
        return (
            replace(
                observations[0],
                metric_version="2.0.0",
            ),
        )

    with pytest.raises(
        HveeContractError,
        match="changed observation identity",
    ):
        run_semantic_evaluator_mutation(
            cases=(
                SyntheticCase(
                    case_id="case.false",
                    expected=False,
                ),
            ),
            mutation=SyntheticMutation.FALSE_TO_TRUE,
            evaluate_case=_evaluate_case,
            compare_case=_compare_case,
            apply_mutation=identity_mutation,
        )


def test_semantic_mutation_rejects_status_or_type_drift():
    def type_mutation(
        *,
        mutation: SyntheticMutation,
        observations: tuple[Observation, ...],
    ) -> tuple[Observation, ...]:
        return (
            replace(
                observations[0],
                value_type=MetricValueType.STRING,
                value="false",
            ),
        )

    with pytest.raises(
        HveeContractError,
        match="changed observation identity",
    ):
        run_semantic_evaluator_mutation(
            cases=(
                SyntheticCase(
                    case_id="case.false",
                    expected=False,
                ),
            ),
            mutation=SyntheticMutation.FALSE_TO_TRUE,
            evaluate_case=_evaluate_case,
            compare_case=_compare_case,
            apply_mutation=type_mutation,
        )


def test_replace_success_observation_value_preserves_contract():
    original = (
        _observation(False),
    )

    changed = replace_success_observation_value(
        original,
        metric_key=METRIC_KEY,
        current_value=False,
        new_value=True,
    )

    assert changed != original
    assert changed[0].value is True

    assert (
        changed[0].metric_key,
        changed[0].metric_version,
        changed[0].evaluator_key,
        changed[0].evaluator_version,
        changed[0].evaluation_type,
        changed[0].status,
        changed[0].value_type,
    ) == (
        original[0].metric_key,
        original[0].metric_version,
        original[0].evaluator_key,
        original[0].evaluator_version,
        original[0].evaluation_type,
        original[0].status,
        original[0].value_type,
    )


def test_mutation_suite_rejects_duplicate_mutations():
    with pytest.raises(
        HveeContractError,
        match="mutations must be unique",
    ):
        run_semantic_evaluator_mutation_suite(
            portfolio_key="synthetic.semantic.portfolio",
            portfolio_version="1.0.0",
            suite_key="synthetic.semantic.mutation-suite",
            suite_version="1.0.0",
            cases=CASES,
            mutations=(
                SyntheticMutation.FALSE_TO_TRUE,
                SyntheticMutation.FALSE_TO_TRUE,
            ),
            evaluate_case=_evaluate_case,
            compare_case=_compare_case,
            apply_mutation=_apply_mutation,
        )


def test_mutation_result_rejects_detected_case_without_change():
    with pytest.raises(
        HveeContractError,
        match="detected cases must be changed cases",
    ):
        SemanticMutationResult(
            mutation=SyntheticMutation.FALSE_TO_TRUE,
            changed_case_ids=("case.false",),
            detected_case_ids=("case.true",),
        )


def test_mutation_rejects_comparison_change_without_observation_change():
    comparison_calls = 0

    def unstable_compare(
        *,
        case: SyntheticCase,
        observations: tuple[Observation, ...],
    ) -> SyntheticResult:
        nonlocal comparison_calls
        comparison_calls += 1

        return SyntheticResult(
            case_id=case.case_id,
            passed=(comparison_calls == 1),
        )

    def no_change_mutation(
        *,
        mutation: SyntheticMutation,
        observations: tuple[Observation, ...],
    ) -> tuple[Observation, ...]:
        return observations

    with pytest.raises(
        HveeContractError,
        match=(
            "comparison changed without "
            "an observation mutation"
        ),
    ):
        run_semantic_evaluator_mutation(
            cases=(
                SyntheticCase(
                    case_id="case.false",
                    expected=False,
                ),
            ),
            mutation=SyntheticMutation.FALSE_TO_TRUE,
            evaluate_case=_evaluate_case,
            compare_case=unstable_compare,
            apply_mutation=no_change_mutation,
        )


def test_mutation_rejects_observation_reordering():
    def evaluate_two_observations(
        case: SyntheticCase,
    ) -> tuple[Observation, ...]:
        first = _observation(case.expected)
        second = replace(
            first,
            metric_key="synthetic.semantic.secondary",
        )

        return (
            first,
            second,
        )

    def always_pass_compare(
        *,
        case: SyntheticCase,
        observations: tuple[Observation, ...],
    ) -> SyntheticResult:
        return SyntheticResult(
            case_id=case.case_id,
            passed=True,
        )

    def reverse_observations(
        *,
        mutation: SyntheticMutation,
        observations: tuple[Observation, ...],
    ) -> tuple[Observation, ...]:
        return tuple(reversed(observations))

    with pytest.raises(
        HveeContractError,
        match="changed observation identity",
    ):
        run_semantic_evaluator_mutation(
            cases=(
                SyntheticCase(
                    case_id="case.false",
                    expected=False,
                ),
            ),
            mutation=SyntheticMutation.FALSE_TO_TRUE,
            evaluate_case=evaluate_two_observations,
            compare_case=always_pass_compare,
            apply_mutation=reverse_observations,
        )
