from __future__ import annotations

from dataclasses import replace

import pytest

from hvee.core.contracts import (
    HveeContractError,
    ObservationStatus,
)
from hvee.core.validation import (
    validate_observation_contract,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_APPLICABLE_METRIC,
    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
    CRITICAL_TERMINOLOGY_FINDINGS_METRIC,
    CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_METRICS,
    CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_OUTCOME_METRIC,
    CRITICAL_TERMINOLOGY_PRESERVED_METRIC,
    CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    ASRCriticalTerminologyFidelityOutcome,
    ASRCriticalTerminologyFindingType,
    ASRCriticalTerminologyProfile,
    ASRCriticalTerminologyReasonCode,
    ASRCriticalTerminologyTerm,
    build_critical_terminology_fidelity_observations,
    calculate_critical_terminology_vocabulary_sha256,
    evaluate_critical_terminology_fidelity,
    extract_critical_terminology_entities,
)


POSTGRES = ASRCriticalTerminologyTerm(
    term_key="database.postgresql",
    canonical_text="PostgreSQL",
    accepted_surfaces=(
        "PostgreSQL",
        "Postgres",
    ),
)

MYSQL = ASRCriticalTerminologyTerm(
    term_key="database.mysql",
    canonical_text="MySQL",
    accepted_surfaces=(
        "MySQL",
    ),
)

KUBERNETES = ASRCriticalTerminologyTerm(
    term_key="platform.kubernetes",
    canonical_text="Kubernetes",
    accepted_surfaces=(
        "Kubernetes",
        "K8s",
    ),
)

NODE_JS = ASRCriticalTerminologyTerm(
    term_key="runtime.node-js",
    canonical_text="Node.js",
    accepted_surfaces=(
        "Node.js",
    ),
)

CSHARP = ASRCriticalTerminologyTerm(
    term_key="language.c-sharp",
    canonical_text="C#",
    accepted_surfaces=(
        "C#",
    ),
)

MACHINE_LEARNING = ASRCriticalTerminologyTerm(
    term_key="concept.machine-learning",
    canonical_text="machine learning",
    accepted_surfaces=(
        "machine learning",
    ),
)

LEARNING = ASRCriticalTerminologyTerm(
    term_key="concept.learning",
    canonical_text="learning",
    accepted_surfaces=(
        "learning",
    ),
)


PROFILE = ASRCriticalTerminologyProfile(
    key="hetren.asr.critical-terminology-profile.en-us.test",
    version="1.0.0",
    language="en",
    locale="en-US",
    terms=(
        POSTGRES,
        MYSQL,
        KUBERNETES,
        NODE_JS,
        CSHARP,
        MACHINE_LEARNING,
        LEARNING,
    ),
)


def _evaluate(
    reference: str,
    generated: str,
):
    return evaluate_critical_terminology_fidelity(
        reference_text=reference,
        generated_text=generated,
        profile=PROFILE,
    )


def test_exact_registered_term_is_preserved():
    evaluation = _evaluate(
        "Deploy PostgreSQL today",
        "Deploy PostgreSQL today",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome.PRESERVED
    )
    assert evaluation.preserved is True
    assert len(evaluation.reference_entities) == 1
    assert len(evaluation.generated_entities) == 1

    finding = evaluation.findings[0]

    assert finding.finding_type == (
        ASRCriticalTerminologyFindingType.MATCH
    )
    assert finding.reason_code == (
        ASRCriticalTerminologyReasonCode
        .EXACT_SURFACE_MATCH
    )


def test_case_difference_is_preserved():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "use postgresql",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome.PRESERVED
    )


def test_whitespace_difference_is_preserved():
    evaluation = _evaluate(
        "Use machine learning",
        "Use machine   learning",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome.PRESERVED
    )


def test_registered_alias_is_preserved():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use Postgres",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome.PRESERVED
    )
    assert evaluation.findings[0].reason_code == (
        ASRCriticalTerminologyReasonCode
        .ACCEPTED_ALIAS_EQUIVALENT
    )


