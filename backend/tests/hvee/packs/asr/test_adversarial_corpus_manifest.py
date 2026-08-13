from __future__ import annotations

import copy
import hashlib
from dataclasses import replace

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_corpus_manifest import (
    ASRAdversarialCorpusAsset,
    ASRAdversarialCorpusManifestBundle,
    ASRAdversarialCorpusManifestDefinition,
    ASRAdversarialCorpusProvenanceType,
    build_asr_adversarial_corpus_manifest_v1,
    calculate_asr_adversarial_corpus_manifest_sha256,
    verify_asr_adversarial_corpus_manifest_v1,
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


def _sha(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _condition(
    *,
    codec=ASRAdversarialCodec.LINEAR_PCM,
    sample_rate_hz=16_000,
):
    return ASRAdversarialCondition(
        channel=ASRAdversarialChannel.CLEAN,
        codec=codec,
        sample_rate_hz=sample_rate_hz,
        microphone_class="studio",
        noise=ASRAdversarialNoiseCondition.NONE,
        speaking_rate=ASRAdversarialSpeakingRate.NORMAL,
        speech_variety_key="declared.fixture",
        overlap=ASRAdversarialOverlapCondition.NONE,
        duration=ASRAdversarialDurationBucket.SHORT,
    )


def _semantic_load():
    return ASRAdversarialSemanticLoad(
        critical_number_count=1,
        critical_identifier_count=0,
        critical_terminology_count=0,
        spoken_number_variation=False,
        multiple_critical_items=False,
        duplicate_critical_items=False,
        ordering_challenge=False,
        long_context_position=(
            ASRAdversarialLongContextPosition.NONE
        ),
    )


def _case(
    *,
    case_id: str,
    audio_sha256: str,
    codec=ASRAdversarialCodec.LINEAR_PCM,
    sample_rate_hz=16_000,
):
    return ASRAdversarialCase(
        case_id=case_id,
        audio_asset_sha256=audio_sha256,
        reference_transcript="Take 250 mg.",
        condition=_condition(
            codec=codec,
            sample_rate_hz=sample_rate_hz,
        ),
        semantic_load=_semantic_load(),
        description="Corpus manifest fixture.",
        tags=("corpus",),
    )


def _suite():
    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            _case(
                case_id="corpus.case-a",
                audio_sha256=_sha("audio-a"),
            ),
            _case(
                case_id="corpus.case-b",
                audio_sha256=_sha("audio-b"),
                codec=ASRAdversarialCodec.MULAW,
                sample_rate_hz=8_000,
            ),
        ),
    )

    return (
        suite,
        build_asr_adversarial_evidence_v1(
            suite
        ),
    )


def _asset(
    *,
    case_id: str,
    audio_sha256: str,
    path: str,
    sample_rate_hz: int,
    codec_name: str,
    provenance_type=(
        ASRAdversarialCorpusProvenanceType
        .PURPOSE_RECORDED
    ),
    transformation_record_sha256=None,
):
    return ASRAdversarialCorpusAsset(
        case_id=case_id,
        relative_audio_path=path,
        audio_asset_sha256=audio_sha256,
        byte_length=12_345,
        duration_ms=2_500,
        sample_rate_hz=sample_rate_hz,
        channel_count=1,
        codec_name=codec_name,
        provenance_type=provenance_type,
        provenance_record_sha256=_sha(
            "provenance-" + case_id
        ),
        rights_record_sha256=_sha(
            "rights-" + case_id
        ),
        transformation_record_sha256=(
            transformation_record_sha256
        ),
    )


def _definition(
    *,
    suite_evidence,
):
    return ASRAdversarialCorpusManifestDefinition(
        corpus_id="qualification.corpus-one",
        corpus_version="1.0.0",
        suite_sha256=suite_evidence.sha256,
        assets=(
            _asset(
                case_id="corpus.case-a",
                audio_sha256=_sha("audio-a"),
                path="audio/case-a.wav",
                sample_rate_hz=16_000,
                codec_name="pcm_s16le",
            ),
            _asset(
                case_id="corpus.case-b",
                audio_sha256=_sha("audio-b"),
                path="audio/case-b.wav",
                sample_rate_hz=8_000,
                codec_name="pcm_mulaw",
                provenance_type=(
                    ASRAdversarialCorpusProvenanceType
                    .DETERMINISTIC_DERIVATIVE
                ),
                transformation_record_sha256=(
                    _sha("transform-b")
                ),
            ),
        ),
    )


