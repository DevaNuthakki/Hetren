"""Pinned real-media proof for deterministic I3 synthetic-noise cases."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import struct
import wave

import pytest

from app.adversarial_asr_corpus_derivative_service import (
    generate_asr_adversarial_derived_case_v1,
)
from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE,
    ASRAdversarialFFmpeg,
    ASRAdversarialFFmpegRecipe,
)
from app.adversarial_asr_ffprobe import (
    ASRAdversarialFFprobe,
)
from hvee.packs.asr.adversarial_corpus_v1 import (
    build_asr_adversarial_corpus_v1,
)
from hvee.packs.asr.adversarial_noise_methodology import (
    ASR_ADVERSARIAL_NOISE_V1_SNR_TOLERANCE_MILLIDB,
    build_asr_adversarial_noise_methodology_v1,
)


REAL_MEDIA_TEST_ENV = (
    "HETREN_REAL_MEDIA_INTEGRATION"
)

CORPUS_ROOT = Path(
    "corpora/asr/adversarial/v1"
)

DERIVATION_PLAN_PATH = (
    CORPUS_ROOT
    / "specification"
    / "derivation-plan.json"
)

CANONICAL_PARENT_PATH = (
    CORPUS_ROOT
    / "generated"
    / "clean"
    / "clean.multi-number-id.wav"
)

PARENT_RELATIVE_PATH = (
    "clean/clean.multi-number-id.wav"
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

EXPECTED_NOISE_METHODOLOGY_SHA256 = (
    "6be586c9cb95f313786f18cf497640f6"
    "ad90198c881ed1de75778234d46b32f3"
)

EXPECTED_DERIVATION_PLAN_SHA256 = (
    "0ff0a36c1c1b4236d56a6459d59cb3a"
    "d53edcb7fa38d99f03b893b38e1afa14c"
)

EXPECTED_SAMPLE_COUNT = 110_241

EXPECTED_SIGNAL_SUM_SQUARES = (
    990_406_972_366
)

EXPECTED_BYTE_LENGTH = 220_560
EXPECTED_DURATION_MS = 6_890
EXPECTED_SAMPLE_RATE_HZ = 16_000
EXPECTED_CHANNEL_COUNT = 1
EXPECTED_CODEC_NAME = "pcm_s16le"


pytestmark = pytest.mark.skipif(
    os.environ.get(
        REAL_MEDIA_TEST_ENV
    )
    != "1",
    reason=(
        "real synthetic-noise corpus integration "
        "runs only in the Hetren media environment"
    ),
)


CASES = (
    (
        "moderate",
        "stress.noise-moderate.multi-number-id",
        (
            "noise/"
            "stress.noise-moderate.multi-number-id.wav"
        ),
        ASR_ADVERSARIAL_FFMPEG_NOISE_MODERATE_RECIPE,
        (
            "66780406d90fc01622fcc9850a6dd3af"
            "4698eb5f07ff3413a012734e8d7d973a"
        ),
        (
            "2f71f0619cb588a211f68de064125301"
            "2ec8209cc633e53b0a15dbe94dfb4682"
        ),
        (
            "c82425954a14ce3f4276e3d902099a94"
            "7d1e8c0e773d758f0f4a68fd46e243cb"
        ),
        10.0,
        99_040_662_345,
        23_794,
    ),
    (
        "severe_usable",
        "stress.noise-severe-usable.multi-number-id",
        (
            "noise/"
            "stress.noise-severe-usable.multi-number-id.wav"
        ),
        ASR_ADVERSARIAL_FFMPEG_NOISE_SEVERE_USABLE_RECIPE,
        (
            "1443bdb65921415ccc8949ae55022b1fc"
            "a540af6ca42fcd625831324bb767ac1"
        ),
        (
            "410054a787ab53be40332d8efcec98c1"
            "91229d772d047626a1c073e946036043"
        ),
        (
            "322bbee058df10d9f5a26f36c317f6be"
            "b4f3bc83900736afc724717cd1cc3779"
        ),
        5.0,
        313_194_049_048,
        25_066,
    ),
)


def _sha256(
    file_path: Path,
) -> str:
    return hashlib.sha256(
        file_path.read_bytes()
    ).hexdigest()


def _read_pcm16(
    file_path: Path,
) -> tuple[int, ...]:
    with wave.open(
        str(file_path),
        "rb",
    ) as audio:
        assert (
            audio.getnchannels()
            == EXPECTED_CHANNEL_COUNT
        )

        assert (
            audio.getsampwidth()
            == 2
        )

        assert (
            audio.getframerate()
            == EXPECTED_SAMPLE_RATE_HZ
        )

        assert (
            audio.getcomptype()
            == "NONE"
        )

        frame_count = (
            audio.getnframes()
        )

        raw = audio.readframes(
            frame_count
        )

    assert (
        len(raw)
        == frame_count * 2
    )

    return struct.unpack(
        f"<{frame_count}h",
        raw,
    )


@pytest.mark.parametrize(
    (
        "condition",
        "case_id",
        "output_relative_path",
        "recipe",
        "expected_transformation_sha256",
        "expected_environment_sha256",
        "expected_audio_sha256",
        "target_snr_db",
        "expected_residual_sum_squares",
        "expected_peak_pcm",
    ),
    CASES,
    ids=(
        "moderate-10db",
        "severe-usable-5db",
    ),
)
def test_real_noise_derivative_is_frozen_and_measured(
    tmp_path: Path,
    condition: str,
    case_id: str,
    output_relative_path: str,
    recipe: ASRAdversarialFFmpegRecipe,
    expected_transformation_sha256: str,
    expected_environment_sha256: str,
    expected_audio_sha256: str,
    target_snr_db: float,
    expected_residual_sum_squares: int,
    expected_peak_pcm: int,
):
    assert condition in {
        "moderate",
        "severe_usable",
    }

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

    methodology = (
        build_asr_adversarial_noise_methodology_v1()
    )

    assert (
        methodology.sha256
        == EXPECTED_NOISE_METHODOLOGY_SHA256
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

    derivation_document = json.loads(
        DERIVATION_PLAN_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert (
        derivation_document[
            "sha256"
        ]
        == EXPECTED_DERIVATION_PLAN_SHA256
    )

    transformer = ASRAdversarialFFmpeg(
        executable_path=Path(
            "/usr/bin/ffmpeg"
        ),
        recipe=recipe,
    )

    assert (
        transformer.transform_environment_sha256
        == expected_environment_sha256
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
            case_id=case_id,
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
        / output_relative_path
    )

    assert output.is_file()

    assert (
        first.audio_asset_sha256
        == expected_audio_sha256
    )

    assert (
        _sha256(
            output
        )
        == expected_audio_sha256
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
        first.derivation_plan_sha256
        == EXPECTED_DERIVATION_PLAN_SHA256
    )

    assert (
        first.transformation_record_sha256
        == expected_transformation_sha256
    )

    assert (
        first.transformer_environment_sha256
        == expected_environment_sha256
    )

    clean = _read_pcm16(
        CANONICAL_PARENT_PATH
    )

    mixed = _read_pcm16(
        output
    )

    assert (
        len(clean)
        == EXPECTED_SAMPLE_COUNT
    )

    assert (
        len(mixed)
        == EXPECTED_SAMPLE_COUNT
    )

    signal_sum_squares = sum(
        sample * sample
        for sample in clean
    )

    assert (
        signal_sum_squares
        == EXPECTED_SIGNAL_SUM_SQUARES
    )

    residual = tuple(
        observed - original
        for observed, original
        in zip(
            mixed,
            clean,
            strict=True,
        )
    )

    residual_sum_squares = sum(
        sample * sample
        for sample in residual
    )

    assert (
        residual_sum_squares
        == expected_residual_sum_squares
    )

    measured_snr_db = (
        10.0
        * math.log10(
            signal_sum_squares
            / residual_sum_squares
        )
    )

    tolerance_db = (
        ASR_ADVERSARIAL_NOISE_V1_SNR_TOLERANCE_MILLIDB
        / 1000.0
    )

    assert (
        abs(
            measured_snr_db
            - target_snr_db
        )
        <= tolerance_db
    )

    output_peak_pcm = max(
        abs(sample)
        for sample in mixed
    )

    assert (
        output_peak_pcm
        == expected_peak_pcm
    )

    assert (
        output_peak_pcm
        < 32_767
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
            case_id=case_id,
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
        == expected_audio_sha256
    )

    assert before == after
