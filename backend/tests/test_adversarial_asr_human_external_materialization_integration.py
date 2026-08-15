"""Real human/external materialization integration tests.

These tests are intentionally opt-in.

They require:

- Hetren's pinned media environment,
- HETREN_REAL_MEDIA_INTEGRATION=1,
- HETREN_HUMAN_EXTERNAL_EVIDENCE_ROOT pointing at the separately retained
  Mini LibriSpeech I4b evidence root.

The source media is never downloaded or modified by these tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.adversarial_asr_ffprobe import (
    ASRAdversarialFFprobe,
)
from app.adversarial_asr_human_external_materialization_service import (
    materialize_asr_adversarial_minilibrispeech_source_v1,
)
from hvee.packs.asr.adversarial_human_external_minilibrispeech_v1 import (
    ASR_ADVERSARIAL_MINILIBRISPEECH_CASES,
    ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256,
    build_asr_adversarial_minilibrispeech_record_pair_v1,
)


REAL_MEDIA_TEST_ENV = (
    "HETREN_REAL_MEDIA_INTEGRATION"
)

HUMAN_EVIDENCE_ROOT_ENV = (
    "HETREN_HUMAN_EXTERNAL_EVIDENCE_ROOT"
)

EXPECTED_FFPROBE_VERSION = (
    "5.1.9-0+deb12u1"
)

FFPROBE_PATH = Path(
    "/usr/bin/ffprobe"
)


pytestmark = [
    pytest.mark.skipif(
        os.environ.get(
            REAL_MEDIA_TEST_ENV
        )
        != "1",
        reason=(
            "real pinned media integration is enabled "
            "only in the Hetren media environment"
        ),
    ),
    pytest.mark.skipif(
        not os.environ.get(
            HUMAN_EVIDENCE_ROOT_ENV
        ),
        reason=(
            "external human evidence root was not supplied"
        ),
    ),
]


def _evidence_root(
) -> Path:
    value = os.environ[
        HUMAN_EVIDENCE_ROOT_ENV
    ]

    root = Path(
        value
    )

    assert root.is_absolute()

    return root


@pytest.fixture(
    scope="module"
)
def pinned_probe(
):
    assert FFPROBE_PATH.is_file()

    probe = ASRAdversarialFFprobe(
        executable_path=FFPROBE_PATH,
    )

    assert probe.reported_version == (
        EXPECTED_FFPROBE_VERSION
    )

    return probe


@pytest.mark.parametrize(
    "case",
    ASR_ADVERSARIAL_MINILIBRISPEECH_CASES,
    ids=lambda case: case.utterance_id,
)
def test_real_minilibrispeech_source_materializes_exactly(
    case,
    pinned_probe,
):
    root = _evidence_root()

    before_audio = (
        root
        / "selected"
        / case.utterance_id
        / (
            case.utterance_id
            + ".flac"
        )
    )

    before_transcript = (
        root
        / "selected"
        / case.utterance_id
        / (
            case.utterance_id
            + ".txt"
        )
    )

    assert before_audio.is_file()
    assert before_transcript.is_file()
    assert not before_audio.is_symlink()
    assert not before_transcript.is_symlink()

    provenance, rights = (
        build_asr_adversarial_minilibrispeech_record_pair_v1(
            case.utterance_id
        )
    )

    materialized = (
        materialize_asr_adversarial_minilibrispeech_source_v1(
            evidence_root=root,
            utterance_id=case.utterance_id,
            media_probe=pinned_probe,
        )
    )

    assert materialized.case_id == (
        case.case_id
    )

    assert materialized.source_item_id == (
        case.utterance_id
    )

    assert materialized.audio_path == (
        before_audio.resolve(
            strict=True
        )
    )

    assert materialized.transcript_path == (
        before_transcript.resolve(
            strict=True
        )
    )

    assert materialized.audio_path.is_relative_to(
        root.resolve(
            strict=True
        )
    )

    assert materialized.transcript_path.is_relative_to(
        root.resolve(
            strict=True
        )
    )

    assert materialized.audio_sha256 == (
        case.source_audio_sha256
    )

    assert materialized.audio_byte_length == (
        case.audio_bytes
    )

    assert materialized.transcript_sha256 == (
        case.reference_transcript_sha256
    )

    assert materialized.reference_transcript.strip()

    assert materialized.duration_ms == (
        case.duration_ms
    )

    assert materialized.sample_rate_hz == (
        case.sample_rate_hz
    )

    assert materialized.channel_count == (
        case.channel_count
    )

    assert materialized.codec_name == (
        case.codec_name
    )

    assert materialized.source_selection_sha256 == (
        ASR_ADVERSARIAL_MINILIBRISPEECH_SELECTION_SHA256
    )

    assert materialized.provenance_record_sha256 == (
        provenance.sha256
    )

    assert materialized.rights_record_sha256 == (
        rights.sha256
    )

    assert materialized.development_evidence_only is True
    assert materialized.rights_adjudicated is False
    assert materialized.production_qualified is False
    assert (
        materialized.release_enforcement_eligible
        is False
    )


def test_real_minilibrispeech_materializes_all_eight_distinct_sources(
    pinned_probe,
):
    root = _evidence_root()

    materialized = tuple(
        materialize_asr_adversarial_minilibrispeech_source_v1(
            evidence_root=root,
            utterance_id=case.utterance_id,
            media_probe=pinned_probe,
        )
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    )

    assert len(
        materialized
    ) == 8

    assert len(
        {
            source.source_item_id
            for source in materialized
        }
    ) == 8

    assert len(
        {
            source.audio_sha256
            for source in materialized
        }
    ) == 8

    assert {
        source.source_item_id
        for source in materialized
    } == {
        case.utterance_id
        for case in (
            ASR_ADVERSARIAL_MINILIBRISPEECH_CASES
        )
    }