def test_unregistered_phonetic_rendering_is_not_equivalent():
    evaluation = _evaluate(
        "Deploy Kubernetes",
        "Deploy Cooper Netties",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome
        .NOT_PRESERVED
    )
    assert evaluation.omission_count == 1
    assert evaluation.substitution_count == 0


def test_registered_wrong_term_is_a_substitution():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use MySQL",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome
        .NOT_PRESERVED
    )
    assert evaluation.substitution_count == 1

    finding = evaluation.findings[0]

    assert finding.finding_type == (
        ASRCriticalTerminologyFindingType
        .SUBSTITUTION
    )
    assert finding.reason_code == (
        ASRCriticalTerminologyReasonCode
        .TERM_SUBSTITUTION
    )


def test_reference_term_can_be_omitted():
    evaluation = _evaluate(
        "Deploy PostgreSQL today",
        "Deploy the database today",
    )

    assert evaluation.omission_count == 1
    assert evaluation.insertion_count == 0
    assert evaluation.preserved is False


def test_generated_term_can_be_inserted():
    evaluation = _evaluate(
        "Deploy the database today",
        "Deploy PostgreSQL today",
    )

    assert evaluation.insertion_count == 1
    assert evaluation.omission_count == 0
    assert evaluation.applicable is True
    assert evaluation.preserved is False


def test_no_registered_terms_is_not_applicable():
    evaluation = _evaluate(
        "Deploy the service",
        "Deploy the service",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome
        .NOT_APPLICABLE
    )
    assert evaluation.applicable is False
    assert evaluation.preserved is None
    assert evaluation.findings == ()


def test_duplicate_terms_are_counted_individually():
    evaluation = _evaluate(
        "Postgres talks to Postgres",
        "Postgres",
    )

    assert len(evaluation.reference_entities) == 2
    assert len(evaluation.generated_entities) == 1
    assert evaluation.omission_count == 1


def test_same_multiset_in_different_order_is_ordering_change():
    evaluation = _evaluate(
        "PostgreSQL then Kubernetes",
        "Kubernetes then PostgreSQL",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome
        .NOT_PRESERVED
    )
    assert evaluation.ordering_change_count == 1
    assert len(evaluation.findings) == 1
    assert evaluation.findings[0].reason_code == (
        ASRCriticalTerminologyReasonCode
        .TERM_ORDER_CHANGED
    )


def test_punctuation_is_semantically_preserved():
    evaluation = _evaluate(
        "Use Node.js with C#",
        "Use Node.js with C#",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome.PRESERVED
    )
    assert len(evaluation.reference_entities) == 2


def test_punctuation_is_not_silently_removed():
    evaluation = _evaluate(
        "Use Node.js",
        "Use Node js",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome
        .NOT_PRESERVED
    )
    assert evaluation.omission_count == 1


def test_csharp_does_not_collapse_to_plain_c():
    evaluation = _evaluate(
        "Use C#",
        "Use C",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome
        .NOT_PRESERVED
    )
    assert evaluation.omission_count == 1


def test_term_is_not_extracted_from_inside_larger_word():
    entities = extract_critical_terminology_entities(
        "PostgreSQLish",
        profile=PROFILE,
    )

    assert entities == ()


def test_longest_registered_surface_wins_at_same_region():
    entities = extract_critical_terminology_entities(
        "machine learning",
        profile=PROFILE,
    )

    assert len(entities) == 1
    assert entities[0].term_key == (
        "concept.machine-learning"
    )


def test_source_span_retains_original_case():
    text = "Please deploy POSTGRES now"

    entities = extract_critical_terminology_entities(
        text,
        profile=PROFILE,
    )

    assert len(entities) == 1
    entity = entities[0]

    assert entity.text == "POSTGRES"
    assert text[
        entity.span_start:entity.span_end
    ] == "POSTGRES"


