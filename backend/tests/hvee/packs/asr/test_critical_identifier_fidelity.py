from dataclasses import replace

import pytest

import hvee.packs.asr as asr_pack
from hvee.core.contracts import (
    HveeContractError,
    ObservationStatus,
)
from hvee.packs.asr.critical_identifier_fidelity import (
    CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC,
    CRITICAL_IDENTIFIER_APPLICABLE_METRIC,
    CRITICAL_IDENTIFIER_EVALUATOR_VERSION,
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    CRITICAL_IDENTIFIER_FINDINGS_METRIC,
    CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC,
    CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_METRICS,
    CRITICAL_IDENTIFIER_METRIC_VERSION,
    CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC,
    CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_OUTCOME_METRIC,
    CRITICAL_IDENTIFIER_PRESERVED_METRIC,
    CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC,
    CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC,
    EN_US_CRITICAL_IDENTIFIER_PROFILE,
    ASRCriticalIdentifierFidelityOutcome,
    ASRCriticalIdentifierFindingType,
    ASRCriticalIdentifierProfile,
    ASRCriticalIdentifierReasonCode,
    ASRCriticalIdentifierType,
    build_critical_identifier_fidelity_observations,
    evaluate_critical_identifier_fidelity,
    extract_critical_identifier_entities,
)


def _evaluate(
    reference_text: str,
    generated_text: str,
):
    return evaluate_critical_identifier_fidelity(
        reference_text=reference_text,
        generated_text=generated_text,
        profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
    )


def _observation_by_key(
    observations,
    metric_key: str,
):
    matches = tuple(
        observation
        for observation in observations
        if observation.metric_key == metric_key
    )

    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize(
    ("cue", "identifier_type"),
    (
        (
            "confirmation code",
            ASRCriticalIdentifierType.CONFIRMATION_CODE,
        ),
        (
            "reference id",
            ASRCriticalIdentifierType.REFERENCE_ID,
        ),
        (
            "ticket id",
            ASRCriticalIdentifierType.TICKET_ID,
        ),
        (
            "case id",
            ASRCriticalIdentifierType.CASE_ID,
        ),
        (
            "order id",
            ASRCriticalIdentifierType.ORDER_ID,
        ),
        (
            "account id",
            ASRCriticalIdentifierType.ACCOUNT_ID,
        ),
        (
            "serial number",
            ASRCriticalIdentifierType.SERIAL_NUMBER,
        ),
        (
            "booking reference",
            ASRCriticalIdentifierType.BOOKING_REFERENCE,
        ),
    ),
)
def test_supported_cues_extract_typed_identifier(
    cue,
    identifier_type,
):
    text = f"{cue} AB7K92"

    entities = extract_critical_identifier_entities(
        text,
        profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
    )

    assert len(entities) == 1

    entity = entities[0]

    assert entity.identifier_type == identifier_type
    assert entity.text == "AB7K92"
    assert entity.canonical_value == "AB7K92"
    assert entity.issue_reason_code is None
    assert text[
        entity.span_start:entity.span_end
    ] == entity.text


@pytest.mark.parametrize(
    ("reference", "generated", "expected_reason"),
    (
        (
            "confirmation code AB7K92",
            "confirmation code AB7K92",
            ASRCriticalIdentifierReasonCode.EXACT_MATCH,
        ),
        (
            "confirmation code AB-7K-92",
            "confirmation code AB7K92",
            ASRCriticalIdentifierReasonCode.FORMAT_EQUIVALENT,
        ),
        (
            "confirmation code ab7k92",
            "confirmation code AB7K92",
            ASRCriticalIdentifierReasonCode.FORMAT_EQUIVALENT,
        ),
        (
            "confirmation code AB7K92",
            "confirmation code A B 7 K 9 2",
            ASRCriticalIdentifierReasonCode.FORMAT_EQUIVALENT,
        ),
    ),
)
def test_supported_identifier_equivalence_golden_vectors(
    reference,
    generated,
    expected_reason,
):
    result = _evaluate(
        reference,
        generated,
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.PRESERVED
    )
    assert result.preserved is True
    assert result.applicable is True
    assert result.substitution_count == 0
    assert result.omission_count == 0
    assert result.insertion_count == 0
    assert result.ordering_change_count == 0

    assert len(result.findings) == 1
    assert (
        result.findings[0].finding_type
        == ASRCriticalIdentifierFindingType.MATCH
    )
    assert (
        result.findings[0].reason_code
        == expected_reason
    )


