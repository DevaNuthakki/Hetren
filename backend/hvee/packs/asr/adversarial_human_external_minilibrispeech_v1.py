"""Concrete Mini LibriSpeech human-source evidence for adversarial ASR.

This module binds the independently acquired and verified OpenSLR SLR31
Mini LibriSpeech ``dev-clean-2`` selection used by Hetren's human/external
development-evidence slice.

The generic human/external methodology and provenance/rights contracts live
in ``adversarial_human_external_evidence``. This module intentionally adds
only source-specific immutable evidence:

- the exact upstream archive identity,
- acquisition-time rights and license evidence commitments,
- the I4b2 source-selection evidence identity,
- the I4b3 pinned-media verification identity,
- eight source-defined human utterance identities,
- exact audio, transcript, locator, metadata, and media commitments.

Raw source URLs, audio, license documents, and inferred speaker attributes
are not embedded here. The selected media remains outside Git under the
``NOT_COMMITTED`` repository-media policy.

This remains development evidence only. It does not establish production
qualification, legal adjudication, human acoustic diversity, accent
coverage, microphone diversity, certification, or release authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_evidence import (
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID,
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION,
    ASRAdversarialHumanExternalProvenanceRecord,
    ASRAdversarialHumanExternalRecordBundle,
    ASRAdversarialHumanExternalRepositoryMediaPolicy,
    ASRAdversarialHumanExternalRightsBasis,
    ASRAdversarialHumanExternalRightsRecord,
    ASRAdversarialHumanExternalSourceKind,
    build_asr_adversarial_human_external_provenance_record_v1,
    build_asr_adversarial_human_external_rights_record_v1,
    calculate_asr_adversarial_human_external_sha256,
    verify_asr_adversarial_human_external_record_pair_v1,
)


ASR_ADVERSARIAL_MINILIBRISPEECH_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_MINILIBRISPEECH_VERSION = "1.0.0"

ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_KEY = (
    "hetren.asr."
    "adversarial-human-external-minilibrispeech-selection.en-us"
)

ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_KEY = (
    "openslr-mini-librispeech"
)

ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_VERSION = (
    "slr31.dev-clean-2"
)

ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_NAME = (
    "dev-clean-2.tar.gz"
)

# This MD5 is retained only because it is the upstream SLR31 checksum.
# SHA-256 below is the local content-security identity used by Hetren.
ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_MD5 = (
    "6d7ab67ac6a1d2c993d050e16d61080d"
)

ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_SHA256 = (
    "176ec501490eced2d6c1f89f4f0ddc7"
    "dfe799e649e5322f8ba49fe3ff50c8012"
)

ASR_ADVERSARIAL_MINILIBRISPEECH_DECLARED_LICENSE = (
    "CC BY 4.0"
)

# Acquisition-time snapshot of the OpenSLR SLR31 resource page that
# declared the corpus license. This is evidence, not legal adjudication.
ASR_ADVERSARIAL_MINILIBRISPEECH_RIGHTS_EVIDENCE_SHA256 = (
    "3da285125fce2c3a7131d45206ae86f7"
    "ed8fd47a4a5b3425f793c0c8ff11bb2f"
)

# Acquisition-time snapshot of the CC BY 4.0 legal-code page.
ASR_ADVERSARIAL_MINILIBRISPEECH_TERMS_EVIDENCE_SHA256 = (
    "6d55b998ed5c54f43426d059a8c549ed"
    "58a3321e5463e6a6af1c6b56ab78c333"
)

ASR_ADVERSARIAL_MINILIBRISPEECH_I4B2_SELECTION_REPORT_SHA256 = (
    "152c830a98344d9d5963a7ce11a8c9f0"
    "6a657d86060228e93232fc9e05eb1aad"
)

ASR_ADVERSARIAL_MINILIBRISPEECH_I4B3_MEDIA_REPORT_SHA256 = (
    "36d275947d58fae0adde44b26b214ae52"
    "cb03d76596ad02375447ba00209ce48"
)

ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256 = (
    "019d09f3989ac16da9484bba48653fe8"
    "9663905ef3db1cb74cae2d287721f409"
)


_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)

_UTTERANCE_ID_PATTERN = re.compile(
    r"^[0-9]+-[0-9]+-[0-9]{4}$"
)


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256"
        )

    return value


def _require_non_empty_text(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise HveeContractError(
            f"{name} must be non-empty text"
        )

    return value


@dataclass(frozen=True, slots=True)
class ASRAdversarialMiniLibriSpeechCase:
    """One immutable selected Mini LibriSpeech source item."""

    utterance_id: str
    speaker_id: str
    chapter_id: str
    selection_reason: str
    source_audio_sha256: str
    audio_bytes: int
    reference_transcript_sha256: str
    source_metadata_sha256: str
    source_locator_sha256: str
    duration_ms: int
    codec_name: str = "flac"
    format_name: str = "flac"
    sample_rate_hz: int = 16_000
    channel_count: int = 1

    def __post_init__(
        self,
    ) -> None:
        if (
            not isinstance(self.utterance_id, str)
            or _UTTERANCE_ID_PATTERN.fullmatch(
                self.utterance_id
            )
            is None
        ):
            raise HveeContractError(
                "Mini LibriSpeech utterance id is invalid"
            )

        identifier_parts = self.utterance_id.split("-")

        if identifier_parts[0] != self.speaker_id:
            raise HveeContractError(
                "Mini LibriSpeech speaker id does not "
                "match utterance id"
            )

        if identifier_parts[1] != self.chapter_id:
            raise HveeContractError(
                "Mini LibriSpeech chapter id does not "
                "match utterance id"
            )

        if (
            not self.speaker_id.isdigit()
            or not self.chapter_id.isdigit()
        ):
            raise HveeContractError(
                "Mini LibriSpeech source identifiers "
                "must be numeric"
            )

        _require_non_empty_text(
            name="Mini LibriSpeech selection reason",
            value=self.selection_reason,
        )

        _require_sha256(
            name="Mini LibriSpeech source audio",
            value=self.source_audio_sha256,
        )
        _require_sha256(
            name="Mini LibriSpeech transcript",
            value=self.reference_transcript_sha256,
        )
        _require_sha256(
            name="Mini LibriSpeech source metadata",
            value=self.source_metadata_sha256,
        )
        _require_sha256(
            name="Mini LibriSpeech source locator",
            value=self.source_locator_sha256,
        )

        if (
            not isinstance(self.audio_bytes, int)
            or isinstance(self.audio_bytes, bool)
            or self.audio_bytes <= 0
        ):
            raise HveeContractError(
                "Mini LibriSpeech audio byte length "
                "must be positive"
            )

        if (
            not isinstance(self.duration_ms, int)
            or isinstance(self.duration_ms, bool)
            or self.duration_ms <= 0
        ):
            raise HveeContractError(
                "Mini LibriSpeech duration must be positive"
            )

        if self.codec_name != "flac":
            raise HveeContractError(
                "Mini LibriSpeech selected codec must be FLAC"
            )

        if self.format_name != "flac":
            raise HveeContractError(
                "Mini LibriSpeech selected format must be FLAC"
            )

        if self.sample_rate_hz != 16_000:
            raise HveeContractError(
                "Mini LibriSpeech selected sample rate "
                "must remain 16 kHz"
            )

        if self.channel_count != 1:
            raise HveeContractError(
                "Mini LibriSpeech selected source must "
                "remain mono"
            )

    @property
    def case_id(
        self,
    ) -> str:
        return (
            "human.minilibrispeech."
            + self.utterance_id
        )


@dataclass(frozen=True, slots=True)
class ASRAdversarialMiniLibriSpeechSelectionBundle:
    """Canonical source-visible I4b selection artifact."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "Mini LibriSpeech selection payload "
                "must be an object"
            )

        _require_sha256(
            name="Mini LibriSpeech selection",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_human_external_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "Mini LibriSpeech selection SHA-256 "
                "does not match its payload"
            )


