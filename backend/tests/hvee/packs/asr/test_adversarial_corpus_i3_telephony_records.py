"""Frozen I3 telephony-bandwidth adversarial ASR record identities."""

from __future__ import annotations

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV,
)
from hvee.packs.asr.adversarial_corpus_records import (
    verify_asr_adversarial_corpus_record_v1,
)
from scripts.build_adversarial_asr_corpus_v1_telephony_records import (
    CASE_ID,
    FFMPEG_PCM8K_ENVIRONMENT_SHA256,
    OUTPUT_RELATIVE_PATH,
    PARENT_AUDIO_SHA256,
    PARENT_CASE_ID,
    PARENT_MANIFEST_SHA256,
    PARENT_RELATIVE_PATH,
    PROVENANCE_RECORD_SHA256,
    RIGHTS_RECORD_SHA256,
    build_records,
)


EXPECTED_TRANSFORMATION_SHA256 = (
    "e1de2962fc3f074382c75cb8850a9bc0"
    "2d9b58930b93c0751df679bea535fcdb"
)

EXPECTED_DERIVATION_PLAN_SHA256 = (
    "6bbd708654191b4f3487e200a464b283"
    "dda4a78cc4261b1b18c51f3908af20a9"
)

EXPECTED_PARENT_MANIFEST_SHA256 = (
    "9823b12023ed39ff482f8636dd8625d0"
    "294905f7f4e406a555506e3ecb766f38"
)

EXPECTED_PARENT_AUDIO_SHA256 = (
    "23f9af39d01afe47e932bd061467bd0b"
    "5f49dc8bf520c2a8296a4556c54f1297"
)

EXPECTED_ENVIRONMENT_SHA256 = (
    "3ac14031af8e2b8f316415b8758b28e1"
    "daa5207677305b064601cb5f6dfb8aa0"
)


def test_i3_telephony_record_identities_are_frozen():
    (
        transformation,
        derivation_plan,
    ) = build_records()

    assert (
        transformation.sha256
        == EXPECTED_TRANSFORMATION_SHA256
    )

    assert (
        derivation_plan.sha256
        == EXPECTED_DERIVATION_PLAN_SHA256
    )

    assert (
        PARENT_MANIFEST_SHA256
        == EXPECTED_PARENT_MANIFEST_SHA256
    )

    assert (
        PARENT_AUDIO_SHA256
        == EXPECTED_PARENT_AUDIO_SHA256
    )

    assert (
        FFMPEG_PCM8K_ENVIRONMENT_SHA256
        == EXPECTED_ENVIRONMENT_SHA256
    )


def test_i3_telephony_records_reverify_canonically():
    (
        transformation,
        derivation_plan,
    ) = build_records()

    verified_transformation = (
        verify_asr_adversarial_corpus_record_v1(
            payload=transformation.payload,
            expected_sha256=(
                transformation.sha256
            ),
        )
    )

    verified_plan = (
        verify_asr_adversarial_corpus_record_v1(
            payload=derivation_plan.payload,
            expected_sha256=(
                derivation_plan.sha256
            ),
        )
    )

    assert (
        verified_transformation
        == transformation
    )

    assert (
        verified_plan
        == derivation_plan
    )


def test_i3_telephony_transformation_binding():
    transformation, _plan = build_records()

    record = transformation.payload[
        "record"
    ]

    assert record[
        "case_id"
    ] == CASE_ID

    assert (
        record[
            "parent_audio_sha256"
        ]
        == EXPECTED_PARENT_AUDIO_SHA256
    )

    assert record[
        "tool"
    ] == {
        "key": "ffmpeg",
        "version": "5.1.9-0+deb12u1",
        "environment_sha256": (
            EXPECTED_ENVIRONMENT_SHA256
        ),
    }

    assert (
        record[
            "argv"
        ]
        == list(
            ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV
        )
    )

    assert record[
        "expected_output"
    ] == {
        "relative_path": OUTPUT_RELATIVE_PATH,
        "sample_rate_hz": 8_000,
        "channel_count": 1,
        "codec_name": "pcm_s16le",
    }


def test_i3_telephony_parent_lineage_is_exact():
    _transformation, plan = build_records()

    record = plan.payload[
        "record"
    ]

    assert (
        record[
            "parent_manifest_sha256"
        ]
        == EXPECTED_PARENT_MANIFEST_SHA256
    )

    assert len(
        record[
            "entries"
        ]
    ) == 1

    entry = record[
        "entries"
    ][0]

    assert (
        entry[
            "case_id"
        ]
        == CASE_ID
    )

    assert (
        entry[
            "parent_case_id"
        ]
        == PARENT_CASE_ID
    )

    assert (
        entry[
            "parent_relative_path"
        ]
        == PARENT_RELATIVE_PATH
    )

    assert (
        entry[
            "parent_audio_sha256"
        ]
        == EXPECTED_PARENT_AUDIO_SHA256
    )

    assert (
        entry[
            "output_relative_path"
        ]
        == OUTPUT_RELATIVE_PATH
    )

    assert (
        entry[
            "provenance_record_sha256"
        ]
        == PROVENANCE_RECORD_SHA256
    )

    assert (
        entry[
            "rights_record_sha256"
        ]
        == RIGHTS_RECORD_SHA256
    )

    assert (
        entry[
            "transformation_record_sha256"
        ]
        == EXPECTED_TRANSFORMATION_SHA256
    )


def test_i3_telephony_builder_is_deterministic_in_memory():
    first = build_records()
    second = build_records()

    assert first == second

    assert (
        first[0].sha256
        == second[0].sha256
    )

    assert (
        first[1].sha256
        == second[1].sha256
    )
