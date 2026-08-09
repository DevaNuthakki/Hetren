from __future__ import annotations

from dataclasses import replace

import pytest

from hvee.core.contracts import (
    HveeContractError,
    ObservationStatus,
)
from hvee.core.validation import validate_observation_contract
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_NUMBER_APPLICABLE_METRIC,
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_FINDINGS_METRIC,
    CRITICAL_NUMBER_GENERATED_COUNT_METRIC,
    CRITICAL_NUMBER_INSERTION_COUNT_METRIC,
    CRITICAL_NUMBER_METRICS,
    CRITICAL_NUMBER_OMISSION_COUNT_METRIC,
    CRITICAL_NUMBER_OUTCOME_METRIC,
    CRITICAL_NUMBER_PRESERVED_METRIC,
    CRITICAL_NUMBER_REFERENCE_COUNT_METRIC,
    CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC,
    EN_US_CRITICAL_NUMBER_PROFILE,
    ASRCriticalNumberFidelityOutcome,
    ASRCriticalNumberFindingType,
    ASRCriticalNumberProfile,
    ASRCriticalNumberReasonCode,
    ASRCriticalNumberType,
    build_critical_number_fidelity_observations,
    evaluate_critical_number_fidelity,
    extract_critical_number_entities,
)


def _evaluate(reference_text: str, generated_text: str):
    return evaluate_critical_number_fidelity(
        reference_text=reference_text,
        generated_text=generated_text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )


def _observation_by_key(evaluation):
    return {
        observation.metric_key: observation
        for observation in build_critical_number_fidelity_observations(
            evaluation
        )
    }


@pytest.mark.parametrize(
    ("reference_text", "generated_text", "numeric_type", "canonical"),
    [
        (
            "take five tablets",
            "take 5 tablets",
            ASRCriticalNumberType.CARDINAL_DECIMAL,
            ("5", None),
        ),
        (
            "use two point five units",
            "use 2.5 units",
            ASRCriticalNumberType.CARDINAL_DECIMAL,
            ("2.5", None),
        ),
        (
            "discount twenty percent today",
            "discount 20% today",
            ASRCriticalNumberType.PERCENTAGE,
            ("20", "percent"),
        ),
        (
            "pay $1,200 now",
            "pay 1,200 US dollars now",
            ASRCriticalNumberType.CURRENCY,
            ("1200", "USD"),
        ),
        (
            "dose five milligrams now",
            "dose 5 mg now",
            ASRCriticalNumberType.MEASUREMENT,
            ("5", "mg"),
        ),
        (
            "meet at nine fifteen AM tomorrow",
            "meet at 9:15 AM tomorrow",
            ASRCriticalNumberType.CLOCK_TIME,
            ("09:15", None),
        ),
        (
            "meet at nine fifteen PM tomorrow",
            "meet at 21:15 tomorrow",
            ASRCriticalNumberType.CLOCK_TIME,
            ("21:15", None),
        ),
        (
            "on August 9, 2026",
            "on 2026-08-09",
            ASRCriticalNumberType.CALENDAR_DATE,
            ("2026-08-09", None),
        ),
    ],
)
def test_supported_semantic_equivalence_golden_vectors(
    reference_text,
    generated_text,
    numeric_type,
    canonical,
):
    evaluation = _evaluate(reference_text, generated_text)

    assert evaluation.outcome == ASRCriticalNumberFidelityOutcome.PRESERVED
    assert evaluation.preserved is True
    assert len(evaluation.reference_entities) == 1
    assert len(evaluation.generated_entities) == 1

    reference = evaluation.reference_entities[0]
    generated = evaluation.generated_entities[0]

    assert reference.numeric_type == numeric_type
    assert generated.numeric_type == numeric_type
    assert (
        reference.canonical_value,
        reference.canonical_unit,
    ) == canonical
    assert (
        generated.canonical_value,
        generated.canonical_unit,
    ) == canonical
    assert evaluation.findings[0].finding_type == (
        ASRCriticalNumberFindingType.MATCH
    )


def test_source_spans_recover_original_text():
    text = "Dose １５ milligrams now"
    entities = extract_critical_number_entities(
        text=text,
        profile=EN_US_CRITICAL_NUMBER_PROFILE,
    )

    assert len(entities) == 1
    entity = entities[0]
    assert text[entity.span_start : entity.span_end] == (
        "１５ milligrams"
    )
    assert entity.text == "１５ milligrams"
    assert entity.canonical_value == "15"