def test_builds_exact_suite_bound_manifest():
    suite, suite_evidence = _suite()

    evidence = (
        build_asr_adversarial_corpus_manifest_v1(
            _definition(
                suite_evidence=suite_evidence,
            ),
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    corpus = evidence.payload["corpus"]

    assert corpus["asset_count"] == 2
    assert corpus["case_ids"] == [
        "corpus.case-a",
        "corpus.case-b",
    ]

    assert corpus["assets"][0][
        "audio_asset_sha256"
    ] == _sha("audio-a")

    assert corpus["assets"][1][
        "media"
    ]["codec_name"] == "pcm_mulaw"


def test_manifest_is_deterministic():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite_evidence=suite_evidence,
    )

    first = build_asr_adversarial_corpus_manifest_v1(
        definition,
        suite=suite,
        suite_evidence=suite_evidence,
    )
    second = build_asr_adversarial_corpus_manifest_v1(
        definition,
        suite=suite,
        suite_evidence=suite_evidence,
    )

    assert first.payload == second.payload
    assert first.sha256 == second.sha256


@pytest.mark.parametrize(
    "path",
    [
        "/absolute/case.wav",
        "../escape.wav",
        "audio/../escape.wav",
        r"audio\case.wav",
        "case.wav",
    ],
)
def test_asset_rejects_unsafe_or_noncanonical_path(
    path,
):
    with pytest.raises(
        HveeContractError,
        match="corpus audio path",
    ):
        _asset(
            case_id="corpus.case-a",
            audio_sha256=_sha("audio-a"),
            path=path,
            sample_rate_hz=16_000,
            codec_name="pcm_s16le",
        )


def test_derivative_requires_transformation_commitment():
    with pytest.raises(
        HveeContractError,
        match="transformation record",
    ):
        _asset(
            case_id="corpus.case-a",
            audio_sha256=_sha("audio-a"),
            path="audio/case-a.wav",
            sample_rate_hz=16_000,
            codec_name="pcm_s16le",
            provenance_type=(
                ASRAdversarialCorpusProvenanceType
                .DETERMINISTIC_DERIVATIVE
            ),
        )


def test_non_derivative_rejects_transformation_commitment():
    with pytest.raises(
        HveeContractError,
        match="non-derivative",
    ):
        _asset(
            case_id="corpus.case-a",
            audio_sha256=_sha("audio-a"),
            path="audio/case-a.wav",
            sample_rate_hz=16_000,
            codec_name="pcm_s16le",
            transformation_record_sha256=(
                _sha("unexpected-transform")
            ),
        )


def test_assets_must_be_sorted():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite_evidence=suite_evidence,
    )

    with pytest.raises(
        HveeContractError,
        match="ordered by case id",
    ):
        replace(
            definition,
            assets=tuple(
                reversed(
                    definition.assets
                )
            ),
        )


