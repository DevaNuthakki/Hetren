from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from hvee.core.contracts import (
    HveeContractError,
    MetricValueType,
    Observation,
    ObservationStatus,
)
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialCondition,
    ASRAdversarialDurationBucket,
    ASRAdversarialLongContextPosition,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSemanticLoad,
    ASRAdversarialSpeakingRate,
    ASRAdversarialSuiteDefinition,
    build_asr_adversarial_evidence_v1,
)
from hvee.packs.asr.adversarial_execution_evidence import (
    ASRAdversarialExecutionDefinition,
    ASRAdversarialExecutionStatus,
    ASRAdversarialSemanticObservations,
    ASRAdversarialTerminologyBinding,
    ASRAdversarialTerminologyState,
    build_asr_adversarial_execution_evidence_v1,
    calculate_asr_adversarial_execution_evidence_sha256,
    calculate_asr_adversarial_transcript_sha256,
    verify_asr_adversarial_execution_evidence_v1,
)
from hvee.packs.asr.critical_identifier_fidelity import (
    CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
    CRITICAL_IDENTIFIER_METRICS,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    CRITICAL_NUMBER_METRICS,
)
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
    CRITICAL_TERMINOLOGY_METRICS,
    CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC,
    ASRCriticalTerminologyProfile,
    ASRCriticalTerminologyTerm,
    calculate_critical_terminology_vocabulary_sha256,
)


def _sha(character: str) -> str:
    return character * 64


def _suite(
    *,
    terminology_count: int = 1,
):
    total = 1 + 1 + terminology_count

    reference = (
        "Administer Cardiovex 250 mg "
        "using confirmation code AB-123."
        if terminology_count
        else (
            "Administer 250 mg using "
            "confirmation code AB-123."
        )
    )

    case = ASRAdversarialCase(
        case_id="qualification.case-one",
        audio_asset_sha256=_sha("a"),
        reference_transcript=reference,
        condition=ASRAdversarialCondition(
            channel=ASRAdversarialChannel.TELEPHONY,
            codec=ASRAdversarialCodec.MULAW,
            sample_rate_hz=8_000,
            microphone_class="headset",
            noise=(
                ASRAdversarialNoiseCondition.MODERATE
            ),
            speaking_rate=(
                ASRAdversarialSpeakingRate.FAST
            ),
            speech_variety_key="declared.fixture-a",
            overlap=(
                ASRAdversarialOverlapCondition.NONE
            ),
            duration=(
                ASRAdversarialDurationBucket.SHORT
            ),
        ),
        semantic_load=ASRAdversarialSemanticLoad(
            critical_number_count=1,
            critical_identifier_count=1,
            critical_terminology_count=(
                terminology_count
            ),
            spoken_number_variation=False,
            multiple_critical_items=(
                total > 1
            ),
            duplicate_critical_items=False,
            ordering_challenge=False,
            long_context_position=(
                ASRAdversarialLongContextPosition.NONE
            ),
        ),
        description=(
            "Adversarial execution evidence fixture."
        ),
        tags=("asr", "telephony"),
    )

    definition = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(case,),
    )

    return (
        definition,
        build_asr_adversarial_evidence_v1(
            definition
        ),
    )


def _value_for_metric(
    metric,
    *,
    vocabulary_sha256: str,
):
    if (
        metric.key
        == CRITICAL_TERMINOLOGY_VOCABULARY_SHA256_METRIC.key
    ):
        return vocabulary_sha256

    if metric.value_type == MetricValueType.BOOLEAN:
        return True

    if metric.value_type == MetricValueType.INTEGER:
        return 0

    if metric.value_type == MetricValueType.NUMBER:
        return 0.0

    if metric.value_type == MetricValueType.STRING:
        return "preserved"

    if metric.value_type == MetricValueType.JSON:
        return []

    raise AssertionError(metric.value_type)


def _family(
    metrics,
    evaluator,
    *,
    vocabulary_sha256: str = _sha("c"),
):
    return tuple(
        Observation(
            metric_key=metric.key,
            metric_version=metric.version,
            evaluator_key=evaluator.key,
            evaluator_version=evaluator.version,
            evaluation_type=evaluator.evaluation_type,
            status=ObservationStatus.SUCCESS,
            value_type=metric.value_type,
            value=_value_for_metric(
                metric,
                vocabulary_sha256=(
                    vocabulary_sha256
                ),
            ),
        )
        for metric in metrics
    )


