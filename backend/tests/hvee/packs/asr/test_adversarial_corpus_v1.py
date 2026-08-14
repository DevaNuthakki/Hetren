from __future__ import annotations

import json
from pathlib import Path

from hvee.packs.asr.adversarial_corpus_manifest import (
    ASRAdversarialCorpusProvenanceType,
    verify_asr_adversarial_corpus_manifest_v1,
)
from hvee.packs.asr.adversarial_corpus_v1 import (
    ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SHA256,
    ASR_ADVERSARIAL_CORPUS_V1_CONTROL_CASE_ID,
    ASR_ADVERSARIAL_CORPUS_V1_REFERENCE_TRANSCRIPT,
    ASR_ADVERSARIAL_CORPUS_V1_TRANSFORMATION_SHA256,
    ASR_ADVERSARIAL_CORPUS_V1_UNSUPPORTED_REFERENCE_EXPRESSIONS,
    build_asr_adversarial_corpus_v1,
)
from hvee.packs.asr.adversarial_evidence import (
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialDurationBucket,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSpeakingRate,
    verify_asr_adversarial_evidence_v1,
)
from hvee.packs.asr.critical_identifier_fidelity import (
    EN_US_CRITICAL_IDENTIFIER_PROFILE,
    extract_critical_identifier_entities,
)
from hvee.packs.asr.critical_number_fidelity import (
    EN_US_CRITICAL_NUMBER_PROFILE,
    extract_critical_number_entities,
)


ROOT = Path(
    "corpora/asr/adversarial/v1"
)


ASR_ADVERSARIAL_CORPUS_V1_SUITE_EVIDENCE_SHA256 = (
    "960cbbb458b2cc581582558837feeebcc"
    "372ba8cff63bbe6057994462cbfb307"
)

ASR_ADVERSARIAL_CORPUS_V1_MANIFEST_SHA256 = (
    "940a2e636c389a48e072bb79715a8d2f"
    "9e193c06eba89c8b0a694669342b40e0"
)


def _load_document(
    relative_path: str,
) -> dict[str, object]:
    return json.loads(
        (
            ROOT
            / relative_path
        ).read_text(
            encoding="utf-8"
        )
    )


def test_committed_transcript_matches_canonical_case():
    transcript = (
        ROOT
        / "specification/transcripts/"
        "control.clean-critical.txt"
    ).read_text(
        encoding="utf-8"
    ).strip()

    assert (
        transcript
        == ASR_ADVERSARIAL_CORPUS_V1_REFERENCE_TRANSCRIPT
    )

    assert (
        ASR_ADVERSARIAL_CORPUS_V1_UNSUPPORTED_REFERENCE_EXPRESSIONS
        == (
            "408-221",
        )
    )


def test_canonical_control_case_has_narrow_declared_semantics():
    (
        suite,
        _suite_evidence,
        _definition,
        _manifest,
    ) = build_asr_adversarial_corpus_v1()

    assert len(
        suite.cases
    ) == 1

    case = suite.cases[0]

    assert (
        case.case_id
        == ASR_ADVERSARIAL_CORPUS_V1_CONTROL_CASE_ID
    )

    assert (
        case.audio_asset_sha256
        == ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SHA256
    )

    semantic = case.semantic_load

    assert semantic.critical_number_count == 1
    assert semantic.critical_identifier_count == 1
    assert semantic.critical_terminology_count == 1
    assert semantic.total_critical_items == 3
    assert semantic.semantic_family_count == 3

    assert semantic.spoken_number_variation is False
    assert semantic.multiple_critical_items is True
    assert semantic.duplicate_critical_items is False
    assert semantic.ordering_challenge is False
    assert semantic.control_case is False


def test_canonical_control_case_has_no_declared_acoustic_stress():
    (
        suite,
        _suite_evidence,
        _definition,
        _manifest,
    ) = build_asr_adversarial_corpus_v1()

    condition = (
        suite.cases[0].condition
    )

    assert (
        condition.channel
        == ASRAdversarialChannel.CLEAN
    )
    assert (
        condition.codec
        == ASRAdversarialCodec.LINEAR_PCM
    )
    assert condition.sample_rate_hz == 16_000
    assert (
        condition.microphone_class
        == "synthetic.direct"
    )
    assert (
        condition.noise
        == ASRAdversarialNoiseCondition.NONE
    )
    assert (
        condition.speaking_rate
        == ASRAdversarialSpeakingRate.NORMAL
    )
    assert (
        condition.speech_variety_key
        == "synthetic.espeak-ng.en-us"
    )
    assert (
        condition.overlap
        == ASRAdversarialOverlapCondition.NONE
    )
    assert (
        condition.duration
        == ASRAdversarialDurationBucket.SHORT
    )
    assert condition.active_stress_count == 0