def test_vocabulary_hash_is_deterministic():
    first = (
        calculate_critical_terminology_vocabulary_sha256(
            PROFILE
        )
    )
    second = (
        calculate_critical_terminology_vocabulary_sha256(
            PROFILE
        )
    )

    assert first == second
    assert len(first) == 64


def test_vocabulary_hash_is_independent_of_term_order():
    reordered = ASRCriticalTerminologyProfile(
        key=PROFILE.key,
        version=PROFILE.version,
        language=PROFILE.language,
        locale=PROFILE.locale,
        terms=tuple(
            reversed(PROFILE.terms)
        ),
    )

    assert (
        calculate_critical_terminology_vocabulary_sha256(
            reordered
        )
        == calculate_critical_terminology_vocabulary_sha256(
            PROFILE
        )
    )


def test_vocabulary_hash_changes_when_vocabulary_changes():
    changed_postgres = ASRCriticalTerminologyTerm(
        term_key=POSTGRES.term_key,
        canonical_text=POSTGRES.canonical_text,
        accepted_surfaces=(
            "PostgreSQL",
            "Postgres",
            "PG",
        ),
    )

    changed = ASRCriticalTerminologyProfile(
        key=PROFILE.key,
        version=PROFILE.version,
        language=PROFILE.language,
        locale=PROFILE.locale,
        terms=(
            changed_postgres,
            *PROFILE.terms[1:],
        ),
    )

    assert (
        calculate_critical_terminology_vocabulary_sha256(
            changed
        )
        != calculate_critical_terminology_vocabulary_sha256(
            PROFILE
        )
    )