def test_supported_introducer_forms():
    cases = (
        "confirmation code AB7K92",
        "confirmation code: AB7K92",
        "confirmation code # AB7K92",
        "confirmation code is AB7K92",
    )

    for text in cases:
        entities = extract_critical_identifier_entities(
            text,
            profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
        )

        assert len(entities) == 1
        assert entities[0].canonical_value == "AB7K92"
        assert entities[0].issue_reason_code is None


def test_source_spans_recover_original_identifier_surface():
    text = "Please use booking reference AB-7K-92 today."

    entities = extract_critical_identifier_entities(
        text,
        profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
    )

    assert len(entities) == 1

    entity = entities[0]

    assert text[
        entity.span_start:entity.span_end
    ] == "AB-7K-92"
    assert entity.canonical_value == "AB7K92"


def test_compact_identifier_does_not_consume_following_prose():
    text = "ticket id 93BZK was created"

    entities = extract_critical_identifier_entities(
        text,
        profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
    )

    assert len(entities) == 1
    assert entities[0].text == "93BZK"
    assert entities[0].canonical_value == "93BZK"


def test_spaced_identifier_does_not_consume_following_prose():
    text = "confirmation code A B 7 K 9 2 was accepted"

    entities = extract_critical_identifier_entities(
        text,
        profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
    )

    assert len(entities) == 1
    assert entities[0].text == "A B 7 K 9 2"
    assert entities[0].canonical_value == "AB7K92"


def test_value_substitution_is_not_preserved():
    result = _evaluate(
        "confirmation code AB7K92",
        "confirmation code AB7K29",
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED
    )
    assert result.preserved is False
    assert result.substitution_count == 1
    assert result.omission_count == 0
    assert result.insertion_count == 0

    finding = result.findings[0]

    assert (
        finding.finding_type
        == ASRCriticalIdentifierFindingType.SUBSTITUTION
    )
    assert (
        finding.reason_code
        == ASRCriticalIdentifierReasonCode.VALUE_SUBSTITUTION
    )


def test_reference_identifier_omission_is_not_preserved():
    result = _evaluate(
        "ticket id 93BZK",
        "the ticket was created",
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED
    )
    assert result.omission_count == 1

    finding = result.findings[0]

    assert (
        finding.finding_type
        == ASRCriticalIdentifierFindingType.OMISSION
    )
    assert (
        finding.reason_code
        == (
            ASRCriticalIdentifierReasonCode
            .REFERENCE_IDENTIFIER_OMITTED
        )
    )


def test_generated_identifier_insertion_is_not_preserved():
    result = _evaluate(
        "the ticket was created",
        "ticket id 93BZK",
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED
    )
    assert result.insertion_count == 1

    finding = result.findings[0]

    assert (
        finding.finding_type
        == ASRCriticalIdentifierFindingType.INSERTION
    )
    assert (
        finding.reason_code
        == (
            ASRCriticalIdentifierReasonCode
            .GENERATED_IDENTIFIER_INSERTED
        )
    )


def test_reordered_identifier_sequence_is_explicit_ordering_change():
    result = _evaluate(
        "ticket id A12 then ticket id B34",
        "ticket id B34 then ticket id A12",
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED
    )
    assert result.ordering_change_count == 1
    assert result.substitution_count == 0
    assert result.omission_count == 0
    assert result.insertion_count == 0

    assert len(result.findings) == 1

    finding = result.findings[0]

    assert (
        finding.finding_type
        == ASRCriticalIdentifierFindingType.ORDERING_CHANGE
    )
    assert (
        finding.reason_code
        == ASRCriticalIdentifierReasonCode.IDENTIFIER_ORDER_CHANGED
    )


def test_multiple_identifiers_preserve_order_and_identity():
    result = _evaluate(
        (
            "ticket id A12 and "
            "booking reference B34"
        ),
        (
            "ticket id A12 and "
            "booking reference B34"
        ),
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.PRESERVED
    )
    assert len(result.reference_entities) == 2
    assert len(result.generated_entities) == 2
    assert all(
        finding.finding_type
        == ASRCriticalIdentifierFindingType.MATCH
        for finding in result.findings
    )


