"""Canonical definition for Hetren adversarial ASR corpus v1.

This module defines the source-visible clean synthetic semantic corpus backed
by the deterministic audio-generation and transformation chain under:

    corpora/asr/adversarial/v1

The v1 corpus currently contains eight reproducible synthetic cases. These
cases expand supported Critical Number and Critical Identifier semantic
coverage while intentionally remaining a clean normal-rate acoustic slice.

The control.clean-critical case additionally carries one declared Critical
Terminology item. Its reference transcript also contains the account-number
expression ``408-221``. The current v1 semantic evaluators do not
conclusively classify that expression, so it remains visible but is not
counted as a supported critical item.

Speaking-rate variation, duplicate-item challenges, ordering challenges,
telephony, noise, codec stress, microphone diversity, overlap, long-form
context, and human acoustic diversity are not claimed by this slice.

This definition is development evidence only. It does not apply a
qualification threshold, issue certification, authorize production use,
or modify release authority.
"""

from __future__ import annotations

from dataclasses import dataclass

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

# Backward-compatible public identities for the originally sealed control
# case. New v1 cases are represented by the canonical case-spec inventory
# below rather than by additional one-off module constants.
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


@dataclass(frozen=True, slots=True)
class _CanonicalCaseSpec:
    case_id: str
    reference_transcript: str
    audio_sha256: str
    byte_length: int
    duration_ms: int
    provenance_sha256: str
    rights_sha256: str
    transformation_sha256: str
    critical_number_count: int
    critical_identifier_count: int
    critical_terminology_count: int
    description: str
    tags: tuple[str, ...]