def test_profile_rejects_surface_collision_between_terms():
    one = ASRCriticalTerminologyTerm(
        term_key="term.one",
        canonical_text="Alpha",
        accepted_surfaces=(
            "Alpha",
        ),
    )

    two = ASRCriticalTerminologyTerm(
        term_key="term.two",
        canonical_text="alpha",
        accepted_surfaces=(
            "alpha",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="cannot map to multiple terms",
    ):
        ASRCriticalTerminologyProfile(
            key="hetren.test.terminology",
            version="1.0.0",
            language="en",
            locale="en-US",
            terms=(one, two),
        )


def test_term_rejects_duplicate_normalized_aliases():
    with pytest.raises(
        HveeContractError,
        match="unique after normalization",
    ):
        ASRCriticalTerminologyTerm(
            term_key="database.postgresql",
            canonical_text="PostgreSQL",
            accepted_surfaces=(
                "PostgreSQL",
                "postgresql",
            ),
        )


def test_term_requires_canonical_text_to_be_accepted():
    with pytest.raises(
        HveeContractError,
        match="canonical text must be an accepted surface",
    ):
        ASRCriticalTerminologyTerm(
            term_key="database.postgresql",
            canonical_text="PostgreSQL",
            accepted_surfaces=(
                "Postgres",
            ),
        )


def test_profile_rejects_duplicate_term_keys():
    duplicate = ASRCriticalTerminologyTerm(
        term_key=POSTGRES.term_key,
        canonical_text="PostgreSQL Database",
        accepted_surfaces=(
            "PostgreSQL Database",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="term keys must be unique",
    ):
        ASRCriticalTerminologyProfile(
            key="hetren.test.terminology",
            version="1.0.0",
            language="en",
            locale="en-US",
            terms=(
                POSTGRES,
                duplicate,
            ),
        )


@pytest.mark.parametrize(
    ("language", "locale"),
    (
        ("fr", "en-US"),
        ("en", "en-GB"),
    ),
)
def test_profile_v1_rejects_unsupported_language_or_locale(
    language,
    locale,
):
    with pytest.raises(HveeContractError):
        ASRCriticalTerminologyProfile(
            key="hetren.test.terminology",
            version="1.0.0",
            language=language,
            locale=locale,
            terms=(POSTGRES,),
        )


@pytest.mark.parametrize(
    "term_key",
    (
        "",
        "PostgreSQL",
        "database postgresql",
        ".database",
    ),
)
def test_term_key_must_be_canonical_identifier(
    term_key,
):
    with pytest.raises(HveeContractError):
        ASRCriticalTerminologyTerm(
            term_key=term_key,
            canonical_text="PostgreSQL",
            accepted_surfaces=(
                "PostgreSQL",
            ),
        )


def test_evaluation_requires_string_transcripts():
    with pytest.raises(
        HveeContractError,
        match="requires string transcripts",
    ):
        evaluate_critical_terminology_fidelity(
            reference_text=123,
            generated_text="PostgreSQL",
            profile=PROFILE,
        )


def test_observations_cover_all_versioned_metrics():
    evaluation = _evaluate(
        "Use PostgreSQL on Kubernetes",
        "Use Postgres on Kubernetes",
    )

    observations = (
        build_critical_terminology_fidelity_observations(
            evaluation,
            profile=PROFILE,
        )
    )

    assert len(observations) == len(
        CRITICAL_TERMINOLOGY_METRICS
    )

    by_key = {
        observation.metric_key: observation
        for observation in observations
    }

    assert set(by_key) == {
        metric.key
        for metric in CRITICAL_TERMINOLOGY_METRICS
    }

    for metric in CRITICAL_TERMINOLOGY_METRICS:
        validate_observation_contract(
            metric=metric,
            evaluator=(
                CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR
            ),
            observation=by_key[metric.key],
        )


def test_observation_values_match_evaluation():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use MySQL",
    )

    observations = (
        build_critical_terminology_fidelity_observations(
            evaluation,
            profile=PROFILE,
        )
    )

    by_key = {
        observation.metric_key: observation
        for observation in observations
    }

    assert by_key[
        CRITICAL_TERMINOLOGY_APPLICABLE_METRIC.key
    ].value is True

    assert by_key[
        CRITICAL_TERMINOLOGY_PRESERVED_METRIC.key
    ].value is False

    assert by_key[
        CRITICAL_TERMINOLOGY_OUTCOME_METRIC.key
    ].value == "not_preserved"

    assert by_key[
        CRITICAL_TERMINOLOGY_REFERENCE_COUNT_METRIC.key
    ].value == 1

    assert by_key[
        CRITICAL_TERMINOLOGY_GENERATED_COUNT_METRIC.key
    ].value == 1

    assert by_key[
        CRITICAL_TERMINOLOGY_SUBSTITUTION_COUNT_METRIC.key
    ].value == 1

    assert by_key[
        CRITICAL_TERMINOLOGY_OMISSION_COUNT_METRIC.key
    ].value == 0

    assert by_key[
        CRITICAL_TERMINOLOGY_INSERTION_COUNT_METRIC.key
    ].value == 0

    assert by_key[
        CRITICAL_TERMINOLOGY_ORDERING_CHANGE_COUNT_METRIC.key
    ].value == 0

    assert by_key[
        CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
    ].value == evaluation.vocabulary_sha256

    assert isinstance(
        by_key[
            CRITICAL_TERMINOLOGY_FINDINGS_METRIC.key
        ].value,
        list,
    )


def test_not_applicable_preserved_observation_abstains():
    evaluation = _evaluate(
        "ordinary transcript",
        "ordinary transcript",
    )

    observations = (
        build_critical_terminology_fidelity_observations(
            evaluation,
            profile=PROFILE,
        )
    )

    by_key = {
        observation.metric_key: observation
        for observation in observations
    }

    preserved = by_key[
        CRITICAL_TERMINOLOGY_PRESERVED_METRIC.key
    ]

    assert preserved.status == (
        ObservationStatus.ABSTAINED
    )
    assert preserved.value is None
    assert preserved.status_detail == (
        "not_applicable"
    )


def test_findings_retain_vocabulary_provenance():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use MySQL",
    )

    assert evaluation.findings

    for finding in evaluation.findings:
        assert finding.profile_key == PROFILE.key
        assert finding.profile_version == PROFILE.version
        assert finding.vocabulary_sha256 == (
            evaluation.vocabulary_sha256
        )