@pytest.mark.parametrize(
    "surface",
    (
        "QF 2841",
        "AB7K 92",
        "AB_7K_92",
        "alpha bravo seven kilo",
    ),
)
def test_unsupported_v1_surfaces_are_insufficient_evidence(
    surface,
):
    result = _evaluate(
        f"reference id {surface}",
        f"reference id {surface}",
    )

    assert (
        result.outcome
        == (
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        )
    )
    assert result.preserved is None
    assert result.applicable is True

    reason_codes = {
        finding.reason_code
        for finding in result.findings
    }

    assert (
        ASRCriticalIdentifierReasonCode
        .REFERENCE_SURFACE_UNSUPPORTED
        in reason_codes
    )
    assert (
        ASRCriticalIdentifierReasonCode
        .GENERATED_SURFACE_UNSUPPORTED
        in reason_codes
    )


def test_ambiguous_alternative_abstains():
    result = _evaluate(
        "reference id AB7K or CD92",
        "reference id AB7K",
    )

    assert (
        result.outcome
        == (
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        )
    )

    assert any(
        finding.finding_type
        == ASRCriticalIdentifierFindingType.AMBIGUITY
        for finding in result.findings
    )

    assert any(
        finding.reason_code
        == (
            ASRCriticalIdentifierReasonCode
            .REFERENCE_EXTRACTION_AMBIGUOUS
        )
        for finding in result.findings
    )


def test_ambiguous_generated_surface_does_not_create_false_omission():
    result = _evaluate(
        "reference id AB7K",
        "reference id AB7K or CD92",
    )

    assert (
        result.outcome
        == (
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        )
    )
    assert result.omission_count == 0
    assert result.insertion_count == 0
    assert result.substitution_count == 0


def test_unsupported_generated_surface_does_not_create_false_omission():
    result = _evaluate(
        "confirmation code AB7K",
        "confirmation code alpha bravo seven kilo",
    )

    assert (
        result.outcome
        == (
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        )
    )
    assert result.omission_count == 0
    assert result.insertion_count == 0
    assert result.substitution_count == 0


def test_proven_error_dominates_unrelated_unsupported_evidence():
    result = _evaluate(
        (
            "ticket id A12 and "
            "booking reference B34"
        ),
        (
            "ticket id A99 and "
            "booking reference alpha bravo"
        ),
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.NOT_PRESERVED
    )
    assert result.substitution_count == 1

    assert any(
        finding.reason_code
        == ASRCriticalIdentifierReasonCode.VALUE_SUBSTITUTION
        for finding in result.findings
    )

    assert any(
        finding.reason_code
        == (
            ASRCriticalIdentifierReasonCode
            .GENERATED_SURFACE_UNSUPPORTED
        )
        for finding in result.findings
    )


def test_no_identifier_transcripts_are_not_applicable():
    result = _evaluate(
        "the request succeeded",
        "the request succeeded",
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.NOT_APPLICABLE
    )
    assert result.applicable is False
    assert result.preserved is None
    assert result.reference_entities == ()
    assert result.generated_entities == ()
    assert result.findings == ()


def test_numeric_identifier_requires_supported_cue():
    result = _evaluate(
        "the value was 49218",
        "the value was 49218",
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.NOT_APPLICABLE
    )


def test_pure_numeric_identifier_is_valid_when_cue_bound():
    result = _evaluate(
        "order id 49218",
        "order id 49218",
    )

    assert (
        result.outcome
        == ASRCriticalIdentifierFidelityOutcome.PRESERVED
    )

    assert (
        result.reference_entities[0].canonical_value
        == "49218"
    )


def test_evaluation_is_deterministic():
    first = _evaluate(
        (
            "ticket id A12 and "
            "booking reference B34"
        ),
        (
            "ticket id A99 and "
            "booking reference B34"
        ),
    )

    second = _evaluate(
        (
            "ticket id A12 and "
            "booking reference B34"
        ),
        (
            "ticket id A99 and "
            "booking reference B34"
        ),
    )

    assert first == second

    assert tuple(
        finding.to_json()
        for finding in first.findings
    ) == tuple(
        finding.to_json()
        for finding in second.findings
    )