def _semantic(
    *,
    configured: bool = True,
    vocabulary_sha256: str = _sha("c"),
):
    return ASRAdversarialSemanticObservations(
        critical_number=_family(
            CRITICAL_NUMBER_METRICS,
            CRITICAL_NUMBER_FIDELITY_EVALUATOR,
        ),
        critical_identifier=_family(
            CRITICAL_IDENTIFIER_METRICS,
            CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
        ),
        critical_terminology=(
            _family(
                CRITICAL_TERMINOLOGY_METRICS,
                CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
                vocabulary_sha256=(
                    vocabulary_sha256
                ),
            )
            if configured
            else ()
        ),
    )


def _terminology_profile(
    *,
    profile_key: str = "qualification.terminology-profile",
    canonical_text: str = "Cardiovex",
) -> ASRCriticalTerminologyProfile:
    return ASRCriticalTerminologyProfile(
        key=profile_key,
        version="1.0.0",
        language="en",
        locale="en-US",
        terms=(
            ASRCriticalTerminologyTerm(
                term_key="medication.cardiovex",
                canonical_text=canonical_text,
                accepted_surfaces=(
                    canonical_text,
                ),
            ),
        ),
    )


def _terminology(
    *,
    configured: bool = True,
    profile: ASRCriticalTerminologyProfile | None = None,
):
    if not configured:
        return ASRAdversarialTerminologyBinding(
            state=(
                ASRAdversarialTerminologyState
                .NOT_CONFIGURED
            ),
        )

    selected_profile = (
        profile
        if profile is not None
        else _terminology_profile()
    )

    return ASRAdversarialTerminologyBinding(
        state=(
            ASRAdversarialTerminologyState.CONFIGURED
        ),
        profile=selected_profile,
    )


def _completed_definition(
    *,
    configured: bool = True,
    profile: ASRCriticalTerminologyProfile | None = None,
):
    terminology = _terminology(
        configured=configured,
        profile=profile,
    )

    vocabulary_sha256 = (
        terminology.vocabulary_sha256
        if terminology.vocabulary_sha256 is not None
        else _sha("c")
    )

    return ASRAdversarialExecutionDefinition(
        execution_id="qualification.execution-one",
        case_id="qualification.case-one",
        provider_key="faster_whisper",
        model_key="large-v3-turbo",
        execution_environment_sha256=_sha("d"),
        status=ASRAdversarialExecutionStatus.COMPLETED,
        terminology=terminology,
        generated_transcript_sha256=(
            calculate_asr_adversarial_transcript_sha256(
                "Administer Cardiovex 250 mg "
                "using confirmation code AB-123."
            )
        ),
        semantic_observations=_semantic(
            configured=configured,
            vocabulary_sha256=vocabulary_sha256,
        ),
    )