def test_asset_paths_must_be_unique():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite_evidence=suite_evidence,
    )

    second = replace(
        definition.assets[1],
        relative_audio_path=(
            definition.assets[0]
            .relative_audio_path
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="audio paths must be unique",
    ):
        replace(
            definition,
            assets=(
                definition.assets[0],
                second,
            ),
        )


def test_manifest_requires_every_suite_case_exactly():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite_evidence=suite_evidence,
    )

    incomplete = replace(
        definition,
        assets=(
            definition.assets[0],
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="retain every sealed suite case exactly",
    ):
        build_asr_adversarial_corpus_manifest_v1(
            incomplete,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_manifest_rejects_wrong_audio_hash():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite_evidence=suite_evidence,
    )

    first = replace(
        definition.assets[0],
        audio_asset_sha256=_sha(
            "different-audio"
        ),
    )

    mismatched = replace(
        definition,
        assets=(
            first,
            definition.assets[1],
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="audio SHA-256",
    ):
        build_asr_adversarial_corpus_manifest_v1(
            mismatched,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_manifest_rejects_sample_rate_mismatch():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite_evidence=suite_evidence,
    )

    first = replace(
        definition.assets[0],
        sample_rate_hz=8_000,
    )

    mismatched = replace(
        definition,
        assets=(
            first,
            definition.assets[1],
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="sample rate",
    ):
        build_asr_adversarial_corpus_manifest_v1(
            mismatched,
            suite=suite,
            suite_evidence=suite_evidence,
        )


@pytest.mark.parametrize(
    (
        "declared",
        "codec_name",
    ),
    [
        (
            ASRAdversarialCodec.LINEAR_PCM,
            "pcm_mulaw",
        ),
        (
            ASRAdversarialCodec.MULAW,
            "pcm_s16le",
        ),
        (
            ASRAdversarialCodec.ALAW,
            "mp3",
        ),
        (
            ASRAdversarialCodec.LOSSY_COMPRESSED,
            "pcm_s16le",
        ),
    ],
)
def test_manifest_rejects_codec_family_mismatch(
    declared,
    codec_name,
):
    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            _case(
                case_id="corpus.case-a",
                audio_sha256=_sha("audio-a"),
                codec=declared,
                sample_rate_hz=16_000,
            ),
        ),
    )
    suite_evidence = (
        build_asr_adversarial_evidence_v1(
            suite
        )
    )

    definition = (
        ASRAdversarialCorpusManifestDefinition(
            corpus_id="qualification.corpus-one",
            corpus_version="1.0.0",
            suite_sha256=suite_evidence.sha256,
            assets=(
                _asset(
                    case_id="corpus.case-a",
                    audio_sha256=_sha("audio-a"),
                    path="audio/case-a.wav",
                    sample_rate_hz=16_000,
                    codec_name=codec_name,
                ),
            ),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="codec does not match",
    ):
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_supported_lossy_codec_family_is_accepted():
    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            _case(
                case_id="corpus.case-a",
                audio_sha256=_sha("audio-a"),
                codec=(
                    ASRAdversarialCodec
                    .LOSSY_COMPRESSED
                ),
                sample_rate_hz=16_000,
            ),
        ),
    )
    suite_evidence = (
        build_asr_adversarial_evidence_v1(
            suite
        )
    )

    definition = (
        ASRAdversarialCorpusManifestDefinition(
            corpus_id="qualification.corpus-one",
            corpus_version="1.0.0",
            suite_sha256=suite_evidence.sha256,
            assets=(
                _asset(
                    case_id="corpus.case-a",
                    audio_sha256=_sha("audio-a"),
                    path="audio/case-a.mp3",
                    sample_rate_hz=16_000,
                    codec_name="mp3",
                ),
            ),
        )
    )

    evidence = (
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    assert evidence.payload["corpus"][
        "assets"
    ][0]["media"]["codec_name"] == "mp3"


def test_rehashed_suite_tampering_is_rejected():
    suite, suite_evidence = _suite()

    tampered = copy.deepcopy(
        suite_evidence.payload
    )
    tampered["scientific_boundary"][
        "production_qualified"
    ] = True

    from hvee.packs.asr.adversarial_evidence import (
        ASRAdversarialEvidenceBundle,
        calculate_asr_adversarial_evidence_sha256,
    )

    tampered_suite = (
        ASRAdversarialEvidenceBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_evidence_sha256(
                    tampered
                )
            ),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        build_asr_adversarial_corpus_manifest_v1(
            _definition(
                suite_evidence=suite_evidence,
            ),
            suite=suite,
            suite_evidence=tampered_suite,
        )


def test_rehashed_manifest_tampering_is_rejected():
    suite, suite_evidence = _suite()
    definition = _definition(
        suite_evidence=suite_evidence,
    )

    evidence = (
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    tampered = copy.deepcopy(
        evidence.payload
    )
    tampered["evidence_boundary"][
        "acoustic_conditions_measured_by_manifest"
    ] = True

    tampered_bundle = (
        ASRAdversarialCorpusManifestBundle(
            payload=tampered,
            sha256=(
                calculate_asr_adversarial_corpus_manifest_sha256(
                    tampered
                )
            ),
        )
    )

    with pytest.raises(
        HveeContractError,
        match="does not match the v1 definition",
    ):
        verify_asr_adversarial_corpus_manifest_v1(
            payload=tampered_bundle.payload,
            expected_sha256=tampered_bundle.sha256,
            definition=definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_manifest_does_not_claim_acoustic_measurement_or_authority():
    suite, suite_evidence = _suite()

    evidence = (
        build_asr_adversarial_corpus_manifest_v1(
            _definition(
                suite_evidence=suite_evidence,
            ),
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    boundary = evidence.payload[
        "evidence_boundary"
    ]

    assert (
        boundary[
            "filesystem_audio_verified_by_manifest"
        ]
        is False
    )
    assert (
        boundary[
            "media_metadata_measured_by_manifest"
        ]
        is False
    )
    assert (
        boundary[
            "acoustic_conditions_measured_by_manifest"
        ]
        is False
    )
    assert (
        boundary[
            "speaker_attributes_inferred_from_audio"
        ]
        is False
    )
    assert (
        boundary[
            "declared_speech_variety_is_not_demographic_inference"
        ]
        is True
    )
    assert boundary[
        "development_evidence_only"
    ] is True
    assert boundary[
        "qualification_threshold_applied"
    ] is False
    assert boundary[
        "certification_issued"
    ] is False
    assert boundary[
        "production_qualified"
    ] is False
    assert boundary[
        "release_enforcement_eligible"
    ] is False


def test_manifest_requires_exact_sealed_suite_sha():
    suite, suite_evidence = _suite()

    definition = replace(
        _definition(
            suite_evidence=suite_evidence,
        ),
        suite_sha256=_sha(
            "different-suite"
        ),
    )

    with pytest.raises(
        HveeContractError,
        match="does not bind the sealed suite",
    ):
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )


def test_adversarial_corpus_manifest_is_publicly_exported():
    import hvee.packs.asr as asr

    expected = {
        "ASR_ADVERSARIAL_CORPUS_MANIFEST_KEY",
        "ASR_ADVERSARIAL_CORPUS_MANIFEST_SCHEMA_VERSION",
        "ASR_ADVERSARIAL_CORPUS_MANIFEST_VERSION",
        "ASRAdversarialCorpusAsset",
        "ASRAdversarialCorpusManifestBundle",
        "ASRAdversarialCorpusManifestDefinition",
        "ASRAdversarialCorpusProvenanceType",
        "build_asr_adversarial_corpus_manifest_v1",
        "calculate_asr_adversarial_corpus_manifest_sha256",
        "verify_asr_adversarial_corpus_manifest_v1",
    }

    for name in expected:
        assert hasattr(asr, name)
        assert name in asr.__all__