ASR_ADVERSARIAL_MINILIBRISPEECH_CASES = (
    ASRAdversarialMiniLibriSpeechCase(
        utterance_id="1272-141231-0016",
        speaker_id="1272",
        chapter_id="141231",
        selection_reason="short-duration",
        source_audio_sha256=(
            "2de6e800e9a973de275a2c57ef2a8ccf"
            "0e25655f0158a0a551bdc0e944607ebc"
        ),
        audio_bytes=37_052,
        reference_transcript_sha256=(
            "221d547c503f8f95d6b8923e00c519c4"
            "e1374ee9558cfd9e01b5f3eca689fd4c"
        ),
        source_metadata_sha256=(
            "c1a4485f3daf0bcb3cf1fa32568c4c87"
            "6dfcc480f14ea66102bdd912a7ad46bb"
        ),
        source_locator_sha256=(
            "da846c6ac13f6de523bf37dd20913ece3"
            "f598132494e5d81f08e83eaf40ffcda"
        ),
        duration_ms=1_850,
    ),
    ASRAdversarialMiniLibriSpeechCase(
        utterance_id="174-168635-0004",
        speaker_id="174",
        chapter_id="168635",
        selection_reason="age-and-archaic-number-phrase",
        source_audio_sha256=(
            "162547b61c075720bbfaac0d1cbfe941a"
            "06f37f6ad9305a433e40cb6872d6eac"
        ),
        audio_bytes=232_298,
        reference_transcript_sha256=(
            "dba95526c1fdb2bfa257b50b076eace7"
            "04c31a1af32caed2981de16749f0530a"
        ),
        source_metadata_sha256=(
            "c85cb5235149949ced752a86bcd8bb6d"
            "781049103def4308f1e15453e7628a8d"
        ),
        source_locator_sha256=(
            "f06493549f0af9c11c81c1c36851a3b2"
            "834bf15ea3f3289a8f8d9706a1425470"
        ),
        duration_ms=12_770,
    ),
    ASRAdversarialMiniLibriSpeechCase(
        utterance_id="2412-153948-0004",
        speaker_id="2412",
        chapter_id="153948",
        selection_reason="large-magnitudes-and-ranges",
        source_audio_sha256=(
            "bc9ddeba5435e59ae39a1aef471a0f6f"
            "af4743d9922a65543c4b0a33bfbcb0ab"
        ),
        audio_bytes=404_370,
        reference_transcript_sha256=(
            "987e947c761fdfd45d20a7b168886470"
            "278e4891d7aa3418f7f820ad36a53105"
        ),
        source_metadata_sha256=(
            "358fb731be854e61bfc7905dc7a2d17b"
            "0c05967698c728b6c2991a34c2dc7224"
        ),
        source_locator_sha256=(
            "091c6f8bd7c2d80c97682a542373dc9e"
            "614702cdef9fcde71a523e050c6e5c78"
        ),
        duration_ms=22_680,
    ),
    ASRAdversarialMiniLibriSpeechCase(
        utterance_id="251-118436-0003",
        speaker_id="251",
        chapter_id="118436",
        selection_reason="repeated-counts",
        source_audio_sha256=(
            "2d6377ec7f350c09fb947aa1fc6ef3a0"
            "7d477c0914bb0e901cd15f6f3e23cc03"
        ),
        audio_bytes=204_641,
        reference_transcript_sha256=(
            "6f02f07c39bfbb3cde039e312fa70e9e"
            "b52e253f901f6bd04c3766873240ca2b"
        ),
        source_metadata_sha256=(
            "975228b27ee7294d7f240e6911707f8f"
            "54736218e14f28c086446c0f080e2292"
        ),
        source_locator_sha256=(
            "02b41063e4f7a538f7e068dbb56d94a9"
            "76cdc7f9154dcb4ec47830d89804ecc0"
        ),
        duration_ms=11_020,
    ),
    ASRAdversarialMiniLibriSpeechCase(
        utterance_id="3000-15664-0017",
        speaker_id="3000",
        chapter_id="15664",
        selection_reason="multiple-measurements-and-magnitude",
        source_audio_sha256=(
            "9778735bbb76df6729e03186a2396fe31"
            "276b571520f9f1d49fb098d02c6358e"
        ),
        audio_bytes=239_228,
        reference_transcript_sha256=(
            "64eac7fe654c4eaa301abb76fe026583b"
            "4c8ce2e7f055672e1a4ae825c21b9b0"
        ),
        source_metadata_sha256=(
            "4e610f4d052356ec32de5a2b618bfbc"
            "8f1df4d6e6833d8dc5bfb8a8dbe356373"
        ),
        source_locator_sha256=(
            "600004d799bc13e2217baae42af9bc770"
            "5586625d3d6506412bfe85084d6dbf1"
        ),
        duration_ms=14_085,
    ),
    ASRAdversarialMiniLibriSpeechCase(
        utterance_id="3576-138058-0038",
        speaker_id="3576",
        chapter_id="138058",
        selection_reason="monetary-quantities",
        source_audio_sha256=(
            "811826282f72f480b703654419d7f3df"
            "36d63d6bbf364986b34e7075ed8202ab"
        ),
        audio_bytes=185_316,
        reference_transcript_sha256=(
            "b8f819c4aecabfae32f60f023d1c04cd"
            "71863e8c4618d7b0b599526a9e7d9273"
        ),
        source_metadata_sha256=(
            "5c0c48602476f0b0b1c33d6cea4b255"
            "8a62fc86380622c156f02d8c3af309cd6"
        ),
        source_locator_sha256=(
            "ec7446d8b9d127d10067a0bb343d4cd0"
            "7fd84aba0f4fe26b9c1421663f2cbf7f"
        ),
        duration_ms=9_650,
    ),
    ASRAdversarialMiniLibriSpeechCase(
        utterance_id="5895-34622-0003",
        speaker_id="5895",
        chapter_id="34622",
        selection_reason="spoken-year-sequence",
        source_audio_sha256=(
            "9e18de26ad97ad32e03a30c51aad5fbec"
            "5ef25622543671297a6d7a5875cb339"
        ),
        audio_bytes=102_457,
        reference_transcript_sha256=(
            "2af468b04f30940156a44d7fd3a2206b"
            "50fdc80ec66e94db986d031cc456f78b"
        ),
        source_metadata_sha256=(
            "e99cb5205eedd86fbfd7074e46ea04428"
            "9fc01dfd58876acc94ab9d5ff793e7f"
        ),
        source_locator_sha256=(
            "1167337617c3c8794ca906417f7e77adf"
            "d5f236a4491e7536623d58b638f5950"
        ),
        duration_ms=5_080,
    ),
    ASRAdversarialMiniLibriSpeechCase(
        utterance_id="6241-61943-0000",
        speaker_id="6241",
        chapter_id="61943",
        selection_reason="ordinal-date-and-time",
        source_audio_sha256=(
            "a87ff71b48e5c43b62c67615b42b5f0f"
            "b781decc85d5c890b3d8fa1219cb14e5"
        ),
        audio_bytes=139_579,
        reference_transcript_sha256=(
            "c2344a8179ea5c3bce612e55b604d0a1"
            "b97b61ed34165750f2f807dfe6d1891b"
        ),
        source_metadata_sha256=(
            "d5f67d4d78a288b1e6253570bb3ffbfb"
            "59418d90999719dd21897122c5a97faa"
        ),
        source_locator_sha256=(
            "22aaeb84884df08edd1ca9349dd04a87f"
            "7f486535105cec9aaccf4497d793d18"
        ),
        duration_ms=6_950,
    ),
)


