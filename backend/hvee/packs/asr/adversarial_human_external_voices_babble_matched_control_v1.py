"""Matched-control VOiCES babble-interference evidence for adversarial ASR.

This source-visible artifact binds Hetren's I4e-A development-evidence slice.

The underlying VOiCES foreground speech was replayed and captured in real
rooms while source-declared distractor noise was played simultaneously.
The frozen I4e-A evidence selects exact babble-interference recordings and
exact no-distractor recordings under matched foreground, room, microphone,
angle, distance, sample-count, and duration conditions.

This artifact establishes a controlled physical-acoustic speech-interference
experiment. It intentionally does not claim verified conversational speaker
overlap, secondary-speaker timing, secondary-speaker transcripts, natural
crosstalk, production qualification, certification, release enforcement, or
an official release verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_evidence import (
    calculate_asr_adversarial_human_external_sha256,
)
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
)


ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SCHEMA_VERSION = 1

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_VERSION = "1.0.0"

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_KEY = (
    "hetren.asr.adversarial-human-external-"
    "voices-babble-matched-control"
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_SHA256 = (
    "a9958c8c0520ce2b070bf16b9a10ef8d"
    "23dcf65e50e5f8358b26f95d718941c4"
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_BYTES = (
    19_254
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ORDERED_PAIR_SHA256 = (
    "dd13eef17694c22689dacaa253e465ec"
    "01edcef33bf8d17f326e486e1663ce64"
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S = (
    "925062c1476b921cc5a458ee138894a735917a98aa8be9aa17ba6c76d0145674",
    "576026c4642e45e091decd79767f007d04d0bd2b9c80e66c67da41f8f3395b07",
    "1be66e975976a8f131c04cc7e3da321fd2d7f641c6f8a70d1e3c52b24b2a89f1",
    "e70ba0c734b50d6a7b4889d8805f4ce83b755d58cd0e389047964f15313f0d47",
    "bf6b8415b33d203a154da7f35c6d875ac0be83c86cf2956e154a30264624dd0c",
    "8df0f4b8a20da72865db9727b11756c6ac9d7b8d557648e34f8bff3311479ef2",
    "685c44565bf33da068ceb71d60f7d091bf644cae4f74524469f544f10e16a8c3",
    "a504f1cafe118597b0fa480bbdd6be719a8dbd4b52fd33e4f0681b1232446b93",
    "63b19e4f60390345a72a742ed735dfea43733f8e36834e2c7dfd10a211e9676c",
    "440a931129289a62282cd9ffe010ea16c047fcc66c12c246831cc4017d5b566e",
    "2db9ce0617952c833d31f9ab1d7e0e9af4a5297f18f3a58c1bc95168c2ab3920",
    "d74a287f392b7d1ac5b770df73b52df51625ab24836132fa78a9b90f273f86db",
    "7f480d2da95bf4885775fac98334eb27970b34d1f52eaad86eda2298ed0514d4",
    "9f64b9175c7cde666bf02e2526befc68f14acb567ed0cb0fb770cdc01b456b22",
    "6c250bd81831f48221e468f0e52d49e3ffab8e2eba1e1d086df4aa98c9495019",
    "0a405a689c021bab2b49a81c16147ed17767b087773150791da9dbfe69567db6",
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT = 16
ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT = 32

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SOURCE_COUNT = 2

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ROOMS = (
    "rm1",
    "rm2",
    "rm3",
    "rm4",
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_IDS = (
    1,
    5,
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_TYPES = (
    "stu",
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_LOCATIONS = (
    "clo",
    "far",
)

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ANGLE_DEGREES = 10

ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE = "babb"
ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL = "none"

# Filled immediately after deterministic payload computation.
ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256 = (
    "0a0b992393fa30dff055155403f4d127eb162cf00d7b5caa34e453d1a7af9b34"
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


def _ordered_pair_hashes_sha256(
    pair_hashes: tuple[str, ...],
) -> str:
    if (
        not isinstance(
            pair_hashes,
            tuple,
        )
        or not pair_hashes
    ):
        raise HveeContractError(
            "VOiCES babble pair hashes must be a non-empty tuple"
        )

    for pair_hash in pair_hashes:
        _require_sha256(
            name="VOiCES babble pair",
            value=pair_hash,
        )

    raw = json.dumps(
        list(
            pair_hashes
        ),
        ensure_ascii=False,
        sort_keys=False,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        raw
    ).hexdigest()


@dataclass(
    frozen=True,
    slots=True,
)
class ASRAdversarialVOiCESBabbleMatchedControlBundle:
    """Immutable identity wrapper for I4e-A matched-control evidence."""

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
                "VOiCES babble matched-control payload "
                "must be an object"
            )

        _require_sha256(
            name="VOiCES babble matched-control artifact",
            value=self.sha256,
        )

        try:
            calculated_sha256 = (
                calculate_asr_adversarial_voices_babble_matched_control_sha256(
                    self.payload
                )
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise HveeContractError(
                "VOiCES babble matched-control canonical "
                "payload is invalid"
            ) from error

        if (
            self.sha256
            != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
            or calculated_sha256
            != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
        ):
            raise HveeContractError(
                "VOiCES babble matched-control identity is unsupported; "
                "SHA-256 does not match its payload"
            )


def calculate_asr_adversarial_voices_babble_matched_control_sha256(
    payload: object,
) -> str:
    """Hash canonical I4e-A matched-control evidence."""

    return calculate_asr_adversarial_human_external_sha256(
        payload
    )


def _matched_control_payload(
) -> dict[str, object]:
    ordered_pair_digest = (
        _ordered_pair_hashes_sha256(
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S
        )
    )

    if (
        ordered_pair_digest
        != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ORDERED_PAIR_SHA256
    ):
        raise HveeContractError(
            "VOiCES babble ordered-pair identity changed"
        )

    return {
        "schema_version": (
            ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SCHEMA_VERSION
        ),
        "artifact": {
            "key": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_KEY
            ),
            "version": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_VERSION
            ),
            "type": (
                "source_visible_physical_acoustic_"
                "speech_interference_evidence"
            ),
        },
        "upstream": {
            "controlled_voices_sha256": (
                ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
            ),
            "external_evidence_sha256": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_SHA256
            ),
            "external_evidence_bytes": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_BYTES
            ),
            "ordered_pair_sha256": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ORDERED_PAIR_SHA256
            ),
        },
        "matched_control_design": {
            "pair_count": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT
            ),
            "audio_file_count": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT
            ),
            "foreground_source_count": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SOURCE_COUNT
            ),
            "rooms": list(
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ROOMS
            ),
            "microphone_ids": list(
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_IDS
            ),
            "microphone_type_codes": list(
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_TYPES
            ),
            "microphone_location_codes": list(
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_LOCATIONS
            ),
            "constant_angle_degrees": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ANGLE_DEGREES
            ),
            "interference_condition": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE
            ),
            "control_condition": (
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL
            ),
            "ordered_pair_sha256s": list(
                ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S
            ),
        },
        "source_methodology": {
            "real_room_recording_source_declared": True,
            "simultaneous_distractor_playback_source_declared": True,
            "babble_distractor_source_declared": True,
            "no_distractor_control_source_declared": True,
            "distractor_distance_metadata_source_declared": True,
        },
        "evidence_boundary": {
            "development_evidence_only": True,
            "source_declared_real_room_recording": True,
            "source_declared_simultaneous_distractor_playback": True,
            "source_declared_babble_interference": True,
            "matched_no_distractor_control_verified": True,
            "selected_media_bytes_reverified": True,
            "physical_acoustic_babble_interference_supported": True,
            "real_room_capture_supported": True,
            "selected_capture_is_post_hoc_digital_mix": False,
            "live_human_conversational_overlap_verified": False,
            "secondary_speaker_identity_verified": False,
            "secondary_speaker_transcript_verified": False,
            "secondary_speaker_timing_verified": False,
            "speaker_overlap_condition_verified": False,
            "natural_crosstalk_verified": False,
            "spoken_content_independently_verified": False,
            "asr_execution_verified": False,
            "rights_adjudicated": False,
            "qualification_threshold_applied": False,
            "certification_issued": False,
            "production_qualified": False,
            "release_enforcement_eligible": False,
            "official_release_verdict_modified": False,
        },
    }


def build_asr_adversarial_voices_babble_matched_control_v1(
) -> ASRAdversarialVOiCESBabbleMatchedControlBundle:
    """Build the exact deterministic I4e-A evidence contract."""

    payload = _matched_control_payload()

    bundle = (
        ASRAdversarialVOiCESBabbleMatchedControlBundle(
            payload=payload,
            sha256=(
                calculate_asr_adversarial_voices_babble_matched_control_sha256(
                    payload
                )
            ),
        )
    )

    if (
        bundle.sha256
        != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
    ):
        raise HveeContractError(
            "VOiCES babble matched-control v1 identity changed"
        )

    return bundle


def verify_asr_adversarial_voices_babble_matched_control_v1(
    *,
    payload: object,
    expected_sha256: str,
) -> ASRAdversarialVOiCESBabbleMatchedControlBundle:
    """Verify the exact frozen I4e-A source-visible contract."""

    _require_sha256(
        name="expected VOiCES babble matched-control artifact",
        value=expected_sha256,
    )

    if (
        expected_sha256
        != ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256
    ):
        raise HveeContractError(
            "VOiCES babble matched-control identity is unsupported"
        )

    expected = (
        build_asr_adversarial_voices_babble_matched_control_v1()
    )

    try:
        payload_sha256 = (
            calculate_asr_adversarial_voices_babble_matched_control_sha256(
                payload
            )
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise HveeContractError(
            "VOiCES babble matched-control failed "
            "canonical verification"
        ) from error

    if (
        payload_sha256 != expected.sha256
        or expected_sha256 != expected.sha256
    ):
        raise HveeContractError(
            "VOiCES babble matched-control failed "
            "canonical verification"
        )

    return expected


__all__ = [
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ANGLE_DEGREES",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_AUDIO_FILE_COUNT",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_CONTROL",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_BYTES",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_EXTERNAL_SHA256",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_INTERFERENCE",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_KEY",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_IDS",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_LOCATIONS",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_MICROPHONE_TYPES",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ORDERED_PAIR_SHA256",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_COUNT",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_PAIR_SHA256S",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_ROOMS",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SCHEMA_VERSION",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SHA256",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_SOURCE_COUNT",
    "ASR_ADVERSARIAL_VOICES_BABBLE_MATCHED_CONTROL_VERSION",
    "ASRAdversarialVOiCESBabbleMatchedControlBundle",
    "build_asr_adversarial_voices_babble_matched_control_v1",
    "calculate_asr_adversarial_voices_babble_matched_control_sha256",
    "verify_asr_adversarial_voices_babble_matched_control_v1",
]
