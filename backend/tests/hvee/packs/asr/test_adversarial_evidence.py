from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import HveeContractError
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
    verify_asr_adversarial_evidence_v1,
)


def _sha(character: str) -> str:
    return character * 64


def _condition(
    *,
    channel: ASRAdversarialChannel = (
        ASRAdversarialChannel.CLEAN
    ),
    codec: ASRAdversarialCodec = (
        ASRAdversarialCodec.LINEAR_PCM
    ),
    sample_rate_hz: int = 16_000,
    noise: ASRAdversarialNoiseCondition = (
        ASRAdversarialNoiseCondition.NONE
    ),
    speaking_rate: ASRAdversarialSpeakingRate = (
        ASRAdversarialSpeakingRate.NORMAL
    ),
    overlap: ASRAdversarialOverlapCondition = (
        ASRAdversarialOverlapCondition.NONE
    ),
    duration: ASRAdversarialDurationBucket = (
        ASRAdversarialDurationBucket.SHORT
    ),
) -> ASRAdversarialCondition:
    return ASRAdversarialCondition(
        channel=channel,
        codec=codec,
        sample_rate_hz=sample_rate_hz,
        microphone_class="headset",
        noise=noise,
        speaking_rate=speaking_rate,
        speech_variety_key="declared.fixture-a",
        overlap=overlap,
        duration=duration,
    )


def _semantic(
    *,
    numbers: int = 1,
    identifiers: int = 1,
    terminology: int = 1,
    spoken_number_variation: bool = False,
    duplicate: bool = False,
    ordering: bool = False,
    position: ASRAdversarialLongContextPosition = (
        ASRAdversarialLongContextPosition.NONE
    ),
    control: bool = False,
) -> ASRAdversarialSemanticLoad:
    total = (
        numbers
        + identifiers
        + terminology
    )

    return ASRAdversarialSemanticLoad(
        critical_number_count=numbers,
        critical_identifier_count=identifiers,
        critical_terminology_count=terminology,
        spoken_number_variation=(
            spoken_number_variation
        ),
        multiple_critical_items=(
            total > 1
        ),
        duplicate_critical_items=duplicate,
        ordering_challenge=ordering,
        long_context_position=position,
        control_case=control,
    )


def _case(
    *,
    case_id: str,
    audio_sha256: str,
    condition: ASRAdversarialCondition,
    semantic: ASRAdversarialSemanticLoad,
) -> ASRAdversarialCase:
    return ASRAdversarialCase(
        case_id=case_id,
        audio_asset_sha256=audio_sha256,
        reference_transcript=(
            "Administer Cardiovex 250 mg "
            "using confirmation code AB-123."
        ),
        condition=condition,
        semantic_load=semantic,
        description=(
            "Adversarial ASR development fixture."
        ),
        tags=(
            "asr",
            "semantic",
        ),
    )


def _suite() -> ASRAdversarialSuiteDefinition:
    clean = _case(
        case_id="control.clean",
        audio_sha256=_sha("a"),
        condition=_condition(),
        semantic=_semantic(),
    )

    compound = _case(
        case_id="stress.telephony-compound",
        audio_sha256=_sha("b"),
        condition=_condition(
            channel=(
                ASRAdversarialChannel.TELEPHONY
            ),
            codec=ASRAdversarialCodec.MULAW,
            sample_rate_hz=8_000,
            noise=(
                ASRAdversarialNoiseCondition.MODERATE
            ),
            speaking_rate=(
                ASRAdversarialSpeakingRate.FAST
            ),
            overlap=(
                ASRAdversarialOverlapCondition.CRITICAL
            ),
            duration=(
                ASRAdversarialDurationBucket.LONG
            ),
        ),
        semantic=_semantic(
            numbers=2,
            identifiers=1,
            terminology=1,
            spoken_number_variation=True,
            ordering=True,
            position=(
                ASRAdversarialLongContextPosition.LATE
            ),
        ),
    )

    return ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            clean,
            compound,
        ),
    )


def test_build_is_deterministic_and_verifiable():
    definition = _suite()

    first = build_asr_adversarial_evidence_v1(
        definition
    )
    second = build_asr_adversarial_evidence_v1(
        definition
    )

    assert first == second

    verified = verify_asr_adversarial_evidence_v1(
        payload=first.payload,
        expected_sha256=first.sha256,
        definition=definition,
    )

    assert verified == first