def test_completed_execution_is_deterministic_and_verifiable():
    suite, suite_evidence = _suite()
    definition = _completed_definition()

    first = (
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )
    second = (
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    assert first == second

    assert (
        verify_asr_adversarial_execution_evidence_v1(
            payload=first.payload,
            expected_sha256=first.sha256,
            definition=definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
        == first
    )


def test_artifact_binds_sealed_case_without_raw_audio_or_transcript():
    suite, suite_evidence = _suite()
    evidence = (
        build_asr_adversarial_execution_evidence_v1(
            _completed_definition(),
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    assert evidence.payload["suite"]["sha256"] == (
        suite_evidence.sha256
    )
    assert evidence.payload["case"] == {
        "case_id": "qualification.case-one",
        "audio_asset_sha256": _sha("a"),
    }

    serialized = str(evidence.payload)

    assert "Administer Cardiovex" not in serialized
    assert "audio_file_path" not in serialized
    assert "generated_transcript" in serialized


def test_completed_semantic_evidence_has_exact_family_counts():
    suite, suite_evidence = _suite()

    evidence = (
        build_asr_adversarial_execution_evidence_v1(
            _completed_definition(),
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    semantic = evidence.payload[
        "semantic_evidence"
    ]

    assert semantic["critical_number"]["count"] == 10
    assert semantic["critical_identifier"]["count"] == 11
    assert semantic["critical_terminology"]["count"] == 11


def test_not_configured_terminology_allows_empty_family():
    suite, suite_evidence = _suite(
        terminology_count=0
    )
    definition = _completed_definition(
        configured=False
    )

    evidence = (
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    assert evidence.payload[
        "semantic_configuration"
    ]["critical_terminology"] == {
        "state": "not_configured",
        "profile": None,
    }

    assert evidence.payload[
        "semantic_evidence"
    ]["critical_terminology"] == {
        "count": 0,
        "observations": [],
    }


def test_declared_terminology_content_requires_configuration():
    suite, suite_evidence = _suite(
        terminology_count=1
    )

    definition = _completed_definition(
        configured=False
    )

    with pytest.raises(
        HveeContractError,
        match="requires configured vocabulary",
    ):
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_reordered_family_is_rejected():
    observations = _family(
        CRITICAL_NUMBER_METRICS,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    )

    with pytest.raises(
        HveeContractError,
        match="canonical scientific identity and order",
    ):
        ASRAdversarialSemanticObservations(
            critical_number=tuple(
                reversed(observations)
            ),
            critical_identifier=_family(
                CRITICAL_IDENTIFIER_METRICS,
                CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
            ),
            critical_terminology=_family(
                CRITICAL_TERMINOLOGY_METRICS,
                CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
            ),
        )


def test_wrong_evaluator_identity_is_rejected():
    observations = list(
        _family(
            CRITICAL_NUMBER_METRICS,
            CRITICAL_NUMBER_FIDELITY_EVALUATOR,
        )
    )

    observations[0] = replace(
        observations[0],
        evaluator_key="hetren.asr.wrong-evaluator",
    )

    with pytest.raises(
        HveeContractError,
        match="canonical scientific identity",
    ):
        ASRAdversarialSemanticObservations(
            critical_number=tuple(
                observations
            ),
            critical_identifier=_family(
                CRITICAL_IDENTIFIER_METRICS,
                CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
            ),
            critical_terminology=_family(
                CRITICAL_TERMINOLOGY_METRICS,
                CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
            ),
        )


def test_terminology_vocabulary_mismatch_is_rejected():
    binding_profile = _terminology_profile(
        canonical_text="Cardiovex",
    )
    observation_profile = _terminology_profile(
        canonical_text="Neurodex",
    )

    observation_vocabulary_sha256 = (
        calculate_critical_terminology_vocabulary_sha256(
            observation_profile
        )
    )

    with pytest.raises(
        HveeContractError,
        match="does not match configured vocabulary",
    ):
        ASRAdversarialExecutionDefinition(
            execution_id="qualification.execution-one",
            case_id="qualification.case-one",
            provider_key="faster_whisper",
            model_key="large-v3-turbo",
            execution_environment_sha256=_sha("d"),
            status=(
                ASRAdversarialExecutionStatus.COMPLETED
            ),
            terminology=_terminology(
                profile=binding_profile,
            ),
            generated_transcript_sha256=_sha("f"),
            semantic_observations=_semantic(
                vocabulary_sha256=(
                    observation_vocabulary_sha256
                ),
            ),
        )


def test_completed_execution_requires_transcript_and_semantics():
    with pytest.raises(
        HveeContractError,
        match="generated transcript commitment",
    ):
        ASRAdversarialExecutionDefinition(
            execution_id="qualification.execution-one",
            case_id="qualification.case-one",
            provider_key="faster_whisper",
            model_key="large-v3-turbo",
            execution_environment_sha256=_sha("d"),
            status=(
                ASRAdversarialExecutionStatus.COMPLETED
            ),
            terminology=_terminology(),
            generated_transcript_sha256=None,
            semantic_observations=_semantic(),
        )

    with pytest.raises(
        HveeContractError,
        match="requires semantic observations",
    ):
        ASRAdversarialExecutionDefinition(
            execution_id="qualification.execution-one",
            case_id="qualification.case-one",
            provider_key="faster_whisper",
            model_key="large-v3-turbo",
            execution_environment_sha256=_sha("d"),
            status=(
                ASRAdversarialExecutionStatus.COMPLETED
            ),
            terminology=_terminology(),
            generated_transcript_sha256=_sha("f"),
            semantic_observations=None,
        )


def test_failed_execution_requires_detail_and_contains_no_semantics():
    failed = ASRAdversarialExecutionDefinition(
        execution_id="qualification.execution-one",
        case_id="qualification.case-one",
        provider_key="faster_whisper",
        model_key="large-v3-turbo",
        execution_environment_sha256=_sha("d"),
        status=ASRAdversarialExecutionStatus.FAILED,
        terminology=_terminology(),
        generated_transcript_sha256=None,
        semantic_observations=None,
        status_detail="provider execution failed",
    )

    suite, suite_evidence = _suite()

    evidence = (
        build_asr_adversarial_execution_evidence_v1(
            failed,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    assert evidence.payload[
        "execution"
    ]["generated_transcript"] is None

    assert evidence.payload[
        "semantic_evidence"
    ] is None

    with pytest.raises(
        HveeContractError,
        match="requires status detail",
    ):
        replace(
            failed,
            status_detail=None,
        )


def test_rehashed_tampering_still_fails_against_definition():
    suite, suite_evidence = _suite()
    definition = _completed_definition()

    evidence = (
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    tampered = copy.deepcopy(
        evidence.payload
    )

    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    tampered_sha256 = (
        calculate_asr_adversarial_execution_evidence_sha256(
            tampered
        )
    )

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        verify_asr_adversarial_execution_evidence_v1(
            payload=tampered,
            expected_sha256=tampered_sha256,
            definition=definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_unknown_case_fails_closed():
    suite, suite_evidence = _suite()

    definition = replace(
        _completed_definition(),
        case_id="qualification.unknown-case",
    )

    with pytest.raises(
        HveeContractError,
        match="does not exist in the sealed suite",
    ):
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_terminology_identity_is_derived_from_profile():
    profile = _terminology_profile()

    binding = _terminology(
        profile=profile,
    )

    assert binding.profile_key == profile.key
    assert (
        binding.profile_version
        == profile.version
    )
    assert binding.vocabulary_sha256 == (
        calculate_critical_terminology_vocabulary_sha256(
            profile
        )
    )


def test_not_configured_terminology_rejects_profile():
    with pytest.raises(
        HveeContractError,
        match="cannot contain a profile",
    ):
        ASRAdversarialTerminologyBinding(
            state=(
                ASRAdversarialTerminologyState
                .NOT_CONFIGURED
            ),
            profile=_terminology_profile(),
        )


def test_non_success_semantic_observation_is_preserved():
    number_observations = list(
        _family(
            CRITICAL_NUMBER_METRICS,
            CRITICAL_NUMBER_FIDELITY_EVALUATOR,
        )
    )

    preserved_index = next(
        index
        for index, observation
        in enumerate(number_observations)
        if observation.metric_key
        == "asr.critical-number.preserved.en-us"
    )

    original = number_observations[
        preserved_index
    ]

    number_observations[
        preserved_index
    ] = replace(
        original,
        status=ObservationStatus.ABSTAINED,
        value=None,
        status_detail="ambiguous",
    )

    terminology = _terminology()

    semantic = ASRAdversarialSemanticObservations(
        critical_number=tuple(
            number_observations
        ),
        critical_identifier=_family(
            CRITICAL_IDENTIFIER_METRICS,
            CRITICAL_IDENTIFIER_FIDELITY_EVALUATOR,
        ),
        critical_terminology=_family(
            CRITICAL_TERMINOLOGY_METRICS,
            CRITICAL_TERMINOLOGY_FIDELITY_EVALUATOR,
            vocabulary_sha256=(
                terminology.vocabulary_sha256
            ),
        ),
    )

    definition = ASRAdversarialExecutionDefinition(
        execution_id="qualification.execution-one",
        case_id="qualification.case-one",
        provider_key="faster_whisper",
        model_key="large-v3-turbo",
        execution_environment_sha256=_sha("d"),
        status=ASRAdversarialExecutionStatus.COMPLETED,
        terminology=terminology,
        generated_transcript_sha256=_sha("f"),
        semantic_observations=semantic,
    )

    suite, suite_evidence = _suite()

    evidence = (
        build_asr_adversarial_execution_evidence_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    preserved = next(
        observation
        for observation
        in evidence.payload[
            "semantic_evidence"
        ]["critical_number"]["observations"]
        if observation["metric"]["key"]
        == "asr.critical-number.preserved.en-us"
    )

    assert preserved["status"] == "abstained"
    assert preserved["value"] is None
    assert (
        preserved["status_detail"]
        == "ambiguous"
    )


def test_adversarial_execution_contract_is_publicly_exported():
    import hvee.packs.asr as asr

    expected_exports = {
        "ASR_ADVERSARIAL_EXECUTION_EVIDENCE_KEY",
        "ASR_ADVERSARIAL_EXECUTION_EVIDENCE_SCHEMA_VERSION",
        "ASR_ADVERSARIAL_EXECUTION_EVIDENCE_VERSION",
        "ASR_ADVERSARIAL_TRANSCRIPT_COMMITMENT_SCHEME",
        "ASRAdversarialExecutionDefinition",
        "ASRAdversarialExecutionEvidenceBundle",
        "ASRAdversarialExecutionStatus",
        "ASRAdversarialSemanticObservations",
        "ASRAdversarialTerminologyBinding",
        "ASRAdversarialTerminologyState",
        "build_asr_adversarial_execution_evidence_v1",
        "calculate_asr_adversarial_execution_evidence_sha256",
        "calculate_asr_adversarial_transcript_sha256",
        "verify_asr_adversarial_execution_evidence_v1",
    }

    for name in expected_exports:
        assert hasattr(asr, name)
        assert name in asr.__all__