@pytest.mark.parametrize(
    ("reference_text", "generated_text", "finding_type", "reason_code"),
    [
        (
            "dose 5 mg now",
            "dose 50 mg now",
            ASRCriticalNumberFindingType.SUBSTITUTION,
            ASRCriticalNumberReasonCode.VALUE_SUBSTITUTION,
        ),
        (
            "dose 5 mg now",
            "dose 5 g now",
            ASRCriticalNumberFindingType.SUBSTITUTION,
            ASRCriticalNumberReasonCode.UNIT_SUBSTITUTION,
        ),
        (
            "dose 5 mg now",
            "dose now",
            ASRCriticalNumberFindingType.OMISSION,
            ASRCriticalNumberReasonCode.REFERENCE_ENTITY_OMITTED,
        ),
        (
            "dose now",
            "dose 5 mg now",
            ASRCriticalNumberFindingType.INSERTION,
            ASRCriticalNumberReasonCode.GENERATED_ENTITY_INSERTED,
        ),
    ],
)
def test_proven_errors_are_not_preserved(
    reference_text,
    generated_text,
    finding_type,
    reason_code,
):
    evaluation = _evaluate(reference_text, generated_text)

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
    )
    assert evaluation.preserved is False
    assert any(
        finding.finding_type == finding_type
        and finding.reason_code == reason_code
        for finding in evaluation.findings
    )


def test_no_number_transcripts_are_not_applicable_not_positive_evidence():
    evaluation = _evaluate("hello world", "hello there")
    observations = _observation_by_key(evaluation)

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.NOT_APPLICABLE
    )
    assert evaluation.preserved is None
    assert observations[CRITICAL_NUMBER_APPLICABLE_METRIC.key].value is False
    preserved = observations[CRITICAL_NUMBER_PRESERVED_METRIC.key]
    assert preserved.status == ObservationStatus.ABSTAINED
    assert preserved.value is None


def test_ambiguous_date_abstains_without_silent_locale_assumption():
    evaluation = _evaluate("date 03/04/26", "date 03/04/26")
    observations = _observation_by_key(evaluation)

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    )
    assert evaluation.ambiguity_count == 2
    assert observations[CRITICAL_NUMBER_PRESERVED_METRIC.key].status == (
        ObservationStatus.ABSTAINED
    )
    assert observations[CRITICAL_NUMBER_APPLICABLE_METRIC.key].value is True


def test_ambiguous_generated_expression_does_not_create_false_omission():
    evaluation = _evaluate(
        "renew on March 4, 2026",
        "renew on 03/04/26",
    )

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    )
    assert evaluation.omission_count == 0
    assert any(
        finding.reason_code
        == ASRCriticalNumberReasonCode.CONTEXT_ALIGNMENT_AMBIGUOUS
        for finding in evaluation.findings
    )


def test_unsupported_generated_expression_does_not_create_false_omission():
    evaluation = _evaluate(
        "pay $5 now",
        "pay £5 now",
    )

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    )
    assert evaluation.omission_count == 0
    assert any(
        finding.reason_code
        == ASRCriticalNumberReasonCode.GENERATED_EXPRESSION_UNSUPPORTED
        for finding in evaluation.findings
    )


@pytest.mark.parametrize(
    "expression",
    [
        "ratio 1/2",
        "range 5-10",
        "scientific 1e3",
        "version 1.2.3",
        "phone 212-555-0199",
        "invalid date 2026-02-31",
        "ratio 3:2",
        "range 5 to 10",
        "range five to ten",
        "between 5 and 10",
        "from five to ten",
        "fraction one half",
        "fraction one and a half",
        "account 12345",
        "bad grouping 12,00",
        "alternate date 2026/08/09",
        "unsupported currency £5",
        "unsupported currency 5 euros",
    ],
)
def test_unsupported_expressions_do_not_silently_pass(expression):
    evaluation = _evaluate(expression, expression)
    observations = _observation_by_key(evaluation)

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.INSUFFICIENT_EVIDENCE
    )
    assert observations[CRITICAL_NUMBER_PRESERVED_METRIC.key].status == (
        ObservationStatus.UNSUPPORTED
    )
    assert any(
        finding.finding_type == ASRCriticalNumberFindingType.UNSUPPORTED
        for finding in evaluation.findings
    )