def test_semantic_counts_match_current_conclusive_evaluator_support():
    reference = (
        ASR_ADVERSARIAL_CORPUS_V1_REFERENCE_TRANSCRIPT
    )

    numbers = (
        extract_critical_number_entities(
            text=reference,
            profile=(
                EN_US_CRITICAL_NUMBER_PROFILE
            ),
        )
    )

    identifiers = (
        extract_critical_identifier_entities(
            reference,
            profile=(
                EN_US_CRITICAL_IDENTIFIER_PROFILE
            ),
        )
    )

    conclusive_numbers = tuple(
        entity
        for entity in numbers
        if entity.issue_reason_code is None
    )

    uncertain_numbers = tuple(
        entity
        for entity in numbers
        if entity.issue_reason_code is not None
    )

    conclusive_identifiers = tuple(
        entity
        for entity in identifiers
        if entity.issue_reason_code is None
    )

    assert len(
        conclusive_numbers
    ) == 1
    assert (
        conclusive_numbers[0].text
        == "250 milligrams"
    )

    assert len(
        conclusive_identifiers
    ) == 1
    assert (
        conclusive_identifiers[0].text
        == "AB-7391"
    )

    assert len(
        uncertain_numbers
    ) == 1
    assert (
        uncertain_numbers[0].text
        == "408-221"
    )
    assert (
        uncertain_numbers[
            0
        ].issue_reason_code.value
        == "reference_expression_unsupported"
    )

    assert all(
        entity.text != "408-221"
        for entity in identifiers
    )

    assert reference.count(
        "Cardiovex"
    ) == 1


def test_real_manifest_binds_exact_generated_derivative():
    (
        _suite,
        suite_evidence,
        definition,
        manifest,
    ) = build_asr_adversarial_corpus_v1()

    assert (
        definition.suite_sha256
        == suite_evidence.sha256
    )

    assert len(
        definition.assets
    ) == 1

    asset = definition.assets[0]

    assert (
        asset.case_id
        == ASR_ADVERSARIAL_CORPUS_V1_CONTROL_CASE_ID
    )
    assert (
        asset.relative_audio_path
        == "clean/control.clean-critical.wav"
    )
    assert (
        asset.audio_asset_sha256
        == ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SHA256
    )
    assert asset.byte_length == 403_394
    assert asset.duration_ms == 12_604
    assert asset.sample_rate_hz == 16_000
    assert asset.channel_count == 1
    assert asset.codec_name == "pcm_s16le"

    assert (
        asset.provenance_type
        == (
            ASRAdversarialCorpusProvenanceType
            .DETERMINISTIC_DERIVATIVE
        )
    )

    assert (
        asset.transformation_record_sha256
        == ASR_ADVERSARIAL_CORPUS_V1_TRANSFORMATION_SHA256
    )

    assert (
        manifest.payload[
            "evidence_boundary"
        ][
            "development_evidence_only"
        ]
        is True
    )


def test_committed_suite_and_manifest_exactly_rebuild():
    (
        suite,
        suite_evidence,
        definition,
        manifest,
    ) = build_asr_adversarial_corpus_v1()

    suite_document = _load_document(
        "specification/suite-evidence.json"
    )

    manifest_document = _load_document(
        "specification/corpus-manifest.json"
    )

    verified_suite = (
        verify_asr_adversarial_evidence_v1(
            payload=(
                suite_document[
                    "payload"
                ]
            ),
            expected_sha256=(
                suite_document[
                    "sha256"
                ]
            ),
            definition=suite,
        )
    )

    verified_manifest = (
        verify_asr_adversarial_corpus_manifest_v1(
            payload=(
                manifest_document[
                    "payload"
                ]
            ),
            expected_sha256=(
                manifest_document[
                    "sha256"
                ]
            ),
            definition=definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    assert (
        verified_suite
        == suite_evidence
    )
    assert (
        verified_manifest
        == manifest
    )


def test_real_corpus_artifacts_never_claim_authority():
    (
        _suite,
        suite_evidence,
        _definition,
        manifest,
    ) = build_asr_adversarial_corpus_v1()

    scientific = (
        suite_evidence.payload[
            "scientific_boundary"
        ]
    )

    assert (
        scientific[
            "development_evidence_only"
        ]
        is True
    )
    assert (
        scientific[
            "certification_issued"
        ]
        is False
    )
    assert (
        scientific[
            "production_qualified"
        ]
        is False
    )
    assert (
        scientific[
            "release_enforcement_eligible"
        ]
        is False
    )

    boundary = manifest.payload[
        "evidence_boundary"
    ]

    assert (
        boundary[
            "development_evidence_only"
        ]
        is True
    )
    assert (
        boundary[
            "qualification_threshold_applied"
        ]
        is False
    )
    assert (
        boundary[
            "certification_issued"
        ]
        is False
    )
    assert (
        boundary[
            "production_qualified"
        ]
        is False
    )
    assert (
        boundary[
            "release_enforcement_eligible"
        ]
        is False
    )
    assert (
        boundary[
            "official_release_verdict_modified"
        ]
        is False
    )


def test_real_suite_and_manifest_identities_are_frozen():
    (
        _suite,
        suite_evidence,
        _definition,
        manifest,
    ) = build_asr_adversarial_corpus_v1()

    assert (
        suite_evidence.sha256
        == ASR_ADVERSARIAL_CORPUS_V1_SUITE_EVIDENCE_SHA256
    )

    assert (
        manifest.sha256
        == ASR_ADVERSARIAL_CORPUS_V1_MANIFEST_SHA256
    )

    suite_document = _load_document(
        "specification/suite-evidence.json"
    )

    manifest_document = _load_document(
        "specification/corpus-manifest.json"
    )

    assert (
        suite_document["sha256"]
        == ASR_ADVERSARIAL_CORPUS_V1_SUITE_EVIDENCE_SHA256
    )

    assert (
        manifest_document["sha256"]
        == ASR_ADVERSARIAL_CORPUS_V1_MANIFEST_SHA256
    )

    assert (
        manifest_document[
            "payload"
        ]["suite"]["sha256"]
        == ASR_ADVERSARIAL_CORPUS_V1_SUITE_EVIDENCE_SHA256
    )
