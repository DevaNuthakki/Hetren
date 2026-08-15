"""Frozen I3 lossy-compression adversarial ASR corpus records."""

from __future__ import annotations

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV,
    ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV,
)
from hvee.packs.asr.adversarial_corpus_records import (
    verify_asr_adversarial_corpus_record_v1,
)
from scripts.build_adversarial_asr_corpus_v1_telephony_records import (
    AAC_CASE_ID,
    AAC_OUTPUT_RELATIVE_PATH,
    AAC_TRANSFORMATION_RECORD_ID,
    FFMPEG_AAC_M4A_CBR32_ENVIRONMENT_SHA256,
    FFMPEG_MP3_CBR32_ENVIRONMENT_SHA256,
    FFMPEG_VERSION,
    MP3_CASE_ID,
    MP3_OUTPUT_RELATIVE_PATH,
    MP3_TRANSFORMATION_RECORD_ID,
    PARENT_AUDIO_SHA256,
    PARENT_CASE_ID,
    PARENT_RELATIVE_PATH,
    PROVENANCE_RECORD_SHA256,
    RIGHTS_RECORD_SHA256,
    build_records,
)


EXPECTED_AAC_TRANSFORMATION_SHA256 = (
    "0cbf53bd9f528f1b8345472d14b3e781"
    "9fec745de77c8df5843119d36eae95a0"
)

EXPECTED_MP3_TRANSFORMATION_SHA256 = (
    "a08d6dd8f929d4b5145ae31116d8cbc3"
    "30e1d6ea92e37a46006a275cbb128cf5"
)

EXPECTED_DERIVATION_PLAN_SHA256 = (
    "306b5c28556a95da98cf7169474d42bd"
    "55408dff75a9762a17d178565dac4489"
)

EXPECTED_AAC_ENVIRONMENT_SHA256 = (
    "8a23edea7a13d66422dbd083023cf7e8"
    "12cc8dbed8bb788d51fe799f9a62a877"
)

EXPECTED_MP3_ENVIRONMENT_SHA256 = (
    "9f442ee2686f49578f817b29a7303241"
    "b379b0b47d1743fc2d1684de77cb1bb3"
)

EXPECTED_PARENT_AUDIO_SHA256 = (
    "23f9af39d01afe47e932bd061467bd0b"
    "5f49dc8bf520c2a8296a4556c54f1297"
)


def _lossy_view():
    (
        _telephony,
        _mulaw,
        _alaw,
        _moderate,
        _severe,
        aac,
        mp3,
        plan,
    ) = build_records()

    return (
        aac,
        mp3,
        plan,
    )


def test_i3_lossy_record_identities_are_frozen():
    (
        aac,
        mp3,
        plan,
    ) = _lossy_view()

    assert (
        aac.sha256
        == EXPECTED_AAC_TRANSFORMATION_SHA256
    )

    assert (
        mp3.sha256
        == EXPECTED_MP3_TRANSFORMATION_SHA256
    )

    assert (
        plan.sha256
        == EXPECTED_DERIVATION_PLAN_SHA256
    )


def test_i3_aac_transformation_record_is_exact():
    (
        aac,
        _mp3,
        _plan,
    ) = _lossy_view()

    record = aac.payload[
        "record"
    ]

    assert (
        AAC_TRANSFORMATION_RECORD_ID
        == (
            "transform."
            "stress-codec-aac-multi-number-id-v1"
        )
    )

    assert record[
        "record_id"
    ] == AAC_TRANSFORMATION_RECORD_ID

    assert record[
        "case_id"
    ] == AAC_CASE_ID

    assert (
        record[
            "parent_audio_sha256"
        ]
        == EXPECTED_PARENT_AUDIO_SHA256
    )

    assert (
        FFMPEG_VERSION
        == "5.1.9-0+deb12u1"
    )

    assert record[
        "tool"
    ] == {
        "key": "ffmpeg",
        "version": FFMPEG_VERSION,
        "environment_sha256": (
            EXPECTED_AAC_ENVIRONMENT_SHA256
        ),
    }

    assert (
        FFMPEG_AAC_M4A_CBR32_ENVIRONMENT_SHA256
        == EXPECTED_AAC_ENVIRONMENT_SHA256
    )

    assert record[
        "argv"
    ] == list(
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_ARGV
    )

    assert record[
        "expected_output"
    ] == {
        "relative_path": (
            AAC_OUTPUT_RELATIVE_PATH
        ),
        "sample_rate_hz": 16_000,
        "channel_count": 1,
        "codec_name": "aac",
    }