def test_observations_follow_hvee_contracts_for_preserved_result():
    evaluation = _evaluate(
        "confirmation code AB7K92",
        "confirmation code AB-7K-92",
    )

    observations = (
        build_critical_identifier_fidelity_observations(
            evaluation
        )
    )

    assert len(observations) == len(
        CRITICAL_IDENTIFIER_METRICS
    )

    identities = {
        (
            observation.metric_key,
            observation.metric_version,
            observation.evaluator_key,
            observation.evaluator_version,
        )
        for observation in observations
    }

    assert len(identities) == len(observations)

    assert all(
        observation.evaluator_key
        == CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.key
        for observation in observations
    )
    assert all(
        observation.evaluator_version
        == CRITICAL_IDENTIFIER_EVALUATOR_VERSION
        for observation in observations
    )

    applicable = _observation_by_key(
        observations,
        CRITICAL_IDENTIFIER_APPLICABLE_METRIC.key,
    )
    preserved = _observation_by_key(
        observations,
        CRITICAL_IDENTIFIER_PRESERVED_METRIC.key,
    )
    outcome = _observation_by_key(
        observations,
        CRITICAL_IDENTIFIER_OUTCOME_METRIC.key,
    )

    assert applicable.status == ObservationStatus.SUCCESS
    assert applicable.value is True

    assert preserved.status == ObservationStatus.SUCCESS
    assert preserved.value is True

    assert outcome.status == ObservationStatus.SUCCESS
    assert (
        outcome.value
        == ASRCriticalIdentifierFidelityOutcome.PRESERVED.value
    )


def test_observation_counts_match_evaluation():
    evaluation = _evaluate(
        "ticket id A12",
        "ticket id B99",
    )

    observations = (
        build_critical_identifier_fidelity_observations(
            evaluation
        )
    )

    expected = {
        CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC.key: 1,
        CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC.key: 1,
        CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC.key: 1,
        CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC.key: 0,
        CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC.key: 0,
        CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC.key: 0,
        CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC.key: 0,
    }

    for metric_key, value in expected.items():
        observation = _observation_by_key(
            observations,
            metric_key,
        )
        assert observation.status == ObservationStatus.SUCCESS
        assert observation.value == value

    findings = _observation_by_key(
        observations,
        CRITICAL_IDENTIFIER_FINDINGS_METRIC.key,
    )

    assert findings.status == ObservationStatus.SUCCESS
    assert findings.value == [
        finding.to_json()
        for finding in evaluation.findings
    ]


@pytest.mark.parametrize(
    ("reference", "generated", "expected_outcome"),
    (
        (
            "the request succeeded",
            "the request succeeded",
            ASRCriticalIdentifierFidelityOutcome.NOT_APPLICABLE,
        ),
        (
            "reference id QF 2841",
            "reference id QF 2841",
            (
                ASRCriticalIdentifierFidelityOutcome
                .INSUFFICIENT_EVIDENCE
            ),
        ),
    ),
)
def test_preserved_observation_abstains_without_conclusive_claim(
    reference,
    generated,
    expected_outcome,
):
    evaluation = _evaluate(
        reference,
        generated,
    )

    assert evaluation.outcome == expected_outcome

    observations = (
        build_critical_identifier_fidelity_observations(
            evaluation
        )
    )

    preserved = _observation_by_key(
        observations,
        CRITICAL_IDENTIFIER_PRESERVED_METRIC.key,
    )

    assert preserved.status == ObservationStatus.ABSTAINED
    assert preserved.value is None
    assert preserved.status_detail == expected_outcome.value


def test_observation_builder_rejects_forged_outcome():
    evaluation = _evaluate(
        "ticket id A12",
        "ticket id B99",
    )

    forged = replace(
        evaluation,
        outcome=ASRCriticalIdentifierFidelityOutcome.PRESERVED,
    )

    with pytest.raises(
        HveeContractError,
        match="outcome is inconsistent",
    ):
        build_critical_identifier_fidelity_observations(
            forged
        )


def test_observation_builder_rejects_wrong_profile_identity():
    evaluation = _evaluate(
        "ticket id A12",
        "ticket id A12",
    )

    forged = replace(
        evaluation,
        profile_version="9.9.9",
    )

    with pytest.raises(
        HveeContractError,
        match="en-US evaluator v1.0.0",
    ):
        build_critical_identifier_fidelity_observations(
            forged
        )


def test_profile_must_be_versioned_and_supported():
    unsupported_profile = ASRCriticalIdentifierProfile(
        key=EN_US_CRITICAL_IDENTIFIER_PROFILE.key,
        version="2.0.0",
        language="en",
        locale="en-US",
        description="unsupported test profile",
    )

    with pytest.raises(
        HveeContractError,
        match="exact en-US profile",
    ):
        evaluate_critical_identifier_fidelity(
            reference_text="ticket id A12",
            generated_text="ticket id A12",
            profile=unsupported_profile,
        )

    with pytest.raises(
        HveeContractError,
        match="exact en-US profile",
    ):
        extract_critical_identifier_entities(
            "ticket id A12",
            profile=unsupported_profile,
        )