_CASE_SPECS = (
    _CanonicalCaseSpec(
        case_id="clean.identifier-account-order",
        reference_transcript=(
            "Account id C81 and order id D52."
        ),
        audio_sha256=(
            "30ea53e9418e448b5ad826abe091e2c0"
            "0895c308781ce13b0e6da4b667e1bad7"
        ),
        byte_length=128_566,
        duration_ms=4_015,
        provenance_sha256=(
            "36bf894c8d87bbc77f87952a205edaa3b"
            "dd1ef7f22a4b75d4dce676a8cdf76bf"
        ),
        rights_sha256=(
            "0efb0b85af7394612abab52185fc43811"
            "ecd5f362a7976f696e01ed39952845c"
        ),
        transformation_sha256=(
            "73a5476351d16890a6c13d67f61baaed"
            "4721978935b8123c640cde8cd025cf45"
        ),
        critical_number_count=0,
        critical_identifier_count=2,
        critical_terminology_count=0,
        description=(
            "Clean synthetic ASR semantic case with one supported "
            "account identifier and one supported order identifier."
        ),
        tags=(
            "asr",
            "clean",
            "semantic",
            "synthetic",
        ),
    ),
    _CanonicalCaseSpec(
        case_id="clean.identifier-confirmation",
        reference_transcript=(
            "Confirmation code AB7K92."
        ),
        audio_sha256=(
            "ebfba31f5c69634d577718bfb9cec6a5"
            "51c1e2afaab2cb8f9b19b5e7536efc33"
        ),
        byte_length=109_212,
        duration_ms=3_410,
        provenance_sha256=(
            "a11556ba44a0381a0e3e6035166b1263"
            "f62d9a6a5ae815fe5151e2a21f9efd02"
        ),
        rights_sha256=(
            "ac9ded0f23b45f96d0f1842cf3d85e34"
            "3d275faba8a1b298c4bae84d6b1eff5b"
        ),
        transformation_sha256=(
            "a19bc2dac6c67eaae14813cd6842ff01"
            "3a37ae2fdb114bb2c40a5aa646387139"
        ),
        critical_number_count=0,
        critical_identifier_count=1,
        critical_terminology_count=0,
        description=(
            "Clean synthetic ASR semantic case with one supported "
            "confirmation-code identifier."
        ),
        tags=(
            "asr",
            "clean",
            "semantic",
            "synthetic",
        ),
    ),
    _CanonicalCaseSpec(
        case_id="clean.identifier-multiple",
        reference_transcript=(
            "Ticket id A12 then booking reference B34."
        ),
        audio_sha256=(
            "5624e44f1b4ab3c8bb043aeb809a09c3"
            "3c798ce92d2f6f1ca903bcfdd0c3fdf2"
        ),
        byte_length=129_274,
        duration_ms=4_037,
        provenance_sha256=(
            "d0de5c0b7de55db1b940f4fbac6f5018"
            "d2edc80f14e1003b58ca968c1ba6fdfd"
        ),
        rights_sha256=(
            "8448ae71a3b9a4c157d9301451a4f86f"
            "f8b32a627829b94aa9a7305ac04bd9b6"
        ),
        transformation_sha256=(
            "29cbce81a09fc05fad49931b77f5c9c3"
            "5ed4d5552d3cae843d99e3562c81dfd1"
        ),
        critical_number_count=0,
        critical_identifier_count=2,
        critical_terminology_count=0,
        description=(
            "Clean synthetic ASR semantic case with one supported "
            "ticket identifier and one supported booking reference."
        ),
        tags=(
            "asr",
            "clean",
            "semantic",
            "synthetic",
        ),
    ),
    _CanonicalCaseSpec(
        case_id="clean.multi-number-id",
        reference_transcript=(
            "Administer five milligrams at nine fifteen AM. "
            "Confirmation code AB7K92."
        ),
        audio_sha256=(
            "23f9af39d01afe47e932bd061467bd0b"
            "5f49dc8bf520c2a8296a4556c54f1297"
        ),
        byte_length=220_560,
        duration_ms=6_890,
        provenance_sha256=(
            "f804bf7391cc39286bc54d5727ebe01f"
            "61d3a460f169a1b9b4d9d43a903113b4"
        ),
        rights_sha256=(
            "0b38e02c548a775ed4db61603fdcc6814"
            "8840d3396feaef59ac8d51c6b3c6ae7"
        ),
        transformation_sha256=(
            "672cf776feddf77a79182103541b2b108"
            "80b8eeae0852c07c3ffdd73701b0044"
        ),
        critical_number_count=2,
        critical_identifier_count=1,
        critical_terminology_count=0,
        description=(
            "Clean synthetic ASR semantic case combining one supported "
            "measurement, one supported clock time, and one supported "
            "confirmation-code identifier."
        ),
        tags=(
            "asr",
            "clean",
            "semantic",
            "synthetic",
        ),
    ),
    _CanonicalCaseSpec(
        case_id="clean.number-currency-time",
        reference_transcript=(
            "Pay 1200 US dollars at nine fifteen AM."
        ),
        audio_sha256=(
            "236cbdcf2d6ca24fa6726eefff1cf075"
            "2bcb87c5db78765a483031deef290446"
        ),
        byte_length=140_890,
        duration_ms=4_400,
        provenance_sha256=(
            "ae8dac7e2893bbe643950b1b6ec64261"
            "1a2bf5c38406c77e6bc9dcff7e44ba8a"
        ),
        rights_sha256=(
            "f3b89d00b8c9be37055514fa6a429259"
            "2768bd797ccde8e9fb8776acfaaf10be"
        ),
        transformation_sha256=(
            "c3ed7e3cee110ed91446506355e232fb"
            "7cb05bf03dd0c9cbf2cbe65ad0711b9e"
        ),
        critical_number_count=2,
        critical_identifier_count=0,
        critical_terminology_count=0,
        description=(
            "Clean synthetic ASR semantic case with one supported "
            "currency value and one supported clock time."
        ),
        tags=(
            "asr",
            "clean",
            "semantic",
            "synthetic",
        ),
    ),
    _CanonicalCaseSpec(
        case_id="clean.number-measurement",
        reference_transcript=(
            "Administer five milligrams now."
        ),
        audio_sha256=(
            "a3045d975c99903e108281951cba856c"
            "695ca0cc96f8d77dcb3279dc1a24fd36"
        ),
        byte_length=78_422,
        duration_ms=2_448,
        provenance_sha256=(
            "84474e713f6889d12c2baeb7fc08efe0"
            "cc7b17ef43ee33fb6facf23ab20bccef"
        ),
        rights_sha256=(
            "aeb089aa364b4d2c0fec5731b74cda61"
            "b484c6433db68553e79c55665f07d5ec"
        ),
        transformation_sha256=(
            "f9f87b23361bdb4b53aef1d28321b9db"
            "efbb26b846fc42fca7a8f81df84223bd"
        ),
        critical_number_count=1,
        critical_identifier_count=0,
        critical_terminology_count=0,
        description=(
            "Clean synthetic ASR semantic case with one supported "
            "measurement value."
        ),
        tags=(
            "asr",
            "clean",
            "semantic",
            "synthetic",
        ),
    ),
    _CanonicalCaseSpec(
        case_id="clean.number-percentage",
        reference_transcript=(
            "Apply a twenty percent discount today."
        ),
        audio_sha256=(
            "6843b1466a34d03c5c8920d8fd7fa2f0"
            "4c1b59bffedd80371a8e44492d9edc17"
        ),
        byte_length=96_972,
        duration_ms=3_028,
        provenance_sha256=(
            "a5ee833742b53fb0a79bfb2b039ff032"
            "55053538ed5895e699ab9aed25f06105"
        ),
        rights_sha256=(
            "067555dd4af75f64c65343edc37614ca"
            "7fdf58d124fc379bf081ac9b8564c41b"
        ),
        transformation_sha256=(
            "23ea98f530e1a258b230a508b45efaecc"
            "ce905843026e0ff4bfeb3a7d8220eac"
        ),
        critical_number_count=1,
        critical_identifier_count=0,
        critical_terminology_count=0,
        description=(
            "Clean synthetic ASR semantic case with one supported "
            "percentage value."
        ),
        tags=(
            "asr",
            "clean",
            "semantic",
            "synthetic",
        ),
    ),
    _CanonicalCaseSpec(
        case_id=(
            ASR_ADVERSARIAL_CORPUS_V1_CONTROL_CASE_ID
        ),
        reference_transcript=(
            ASR_ADVERSARIAL_CORPUS_V1_REFERENCE_TRANSCRIPT
        ),
        audio_sha256=(
            ASR_ADVERSARIAL_CORPUS_V1_AUDIO_SHA256
        ),
        byte_length=(
            ASR_ADVERSARIAL_CORPUS_V1_AUDIO_BYTE_LENGTH
        ),
        duration_ms=(
            ASR_ADVERSARIAL_CORPUS_V1_AUDIO_DURATION_MS
        ),
        provenance_sha256=(
            ASR_ADVERSARIAL_CORPUS_V1_PROVENANCE_SHA256
        ),
        rights_sha256=(
            ASR_ADVERSARIAL_CORPUS_V1_RIGHTS_SHA256
        ),
        transformation_sha256=(
            ASR_ADVERSARIAL_CORPUS_V1_TRANSFORMATION_SHA256
        ),
        critical_number_count=1,
        critical_identifier_count=1,
        critical_terminology_count=1,
        description=(
            "Clean synthetic ASR acoustic baseline with one supported "
            "critical number, one supported confirmation-code "
            "identifier, one declared critical terminology item, "
            "and one additional unsupported account-number expression."
        ),
        tags=(
            "asr",
            "control",
            "semantic",
            "synthetic",
        ),
    ),
)


