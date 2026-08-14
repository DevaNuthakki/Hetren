from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hvee.packs.asr.adversarial_corpus_records import (
    verify_asr_adversarial_corpus_record_v1,
)


CORPUS_ROOT = (
    Path(__file__).resolve()
    .parents[4]
    / "corpora"
    / "asr"
    / "adversarial"
    / "v1"
)

TRANSCRIPT_SHA256 = (
    "cb85655794bc5b0c2a5d5d5c1626b0e"
    "3b208bc28ecfce4aa3275ed73ea2e6744"
)


def _sha256(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _load_record(
    path: Path,
):
    loaded = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    return verify_asr_adversarial_corpus_record_v1(
        payload=loaded["payload"],
        expected_sha256=loaded["sha256"],
    )


def test_committed_clean_control_transcript_identity():
    transcript = (
        CORPUS_ROOT
        / "specification/transcripts/"
        "control.clean-critical.txt"
    )

    assert transcript.is_file()

    assert (
        _sha256(
            transcript
        )
        == TRANSCRIPT_SHA256
    )


def test_committed_clean_control_provenance_record():
    bundle = _load_record(
        CORPUS_ROOT
        / "records/provenance/"
        "control.clean-critical.json"
    )

    record = bundle.payload["record"]

    assert (
        record["case_id"]
        == "control.clean-critical"
    )
    assert (
        record["source_kind"]
        == "synthetic_tts"
    )
    assert (
        record["transcript_sha256"]
        == TRANSCRIPT_SHA256
    )
    assert (
        record["generator"]["voice_key"]
        == "en-us"
    )
    assert (
        record["generator"]["platform_key"]
        == "linux-amd64"
    )


def test_committed_clean_control_rights_record():
    bundle = _load_record(
        CORPUS_ROOT
        / "records/rights/"
        "control.clean-critical.json"
    )

    record = bundle.payload["record"]

    assert (
        record["review_status"]
        == "not_adjudicated"
    )
    assert (
        record["development_use_only"]
        is True
    )

    boundary = bundle.payload[
        "evidence_boundary"
    ]

    assert boundary["rights_adjudicated"] is False
    assert boundary["production_qualified"] is False
    assert (
        boundary["human_acoustic_diversity_established"]
        is False
    )


def test_committed_generation_plan_binds_clean_source_records():
    bundle = _load_record(
        CORPUS_ROOT
        / "specification/generation-plan.json"
    )

    record = bundle.payload[
        "record"
    ]

    assert (
        record["corpus_id"]
        == "qualification.synthetic-v1"
    )
    assert (
        record["corpus_version"]
        == "1.0.0"
    )

    assert len(
        record["entries"]
    ) == 1

    entry = record[
        "entries"
    ][0]

    assert (
        entry["case_id"]
        == "control.clean-critical"
    )
    assert (
        entry["output_relative_path"]
        == "source/control.clean-critical.wav"
    )
    assert (
        entry["provenance_record_sha256"]
        == (
            "30d7a75e8ad8dca1f03a3576d167a12b"
            "62bff7df2fbd5bfe7a2e825771dde1c4"
        )
    )
    assert (
        entry["rights_record_sha256"]
        == (
            "cfcc0861946a6fe96da954f6efda69e7"
            "45e7bd2533e1f9b8718e0084d7bcdb14"
        )
    )
    assert (
        entry["transformation_record_sha256"]
        is None
    )