@pytest.mark.parametrize(
    ("reference", "generated"),
    (
        (None, "ticket id A12"),
        ("ticket id A12", None),
        (123, "ticket id A12"),
        ("ticket id A12", 123),
    ),
)
def test_evaluation_requires_string_transcripts(
    reference,
    generated,
):
    with pytest.raises(
        HveeContractError,
        match="string transcripts",
    ):
        evaluate_critical_identifier_fidelity(
            reference_text=reference,
            generated_text=generated,
            profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
        )


def test_extractor_requires_string():
    with pytest.raises(
        HveeContractError,
        match="requires a string",
    ):
        extract_critical_identifier_entities(
            None,
            profile=EN_US_CRITICAL_IDENTIFIER_PROFILE,
        )


def test_metric_and_evaluator_versions_are_pinned():
    assert CRITICAL_IDENTIFIER_METRIC_VERSION == "1.0.0"
    assert CRITICAL_IDENTIFIER_EVALUATOR_VERSION == "1.0.0"

    assert (
        CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR.version
        == "1.0.0"
    )

    assert (
        EN_US_CRITICAL_IDENTIFIER_PROFILE.version
        == "1.0.0"
    )


def test_public_asr_exports_are_available():
    expected_names = (
        "ASRCriticalIdentifierEntity",
        "ASRCriticalIdentifierFidelityEvaluation",
        "ASRCriticalIdentifierFidelityOutcome",
        "ASRCriticalIdentifierFinding",
        "ASRCriticalIdentifierFindingType",
        "ASRCriticalIdentifierProfile",
        "ASRCriticalIdentifierReasonCode",
        "ASRCriticalIdentifierType",
        "CRITICAL_IDENTIFIER_AMBIGUITY_COUNT_METRIC",
        "CRITICAL_IDENTIFIER_APPLICABLE_METRIC",
        "CRITICAL_IDENTIFIER_EVALUATOR_VERSION",
        "CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR",
        "CRITICAL_IDENTIFIER_FINDINGS_METRIC",
        "CRITICAL_IDENTIFIER_GENERATED_COUNT_METRIC",
        "CRITICAL_IDENTIFIER_INSERTION_COUNT_METRIC",
        "CRITICAL_IDENTIFIER_METRICS",
        "CRITICAL_IDENTIFIER_METRIC_VERSION",
        "CRITICAL_IDENTIFIER_OMISSION_COUNT_METRIC",
        "CRITICAL_IDENTIFIER_ORDERING_CHANGE_COUNT_METRIC",
        "CRITICAL_IDENTIFIER_OUTCOME_METRIC",
        "CRITICAL_IDENTIFIER_PRESERVED_METRIC",
        "CRITICAL_IDENTIFIER_REFERENCE_COUNT_METRIC",
        "CRITICAL_IDENTIFIER_SUBSTITUTION_COUNT_METRIC",
        "EN_US_CRITICAL_IDENTIFIER_PROFILE",
        "build_critical_identifier_fidelity_observations",
        "evaluate_critical_identifier_fidelity",
        "extract_critical_identifier_entities",
    )

    for name in expected_names:
        assert hasattr(asr_pack, name)
        assert name in asr_pack.__all__


@pytest.mark.parametrize(
    "surface",
    (
        "AB--12",
        "AB-",
        "AB- 12",
        "AB---CD",
    ),
)
def test_malformed_hyphen_surfaces_do_not_silently_truncate(
    surface,
):
    result = _evaluate(
        f"reference id {surface}",
        f"reference id {surface}",
    )

    assert (
        result.outcome
        == (
            ASRCriticalIdentifierFidelityOutcome
            .INSUFFICIENT_EVIDENCE
        )
    )
    assert result.preserved is None
    assert result.reference_entities == ()
    assert result.generated_entities == ()

    reasons = {
        finding.reason_code
        for finding in result.findings
    }

    assert (
        ASRCriticalIdentifierReasonCode
        .REFERENCE_SURFACE_UNSUPPORTED
        in reasons
    )
    assert (
        ASRCriticalIdentifierReasonCode
        .GENERATED_SURFACE_UNSUPPORTED
        in reasons
    )