def _case_snapshot(
    case: ASRAdversarialMiniLibriSpeechCase,
) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "source_item_id": case.utterance_id,
        "source_defined_speaker_id": case.speaker_id,
        "source_defined_chapter_id": case.chapter_id,
        "selection_reason": case.selection_reason,
        "commitments": {
            "source_audio_sha256": (
                case.source_audio_sha256
            ),
            "audio_bytes": case.audio_bytes,
            "reference_transcript_sha256": (
                case.reference_transcript_sha256
            ),
            "source_metadata_sha256": (
                case.source_metadata_sha256
            ),
            "source_locator_sha256": (
                case.source_locator_sha256
            ),
        },
        "verified_media": {
            "codec_name": case.codec_name,
            "format_name": case.format_name,
            "sample_rate_hz": case.sample_rate_hz,
            "channel_count": case.channel_count,
            "duration_ms": case.duration_ms,
        },
    }


def _selection_payload(
) -> dict[str, object]:
    return {
        "schema_version": (
            ASR_ADVERSARIAL_MINILIBRISPEECH_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_VERSION
            ),
            "type": (
                "source_visible_adversarial_"
                "human_external_dataset_selection"
            ),
        },
        "source": {
            "corpus_id": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID
            ),
            "corpus_version": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION
            ),
            "collection_key": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_KEY
            ),
            "collection_version": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_VERSION
            ),
            "archive_name": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_NAME
            ),
            "archive_md5": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_MD5
            ),
            "archive_sha256": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_ARCHIVE_SHA256
            ),
            "declared_license": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_DECLARED_LICENSE
            ),
            "rights_evidence_sha256": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_RIGHTS_EVIDENCE_SHA256
            ),
            "terms_evidence_sha256": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_TERMS_EVIDENCE_SHA256
            ),
            "repository_media_policy": (
                ASRAdversarialHumanExternalRepositoryMediaPolicy
                .NOT_COMMITTED
                .value
            ),
        },
        "acquisition_evidence": {
            "selection_report_sha256": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_I4B2_SELECTION_REPORT_SHA256
            ),
            "media_verification_report_sha256": (
                ASR_ADVERSARIAL_MINILIBRISPEECH_I4B3_MEDIA_REPORT_SHA256
            ),
        },
        "cases": [
            _case_snapshot(case)
            for case in ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        ],
        "evidence_boundary": {
            "source_speaker_ids_are_source_defined": True,
            "speaker_attributes_inferred": False,
            "accent_inferred": False,
            "microphone_class_inferred": False,
            "human_acoustic_diversity_established": False,
            "rights_adjudicated": False,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }


