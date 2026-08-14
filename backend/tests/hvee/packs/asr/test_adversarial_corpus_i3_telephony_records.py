"""Frozen I3 telephony and G.711 adversarial ASR records."""

from __future__ import annotations

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_ALAW8K_ARGV,
    ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV,
    ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV,
)
from hvee.packs.asr.adversarial_corpus_records import (
    verify_asr_adversarial_corpus_record_v1,
)
from scripts.build_adversarial_asr_corpus_v1_telephony_records import (
    ALAW_CASE_ID,
    ALAW_OUTPUT_RELATIVE_PATH,
    CASE_ID,
    FFMPEG_ALAW8K_ENVIRONMENT_SHA256,
    FFMPEG_MULAW8K_ENVIRONMENT_SHA256,
    FFMPEG_PCM8K_ENVIRONMENT_SHA256,
    MULAW_CASE_ID,
    MULAW_OUTPUT_RELATIVE_PATH,
    OUTPUT_RELATIVE_PATH,
    PARENT_AUDIO_SHA256,
    PARENT_CASE_ID,
    PARENT_MANIFEST_SHA256,
    PARENT_RELATIVE_PATH,
    PROVENANCE_RECORD_SHA256,
    RIGHTS_RECORD_SHA256,
    build_records,
)


EXPECTED_TELEPHONY_TRANSFORMATION_SHA256 = (
    "e1de2962fc3f074382c75cb8850a9bc0"
    "2d9b58930b93c0751df679bea535fcdb"
)

EXPECTED_MULAW_TRANSFORMATION_SHA256 = (
    "5d2f4c99e16410a359d92aeb7bfc7f42"
    "579927d1eeacbc70d9af256d596636c2"
)

EXPECTED_ALAW_TRANSFORMATION_SHA256 = (
    "5d7202803ca6b26f0ac8ef45fcf42ed7"
    "f9b87e70279eee0dc76f8e792ebdb2ed"
)

EXPECTED_DERIVATION_PLAN_SHA256 = (
    "bdfcbea2d5983f5c3f72b8d58ddac549"
    "0b6e0641e18a7d6c5f213ebc26fbf8f4"
)

EXPECTED_PARENT_MANIFEST_SHA256 = (
    "9823b12023ed39ff482f8636dd8625d0"
    "294905f7f4e406a555506e3ecb766f38"
)

EXPECTED_PARENT_AUDIO_SHA256 = (
    "23f9af39d01afe47e932bd061467bd0b"
    "5f49dc8bf520c2a8296a4556c54f1297"
)

EXPECTED_PCM8K_ENVIRONMENT_SHA256 = (
    "3ac14031af8e2b8f316415b8758b28e1"
    "daa5207677305b064601cb5f6dfb8aa0"
)

EXPECTED_MULAW_ENVIRONMENT_SHA256 = (
    "db90491d9804eeb81620b6585ee361ee"
    "15095716bd739b51f5b09e954fa419d4"
)

EXPECTED_ALAW_ENVIRONMENT_SHA256 = (
    "73e3a2fd247e2f0ecf4fdb68e5ed4e9"
    "f96e582eb58515ef699ca0361fdf79d42"
)


def test_i3_portfolio_record_identities_are_frozen():
    (
        telephony,
        mulaw,
        alaw,
        derivation_plan,
    ) = build_records()

    assert (
        telephony.sha256
        == EXPECTED_TELEPHONY_TRANSFORMATION_SHA256
    )

    assert (
        mulaw.sha256
        == EXPECTED_MULAW_TRANSFORMATION_SHA256
    )

    assert (
        alaw.sha256
        == EXPECTED_ALAW_TRANSFORMATION_SHA256
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


def test_i3_portfolio_records_reverify_canonically():
    records = build_records()

    for record in records:
        verified = (
            verify_asr_adversarial_corpus_record_v1(
                payload=record.payload,
                expected_sha256=record.sha256,
            )
        )

        assert verified == record


def test_i3_telephony_transformation_remains_frozen():
    (
        telephony,
        _mulaw,
        _alaw,
        _plan,
    ) = build_records()

    record = telephony.payload[
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
            EXPECTED_PCM8K_ENVIRONMENT_SHA256
        ),
    }

    assert (
        FFMPEG_PCM8K_ENVIRONMENT_SHA256
        == EXPECTED_PCM8K_ENVIRONMENT_SHA256
    )

    assert record[
        "argv"
    ] == list(
        ASR_ADVERSARIAL_FFMPEG_PCM8K_ARGV
    )

    assert record[
        "expected_output"
    ] == {
        "relative_path": OUTPUT_RELATIVE_PATH,
        "sample_rate_hz": 8_000,
        "channel_count": 1,
        "codec_name": "pcm_s16le",
    }


