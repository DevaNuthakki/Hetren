"""Canonical definition for the first Hetren adversarial ASR corpus.

This module defines the source-visible v1 corpus case that is backed by
the deterministic audio-generation chain under:

    corpora/asr/adversarial/v1

The case is intentionally a clean synthetic acoustic baseline. It establishes one
reproducible real-audio baseline before later corpus slices add telephony,
noise, codec, speaking-rate, microphone, overlap, and long-form stresses.

Semantic counts represent currently supported conclusive evaluator
evidence. The reference transcript also contains the account-number
expression ``408-221``. The current v1 semantic evaluators do not
conclusively classify that expression, so it remains visible in the
reference transcript but is not counted as a supported critical item.

This definition is development evidence only. It does not apply a
qualification threshold, issue certification, authorize production use,
or modify release authority.
"""

from __future__ import annotations

from hvee.packs.asr.adversarial_corpus_manifest import (
    ASRAdversarialCorpusAsset,
    ASRAdversarialCorpusManifestBundle,
    ASRAdversarialCorpusManifestDefinition,
    ASRAdversarialCorpusProvenanceType,
    build_asr_adversarial_corpus_manifest_v1,
)
from hvee.packs.asr.adversarial_evidence import (
    ASR_ADVERSARIAL_EVIDENCE_KEY,
    ASR_ADVERSARIAL_EVIDENCE_VERSION,
    ASRAdversarialCase,
    ASRAdversarialChannel,
    ASRAdversarialCodec,
    ASRAdversarialCondition,
    ASRAdversarialDurationBucket,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialLongContextPosition,
    ASRAdversarialNoiseCondition,
    ASRAdversarialOverlapCondition,
    ASRAdversarialSemanticLoad,
    ASRAdversarialSpeakingRate,
    ASRAdversarialSuiteDefinition,
    build_asr_adversarial_evidence_v1,
)


ASR_ADVERSARIAL_CORPUS_V1_ID = (
    "qualification.synthetic-v1"
)
ASR_ADVERSARIAL_CORPUS_V1_VERSION = "1.0.0"

ASR_ADVERSARIAL_CORPUS_V1_CONTROL_CASE_ID = (
    "control.clean-critical"
)

ASR_ADVERSARIAL_CORPUS_V1_REFERENCE_TRANSCRIPT = (
    "Administer Cardiovex 250 milligrams. "
    "Confirmation code AB-7391. "
    "Account number 408-221."
)

ASR_ADVERSARIAL_CORPUS_V1_UNSUPPORTED_REFERENCE_EXPRESSIONS = (
    "408-221",
)

ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SHA256 = (
    "f97e1d36b87676aaacf4dbd8059fa8fe"
    "f2d323d23cfb8468aa22426f05dbd3b3"
)

ASR_ADVERSARIAL_CORPUS_V1_AUDIO_BYTE_LENGTH = 403_394
ASR_ADVERSARIAL_CORPUS_V1_AUDIO_DURATION_MS = 12_604
ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SAMPLE_RATE_HZ = 16_000
ASR_ADVERSARIAL_CORPUS_V1_AUDIO_CHANNEL_COUNT = 1
ASR_ADVERSARIAL_CORPUS_V1_AUDIO_CODEC_NAME = (
    "pcm_s16le"
)
ASR_ADVERSARIAL_CORPUS_V1_AUDIO_RELATIVE_PATH = (
    "clean/control.clean-critical.wav"
)

ASR_ADVERSARIAL_CORPUS_V1_PROVENANCE_SHA256 = (
    "30d7a75e8ad8dca1f03a3576d167a12b"
    "62bff7df2fbd5bfe7a2e825771dde1c4"
)

ASR_ADVERSARIAL_CORPUS_V1_RIGHTS_SHA256 = (
    "cfcc0861946a6fe96da954f6efda69e7"
    "45e7bd2533e1f9b8718e0084d7bcdb14"
)

ASR_ADVERSARIAL_CORPUS_V1_TRANSFORMATION_SHA256 = (
    "4cd349d56ca7c5fc60c773024dc36488"
    "b75f3944a4b1a98da260178c726c3f0f"
)


def build_asr_adversarial_corpus_v1_suite(
) -> tuple[
    ASRAdversarialSuiteDefinition,
    ASRAdversarialEvidenceBundle,
]:
    """Build the exact deterministic v1 suite and its sealed evidence."""

    condition = ASRAdversarialCondition(
        channel=(
            ASRAdversarialChannel.CLEAN
        ),
        codec=(
            ASRAdversarialCodec.LINEAR_PCM
        ),
        sample_rate_hz=(
            ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SAMPLE_RATE_HZ
        ),
        microphone_class="synthetic.direct",
        noise=(
            ASRAdversarialNoiseCondition.NONE
        ),
        speaking_rate=(
            ASRAdversarialSpeakingRate.NORMAL
        ),
        speech_variety_key=(
            "synthetic.espeak-ng.en-us"
        ),
        overlap=(
            ASRAdversarialOverlapCondition.NONE
        ),
        duration=(
            ASRAdversarialDurationBucket.SHORT
        ),
    )

    semantic_load = (
        ASRAdversarialSemanticLoad(
            critical_number_count=1,
            critical_identifier_count=1,
            critical_terminology_count=1,
            spoken_number_variation=False,
            multiple_critical_items=True,
            duplicate_critical_items=False,
            ordering_challenge=False,
            long_context_position=(
                ASRAdversarialLongContextPosition.NONE
            ),
            # This is an acoustic control/baseline, not a
            # semantic-control case. It carries supported
            # critical items and therefore remains False.
            control_case=False,
        )
    )

    case = ASRAdversarialCase(
        case_id=(
            ASR_ADVERSARIAL_CORPUS_V1_CONTROL_CASE_ID
        ),
        audio_asset_sha256=(
            ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SHA256
        ),
        reference_transcript=(
            ASR_ADVERSARIAL_CORPUS_V1_REFERENCE_TRANSCRIPT
        ),
        condition=condition,
        semantic_load=semantic_load,
        description=(
            "Clean synthetic ASR acoustic baseline with one supported "
            "critical number, one supported confirmation-code "
            "identifier, one declared critical terminology item, "
            "and one additional unsupported account-number "
            "expression."
        ),
        tags=(
            "asr",
            "control",
            "semantic",
            "synthetic",
        ),
    )

    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=(
            case,
        ),
    )

    return (
        suite,
        build_asr_adversarial_evidence_v1(
            suite
        ),
    )