ASR_ADVERSARIAL_CORPUS_V1_CASE_IDS = tuple(
    spec.case_id
    for spec in _CASE_SPECS
)


def _clean_condition(
) -> ASRAdversarialCondition:
    return ASRAdversarialCondition(
        channel=ASRAdversarialChannel.CLEAN,
        codec=ASRAdversarialCodec.LINEAR_PCM,
        sample_rate_hz=16_000,
        microphone_class="synthetic.direct",
        noise=ASRAdversarialNoiseCondition.NONE,
        speaking_rate=ASRAdversarialSpeakingRate.NORMAL,
        speech_variety_key="synthetic.espeak-ng.en-us",
        overlap=ASRAdversarialOverlapCondition.NONE,
        duration=ASRAdversarialDurationBucket.SHORT,
    )


def _semantic_load(
    spec: _CanonicalCaseSpec,
) -> ASRAdversarialSemanticLoad:
    total = (
        spec.critical_number_count
        + spec.critical_identifier_count
        + spec.critical_terminology_count
    )

    return ASRAdversarialSemanticLoad(
        critical_number_count=(
            spec.critical_number_count
        ),
        critical_identifier_count=(
            spec.critical_identifier_count
        ),
        critical_terminology_count=(
            spec.critical_terminology_count
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
        control_case=False,
    )


def _case(
    spec: _CanonicalCaseSpec,
) -> ASRAdversarialCase:
    return ASRAdversarialCase(
        case_id=spec.case_id,
        audio_asset_sha256=spec.audio_sha256,
        reference_transcript=(
            spec.reference_transcript
        ),
        condition=_clean_condition(),
        semantic_load=_semantic_load(
            spec
        ),
        description=spec.description,
        tags=spec.tags,
    )


def build_asr_adversarial_corpus_v1_suite(
) -> tuple[
    ASRAdversarialSuiteDefinition,
    ASRAdversarialEvidenceBundle,
]:
    """Build the exact deterministic eight-case v1 suite."""

    suite = ASRAdversarialSuiteDefinition(
        key=ASR_ADVERSARIAL_EVIDENCE_KEY,
        version=ASR_ADVERSARIAL_EVIDENCE_VERSION,
        cases=tuple(
            _case(spec)
            for spec in _CASE_SPECS
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
    """Bind every canonical derivative to the sealed v1 suite."""

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
        assets=tuple(
            ASRAdversarialCorpusAsset(
                case_id=spec.case_id,
                relative_audio_path=(
                    f"clean/{spec.case_id}.wav"
                ),
                audio_asset_sha256=(
                    spec.audio_sha256
                ),
                byte_length=(
                    spec.byte_length
                ),
                duration_ms=(
                    spec.duration_ms
                ),
                sample_rate_hz=16_000,
                channel_count=1,
                codec_name="pcm_s16le",
                provenance_type=(
                    ASRAdversarialCorpusProvenanceType
                    .DETERMINISTIC_DERIVATIVE
                ),
                provenance_record_sha256=(
                    spec.provenance_sha256
                ),
                rights_record_sha256=(
                    spec.rights_sha256
                ),
                transformation_record_sha256=(
                    spec.transformation_sha256
                ),
            )
            for spec in _CASE_SPECS
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
    "ASR_ADVERSARIAL_CORPUS_V1_CASE_IDS",
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