def test_compound_case_coverage_is_reported():
    evidence = build_asr_adversarial_evidence_v1(
        _suite()
    )

    coverage = evidence.payload["coverage"]

    assert coverage == {
        "total_cases": 2,
        "audio": {
            "channel": {
                "clean": 1,
                "telephony": 1,
            },
            "codec": {
                "linear_pcm": 1,
                "mulaw": 1,
                "alaw": 0,
                "lossy_compressed": 0,
            },
            "sample_rate_hz": {
                "8000": 1,
                "16000": 1,
            },
            "microphone_class": {
                "headset": 2,
            },
            "noise": {
                "none": 1,
                "moderate": 1,
                "severe_usable": 0,
            },
            "speaking_rate": {
                "slow": 0,
                "normal": 1,
                "fast": 1,
            },
            "speech_variety_key": {
                "declared.fixture-a": 2,
            },
            "overlap": {
                "none": 1,
                "non_critical": 0,
                "critical": 1,
            },
            "duration": {
                "short": 1,
                "medium": 0,
                "long": 1,
            },
            "compound_stress_cases": 1,
        },
        "semantic": {
            "control_cases": 0,
            "critical_number_cases": 2,
            "critical_identifier_cases": 2,
            "critical_terminology_cases": 2,
            "spoken_number_variation_cases": 1,
            "duplicate_critical_item_cases": 0,
            "ordering_challenge_cases": 1,
            "long_context_position": {
                "none": 1,
                "early": 0,
                "middle": 0,
                "late": 1,
            },
            "multi_family_cases": 2,
            "three_family_cases": 2,
            "compound_adversarial_cases": 1,
        },
    }


def test_boundary_remains_non_certifying():
    evidence = build_asr_adversarial_evidence_v1(
        _suite()
    )

    assert evidence.payload[
        "scientific_boundary"
    ] == {
        "condition_metadata_caller_declared": True,
        "condition_metadata_independently_verified": False,
        "acoustic_cause_inferred_from_transcript": False,
        "speaker_attributes_inferred": False,
        "semantic_evaluator_methodology_modified": False,
        "development_evidence_only": True,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


def test_non_control_case_requires_critical_content():
    with pytest.raises(
        HveeContractError,
        match="at least one critical item",
    ):
        _semantic(
            numbers=0,
            identifiers=0,
            terminology=0,
        )


def test_control_case_may_have_no_critical_content():
    semantic = _semantic(
        numbers=0,
        identifiers=0,
        terminology=0,
        control=True,
    )

    assert semantic.total_critical_items == 0
    assert semantic.semantic_family_count == 0


def test_spoken_number_variation_requires_number():
    with pytest.raises(
        HveeContractError,
        match="requires a critical number",
    ):
        _semantic(
            numbers=0,
            identifiers=1,
            terminology=0,
            spoken_number_variation=True,
        )


def test_long_context_position_requires_long_audio():
    with pytest.raises(
        HveeContractError,
        match="long-context position",
    ):
        _case(
            case_id="invalid.long-context",
            audio_sha256=_sha("c"),
            condition=_condition(
                duration=(
                    ASRAdversarialDurationBucket.SHORT
                ),
            ),
            semantic=_semantic(
                position=(
                    ASRAdversarialLongContextPosition.MIDDLE
                ),
            ),
        )


def test_suite_requires_sorted_case_ids():
    definition = _suite()

    with pytest.raises(
        HveeContractError,
        match="ordered by case id",
    ):
        ASRAdversarialSuiteDefinition(
            key=definition.key,
            version=definition.version,
            cases=tuple(
                reversed(definition.cases)
            ),
        )


def test_tampering_fails_closed():
    definition = _suite()
    evidence = build_asr_adversarial_evidence_v1(
        definition
    )

    tampered = copy.deepcopy(
        evidence.payload
    )

    tampered["coverage"][
        "telephony_cases"
    ] = 0

    with pytest.raises(
        HveeContractError,
    ):
        verify_asr_adversarial_evidence_v1(
            payload=tampered,
            expected_sha256=evidence.sha256,
            definition=definition,
        )


def test_rehashed_tampering_still_fails_against_definition():
    from hvee.packs.asr.adversarial_evidence import (
        calculate_asr_adversarial_evidence_sha256,
    )

    definition = _suite()
    evidence = build_asr_adversarial_evidence_v1(
        definition
    )

    tampered = copy.deepcopy(
        evidence.payload
    )

    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    tampered_sha256 = (
        calculate_asr_adversarial_evidence_sha256(
            tampered
        )
    )

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        verify_asr_adversarial_evidence_v1(
            payload=tampered,
            expected_sha256=tampered_sha256,
            definition=definition,
        )


def test_adversarial_contract_is_publicly_exported():
    import hvee.packs.asr as asr

    expected_exports = {
        "ASR_ADVERSARIAL_EVIDENCE_KEY",
        "ASR_ADVERSARIAL_EVIDENCE_SCHEMA_VERSION",
        "ASR_ADVERSARIAL_EVIDENCE_VERSION",
        "ASRAdversarialCase",
        "ASRAdversarialChannel",
        "ASRAdversarialCodec",
        "ASRAdversarialCondition",
        "ASRAdversarialDurationBucket",
        "ASRAdversarialEvidenceBundle",
        "ASRAdversarialLongContextPosition",
        "ASRAdversarialNoiseCondition",
        "ASRAdversarialOverlapCondition",
        "ASRAdversarialSemanticLoad",
        "ASRAdversarialSpeakingRate",
        "ASRAdversarialSuiteDefinition",
        "build_asr_adversarial_evidence_v1",
        "calculate_asr_adversarial_evidence_sha256",
        "verify_asr_adversarial_evidence_v1",
    }

    for name in expected_exports:
        assert hasattr(asr, name)
        assert name in asr.__all__
