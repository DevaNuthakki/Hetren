"""Integrity contract for I2 deterministic ASR derivative records.

This test freezes the eight-case source-to-derivative relationship before
real FFmpeg execution. It verifies cryptographic identities, source parent
bindings, exact PCM16K transformation parameters, and the non-authoritative
development evidence boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV,
)
from hvee.packs.asr.adversarial_corpus_records import (
    verify_asr_adversarial_corpus_record_v1,
)


ROOT = Path(
    "corpora/asr/adversarial/v1"
)

SOURCE_PLAN_SHA256 = (
    "7c3f4a729a490ea2471f86ef4077e1c4"
    "eb38f5c095ba29e66373c139a14e1c57"
)

DERIVATIVE_PLAN_SHA256 = (
    "3b428ccf140a5bf6666a0b6f60d7b662"
    "827e769de16272e8986861f8e5ced53f"
)

FFMPEG_ENVIRONMENT_SHA256 = (
    "e400ae359be1dc681937ba5caefc2d1f"
    "a077247c8939aa04aee0067e67fc87fc"
)


CASE_IDENTITIES = {
    "clean.identifier-account-order": {
        "parent": (
            "bfd7493488c37023b5b4429b25022462"
            "60a9dd1723bc2214439309c493d04e6a"
        ),
        "transformation": (
            "73a5476351d16890a6c13d67f61baaed"
            "4721978935b8123c640cde8cd025cf45"
        ),
    },
    "clean.identifier-confirmation": {
        "parent": (
            "2ed4f6de5b2ae6ea96a7b49c635d030e"
            "2679a42c55e5511911b82bbc56227936"
        ),
        "transformation": (
            "a19bc2dac6c67eaae14813cd6842ff013"
            "a37ae2fdb114bb2c40a5aa646387139"
        ),
    },
    "clean.identifier-multiple": {
        "parent": (
            "5124ea409f0d0c8022da5ea36a1ace63"
            "bb57385c9d28b4196ad85ccacaeb4179"
        ),
        "transformation": (
            "29cbce81a09fc05fad49931b77f5c9c3"
            "5ed4d5552d3cae843d99e3562c81dfd1"
        ),
    },
    "clean.multi-number-id": {
        "parent": (
            "61f967d306ab7e819133a27792ef666f4"
            "8069d72965b4d6918580e12f3f6e9e8"
        ),
        "transformation": (
            "672cf776feddf77a79182103541b2b108"
            "80b8eeae0852c07c3ffdd73701b0044"
        ),
    },
    "clean.number-currency-time": {
        "parent": (
            "191dbd877ad0cd425e4223b3e00b7916"
            "5790ab3bed76194f5384d01a5629272e"
        ),
        "transformation": (
            "c3ed7e3cee110ed91446506355e232fb7"
            "cb05bf03dd0c9cbf2cbe65ad0711b9e"
        ),
    },
    "clean.number-measurement": {
        "parent": (
            "1e5aeed9bf1d861b041de5283b96c78b"
            "1e1e09b71bba3f01e15f68c12e50f3bb"
        ),
        "transformation": (
            "f9f87b23361bdb4b53aef1d28321b9db"
            "efbb26b846fc42fca7a8f81df84223bd"
        ),
    },
    "clean.number-percentage": {
        "parent": (
            "464d479c353cabb37123f58971b61d973"
            "0dd85ce4d03ee76681cf4b76537d5b6"
        ),
        "transformation": (
            "23ea98f530e1a258b230a508b45efaecc"
            "ce905843026e0ff4bfeb3a7d8220eac"
        ),
    },
    "control.clean-critical": {
        "parent": (
            "d1fe44656a114a0e66fb6ea950ae4217"
            "d31691486842f4421eff8317cc6ab440"
        ),
        "transformation": (
            "4cd349d56ca7c5fc60c773024dc36488"
            "b75f3944a4b1a98da260178c726c3f0f"
        ),
    },
}


EXPECTED_CASE_IDS = tuple(
    CASE_IDENTITIES
)


def _load(
    relative_path: str,
):
    file_path = (
        ROOT
        / relative_path
    )

    document = json.loads(
        file_path.read_text(
            encoding="utf-8"
        )
    )

    return (
        verify_asr_adversarial_corpus_record_v1(
            payload=document["payload"],
            expected_sha256=document["sha256"],
        )
    )


def test_i2_source_plan_identity_and_inventory_are_frozen():
    bundle = _load(
        "specification/generation-plan.json"
    )

    assert bundle.sha256 == SOURCE_PLAN_SHA256

    record = bundle.payload[
        "record"
    ]

    assert (
        record["corpus_id"]
        == "qualification.synthetic-v1"
    )
    assert record["corpus_version"] == "1.0.0"

    entries = record[
        "entries"
    ]

    assert tuple(
        entry["case_id"]
        for entry in entries
    ) == EXPECTED_CASE_IDS

    assert all(
        entry[
            "transformation_record_sha256"
        ]
        is None
        for entry in entries
    )


def test_i2_transformation_records_bind_exact_source_audio():
    for case_id in EXPECTED_CASE_IDS:
        bundle = _load(
            "records/transformations/"
            f"{case_id}.json"
        )

        identity = CASE_IDENTITIES[
            case_id
        ]

        assert (
            bundle.sha256
            == identity["transformation"]
        )

        record = bundle.payload[
            "record"
        ]

        assert record["case_id"] == case_id

        assert (
            record["parent_audio_sha256"]
            == identity["parent"]
        )

        assert (
            record["tool"]
            == {
                "key": "ffmpeg",
                "version": (
                    "5.1.9-0+deb12u1"
                ),
                "environment_sha256": (
                    FFMPEG_ENVIRONMENT_SHA256
                ),
            }
        )

        assert tuple(
            record["argv"]
        ) == (
            ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
        )

        assert (
            record["expected_output"]
            == {
                "relative_path": (
                    f"clean/{case_id}.wav"
                ),
                "sample_rate_hz": 16_000,
                "channel_count": 1,
                "codec_name": "pcm_s16le",
            }
        )


def test_i2_derivative_plan_exactly_binds_transformations():
    source = _load(
        "specification/generation-plan.json"
    )

    derivative = _load(
        "specification/derivative-plan.json"
    )

    assert (
        derivative.sha256
        == DERIVATIVE_PLAN_SHA256
    )

    record = derivative.payload[
        "record"
    ]

    assert (
        record["corpus_id"]
        == "qualification.synthetic-derivative-v1"
    )
    assert record["corpus_version"] == "1.0.0"

    derivative_entries = record[
        "entries"
    ]

    assert tuple(
        entry["case_id"]
        for entry in derivative_entries
    ) == EXPECTED_CASE_IDS

    source_by_case = {
        entry["case_id"]: entry
        for entry in source.payload[
            "record"
        ]["entries"]
    }

    assert len(
        source_by_case
    ) == len(
        EXPECTED_CASE_IDS
    )

    for entry in derivative_entries:
        case_id = entry[
            "case_id"
        ]

        source_entry = source_by_case[
            case_id
        ]

        assert (
            entry["output_relative_path"]
            == f"clean/{case_id}.wav"
        )

        assert (
            entry["provenance_record_sha256"]
            == source_entry[
                "provenance_record_sha256"
            ]
        )

        assert (
            entry["rights_record_sha256"]
            == source_entry[
                "rights_record_sha256"
            ]
        )

        assert (
            entry[
                "transformation_record_sha256"
            ]
            == CASE_IDENTITIES[
                case_id
            ]["transformation"]
        )


def test_i2_derivative_evidence_remains_non_authoritative():
    bundles = [
        _load(
            "specification/derivative-plan.json"
        )
    ]

    bundles.extend(
        _load(
            "records/transformations/"
            f"{case_id}.json"
        )
        for case_id in EXPECTED_CASE_IDS
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
