from __future__ import annotations

import json
from pathlib import Path

from hvee.packs.asr.adversarial_corpus_records import (
    verify_asr_adversarial_corpus_record_v1,
)


ROOT = Path(
    "corpora/asr/adversarial/v1"
)

SOURCE_PLAN_SHA256 = (
    "4c6cc01ac38986dc66d2f18326a95680b"
    "a86139d7aedc5d4cc69498635c32ea4"
)

TRANSFORMATION_SHA256 = (
    "4cd349d56ca7c5fc60c773024dc36488"
    "b75f3944a4b1a98da260178c726c3f0f"
)

DERIVATIVE_PLAN_SHA256 = (
    "f5b40bd42bff3a2bf35e68108b024146"
    "2bdcd35abeaf3f857a77a7284ac85897"
)

PARENT_AUDIO_SHA256 = (
    "d1fe44656a114a0e66fb6ea950ae4217"
    "d31691486842f4421eff8317cc6ab440"
)

FFMPEG_ENVIRONMENT_SHA256 = (
    "e400ae359be1dc681937ba5caefc2d1f"
    "a077247c8939aa04aee0067e67fc87fc"
)

EXPECTED_ARGV = [
    "-hide_banner",
    "-loglevel",
    "error",
    "-nostdin",
    "-n",
    "-i",
    "{input}",
    "-map_metadata",
    "-1",
    "-ar",
    "16000",
    "-ac",
    "1",
    "-c:a",
    "pcm_s16le",
    "{output}",
]


def _load(
    relative_path: str,
):
    path = (
        ROOT
        / relative_path
    )

    document = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    return (
        verify_asr_adversarial_corpus_record_v1(
            payload=document["payload"],
            expected_sha256=document["sha256"],
        )
    )


def test_source_plan_identity_remains_frozen():
    bundle = _load(
        "specification/generation-plan.json"
    )

    assert (
        bundle.sha256
        == SOURCE_PLAN_SHA256
    )

    entry = bundle.payload[
        "record"
    ]["entries"][0]

    assert (
        entry["case_id"]
        == "control.clean-critical"
    )
    assert (
        entry["output_relative_path"]
        == "source/control.clean-critical.wav"
    )
    assert (
        entry[
            "transformation_record_sha256"
        ]
        is None
    )


def test_transformation_record_identity_is_frozen():
    bundle = _load(
        "records/transformations/"
        "control.clean-critical.json"
    )

    assert (
        bundle.sha256
        == TRANSFORMATION_SHA256
    )

    record = bundle.payload[
        "record"
    ]

    assert (
        record["case_id"]
        == "control.clean-critical"
    )
    assert (
        record["parent_audio_sha256"]
        == PARENT_AUDIO_SHA256
    )

    assert (
        record["tool"]
        == {
            "key": "ffmpeg",
            "version": "5.1.9-0+deb12u1",
            "environment_sha256": (
                FFMPEG_ENVIRONMENT_SHA256
            ),
        }
    )

    assert (
        record["argv"]
        == EXPECTED_ARGV
    )

    assert (
        record["expected_output"]
        == {
            "relative_path": (
                "clean/control.clean-critical.wav"
            ),
            "sample_rate_hz": 16_000,
            "channel_count": 1,
            "codec_name": "pcm_s16le",
        }
    )


def test_derivative_plan_identity_is_frozen():
    bundle = _load(
        "specification/derivative-plan.json"
    )

    assert (
        bundle.sha256
        == DERIVATIVE_PLAN_SHA256
    )

    record = bundle.payload[
        "record"
    ]

    assert (
        record["corpus_id"]
        == "qualification.synthetic-derivative-v1"
    )

    entry = record[
        "entries"
    ][0]

    assert (
        entry["case_id"]
        == "control.clean-critical"
    )
    assert (
        entry["output_relative_path"]
        == "clean/control.clean-critical.wav"
    )
    assert (
        entry[
            "transformation_record_sha256"
        ]
        == TRANSFORMATION_SHA256
    )


def test_derivative_records_preserve_non_authority_boundary():
    bundles = (
        _load(
            "records/transformations/"
            "control.clean-critical.json"
        ),
        _load(
            "specification/derivative-plan.json"
        ),
    )

    for bundle in bundles:
        boundary = bundle.payload[
            "evidence_boundary"
        ]

        assert (
            boundary[
                "development_evidence_only"
            ]
            is True
        )
        assert (
            boundary[
                "rights_adjudicated"
            ]
            is False
        )
        assert (
            boundary[
                "human_acoustic_diversity_established"
            ]
            is False
        )
        assert (
            boundary[
                "qualification_threshold_applied"
            ]
            is False
        )
        assert (
            boundary[
                "certification_issued"
            ]
            is False
        )
        assert (
            boundary[
                "production_qualified"
            ]
            is False
        )
        assert (
            boundary[
                "release_enforcement_eligible"
            ]
            is False
        )
        assert (
            boundary[
                "official_release_verdict_modified"
            ]
            is False
        )
