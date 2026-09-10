from __future__ import annotations

import pytest

from hvee.core.contracts import EvaluatorVersion, HveeContractError
from hvee.packs.asr.critical_number_fidelity import (
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberFindingType,
    ASRCriticalNumberType,
    CRITICAL_NUMBER_EVALUATOR_VERSION,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    EN_US_CRITICAL_NUMBER_PROFILE,
    build_critical_number_fidelity_observations,
    evaluate_critical_number_fidelity,
    extract_critical_number_entities,
)


def _evaluate(
    reference_text: str,
    generated_text: str,
    *,
    evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
):
    return evaluate_critical_number_fidelity(
        reference_text=reference_text,
        generated_text=generated_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=evaluator,
    )


def test_v1_2_is_explicit_and_does_not_replace_default_v1_1():
    assert CRITICAL_NUMBER_EVALUATOR_VERSION == "1.1.0"
    assert CRITICAL_NUMBER_FIDELITY_EVALUATOR.version == "1.1.0"
    assert CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.version == "1.0.0"
    assert CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.version == "1.2.0"

    assert (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key
        == CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.key
        == CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.key
    )
    assert (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type
        == CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1.evaluation_type
        == CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2.evaluation_type
        == "asr"
    )

    default_evaluation = evaluate_critical_number_fidelity(
        reference_text="The value is 2",
        generated_text="The value is 3",
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )
    assert default_evaluation.evaluator_version == "1.1.0"


@pytest.mark.parametrize(
    ("reference_text", "generated_text", "expected"),
    (
        (
            "The value is 2.",
            "The value is 3.",
            ASRCriticalNumberFidelityOutcome.NOT_PRESERVED,
        ),
        (
            "The value is 2.5.",
            "The value is 3.5.",
            ASRCriticalNumberFidelityOutcome.NOT_PRESERVED,
        ),
        (
            "The first value is 10 and the second value is 2.",
            "The first value is 10 and the second value is 3.",
            ASRCriticalNumberFidelityOutcome.NOT_PRESERVED,
        ),
        (
            "The value is two.",
            "The value is 2.",
            ASRCriticalNumberFidelityOutcome.PRESERVED,
        ),
        (
            "The value is 2.",
            "The value is 2.",
            ASRCriticalNumberFidelityOutcome.PRESERVED,
        ),
    ),
)
def test_v1_2_corrects_reproduced_sentence_period_defects(
    reference_text: str,
    generated_text: str,
    expected: ASRCriticalNumberFidelityOutcome,
):
    evaluation = _evaluate(reference_text, generated_text)

    assert evaluation.outcome == expected
    assert evaluation.evaluator_version == "1.2.0"


@pytest.mark.parametrize(
    "evaluator",
    (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    ),
)
def test_historical_evaluators_retain_their_recorded_period_behavior(
    evaluator,
):
    evaluation = _evaluate(
        "The value is 2.",
        "The value is 3.",
        evaluator=evaluator,
    )

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE
    )


@pytest.mark.parametrize(
    ("reference_text", "generated_text"),
    (
        ("The value is 2.", "The value is 3."),
        ("The value is 2!", "The value is 3!"),
        ("The value is 2?", "The value is 3?"),
        ("The value is 2;", "The value is 3;"),
        ("The value is 2:", "The value is 3:"),
        ("The value is 2, next.", "The value is 3, next."),
        ('The value is "2".', 'The value is "3".'),
        ("The value is (2).", "The value is (3)."),
        ("The value is 2...", "The value is 3..."),
        ("The value is 2.\n", "The value is 3.\n"),
        ("The value is 2.   ", "The value is 3.   "),
    ),
)
def test_v1_2_extracts_numbers_at_supported_punctuation_boundaries(
    reference_text: str,
    generated_text: str,
):
    evaluation = _evaluate(reference_text, generated_text)

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
    )
    assert len(evaluation.reference_entities) == 1
    assert len(evaluation.generated_entities) == 1


@pytest.mark.parametrize(
    ("reference_text", "generated_text"),
    (
        ("The value is two.", "The value is 2."),
        ("The value is two...", "The value is 2..."),
        ("The value is 2.5.", "The value is 2.5."),
        ("The value is 1,234.", "The value is 1,234."),
        ("The value is 1,234.50.", "The value is 1234.50."),
    ),
)
def test_v1_2_preserves_supported_equivalent_terminal_numbers(
    reference_text: str,
    generated_text: str,
):
    evaluation = _evaluate(reference_text, generated_text)

    assert evaluation.outcome == ASRCriticalNumberFidelityOutcome.PRESERVED
    assert evaluation.preserved is True