def build_asr_adversarial_minilibrispeech_selection_v1(
) -> ASRAdversarialMiniLibriSpeechSelectionBundle:
    """Build the exact source-visible I4b Mini LibriSpeech selection."""

    payload = _selection_payload()

    bundle = ASRAdversarialMiniLibriSpeechSelectionBundle(
        payload=payload,
        sha256=(
            calculate_asr_adversarial_human_external_sha256(
                payload
            )
        ),
    )

    if (
        bundle.sha256
        != ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256
    ):
        raise HveeContractError(
            "Mini LibriSpeech selection v1 identity changed"
        )

    return bundle


def verify_asr_adversarial_minilibrispeech_selection_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialMiniLibriSpeechSelectionBundle:
    """Verify the exact frozen I4b Mini LibriSpeech selection."""

    _require_sha256(
        name="expected Mini LibriSpeech selection",
        value=expected_sha256,
    )

    if (
        expected_sha256
        != ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256
    ):
        raise HveeContractError(
            "Mini LibriSpeech selection identity "
            "is unsupported"
        )

    expected = (
        build_asr_adversarial_minilibrispeech_selection_v1()
    )

    if (
        payload != expected.payload
        or expected_sha256 != expected.sha256
    ):
        raise HveeContractError(
            "Mini LibriSpeech selection failed "
            "canonical verification"
        )

    return expected


