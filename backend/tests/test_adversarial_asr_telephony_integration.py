"""Pinned real-media proof for the first I3 telephony-bandwidth case."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from app.adversarial_asr_corpus_derivative_service import (
    generate_asr_adversarial_derived_case_v1,
)
from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE,
    ASRAdversarialFFmpeg,
)
from app.adversarial_asr_ffprobe import (
    ASRAdversarialFFprobe,
)
from hvee.packs.asr.adversarial_corpus_v1 import (
    build_asr_adversarial_corpus_v1,
)


REAL_MEDIA_TEST_ENV = (
    "HETREN_REAL_MEDIA_INTEGRATION"
)

CORPUS_ROOT = Path(
    "corpora/asr/adversarial/v1"
)

CANONICAL_PARENT_PATH = (
    CORPUS_ROOT
    / "generated"
    / "clean"
    / "clean.multi-number-id.wav"
)

CASE_ID = (
    "stress.telephony-bandwidth.multi-number-id"
)

PARENT_RELATIVE_PATH = (
    "clean/clean.multi-number-id.wav"
)

OUTPUT_RELATIVE_PATH = (
    "telephony/"
    "stress.telephony-bandwidth.multi-number-id.wav"
)

EXPECTED_PARENT_SHA256 = (
    "23f9af39d01afe47e932bd061467bd0b"
    "5f49dc8bf520c2a8296a4556c54f1297"
)

EXPECTED_PARENT_BYTE_LENGTH = 220_560

EXPECTED_PARENT_MANIFEST_SHA256 = (
    "9823b12023ed39ff482f8636dd8625d0"
    "294905f7f4e406a555506e3ecb766f38"
)

EXPECTED_TRANSFORMATION_SHA256 = (
    "e1de2962fc3f074382c75cb8850a9bc0"
    "2d9b58930b93c0751df679bea535fcdb"
)

EXPECTED_DERIVATION_PLAN_SHA256 = (
    "6bbd708654191b4f3487e200a464b283"
    "dda4a78cc4261b1b18c51f3908af20a9"
)

EXPECTED_TRANSFORMER_ENVIRONMENT_SHA256 = (
    "3ac14031af8e2b8f316415b8758b28e1"
    "daa5207677305b064601cb5f6dfb8aa0"
)

EXPECTED_AUDIO_SHA256 = (
    "eca7b899ffece23f005586096e44ed9a"
    "039fdb29c493d17364e225894371f169"
)

EXPECTED_BYTE_LENGTH = 110_320
EXPECTED_DURATION_MS = 6_890
EXPECTED_SAMPLE_RATE_HZ = 8_000
EXPECTED_CHANNEL_COUNT = 1
EXPECTED_CODEC_NAME = "pcm_s16le"


pytestmark = pytest.mark.skipif(
    os.environ.get(
        REAL_MEDIA_TEST_ENV
    )
    != "1",
    reason=(
        "real telephony corpus integration "
        "runs only in the Hetren media environment"
    ),
)


def _sha256(
    file_path: Path,
) -> str:
    return hashlib.sha256(
        file_path.read_bytes()
    ).hexdigest()


def test_real_telephony_bandwidth_derivative_is_frozen(
    tmp_path: Path,
):
    assert CANONICAL_PARENT_PATH.is_file()

    assert (
        _sha256(
            CANONICAL_PARENT_PATH
        )
        == EXPECTED_PARENT_SHA256
    )

    assert (
        CANONICAL_PARENT_PATH.stat().st_size
        == EXPECTED_PARENT_BYTE_LENGTH
    )

    generated_root = (
        tmp_path
        / "generated"
    )

    parent = (
        generated_root
        / PARENT_RELATIVE_PATH
    )

    parent.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    parent.write_bytes(
        CANONICAL_PARENT_PATH.read_bytes()
    )

    (
        suite,
        suite_evidence,
        manifest_definition,
        manifest,
    ) = build_asr_adversarial_corpus_v1()

    assert (
        manifest.sha256
        == EXPECTED_PARENT_MANIFEST_SHA256
    )

    transformer = ASRAdversarialFFmpeg(
        executable_path=Path(
            "/usr/bin/ffmpeg"
        ),
        recipe=(
            ASR_ADVERSARIAL_FFMPEG_PCM8K_RECIPE
        ),
    )

    probe = ASRAdversarialFFprobe(
        executable_path=Path(
            "/usr/bin/ffprobe"
        ),
    )

    first = (
        generate_asr_adversarial_derived_case_v1(
            corpus_root=CORPUS_ROOT,
            generated_root=generated_root,
            case_id=CASE_ID,
            parent_manifest_definition=(
                manifest_definition
            ),
            parent_suite=suite,
            parent_suite_evidence=(
                suite_evidence
            ),
            transformer=transformer,
            probe=probe,
        )
    )

    output = (
        generated_root
        / OUTPUT_RELATIVE_PATH
    )

    assert output.is_file()

    assert (
        first.audio_asset_sha256
        == EXPECTED_AUDIO_SHA256
    )

    assert (
        _sha256(
            output
        )
        == EXPECTED_AUDIO_SHA256
    )

    assert (
        first.byte_length
        == EXPECTED_BYTE_LENGTH
    )

    assert (
        output.stat().st_size
        == EXPECTED_BYTE_LENGTH
    )

    assert (
        first.duration_ms
        == EXPECTED_DURATION_MS
    )

    assert (
        first.sample_rate_hz
        == EXPECTED_SAMPLE_RATE_HZ
    )

    assert (
        first.channel_count
        == EXPECTED_CHANNEL_COUNT
    )

    assert (
        first.codec_name
        == EXPECTED_CODEC_NAME
    )

    assert (
        first.parent_manifest_sha256
        == EXPECTED_PARENT_MANIFEST_SHA256
    )

    assert (
        first.transformation_record_sha256
        == EXPECTED_TRANSFORMATION_SHA256
    )

    assert (
        first.derivation_plan_sha256
        == EXPECTED_DERIVATION_PLAN_SHA256
    )

    assert (
        first.transformer_environment_sha256
        == EXPECTED_TRANSFORMER_ENVIRONMENT_SHA256
    )

    before = (
        _sha256(
            output
        ),
        output.stat().st_size,
        output.stat().st_mtime_ns,
    )

    second = (
        generate_asr_adversarial_derived_case_v1(
            corpus_root=CORPUS_ROOT,
            generated_root=generated_root,
            case_id=CASE_ID,
            parent_manifest_definition=(
                manifest_definition
            ),
            parent_suite=suite,
            parent_suite_evidence=(
                suite_evidence
            ),
            transformer=transformer,
            probe=probe,
        )
    )

    after = (
        _sha256(
            output
        ),
        output.stat().st_size,
        output.stat().st_mtime_ns,
    )

    assert (
        second.audio_asset_sha256
        == EXPECTED_AUDIO_SHA256
    )

    assert before == after