def test_i3_mp3_transformation_record_is_exact():
    (
        _aac,
        mp3,
        _plan,
    ) = _lossy_view()

    record = mp3.payload[
        "record"
    ]

    assert (
        MP3_TRANSFORMATION_RECORD_ID
        == (
            "transform."
            "stress-codec-mp3-multi-number-id-v1"
        )
    )

    assert record[
        "record_id"
    ] == MP3_TRANSFORMATION_RECORD_ID

    assert record[
        "case_id"
    ] == MP3_CASE_ID

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
        "version": FFMPEG_VERSION,
        "environment_sha256": (
            EXPECTED_MP3_ENVIRONMENT_SHA256
        ),
    }

    assert (
        FFMPEG_MP3_CBR32_ENVIRONMENT_SHA256
        == EXPECTED_MP3_ENVIRONMENT_SHA256
    )

    assert record[
        "argv"
    ] == list(
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_ARGV
    )

    assert record[
        "expected_output"
    ] == {
        "relative_path": (
            MP3_OUTPUT_RELATIVE_PATH
        ),
        "sample_rate_hz": 16_000,
        "channel_count": 1,
        "codec_name": "mp3",
    }


def test_i3_seven_case_plan_binds_lossy_lineage_exactly():
    (
        aac,
        mp3,
        plan,
    ) = _lossy_view()

    record = plan.payload[
        "record"
    ]

    entries = record[
        "entries"
    ]

    assert len(
        entries
    ) == 7

    assert [
        entry[
            "case_id"
        ]
        for entry in entries
    ] == [
        "stress.codec-aac.multi-number-id",
        "stress.codec-alaw.multi-number-id",
        "stress.codec-mp3.multi-number-id",
        "stress.codec-mulaw.multi-number-id",
        "stress.noise-moderate.multi-number-id",
        "stress.noise-severe-usable.multi-number-id",
        "stress.telephony-bandwidth.multi-number-id",
    ]

    by_case = {
        entry[
            "case_id"
        ]: entry
        for entry in entries
    }

    expected = {
        AAC_CASE_ID: {
            "output": AAC_OUTPUT_RELATIVE_PATH,
            "transformation": aac.sha256,
        },
        MP3_CASE_ID: {
            "output": MP3_OUTPUT_RELATIVE_PATH,
            "transformation": mp3.sha256,
        },
    }

    for case_id, identity in expected.items():
        entry = by_case[
            case_id
        ]

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
            == PARENT_AUDIO_SHA256
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
                "output_relative_path"
            ]
            == identity[
                "output"
            ]
        )

        assert (
            entry[
                "transformation_record_sha256"
            ]
            == identity[
                "transformation"
            ]
        )


def test_i3_lossy_records_reverify_canonically():
    for bundle in _lossy_view():
        assert (
            verify_asr_adversarial_corpus_record_v1(
                payload=bundle.payload,
                expected_sha256=bundle.sha256,
            )
            == bundle
        )


def test_i3_lossy_evidence_remains_non_authoritative():
    expected_boundary = {
        "certification_issued": False,
        "development_evidence_only": True,
        "human_acoustic_diversity_established": False,
        "official_release_verdict_modified": False,
        "production_qualified": False,
        "qualification_threshold_applied": False,
        "release_enforcement_eligible": False,
        "rights_adjudicated": False,
        "speaker_attributes_inferred": False,
    }

    for bundle in _lossy_view():
        assert (
            bundle.payload[
                "evidence_boundary"
            ]
            == expected_boundary
        )
