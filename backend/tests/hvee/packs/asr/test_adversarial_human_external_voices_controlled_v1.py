from __future__ import annotations

import copy

import pytest

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.adversarial_human_external_voices_controlled_v1 import (
    ASR_ADVERSARIAL_VOICES_CONTROLLED_KEY,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SCHEMA_VERSION,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256,
    ASR_ADVERSARIAL_VOICES_CONTROLLED_VERSION,
    ASRAdversarialVOiCESControlledBundle,
    build_asr_adversarial_voices_controlled_v1,
    calculate_asr_adversarial_voices_controlled_sha256,
    verify_asr_adversarial_voices_controlled_v1,
)


def test_voices_controlled_identity_is_frozen():
    first = (
        build_asr_adversarial_voices_controlled_v1()
    )

    second = (
        build_asr_adversarial_voices_controlled_v1()
    )

    assert first == second

    assert first.sha256 == (
        ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
    )

    assert first.sha256 == (
        "2f2749622f34ef6332ba6fa7f2f9219f"
        "dcc39f30617e153033a888693f61ffe9"
    )


def test_voices_controlled_binds_exact_artifact_identity():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    assert bundle.payload[
        "schema_version"
    ] == (
        ASR_ADVERSARIAL_VOICES_CONTROLLED_SCHEMA_VERSION
    )

    assert bundle.payload[
        "artifact"
    ] == {
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
    }


def test_voices_controlled_binds_frozen_external_evidence_chain():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    source = bundle.payload[
        "source"
    ]

    assert source == {
        "collection_key": "lab41-sri-voices",
        "collection_version": "voices-devkit",
        "declared_license": "CC BY 4.0",
        "repository_media_policy": "not_committed",
        "voices_devkit_archive_sha256": (
            "dd79fd878bcf0faa250a918e13e8f1f0"
            "a19463ce1dc29bc343c3a55d0fa72329"
        ),
        "recording_metadata_archive_sha256": (
            "45c573afc80de8a027b2c870c77dac54"
            "8bc6c90ac6c475e059193699607396fc"
        ),
        "source_description_sha256": (
            "1723ea0f40bcacb8863047bdc6a3536f"
            "a0fb13a0335a07b167a9bdf3b7bb31d9"
        ),
        "rights_evidence_sha256": (
            "61deed1d0090144a8ce4fbc6bc503312"
            "411e57c3ac3059ef0d5825a09fe01745"
        ),
        "terms_evidence_sha256": (
            "9ba9550ad48438d0836ddab3da480b3b"
            "69ffa0aac7b7878b5a0039e7ab429411"
        ),
        "rights_manifest_sha256": (
            "48d3464a9d7718b72db92e6ded490d9a"
            "0f99e373c38de00a91b7e38ee9a25cf7"
        ),
    }

    assert bundle.payload[
        "acquisition_evidence"
    ] == {
        "controlled_selection_sha256": (
            "5919f15396171255f5ce5905e9cc26fe"
            "c8743df3e58a95c8d5649726f02c7c2e"
        ),
        "materialization_manifest_sha256": (
            "de02c18cbf82e00ef1b3e9ff6be64dc7"
            "f74b156c51538a4499c992ff73a7886c"
        ),
        "media_verification_report_sha256": (
            "7d5f75110c241cc7d62335ce23b10838"
            "2bb4111cbe6bf30a5126e361888f733b"
        ),
        "media_observation_sha256": (
            "69c2f06c099a8b209f42d2f22d61d6bf"
            "3397be1b2d378766b0a015a6f4fd8380"
        ),
    }


def test_voices_controlled_selection_is_exact():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    selection = bundle.payload[
        "controlled_selection"
    ]

    assert selection[
        "partition"
    ] == "train"

    assert selection[
        "selected_source_count"
    ] == 2

    assert selection[
        "selected_capture_count"
    ] == 64

    assert selection[
        "captures_per_source"
    ] == 32

    assert selection[
        "selected_source_keys"
    ] == [
        [
            652,
            129742,
            3,
        ],
        [
            7850,
            111771,
            4,
        ],
    ]

    assert tuple(
        tuple(
            source_key
        )
        for source_key in selection[
            "selected_source_keys"
        ]
    ) == (
        ASR_ADVERSARIAL_VOICES_CONTROLLED_SELECTED_SOURCE_KEYS
    )

    assert selection[
        "constant_angle_degrees"
    ] == 10


def test_voices_controlled_condition_lattice_is_exact():
    selection = (
        build_asr_adversarial_voices_controlled_v1()
        .payload[
            "controlled_selection"
        ]
    )

    assert selection[
        "rooms"
    ] == [
        "rm1",
        "rm2",
        "rm3",
        "rm4",
    ]

    assert selection[
        "distractors"
    ] == [
        "babb",
        "musi",
        "none",
        "tele",
    ]

    assert selection[
        "microphone_ids"
    ] == [
        1,
        5,
    ]

    assert selection[
        "microphone_type_codes"
    ] == [
        "stu",
    ]

    assert selection[
        "microphone_location_codes"
    ] == [
        "clo",
        "far",
    ]

    assert (
        len(
            selection[
                "rooms"
            ]
        )
        * len(
            selection[
                "distractors"
            ]
        )
        * len(
            selection[
                "microphone_ids"
            ]
        )
        == 32
    )