def test_observation_builder_rejects_forged_outcome():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use MySQL",
    )

    forged = replace(
        evaluation,
        outcome=(
            ASRCriticalTerminologyFidelityOutcome
            .PRESERVED
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="inconsistent with findings",
    ):
        build_critical_terminology_fidelity_observations(
            forged,
            profile=PROFILE,
        )


def test_observation_builder_rejects_forged_provenance():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use MySQL",
    )

    forged_finding = replace(
        evaluation.findings[0],
        vocabulary_sha256=("0" * 64),
    )

    forged = replace(
        evaluation,
        findings=(
            forged_finding,
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="retain vocabulary provenance",
    ):
        build_critical_terminology_fidelity_observations(
            forged,
            profile=PROFILE,
        )


def test_generated_only_registered_term_is_applicable_failure():
    evaluation = _evaluate(
        "The database is ready",
        "PostgreSQL is ready",
    )

    assert evaluation.applicable is True
    assert evaluation.preserved is False
    assert evaluation.insertion_count == 1


def test_nfkc_equivalent_surface_is_preserved():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use ＰｏｓｔｇｒｅＳＱＬ",
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome.PRESERVED
    )
    assert evaluation.preserved is True


def test_profile_rejects_surface_collision_after_nfkc():
    one = ASRCriticalTerminologyTerm(
        term_key="term.ascii",
        canonical_text="Alpha",
        accepted_surfaces=(
            "Alpha",
        ),
    )

    two = ASRCriticalTerminologyTerm(
        term_key="term.fullwidth",
        canonical_text="Ａｌｐｈａ",
        accepted_surfaces=(
            "Ａｌｐｈａ",
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="cannot map to multiple terms",
    ):
        ASRCriticalTerminologyProfile(
            key="hetren.test.terminology",
            version="1.0.0",
            language="en",
            locale="en-US",
            terms=(
                one,
                two,
            ),
        )


def test_extraction_is_independent_of_profile_term_order():
    reordered = ASRCriticalTerminologyProfile(
        key=PROFILE.key,
        version=PROFILE.version,
        language=PROFILE.language,
        locale=PROFILE.locale,
        terms=tuple(
            reversed(PROFILE.terms)
        ),
    )

    original_entities = (
        extract_critical_terminology_entities(
            "Use machine learning with PostgreSQL",
            profile=PROFILE,
        )
    )

    reordered_entities = (
        extract_critical_terminology_entities(
            "Use machine learning with PostgreSQL",
            profile=reordered,
        )
    )

    assert tuple(
        entity.term_key
        for entity in original_entities
    ) == tuple(
        entity.term_key
        for entity in reordered_entities
    )


def test_symbol_term_does_not_match_inside_larger_token():
    entities = (
        extract_critical_terminology_entities(
            "C#script",
            profile=PROFILE,
        )
    )

    assert entities == ()


def test_finding_rejects_reason_code_inconsistent_with_type():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use PostgreSQL",
    )

    with pytest.raises(
        HveeContractError,
        match="reason code is inconsistent",
    ):
        replace(
            evaluation.findings[0],
            reason_code=(
                ASRCriticalTerminologyReasonCode
                .TERM_SUBSTITUTION
            ),
        )