def test_proven_error_dominates_unsupported_evidence():
    evaluation = _evaluate(
        "dose 5 mg ratio 1/2",
        "dose 50 mg ratio 1/2",
    )

    assert evaluation.outcome == (
        ASRCriticalNumberFidelityOutcome.NOT_PRESERVED
    )
    assert evaluation.preserved is False
    assert evaluation.substitution_count == 1
    assert any(
        finding.finding_type == ASRCriticalNumberFindingType.UNSUPPORTED
        for finding in evaluation.findings
    )


def test_deterministic_repeated_evaluation_and_json_findings():
    first = _evaluate(
        "pay $1,200 at 9:15 AM",
        "pay 1200 dollars at nine fifteen AM",
    )
    second = _evaluate(
        "pay $1,200 at 9:15 AM",
        "pay 1200 dollars at nine fifteen AM",
    )

    assert first == second
    first_findings = _observation_by_key(first)[
        CRITICAL_NUMBER_FINDINGS_METRIC.key
    ].value
    second_findings = _observation_by_key(second)[
        CRITICAL_NUMBER_FINDINGS_METRIC.key
    ].value
    assert first_findings == second_findings


def test_observations_follow_hvee_contracts():
    evaluation = _evaluate("dose 5 mg", "dose 50 mg")
    observations = build_critical_number_fidelity_observations(evaluation)

    assert len(observations) == len(CRITICAL_NUMBER_METRICS) == 10
    for metric, observation in zip(
        CRITICAL_NUMBER_METRICS,
        observations,
        strict=True,
    ):
        validate_observation_contract(
            metric=metric,
            evaluator=CRITICAL_NUMBER_FIDELITY_EVALUATOR,
            observation=observation,
        )

    by_key = {observation.metric_key: observation for observation in observations}
    assert by_key[CRITICAL_NUMBER_OUTCOME_METRIC.key].value == "not_preserved"
    assert by_key[CRITICAL_NUMBER_REFERENCE_COUNT_METRIC.key].value == 1
    assert by_key[CRITICAL_NUMBER_GENERATED_COUNT_METRIC.key].value == 1
    assert by_key[CRITICAL_NUMBER_SUBSTITUTION_COUNT_METRIC.key].value == 1
    assert by_key[CRITICAL_NUMBER_OMISSION_COUNT_METRIC.key].value == 0
    assert by_key[CRITICAL_NUMBER_INSERTION_COUNT_METRIC.key].value == 0
    assert by_key[CRITICAL_NUMBER_AMBIGUITY_COUNT_METRIC.key].value == 0


def test_observation_builder_rejects_inconsistent_forged_outcome():
    evaluation = _evaluate("dose 5 mg", "dose 50 mg")
    forged = replace(
        evaluation,
        outcome=ASRCriticalNumberFidelityOutcome.PRESERVED,
    )

    with pytest.raises(
        HveeContractError,
        match="outcome is inconsistent",
    ):
        build_critical_number_fidelity_observations(forged)


def test_profile_must_be_explicit_and_exactly_supported():
    with pytest.raises(
        HveeContractError,
        match="requires ASRCriticalNumberProfile",
    ):
        evaluate_critical_number_fidelity(
            reference_text="five",
            generated_text="5",
            profile=None,  # type: ignore[arg-type]
        )

    unsupported_profile = ASRCriticalNumberProfile(
        key="hetren.asr.critical-number-profile.en-gb",
        version="1.0.0",
        language="en",
        locale="en-GB",
        description="Unsupported test profile.",
    )
    with pytest.raises(
        HveeContractError,
        match="explicit Hetren en-US profile",
    ):
        evaluate_critical_number_fidelity(
            reference_text="five",
            generated_text="5",
            profile=unsupported_profile,
        )


def test_transcripts_must_be_strings():
    with pytest.raises(
        HveeContractError,
        match="requires string transcripts",
    ):
        evaluate_critical_number_fidelity(
            reference_text=5,  # type: ignore[arg-type]
            generated_text="5",
            profile=EN_US_CRITICAL_NUMBER_PROFILE,
        )