def build_asr_adversarial_corpus_v1_manifest_definition(
    *,
    suite_evidence: ASRAdversarialEvidenceBundle,
) -> ASRAdversarialCorpusManifestDefinition:
    """Bind the canonical generated derivative to the sealed v1 suite."""

    return ASRAdversarialCorpusManifestDefinition(
        corpus_id=(
            ASR_ADVERSARIAL_CORPUS_V1_ID
        ),
        corpus_version=(
            ASR_ADVERSARIAL_CORPUS_V1_VERSION
        ),
        suite_sha256=(
            suite_evidence.sha256
        ),
        assets=(
            ASRAdversarialCorpusAsset(
                case_id=(
                    ASR_ADVERSARIAL_CORPUS_V1_CONTROL_CASE_ID
                ),
                relative_audio_path=(
                    ASR_ADVERSARIAL_CORPUS_V1_AUDIO_RELATIVE_PATH
                ),
                audio_asset_sha256=(
                    ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SHA256
                ),
                byte_length=(
                    ASR_ADVERSARIAL_CORPUS_V1_AUDIO_BYTE_LENGTH
                ),
                duration_ms=(
                    ASR_ADVERSARIAL_CORPUS_V1_AUDIO_DURATION_MS
                ),
                sample_rate_hz=(
                    ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SAMPLE_RATE_HZ
                ),
                channel_count=(
                    ASR_ADVERSARIAL_CORPUS_V1_AUDIO_CHANNEL_COUNT
                ),
                codec_name=(
                    ASR_ADVERSARIAL_CORPUS_V1_AUDIO_CODEC_NAME
                ),
                provenance_type=(
                    ASRAdversarialCorpusProvenanceType
                    .DETERMINISTIC_DERIVATIVE
                ),
                provenance_record_sha256=(
                    ASR_ADVERSARIAL_CORPUS_V1_PROVENANCE_SHA256
                ),
                rights_record_sha256=(
                    ASR_ADVERSARIAL_CORPUS_V1_RIGHTS_SHA256
                ),
                transformation_record_sha256=(
                    ASR_ADVERSARIAL_CORPUS_V1_TRANSFORMATION_SHA256
                ),
            ),
        ),
    )


def build_asr_adversarial_corpus_v1(
) -> tuple[
    ASRAdversarialSuiteDefinition,
    ASRAdversarialEvidenceBundle,
    ASRAdversarialCorpusManifestDefinition,
    ASRAdversarialCorpusManifestBundle,
]:
    """Build the complete deterministic v1 suite and G manifest."""

    suite, suite_evidence = (
        build_asr_adversarial_corpus_v1_suite()
    )

    definition = (
        build_asr_adversarial_corpus_v1_manifest_definition(
            suite_evidence=suite_evidence
        )
    )

    manifest = (
        build_asr_adversarial_corpus_manifest_v1(
            definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    return (
        suite,
        suite_evidence,
        definition,
        manifest,
    )


__all__ = [
    "ASR_ADVERSARIAL_CORPUS_V1_AUDIO_BYTE_LENGTH",
    "ASR_ADVERSARIAL_CORPUS_V1_AUDIO_CHANNEL_COUNT",
    "ASR_ADVERSARIAL_CORPUS_V1_AUDIO_CODEC_NAME",
    "ASR_ADVERSARIAL_CORPUS_V1_AUDIO_DURATION_MS",
    "ASR_ADVERSARIAL_CORPUS_V1_AUDIO_RELATIVE_PATH",
    "ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SAMPLE_RATE_HZ",
    "ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SHA256",
    "ASR_ADVERSARIAL_CORPUS_V1_CONTROL_CASE_ID",
    "ASR_ADVERSARIAL_CORPUS_V1_ID",
    "ASR_ADVERSARIAL_CORPUS_V1_PROVENANCE_SHA256",
    "ASR_ADVERSARIAL_CORPUS_V1_REFERENCE_TRANSCRIPT",
    "ASR_ADVERSARIAL_CORPUS_V1_RIGHTS_SHA256",
    "ASR_ADVERSARIAL_CORPUS_V1_TRANSFORMATION_SHA256",
    "ASR_ADVERSARIAL_CORPUS_V1_UNSUPPORTED_REFERENCE_EXPRESSIONS",
    "ASR_ADVERSARIAL_CORPUS_V1_VERSION",
    "build_asr_adversarial_corpus_v1",
    "build_asr_adversarial_corpus_v1_manifest_definition",
    "build_asr_adversarial_corpus_v1_suite",
]