def test_i3_mulaw_transformation_remains_frozen():
    (
        _telephony,
        mulaw,
        _alaw,
        _plan,
    ) = build_records()

    record = mulaw.payload[
        "record"
    ]

    assert (
        record[
            "case_id"
        ]
        == MULAW_CASE_ID
    )

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
            EXPECTED_MULAW_ENVIRONMENT_SHA256
        ),
    }

    assert (
        FFMPEG_MULAW8K_ENVIRONMENT_SHA256
        == EXPECTED_MULAW_ENVIRONMENT_SHA256
    )

    assert record[
        "argv"
    ] == list(
        ASR_ADVERSARIAL_FFMPEG_MULAW8K_ARGV
    )

    assert record[
        "expected_output"
    ] == {
        "relative_path": (
            MULAW_OUTPUT_RELATIVE_PATH
        ),
        "sample_rate_hz": 8_000,
        "channel_count": 1,
        "codec_name": "pcm_mulaw",
    }


def test_i3_alaw_transformation_is_frozen():
    (
        _telephony,
        _mulaw,
        alaw,
        _plan,
    ) = build_records()

    record = alaw.payload[
        "record"
    ]

    assert (
        record[
            "case_id"
        ]
        == ALAW_CASE_ID
    )

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
            EXPECTED_ALAW_ENVIRONMENT_SHA256
        ),
    }

    assert (
        FFMPEG_ALAW8K_ENVIRONMENT_SHA256
        == EXPECTED_ALAW_ENVIRONMENT_SHA256
    )

    assert record[
        "argv"
    ] == list(
        ASR_ADVERSARIAL_FFMPEG_ALAW8K_ARGV
    )

    assert record[
        "expected_output"
    ] == {
        "relative_path": (
            ALAW_OUTPUT_RELATIVE_PATH
        ),
        "sample_rate_hz": 8_000,
        "channel_count": 1,
        "codec_name": "pcm_alaw",
    }


def test_i3_derivation_portfolio_contains_exact_three_cases():
    (
        _telephony,
        _mulaw,
        _alaw,
        plan,
    ) = build_records()

    record = plan.payload[
        "record"
    ]

    assert (
        record[
            "parent_manifest_sha256"
        ]
        == EXPECTED_PARENT_MANIFEST_SHA256
    )

    entries = record[
        "entries"
    ]

    assert len(entries) == 3

    assert [
        entry[
            "case_id"
        ]
        for entry in entries
    ] == [
        ALAW_CASE_ID,
        MULAW_CASE_ID,
        CASE_ID,
    ]

    by_case = {
        entry[
            "case_id"
        ]: entry
        for entry in entries
    }

    alaw = by_case[
        ALAW_CASE_ID
    ]

    mulaw = by_case[
        MULAW_CASE_ID
    ]

    telephony = by_case[
        CASE_ID
    ]

    for entry in (
        alaw,
        mulaw,
        telephony,
    ):
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
        telephony[
            "output_relative_path"
        ]
        == OUTPUT_RELATIVE_PATH
    )

    assert (
        telephony[
            "transformation_record_sha256"
        ]
        == EXPECTED_TELEPHONY_TRANSFORMATION_SHA256
    )

    assert (
        mulaw[
            "output_relative_path"
        ]
        == MULAW_OUTPUT_RELATIVE_PATH
    )

    assert (
        mulaw[
            "transformation_record_sha256"
        ]
        == EXPECTED_MULAW_TRANSFORMATION_SHA256
    )

    assert (
        alaw[
            "output_relative_path"
        ]
        == ALAW_OUTPUT_RELATIVE_PATH
    )

    assert (
        alaw[
            "transformation_record_sha256"
        ]
        == EXPECTED_ALAW_TRANSFORMATION_SHA256
    )


def test_i3_portfolio_builder_is_deterministic_in_memory():
    first = build_records()
    second = build_records()

    assert first == second

    assert tuple(
        record.sha256
        for record in first
    ) == tuple(
        record.sha256
        for record in second
    )
