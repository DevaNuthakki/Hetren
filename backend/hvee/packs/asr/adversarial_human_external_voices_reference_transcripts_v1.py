"""Source-visible VOiCES reference-transcript evidence for adversarial ASR.

This I4e-B4 artifact binds the exact source-declared orthographic transcripts
for the two foreground recordings used by Hetren's frozen VOiCES babble versus
no-distractor matched-control slice.

The transcript rows were selected from the official VOiCES devkit
``references/train_index.csv`` after verifying the complete file's byte length
and SHA-256.  Every one of the 32 index rows for each source agreed on the
source path, transcript, source media statistics, and exact room/distractor/
microphone/angle lattice.

This artifact binds trusted dataset reference text for later ASR execution. It
does not claim that Hetren independently transcribed the source audio, that the
babble speakers have transcripts, that an ASR system was executed, or that a
production/release verdict was issued.
"""

from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_evidence import (
    calculate_asr_adversarial_human_external_sha256,
)
from hvee.packs.asr.adversarial_human_external_voices_babble_matched_control_v1 import (
    ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_COLLECTION_KEY,
    ASR_ADVERSARIAL_VOICES_COLLECTION_VERSION,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
    ASR_ADVERSARIAL_VOICES_DEVKIT_ARCHIVE_SHA256,
)


ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SCHEMA_VERSION = 1

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_VERSION = "1.0.0"

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_KEY = (
    "hetren.asr.adversarial-human-external-"
    "voices-reference-transcripts"
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_ARCHIVE_PATH = (
    "VOiCES_devkit/references/train_index.csv"
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_RETAINED_PATH = (
    "references/train_index.csv"
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_BYTES = (
    7_170_342
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_SHA256 = (
    "223219468240d96889dd74f52c26e081"
    "2453a24ae6462f76077d4b95819552b4"
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SELECTED_INDEX_SHA256 = (
    "5d32141bff6340beb4b7c47687e2824f"
    "f52ffaf52269a50530917aa6613b4d5b"
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_KEYS = (
    (
        652,
        129742,
        3,
    ),
    (
        7850,
        111771,
        4,
    ),
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS = (
    (
        "cabbage salad chop or shave fine half "
        "a medium size head of cabbage that has "
        "been left in cold water until crisp "
        "then drain"
    ),
    (
        "indeed if ever a general deserved honor "
        "grant had won it he had opened the "
        "mississippi to navigation and had "
        "captured nearly one hundred thousand "
        "prisoners and arms"
    ),
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S = (
    "63f61783189d5e3ce9bc6e900e80d29b35a55775e07cc5d24698fc20b20d90f8",
    "085ab0d18cd4d3e5e495fc38b6a69077695746d272d9f487548405392f8e97e9",
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_COUNT = 2
ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROWS_PER_SOURCE = 32
ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROW_COUNT = 64

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_ROOMS = (
    "rm1",
    "rm2",
    "rm3",
    "rm4",
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_DISTRACTORS = (
    "babb",
    "musi",
    "none",
    "tele",
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_MICROPHONE_IDS = (
    1,
    5,
)

ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_ANGLE_DEGREES = 10

# Filled after deterministic source-visible payload computation.
ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256 = (
    "b6a87eda150c732a13513ccc1b50e08e33195203800cd7c94c2a6bbddfa1fc45"
)


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256"
        )

    return value


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESReferenceTranscriptsBundle:
    """Immutable identity wrapper for I4e-B4 transcript evidence."""

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
                "VOiCES reference-transcript payload must be an object"
            )

        _require_sha256(
            name="VOiCES reference-transcript artifact",
            value=self.sha256,
        )

        try:
            calculated_sha256 = (
                calculate_asr_adversarial_voices_reference_transcripts_sha256(
                    self.payload
                )
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise HveeContractError(
                "VOiCES reference-transcript canonical payload is invalid"
            ) from error

        if (
            self.sha256
            != ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
            or calculated_sha256
            != ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
        ):
            raise HveeContractError(
                "VOiCES reference-transcript identity is unsupported; "
                "SHA-256 does not match its payload"
            )


def calculate_asr_adversarial_voices_reference_transcripts_sha256(
    payload: object,
) -> str:
    """Hash canonical I4e-B4 reference-transcript evidence."""

    return calculate_asr_adversarial_human_external_sha256(
        payload
    )


def _source_payloads(
) -> list[dict[str, object]]:
    return [
        {
            "source_key": {
                "speaker_id": 652,
                "chapter_id": 129742,
                "segment_id": 3,
            },
            "source_relative_path": (
                "source-16k/train/sp0652/"
                "Lab41-SRI-VOiCES-src-"
                "sp0652-ch129742-sg0003.wav"
            ),
            "source_index_gender": "M",
            "reference_transcript": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS[0]
            ),
            "reference_transcript_sha256": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S[0]
            ),
            "source_sample_count": 146_880,
            "source_sample_rate_hz": 16_000,
            "source_duration_seconds": "9.18",
            "official_index_capture_row_count": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROWS_PER_SOURCE
            ),
        },
        {
            "source_key": {
                "speaker_id": 7850,
                "chapter_id": 111771,
                "segment_id": 4,
            },
            "source_relative_path": (
                "source-16k/train/sp7850/"
                "Lab41-SRI-VOiCES-src-"
                "sp7850-ch111771-sg0004.wav"
            ),
            "source_index_gender": "F",
            "reference_transcript": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS[1]
            ),
            "reference_transcript_sha256": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPT_SHA256S[1]
            ),
            "source_sample_count": 176_081,
            "source_sample_rate_hz": 16_000,
            "source_duration_seconds": "11.0050625",
            "official_index_capture_row_count": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROWS_PER_SOURCE
            ),
        },
    ]


def _reference_transcripts_payload(
) -> dict[str, object]:
    return {
        "schema_version": (
            ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_VERSION
            ),
            "type": (
                "source_visible_dataset_reference_transcript_evidence"
            ),
        },
        "upstream": {
            "collection_key": (
                ASR_ADVERSARIAL_VOICES_COLLECTION_KEY
            ),
            "collection_version": (
                ASR_ADVERSARIAL_VOICES_COLLECTION_VERSION
            ),
            "voices_devkit_archive_sha256": (
                ASR_ADVERSARIAL_VOICES_DEVKIT_ARCHIVE_SHA256
            ),
            "controlled_voices_sha256": (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
            ),
            "babble_matched_control_sha256": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
            ),
            "train_index_archive_path": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_ARCHIVE_PATH
            ),
            "train_index_retained_path": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_RETAINED_PATH
            ),
            "train_index_bytes": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_BYTES
            ),
            "train_index_sha256": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_TRAIN_INDEX_SHA256
            ),
            "selected_index_projection_sha256": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SELECTED_INDEX_SHA256
            ),
        },
        "source_reference_transcripts": (
            _source_payloads()
        ),
        "verification": {
            "selected_source_count": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SOURCE_COUNT
            ),
            "official_index_capture_row_count": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROW_COUNT
            ),
            "official_index_capture_rows_per_source": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_CAPTURE_ROWS_PER_SOURCE
            ),
            "rooms": list(
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_ROOMS
            ),
            "distractors": list(
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_DISTRACTORS
            ),
            "microphone_ids": list(
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_MICROPHONE_IDS
            ),
            "constant_angle_degrees": (
                ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_ANGLE_DEGREES
            ),
            "complete_train_index_bytes_verified": True,
            "complete_train_index_sha256_verified": True,
            "selected_rows_parsed_by_column_name": True,
            "exact_source_keys_verified": True,
            "source_paths_consistent_per_source": True,
            "reference_transcripts_consistent_per_source": True,
            "source_media_statistics_consistent_per_source": True,
            "exact_capture_condition_lattice_verified": True,
        },
        "evidence_boundary": {
            "development_evidence_only": True,
            "official_dataset_reference_metadata_verified": True,
            "source_declared_reference_transcripts_bound": True,
            "matched_control_foreground_reference_text_ready": True,
            "source_audio_spoken_content_independently_verified": False,
            "babble_speaker_transcripts_verified": False,
            "secondary_speaker_identity_verified": False,
            "secondary_speaker_timing_verified": False,
            "speaker_overlap_condition_verified": False,
            "natural_crosstalk_verified": False,
            "adversarial_suite_built": False,
            "asr_execution_verified": False,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }


def build_asr_adversarial_voices_reference_transcripts_v1(
) -> ASRAdversarialVOiCESReferenceTranscriptsBundle:
    """Build the exact deterministic I4e-B4 transcript contract."""

    payload = _reference_transcripts_payload()

    bundle = (
        ASRAdversarialVOiCESReferenceTranscriptsBundle(
            payload=payload,
            sha256=(
                calculate_asr_adversarial_voices_reference_transcripts_sha256(
                    payload
                )
            ),
        )
    )

    if (
        bundle.sha256
        != ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
    ):
        raise HveeContractError(
            "VOiCES reference-transcript v1 identity changed"
        )

    return bundle


def verify_asr_adversarial_voices_reference_transcripts_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialVOiCESReferenceTranscriptsBundle:
    """Verify the exact frozen I4e-B4 source-visible contract."""

    _require_sha256(
        name="expected VOiCES reference-transcript artifact",
        value=expected_sha256,
    )

    if (
        expected_sha256
        != ASR_ADVERSARIAL_VOICES_REFERENCE_TRANSCRIPTS_SHA256
    ):
        raise HveeContractError(
            "VOiCES reference-transcript identity is unsupported"
        )

    expected = (
        build_asr_adversarial_voices_reference_transcripts_v1()
    )

    try:
        payload_sha256 = (
            calculate_asr_adversarial_voices_reference_transcripts_sha256(
                payload
            )
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise HveeContractError(
            "VOiCES reference-transcript failed canonical verification"
        ) from error

    if (
        payload_sha256 != expected.sha256
        or expected_sha256 != expected.sha256
    ):
        raise HveeContractError(
            "VOiCES reference-transcript failed canonical verification"
        )

    return ASRAdversarialVOiCESReferenceTranscriptsBundle(
        payload=expected.payload,
        sha256=expected.sha256,
    )