def test_observation_builder_rejects_different_bound_vocabulary():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use PostgreSQL",
    )

    changed_postgres = ASRCriticalTerminologyTerm(
        term_key=POSTGRES.term_key,
        canonical_text=POSTGRES.canonical_text,
        accepted_surfaces=(
            "PostgreSQL",
            "Postgres",
            "PG",
        ),
    )

    different_profile = (
        ASRCriticalTerminologyProfile(
            key=PROFILE.key,
            version=PROFILE.version,
            language=PROFILE.language,
            locale=PROFILE.locale,
            terms=(
                changed_postgres,
                *PROFILE.terms[1:],
            ),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="exact vocabulary profile",
    ):
        build_critical_terminology_fidelity_observations(
            evaluation,
            profile=different_profile,
        )


def test_nfkc_composed_and_decomposed_surface_are_equivalent():
    cafe = ASRCriticalTerminologyTerm(
        term_key="term.cafe",
        canonical_text="Café",
        accepted_surfaces=(
            "Café",
        ),
    )

    profile = ASRCriticalTerminologyProfile(
        key="hetren.test.terminology.cafe",
        version="1.0.0",
        language="en",
        locale="en-US",
        terms=(cafe,),
    )

    evaluation = (
        evaluate_critical_terminology_fidelity(
            reference_text="Visit Café",
            generated_text="Visit Cafe\u0301",
            profile=profile,
        )
    )

    assert evaluation.outcome == (
        ASRCriticalTerminologyFidelityOutcome.PRESERVED
    )
    assert evaluation.generated_entities[0].text == (
        "Cafe\u0301"
    )


def test_observation_builder_rejects_missing_evidence_finding():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use the database",
    )

    forged = replace(
        evaluation,
        findings=(),
        outcome=(
            ASRCriticalTerminologyFidelityOutcome
            .PRESERVED
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="account for every extracted entity",
    ):
        build_critical_terminology_fidelity_observations(
            forged,
            profile=PROFILE,
        )


def test_observation_builder_rejects_match_between_different_terms():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use MySQL",
    )

    forged_finding = replace(
        evaluation.findings[0],
        finding_type=(
            ASRCriticalTerminologyFindingType.MATCH
        ),
        reason_code=(
            ASRCriticalTerminologyReasonCode
            .EXACT_SURFACE_MATCH
        ),
    )

    forged = replace(
        evaluation,
        findings=(forged_finding,),
        outcome=(
            ASRCriticalTerminologyFidelityOutcome
            .PRESERVED
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="match must preserve term identity",
    ):
        build_critical_terminology_fidelity_observations(
            forged,
            profile=PROFILE,
        )


def test_observation_builder_rejects_substitution_of_same_term():
    evaluation = _evaluate(
        "Use PostgreSQL",
        "Use Postgres",
    )

    forged_finding = replace(
        evaluation.findings[0],
        finding_type=(
            ASRCriticalTerminologyFindingType
            .SUBSTITUTION
        ),
        reason_code=(
            ASRCriticalTerminologyReasonCode
            .TERM_SUBSTITUTION
        ),
    )

    forged = replace(
        evaluation,
        findings=(forged_finding,),
        outcome=(
            ASRCriticalTerminologyFidelityOutcome
            .NOT_PRESERVED
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="requires distinct term identities",
    ):
        build_critical_terminology_fidelity_observations(
            forged,
            profile=PROFILE,
        )


def test_observation_builder_rejects_false_ordering_change():
    evaluation = _evaluate(
        "PostgreSQL then Kubernetes",
        "PostgreSQL then MySQL",
    )

    substitution = next(
        finding
        for finding in evaluation.findings
        if finding.finding_type
        == ASRCriticalTerminologyFindingType.SUBSTITUTION
    )

    forged_finding = replace(
        substitution,
        finding_type=(
            ASRCriticalTerminologyFindingType
            .ORDERING_CHANGE
        ),
        reason_code=(
            ASRCriticalTerminologyReasonCode
            .TERM_ORDER_CHANGED
        ),
    )

    forged = replace(
        evaluation,
        findings=(forged_finding,),
    )

    with pytest.raises(
        HveeContractError,
        match="same reordered critical-term multiset",
    ):
        build_critical_terminology_fidelity_observations(
            forged,
            profile=PROFILE,
        )


def test_v1_outcome_surface_contains_only_reachable_states():
    assert {
        outcome.value
        for outcome in ASRCriticalTerminologyFidelityOutcome
    } == {
        "preserved",
        "not_preserved",
        "not_applicable",
    }