def test_v1_2_complete_grouped_decimal_is_not_reduced_to_prefix_one():
    text = "Amount is 1,234.50."

    entities = extract_critical_number_entities(
        text=text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    )

    assert len(entities) == 1
    assert entities[0].text == "1,234.50"
    assert text[entities[0].span_start : entities[0].span_end] == (
        "1,234.50"
    )
    assert entities[0].numeric_type == (
        ASRCriticalNumberType.CARDINAL_DECIMAL
    )


@pytest.mark.parametrize(
    ("text", "expected_text"),
    (
        ("The value is 2.", "2"),
        ("The value is 2.5.", "2.5"),
        ("The value is 2...", "2"),
        ('He said "2."', "2"),
        ("The value is (2).", "2"),
        ("The value is 1,234.50.", "1,234.50"),
    ),
)
def test_v1_2_source_spans_exclude_sentence_punctuation(
    text: str,
    expected_text: str,
):
    entities = extract_critical_number_entities(
        text=text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
        evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR_V1_2,
    )

    assert len(entities) == 1
    entity = entities[0]

    assert entity.text == expected_text
    assert text[entity.span_start : entity.span_end] == expected_text


@pytest.mark.parametrize(
    "text",
    (
        "The value is 2..",
        "The value is 2....",
        "The value is 2.....",
        "The value is 2.5..",
        "The value is 2.5....",
        "The value is 1,23.",
        "The value is 12,34.",
        "The value is 1,23,456.",
        "The value is 1234,567.",
        "The version is 1.2.3.",
    ),
)
def test_v1_2_malformed_numeric_runs_do_not_silently_pass(text: str):
    evaluation = _evaluate(text, text)

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    )
    assert evaluation.preserved is None
    assert any(
        finding.finding_type
        == ASRCriticalNumberFindingType.UNSUPPORTED
        for finding in evaluation.findings
    )


def test_v1_2_valid_repeated_thousands_groups_remain_supported():
    evaluation = _evaluate(
        "The amount is 1,234,567.",
        "The amount is 1,234,567.",
    )

    assert evaluation.outcome == ASRCriticalNumberFidelityOutcome.PRESERVED
    assert len(evaluation.reference_entities) == 1
    assert evaluation.reference_entities[0].text == "1,234,567"


def test_v1_2_bare_seven_digit_run_remains_intentionally_unsupported():
    evaluation = _evaluate(
        "The value is 1234567.",
        "The value is 1234567.",
    )

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    )
    assert evaluation.preserved is None

    assert any(
        finding.finding_type
        == ASRCriticalNumberFindingType.UNSUPPORTED
        for finding in evaluation.findings
    )


def test_v1_2_multiple_numbers_include_the_terminal_number():
    evaluation = _evaluate(
        "The first value is 10 and the second value is 2.",
        "The first value is 10 and the second value is 3.",
    )

    assert [entity.canonical_value for entity in evaluation.reference_entities] == [
        "10",
        "2",
    ]
    assert [entity.canonical_value for entity in evaluation.generated_entities] == [
        "10",
        "3",
    ]
    assert evaluation.substitution_count == 1
    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
    )


def test_v1_2_keeps_v1_1_dot_clock_semantics():
    evaluation = _evaluate(
        "meet at nine fifteen AM tomorrow",
        "meet at 9.15 a.m. tomorrow",
    )

    assert evaluation.outcome == ASRCriticalNumberFidelityOutcome.PRESERVED
    assert evaluation.generated_entities[0].numeric_type == (
        ASRCriticalNumberType.CLOCK_TIME
    )
    assert evaluation.generated_entities[0].canonical_value == "09:15"


def test_v1_2_observations_retain_explicit_evaluator_identity():
    evaluation = _evaluate(
        "The value is 2.",
        "The value is 3.",
    )
    observations = build_critical_number_fidelity_observations(evaluation)

    assert {
        observation.evaluator_version
        for observation in observations
    } == {"1.2.0"}


def test_unknown_evaluator_still_fails_closed():
    unsupported = EvaluatorVersion(
        key=CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        version="9.9.9",
        evaluation_type="asr",
        description="Unsupported synthetic evaluator.",
    )

    with pytest.raises(
        HveeContractError,
        match="evaluator identity is unsupported",
    ):
        _evaluate(
            "The value is 2.",
            "The value is 3.",
            evaluator=unsupported,
        )
