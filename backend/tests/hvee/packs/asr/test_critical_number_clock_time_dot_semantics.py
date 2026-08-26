from __future__ import annotations

import pytest

from hvee.packs.asr.critical_number_fidelity import (
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberFindingType,
    ASRCriticalNumberReasonCode,
    ASRCriticalNumberType,
    CRITICAL_NUMBER_EVALUATOR_VERSION,
    EN_US_CRITICAL_NUMBER_PROFILE,
    evaluate_critical_number_fidelity,
)


def _evaluate(reference: str, generated: str):
    return evaluate_critical_number_fidelity(
        reference_text=reference,
        generated_text=generated,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )


@pytest.mark.parametrize(
    ("generated", "expected"),
    (
        ("meet at 9.15 AM tomorrow", "09:15"),
        ("meet at 9.15 am tomorrow", "09:15"),
        ("meet at 9.15 a.m. tomorrow", "09:15"),
        ("meet at 9.15 PM tomorrow", "21:15"),
        ("meet at 9.15 p.m. tomorrow", "21:15"),
    ),
)
def test_dot_time_with_explicit_period_is_clock_time_equivalent(
    generated: str,
    expected: str,
) -> None:
    reference = (
        "meet at nine fifteen AM tomorrow"
        if expected == "09:15"
        else "meet at nine fifteen PM tomorrow"
    )

    evaluation = _evaluate(
        reference,
        generated,
    )

    assert (
        evaluation.outcome
        == ASRCriticalNumberFidelityOutcome.PRESERVED
    )

    assert evaluation.preserved is True

    assert len(evaluation.reference_entities) == 1
    assert len(evaluation.generated_entities) == 1

    reference_entity = evaluation.reference_entities[0]
    generated_entity = evaluation.generated_entities[0]

    assert (
        reference_entity.numeric_type
        == ASRCriticalNumberType.CLOCK_TIME
    )

    assert (
        generated_entity.numeric_type
        == ASRCriticalNumberType.CLOCK_TIME
    )

    assert reference_entity.canonical_value == expected
    assert generated_entity.canonical_value == expected

    assert len(evaluation.findings) == 1

    finding = evaluation.findings[0]

    assert (
        finding.finding_type
        == ASRCriticalNumberFindingType.MATCH
    )

    assert (
        finding.reason_code
        == ASRCriticalNumberReasonCode.FORMAT_EQUIVALENT
    )


def test_dot_decimal_without_period_remains_decimal() -> None:
    evaluation = _evaluate(
        "threshold is 9.15",
        "threshold is 9.15",
    )

    assert (
        evaluation.outcome
        == ASRCriticalNumberFidelityOutcome.PRESERVED
    )

    assert evaluation.preserved is True
    assert len(evaluation.generated_entities) == 1

    entity = evaluation.generated_entities[0]

    assert (
        entity.numeric_type
        == ASRCriticalNumberType.CARDINAL_DECIMAL
    )

    assert entity.canonical_value == "9.15"


def test_different_valid_dot_clock_time_is_value_substitution() -> None:
    evaluation = _evaluate(
        "meet at nine fifteen AM tomorrow",
        "meet at 9.50 a.m. tomorrow",
    )

    assert (
        evaluation.outcome
        == ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
    )

    assert evaluation.preserved is False
    assert len(evaluation.findings) == 1

    finding = evaluation.findings[0]

    assert (
        finding.finding_type
        == ASRCriticalNumberFindingType.SUBSTITUTION
    )

    assert (
        finding.reason_code
        == ASRCriticalNumberReasonCode.VALUE_SUBSTITUTION
    )

    assert (
        finding.numeric_type
        == ASRCriticalNumberType.CLOCK_TIME
    )

    assert finding.reference is not None
    assert finding.generated is not None

    assert finding.reference.canonical_value == "09:15"
    assert finding.generated.canonical_value == "09:50"


@pytest.mark.parametrize(
    "generated",
    (
        "meet at 9.75 AM tomorrow",
        "meet at 13.15 PM tomorrow",
    ),
)
def test_invalid_dot_clock_values_do_not_become_clock_times(
    generated: str,
) -> None:
    evaluation = _evaluate(
        "meet at nine fifteen AM tomorrow",
        generated,
    )

    assert evaluation.preserved is False

    assert all(
        entity.numeric_type
        != ASRCriticalNumberType.CLOCK_TIME
        for entity in evaluation.generated_entities
    )


def test_clock_time_semantic_change_has_new_evaluator_identity() -> None:
    assert CRITICAL_NUMBER_EVALUATOR_VERSION == "1.1.0"