def test_voices_controlled_foreground_distance_geometry_is_exact():
    selection = (
        build_asr_adversarial_voices_controlled_v1()
        .payload[
            "controlled_selection"
        ]
    )

    assert selection[
        "foreground_distance_inches_by_room_and_microphone"
    ] == {
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
    }


def test_voices_controlled_verified_media_is_exact():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    assert bundle.payload[
        "verified_media"
    ] == {
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
    }


def test_voices_controlled_positive_claims_are_narrow():
    boundary = (
        build_asr_adversarial_voices_controlled_v1()
        .payload[
            "evidence_boundary"
        ]
    )

    for field_name in (
        "source_speaker_ids_are_source_defined",
        "source_chapter_ids_are_source_defined",
        "source_segments_are_source_defined",
        "controlled_room_variation_verified",
        "controlled_distractor_variation_verified",
        "controlled_microphone_location_variation_verified",
        "controlled_foreground_distance_variation_verified",
        "constant_source_angle_verified",
        "source_declared_transcripts_bound",
        "development_evidence_only",
    ):
        assert boundary[
            field_name
        ] is True


def test_voices_controlled_authority_and_broad_claims_stay_negative():
    boundary = (
        build_asr_adversarial_voices_controlled_v1()
        .payload[
            "evidence_boundary"
        ]
    )

    for field_name in (
        "source_chapter_ids_treated_as_recording_sessions",
        "source_chapter_ids_treated_as_recording_environments",
        "speaker_attributes_inferred",
        "accent_inferred",
        "microphone_class_inferred",
        "recording_environment_inferred",
        "technical_variation_establishes_acoustic_diversity",
        "human_acoustic_diversity_established",
        "microphone_type_diversity_established",
        "live_human_in_room_diversity_established",
        "spoken_content_independently_verified",
        "asr_execution_verified",
        "rights_adjudicated",
        "qualification_threshold_applied",
        "certification_issued",
        "production_qualified",
        "release_enforcement_eligible",
        "official_release_verdict_modified",
    ):
        assert boundary[
            field_name
        ] is False


def test_voices_controlled_contains_no_raw_locator_or_local_path():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    serialized = repr(
        bundle.payload
    )

    assert "https://" not in serialized
    assert "/Users/" not in serialized
    assert "hetren-local-evidence" not in serialized
    assert ".wav" not in serialized


def test_voices_controlled_contains_no_run_timestamp():
    serialized = repr(
        build_asr_adversarial_voices_controlled_v1()
        .payload
    ).lower()

    assert "timestamp" not in serialized
    assert "created_at" not in serialized
    assert "generated_at" not in serialized


def test_voices_controlled_verifies_exact_identity():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    verified = (
        verify_asr_adversarial_voices_controlled_v1(
            payload=bundle.payload,
            expected_sha256=(
                bundle.sha256
            ),
        )
    )

    assert verified == bundle


def test_voices_controlled_rejects_tampering():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "evidence_boundary"
    ][
        "production_qualified"
    ] = True

    with pytest.raises(
        HveeContractError,
        match="canonical verification",
    ):
        verify_asr_adversarial_voices_controlled_v1(
            payload=tampered,
            expected_sha256=bundle.sha256,
        )


def test_voices_controlled_rehashed_substitution_is_unsupported():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    tampered = copy.deepcopy(
        bundle.payload
    )

    tampered[
        "controlled_selection"
    ][
        "selected_capture_count"
    ] = 63

    substituted_sha256 = (
        calculate_asr_adversarial_voices_controlled_sha256(
            tampered
        )
    )

    assert substituted_sha256 != (
        bundle.sha256
    )

    with pytest.raises(
        HveeContractError,
        match="identity is unsupported",
    ):
        verify_asr_adversarial_voices_controlled_v1(
            payload=tampered,
            expected_sha256=(
                substituted_sha256
            ),
        )


def test_voices_controlled_bundle_rejects_wrong_digest():
    bundle = (
        build_asr_adversarial_voices_controlled_v1()
    )

    with pytest.raises(
        HveeContractError,
        match="does not match its payload",
    ):
        ASRAdversarialVOiCESControlledBundle(
            payload=bundle.payload,
            sha256=(
                "0" * 64
            ),
        )


def test_voices_controlled_contract_is_publicly_exported():
    import hvee.packs.asr as asr

    expected_names = (
        "ASR_ADVERSARIAL_VOICES_CONTROLLED_KEY",
        "ASR_ADVERSARIAL_VOICES_CONTROLLED_SCHEMA_VERSION",
        "ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256",
        "ASR_ADVERSARIAL_VOICES_CONTROLLED_VERSION",
        "ASRAdversarialVOiCESControlledBundle",
        "build_asr_adversarial_voices_controlled_v1",
        "calculate_asr_adversarial_voices_controlled_sha256",
        "verify_asr_adversarial_voices_controlled_v1",
    )

    for name in expected_names:
        assert hasattr(
            asr,
            name,
        )

        assert name in (
            asr.__all__
        )

    bundle = (
        asr.build_asr_adversarial_voices_controlled_v1()
    )

    assert bundle.sha256 == (
        asr.ASR_ADVERSARIAL_VOICES_CONTROLLED_SHA256
    )
