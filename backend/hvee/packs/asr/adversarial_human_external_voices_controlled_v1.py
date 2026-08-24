"""Controlled VOiCES human/external capture evidence for adversarial ASR.

This source-visible artifact binds Hetren's exact development-only VOiCES
controlled-capture slice.

The selected foreground speech originates from source dataset recordings
that were replayed and captured in real rooms. This artifact therefore
establishes specific controlled capture-condition facts without claiming
that the original human speakers were physically speaking in those rooms.

The contract binds:

- the independently frozen VOiCES source and rights evidence,
- the exact two-source train-partition selection,
- the exact 64-capture condition lattice,
- the external materialization-manifest identity,
- the pinned-media verification identity,
- source-declared room, distractor, microphone, location, and angle fields,
- independently joined foreground-distance metadata.

Raw audio, local filesystem paths, source URLs, and demographic attributes
are not embedded in this module.

This remains development evidence only. It does not establish broad human
acoustic diversity, microphone-type diversity, live-human-in-room diversity,
production qualification, certification, release enforcement, or an
official release verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_evidence import (
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID,
    ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION,
    calculate_asr_adversarial_human_external_sha256,
)


ASR_ADVERSARIAL_VOICES_CONTROLLED_SCHEMA_VERSION = 1

ASR_ADVERSARIAL_VOICES_CONTROLLED_VERSION = "1.0.0"

ASR_ADVERSARIAL_VOICES_CONTROLLED_KEY = (
    "hetren.asr.adversarial-human-external-"
    "voices-controlled-capture"
)

ASR_ADVERSARIAL_VOICES_COLLECTION_KEY = (
    "lab41-sri-voices"
)

ASR_ADVERSARIAL_VOICES_COLLECTION_VERSION = (
    "voices-devkit"
)

ASR_ADVERSARIAL_VOICES_DECLARED_LICENSE = (
    "CC BY 4.0"
)

ASR_ADVERSARIAL_VOICES_DEVKIT_ARCHIVE_SHA256 = (
    "dd79fd878bcf0faa250a918e13e8f1f0"
    "a19463ce1dc29bc343c3a55d0fa72329"
)

ASR_ADVERSARIAL_VOICES_RECORDING_METADATA_ARCHIVE_SHA256 = (
    "45c573afc80de8a027b2c870c77dac54"
    "8bc6c90ac6c475e059193699607396fc"
)

ASR_ADVERSARIAL_VOICES_SOURCE_DESCRIPTION_SHA256 = (
    "1723ea0f40bcacb8863047bdc6a3536f"
    "a0fb13a0335a07b167a9bdf3b7bb31d9"
)

ASR_ADVERSARIAL_VOICES_RIGHTS_EVIDENCE_SHA256 = (
    "61deed1d0090144a8ce4fbc6bc503312"
    "411e57c3ac3059ef0d5825a09fe01745"
)

ASR_ADVERSARIAL_VOICES_TERMS_EVIDENCE_SHA256 = (
    "9ba9550ad48438d0836ddab3da480b3b"
    "69ffa0aac7b7878b5a0039e7ab429411"
)

ASR_ADVERSARIAL_VOICES_RIGHTS_MANIFEST_SHA256 = (
    "48d3464a9d7718b72db92e6ded490d9a"
    "0f99e373c38de00a91b7e38ee9a25cf7"
)

ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTION_SHA256 = (
    "5919f15396171255f5ce5905e9cc26fe"
    "c8743df3e58a95c8d5649726f02c7c2e"
)

ASR_ADVERSARIAL_VOICES_MATERIALIZATION_MANIFEST_SHA256 = (
    "de02c18cbf82e00ef1b3e9ff6be64dc7"
    "f74b156c51538a4499c992ff73a7886c"
)

ASR_ADVERSARIAL_VOICES_MEDIA_VERIFICATION_REPORT_SHA256 = (
    "7d5f75110c241cc7d62335ce23b10838"
    "2bb4111cbe6bf30a5126e361888f733b"
)

ASR_ADVERSARIAL_VOICES_MEDIA_OBSERVATION_SHA256 = (
    "69c2f06c099a8b209f42d2f22d61d6bf"
    "3397be1b2d378766b0a015a6f4fd8380"
)

ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS = (
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

ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS = (
    "rm1",
    "rm2",
    "rm3",
    "rm4",
)

ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS = (
    "babb",
    "musi",
    "none",
    "tele",
)

ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS = (
    1,
    5,
)

ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_TYPE_CODES = (
    "stu",
)

ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_LOCATION_CODES = (
    "clo",
    "far",
)

ASR_ADVERSARIAL_VOICES_CONTROLLED_CONSTANT_ANGLE_DEGREES = (
    10
)

ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256 = (
    "2f2749622f34ef6332ba6fa7f2f9219f"
    "dcc39f30617e153033a888693f61ffe9"
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
            character
            not in "0123456789abcdef"
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
class ASRAdversarialVOiCESControlledBundle:
    """Immutable identity wrapper for the controlled VOiCES artifact."""

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
                "controlled VOiCES payload must be an object"
            )

        _require_sha256(
            name="controlled VOiCES artifact",
            value=self.sha256,
        )

        if (
            calculate_asr_adversarial_human_external_sha256(
                self.payload
            )
            != self.sha256
        ):
            raise HveeContractError(
                "controlled VOiCES SHA-256 "
                "does not match its payload"
            )


def calculate_asr_adversarial_voices_controlled_sha256(
    payload: object,
) -> str:
    """Hash canonical controlled VOiCES evidence."""

    return (
        calculate_asr_adversarial_human_external_sha256(
            payload
        )
    )


def _controlled_payload(
) -> dict[str, object]:
    return {
        "schema_version": (
            ASR_ADVERSARIAL_VOICES_CONTROLLED_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_VERSION
            ),
            "type": (
                "source_visible_adversarial_human_external_"
                "controlled_capture_evidence"
            ),
        },
        "human_external_corpus": {
            "corpus_id": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_ID
            ),
            "corpus_version": (
                ASR_ADVERSARIAL_HUMAN_EXTERNAL_CORPUS_VERSION
            ),
        },
        "source": {
            "collection_key": (
                ASR_ADVERSARIAL_VOICES_COLLECTION_KEY
            ),
            "collection_version": (
                ASR_ADVERSARIAL_VOICES_COLLECTION_VERSION
            ),
            "declared_license": (
                ASR_ADVERSARIAL_VOICES_DECLARED_LICENSE
            ),
            "repository_media_policy": (
                "not_committed"
            ),
            "voices_devkit_archive_sha256": (
                ASR_ADVERSARIAL_VOICES_DEVKIT_ARCHIVE_SHA256
            ),
            "recording_metadata_archive_sha256": (
                ASR_ADVERSARIAL_VOICES_RECORDING_METADATA_ARCHIVE_SHA256
            ),
            "source_description_sha256": (
                ASR_ADVERSARIAL_VOICES_SOURCE_DESCRIPTION_SHA256
            ),
            "rights_evidence_sha256": (
                ASR_ADVERSARIAL_VOICES_RIGHTS_EVIDENCE_SHA256
            ),
            "terms_evidence_sha256": (
                ASR_ADVERSARIAL_VOICES_TERMS_EVIDENCE_SHA256
            ),
            "rights_manifest_sha256": (
                ASR_ADVERSARIAL_VOICES_RIGHTS_MANIFEST_SHA256
            ),
        },
        "acquisition_evidence": {
            "controlled_selection_sha256": (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTION_SHA256
            ),
            "materialization_manifest_sha256": (
                ASR_ADVERSARIAL_VOICES_MATERIALIZATION_MANIFEST_SHA256
            ),
            "media_verification_report_sha256": (
                ASR_ADVERSARIAL_VOICES_MEDIA_VERIFICATION_REPORT_SHA256
            ),
            "media_observation_sha256": (
                ASR_ADVERSARIAL_VOICES_MEDIA_OBSERVATION_SHA256
            ),
        },
        "controlled_selection": {
            "partition": "train",
            "selected_source_count": 2,
            "selected_capture_count": 64,
            "captures_per_source": 32,
            "selected_source_keys": [
                list(
                    source_key
                )
                for source_key in (
                    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
                )
            ],
            "constant_angle_degrees": (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_CONSTANT_ANGLE_DEGREES
            ),
            "rooms": list(
                ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS
            ),
            "distractors": list(
                ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS
            ),
            "microphone_ids": list(
                ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS
            ),
            "microphone_type_codes": list(
                ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_TYPE_CODES
            ),
            "microphone_location_codes": list(
                ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_LOCATION_CODES
            ),
            "foreground_distance_inches_by_room_and_microphone": {
                "rm1": {
                    "mc01": 38,
                    "mc05": 119,
                },
                "rm2": {
                    "mc01": 80,
                    "mc05": 228,
                },
                "rm3": {
                    "mc01": 67,
                    "mc05": 281,
                },
                "rm4": {
                    "mc01": 72,
                    "mc05": 387,
                },
            },
        },
        "verified_media": {
            "file_count": 66,
            "source_file_count": 2,
            "capture_file_count": 64,
            "codec_names": [
                "pcm_s16le",
            ],
            "sample_rates_hz": [
                16_000,
            ],
            "channel_counts": [
                1,
            ],
            "sample_width_bytes": [
                2,
            ],
            "media_probe_verified": True,
            "post_probe_hash_stability": True,
            "controlled_condition_lattice_verified": True,
        },
        "evidence_boundary": {
            "source_speaker_ids_are_source_defined": True,
            "source_chapter_ids_are_source_defined": True,
            "source_segments_are_source_defined": True,
            "source_chapter_ids_treated_as_recording_sessions": False,
            "source_chapter_ids_treated_as_recording_environments": False,
            "speaker_attributes_inferred": False,
            "accent_inferred": False,
            "microphone_class_inferred": False,
            "recording_environment_inferred": False,
            "controlled_room_variation_verified": True,
            "controlled_distractor_variation_verified": True,
            "controlled_microphone_location_variation_verified": True,
            "controlled_foreground_distance_variation_verified": True,
            "constant_source_angle_verified": True,
            "technical_variation_establishes_acoustic_diversity": False,
            "human_acoustic_diversity_established": False,
            "microphone_type_diversity_established": False,
            "live_human_in_room_diversity_established": False,
            "source_declared_transcripts_bound": True,
            "spoken_content_independently_verified": False,
            "asr_execution_verified": False,
            "rights_adjudicated": False,
            "development_evidence_only": True,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }


def build_asr_adversarial_voices_controlled_v1(
) -> ASRAdversarialVOiCESControlledBundle:
    """Build the exact deterministic controlled VOiCES evidence."""

    payload = _controlled_payload()

    bundle = (
        ASRAdversarialVOiCESControlledBundle(
            payload=payload,
            sha256=(
                calculate_asr_adversarial_voices_controlled_sha256(
                    payload
                )
            ),
        )
    )

    if (
        bundle.sha256
        != ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
    ):
        raise HveeContractError(
            "controlled VOiCES v1 identity changed"
        )

    return bundle


def verify_asr_adversarial_voices_controlled_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialVOiCESControlledBundle:
    """Rebuild and verify the exact frozen controlled VOiCES artifact."""

    _require_sha256(
        name="expected controlled VOiCES artifact",
        value=expected_sha256,
    )

    if (
        expected_sha256
        != ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
    ):
        raise HveeContractError(
            "controlled VOiCES identity is unsupported"
        )

    expected = (
        build_asr_adversarial_voices_controlled_v1()
    )

    if (
        payload != expected.payload
        or expected_sha256
        != expected.sha256
    ):
        raise HveeContractError(
            "controlled VOiCES failed canonical verification"
        )

    return expected


__all__ = [
    "ASR_ADVERSARIAL_VOICES_COLLECTION_KEY",
    "ASR_ADVERSARIAL_VOICES_COLLECTION_VERSION",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_CONSTANT_ANGLE_DEGREES",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_DISTRACTORS",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_KEY",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_IDS",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_LOCATION_CODES",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_MICROPHONE_TYPE_CODES",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_ROOMS",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_SCHEMA_VERSION",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTION_SHA256",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256",
    "ASR_ADVERSARIAL_VOICES_CONTROLLED_VERSION",
    "ASR_ADVERSARIAL_VOICES_DECLARED_LICENSE",
    "ASR_ADVERSARIAL_VOICES_DEVKIT_ARCHIVE_SHA256",
    "ASR_ADVERSARIAL_VOICES_MATERIALIZATION_MANIFEST_SHA256",
    "ASR_ADVERSARIAL_VOICES_MEDIA_OBSERVATION_SHA256",
    "ASR_ADVERSARIAL_VOICES_MEDIA_VERIFICATION_REPORT_SHA256",
    "ASR_ADVERSARIAL_VOICES_RECORDING_METADATA_ARCHIVE_SHA256",
    "ASR_ADVERSARIAL_VOICES_RIGHTS_EVIDENCE_SHA256",
    "ASR_ADVERSARIAL_VOICES_RIGHTS_MANIFEST_SHA256",
    "ASR_ADVERSARIAL_VOICES_SOURCE_DESCRIPTION_SHA256",
    "ASR_ADVERSARIAL_VOICES_TERMS_EVIDENCE_SHA256",
    "ASRAdversarialVOiCESControlledBundle",
    "build_asr_adversarial_voices_controlled_v1",
    "calculate_asr_adversarial_voices_controlled_sha256",
    "verify_asr_adversarial_voices_controlled_v1",
]
