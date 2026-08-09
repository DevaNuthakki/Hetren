from __future__ import annotations

import pytest

from hvee.core.contracts import (
    HveeContractError,
)
from hvee.packs.asr.evaluator_mutation import (
    ASR_EVALUATOR_MUTATIONS_V1,
    ASREvaluatorMutation,
    apply_asr_evaluator_mutation,
    run_asr_evaluator_mutation,
    run_asr_evaluator_mutation_suite,
)
from hvee.packs.asr.portfolio import (
    ASR_EVALUATION_PORTFOLIO_V1,
)
from hvee.packs.asr.portfolio_runner import (
    evaluate_asr_portfolio_case_observations,
)


def _case(case_id: str):
    matches = [
        case
        for case
        in ASR_EVALUATION_PORTFOLIO_V1.cases
        if case.case_id == case_id
    ]

    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize(
    ("mutation", "expected_case"),
    [
        (
            ASREvaluatorMutation
            .WORD_SUBSTITUTION_BLIND,
            "mutation.word-substitution",
        ),
        (
            ASREvaluatorMutation
            .WORD_DELETION_BLIND,
            "mutation.word-deletion",
        ),
        (
            ASREvaluatorMutation
            .WORD_INSERTION_BLIND,
            "mutation.word-insertion",
        ),
        (
            ASREvaluatorMutation
            .MISSING_OUTPUT_BLIND,
            "mutation.missing-output",
        ),
        (
            ASREvaluatorMutation
            .UNEXPECTED_OUTPUT_BLIND,
            "mutation.unexpected-output",
        ),
        (
            ASREvaluatorMutation
            .NUMERIC_ORDER_INSENSITIVE,
            "mutation.numeric-reorder",
        ),
        (
            ASREvaluatorMutation
            .NUMERIC_MISSING_BLIND,
            "mutation.numeric-deletion",
        ),
        (
            ASREvaluatorMutation
            .NUMERIC_UNEXPECTED_BLIND,
            "mutation.numeric-insertion",
        ),
    ],
)
def test_each_mutant_is_detected_by_targeted_case(
    mutation: ASREvaluatorMutation,
    expected_case: str,
):
    result = run_asr_evaluator_mutation(
        portfolio=ASR_EVALUATION_PORTFOLIO_V1,
        mutation=mutation,
    )

    assert result.killed is True
    assert result.changed_cases > 0
    assert expected_case in result.detected_case_ids


def test_deletion_blind_mutant_is_detected_by_multiple_cases():
    result = run_asr_evaluator_mutation(
        portfolio=ASR_EVALUATION_PORTFOLIO_V1,
        mutation=(
            ASREvaluatorMutation
            .WORD_DELETION_BLIND
        ),
    )

    assert "mutation.word-deletion" in (
        result.detected_case_ids
    )
    assert "mutation.missing-output" in (
        result.detected_case_ids
    )


def test_numeric_missing_blind_detects_substitution_and_deletion():
    result = run_asr_evaluator_mutation(
        portfolio=ASR_EVALUATION_PORTFOLIO_V1,
        mutation=(
            ASREvaluatorMutation
            .NUMERIC_MISSING_BLIND
        ),
    )

    assert "mutation.numeric-substitution" in (
        result.detected_case_ids
    )
    assert "mutation.numeric-deletion" in (
        result.detected_case_ids
    )


def test_numeric_unexpected_blind_detects_substitution_and_insertion():
    result = run_asr_evaluator_mutation(
        portfolio=ASR_EVALUATION_PORTFOLIO_V1,
        mutation=(
            ASREvaluatorMutation
            .NUMERIC_UNEXPECTED_BLIND
        ),
    )

    assert "mutation.numeric-substitution" in (
        result.detected_case_ids
    )
    assert "mutation.numeric-insertion" in (
        result.detected_case_ids
    )


def test_order_insensitive_mutant_is_caught_by_reorder_case():
    result = run_asr_evaluator_mutation(
        portfolio=ASR_EVALUATION_PORTFOLIO_V1,
        mutation=(
            ASREvaluatorMutation
            .NUMERIC_ORDER_INSENSITIVE
        ),
    )

    assert result.detected_case_ids == (
        "mutation.numeric-reorder",
    )


def test_full_mutation_suite_kills_all_v1_mutants():
    report = run_asr_evaluator_mutation_suite(
        ASR_EVALUATION_PORTFOLIO_V1
    )

    assert report.portfolio_key == (
        "hetren.asr.evaluation-portfolio"
    )
    assert report.portfolio_version == "1.0.0"

    assert report.total_mutants == 8
    assert report.killed_mutants == 8
    assert report.survived_mutants == 0
    assert report.mutation_score == 1.0


def test_mutation_suite_identity_is_complete_and_unique():
    assert len(
        ASR_EVALUATOR_MUTATIONS_V1
    ) == 8

    assert len(
        set(ASR_EVALUATOR_MUTATIONS_V1)
    ) == 8


def test_mutation_preserves_observation_identity():
    case = _case(
        "mutation.word-substitution"
    )

    original = (
        evaluate_asr_portfolio_case_observations(
            case
        )
    )

    mutated = apply_asr_evaluator_mutation(
        mutation=(
            ASREvaluatorMutation
            .WORD_SUBSTITUTION_BLIND
        ),
        observations=original,
    )

    assert len(mutated) == len(original)

    original_identities = tuple(
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
            observation.status,
            observation.value_type,
        )
        for observation
        in original
    )

    mutated_identities = tuple(
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
            observation.status,
            observation.value_type,
        )
        for observation
        in mutated
    )

    assert mutated_identities == (
        original_identities
    )
    assert mutated != original


def test_invalid_mutation_type_is_rejected():
    case = _case("control.exact")

    observations = (
        evaluate_asr_portfolio_case_observations(
            case
        )
    )

    with pytest.raises(
        HveeContractError,
        match="must be ASREvaluatorMutation",
    ):
        apply_asr_evaluator_mutation(
            mutation="broken",  # type: ignore[arg-type]
            observations=observations,
        )