def get_asr_adversarial_minilibrispeech_case_v1(
    utterance_id: str,
) -> ASRAdversarialMiniLibriSpeechCase:
    """Return one exact selected source item."""

    for case in ASR_ADVERSARIAL_MINILIBRISPEECH_CASES:
        if case.utterance_id == utterance_id:
            return case

    raise HveeContractError(
        "Mini LibriSpeech source item is unsupported"
    )


def build_asr_adversarial_minilibrispeech_record_pair_v1(
    utterance_id: str,
) -> tuple[
    ASRAdversarialHumanExternalRecordBundle,
    ASRAdversarialHumanExternalRecordBundle,
]:
    """Build and verify provenance/rights for one selected source."""

    case = get_asr_adversarial_minilibrispeech_case_v1(
        utterance_id
    )

    provenance = (
        build_asr_adversarial_human_external_provenance_record_v1(
            ASRAdversarialHumanExternalProvenanceRecord(
                record_id=(
                    "source.human-minilibrispeech-"
                    + case.utterance_id
                    + "-v1"
                ),
                case_id=case.case_id,
                source_kind=(
                    ASRAdversarialHumanExternalSourceKind
                    .LICENSED_DATASET
                ),
                source_collection_key=(
                    ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_KEY
                ),
                source_collection_version=(
                    ASR_ADVERSARIAL_MINILIBRISPEECH_COLLECTION_VERSION
                ),
                source_item_id=case.utterance_id,
                source_audio_sha256=(
                    case.source_audio_sha256
                ),
                reference_transcript_sha256=(
                    case.reference_transcript_sha256
                ),
                source_metadata_sha256=(
                    case.source_metadata_sha256
                ),
                source_locator_sha256=(
                    case.source_locator_sha256
                ),
                declared_speaker_metadata_sha256=None,
                declared_recording_metadata_sha256=None,
            )
        )
    )

    rights = (
        build_asr_adversarial_human_external_rights_record_v1(
            ASRAdversarialHumanExternalRightsRecord(
                record_id=(
                    "rights.human-minilibrispeech-"
                    + case.utterance_id
                    + "-v1"
                ),
                case_id=case.case_id,
                source_kind=(
                    ASRAdversarialHumanExternalSourceKind
                    .LICENSED_DATASET
                ),
                source_audio_sha256=(
                    case.source_audio_sha256
                ),
                source_locator_sha256=(
                    case.source_locator_sha256
                ),
                rights_basis=(
                    ASRAdversarialHumanExternalRightsBasis
                    .DATASET_LICENSE
                ),
                rights_evidence_sha256=(
                    ASR_ADVERSARIAL_MINILIBRISPEECH_RIGHTS_EVIDENCE_SHA256
                ),
                terms_evidence_sha256=(
                    ASR_ADVERSARIAL_MINILIBRISPEECH_TERMS_EVIDENCE_SHA256
                ),
                repository_media_policy=(
                    ASRAdversarialHumanExternalRepositoryMediaPolicy
                    .NOT_COMMITTED
                ),
                review_status="not_adjudicated",
                development_use_only=True,
            )
        )
    )

    return (
        verify_asr_adversarial_human_external_record_pair_v1(
            provenance=provenance,
            rights=rights,
        )
    )


def build_asr_adversarial_minilibrispeech_record_pairs_v1(
) -> tuple[
    tuple[
        ASRAdversarialHumanExternalRecordBundle,
        ASRAdversarialHumanExternalRecordBundle,
    ],
    ...,
]:
    """Build all eight canonical provenance/rights record pairs."""

    return tuple(
        build_asr_adversarial_minilibrispeech_record_pair_v1(
            case.utterance_id
        )
        for case in ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
    )
