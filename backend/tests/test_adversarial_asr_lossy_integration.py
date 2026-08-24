"""Pinned real-media proof for I3 AAC/M4A and MP3 lossy cases."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from app.adversarial_asr_corpus_derivative_service import (
    generate_asr_adversarial_derived_case_v1,
)
from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE,
    ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE,
    ASRAdversarialFFmpeg,
    ASRAdversarialFFmpegRecipe,
)
from app.adversarial_asr_ffprobe import (
    ASRAdversarialFFprobe,
)
from hvee.packs.asr.adversarial_corpus_v1 import (
    build_asr_adversarial_corpus_v1,
)
from hvee.packs.asr.adversarial_lossy_codec_methodology import (
    build_asr_adversarial_lossy_codec_methodology_v1,
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

EXPECTED_DERIVATION_PLAN_SHA256 = (
    "306b5c28556a95da98cf7169474d42bd"
    "55408dff75a9762a17d178565dac4489"
)

EXPECTED_LOSSY_METHODOLOGY_SHA256 = (
    "db2d0f0181be5a0bb1beda58cf2099dc"
    "72fbcebaf5eebd1d40d5c554b9817496"
)


CASES = (
    (
        "aac_m4a",
        "stress.codec-aac.multi-number-id",
        (
            "lossy/"
            "stress.codec-aac.multi-number-id.m4a"
        ),
        ASR_ADVERSARIAL_FFMPEG_AAC_M4A_CBR32_RECIPE,
        (
            "0cbf53bd9f528f1b8345472d14b3e781"
            "9fec745de77c8df5843119d36eae95a0"
        ),
        (
            "8a23edea7a13d66422dbd083023cf7e8"
            "12cc8dbed8bb788d51fe799f9a62a877"
        ),
        (
            "1f303beee42f35d86f920487fbbb67e8"
            "70576f7278a1d3b6bd97a7bd6e67fb09"
        ),
        28_701,
        6_891,
        "aac",
    ),
    (
        "mp3",
        "stress.codec-mp3.multi-number-id",
        (
            "lossy/"
            "stress.codec-mp3.multi-number-id.mp3"
        ),
        ASR_ADVERSARIAL_FFMPEG_MP3_CBR32_RECIPE,
        (
            "a08d6dd8f929d4b5145ae31116d8cbc3"
            "30e1d6ea92e37a46006a275cbb128cf5"
        ),
        (
            "9f442ee2686f49578f817b29a7303241"
            "b379b0b47d1743fc2d1684de77cb1bb3"
        ),
        (
            "938fc367f744dee780d57c8b7e64f9dd"
            "781fe1e8599abbe4bb0987b8f844d2f3"
        ),
        27_981,
        6_984,
        "mp3",
    ),
)


pytestmark = pytest.mark.skipif(
    os.environ.get(
        REAL_MEDIA_TEST_ENV
    )
    != "1",
    reason=(
        "real lossy corpus integration "
        "runs only in the Hetren media environment"
    ),
)


def _sha256(
    file_path: Path,
) -> str:
    return hashlib.sha256(
        file_path.read_bytes()
    ).hexdigest()


@pytest.mark.parametrize(
    (
        "profile",
        "case_id",
        "output_relative_path",
        "recipe",
        "expected_transformation_sha256",
        "expected_environment_sha256",
        "expected_audio_sha256",
        "expected_byte_length",
        "expected_duration_ms",
        "expected_codec_name",
    ),
    CASES,
    ids=(
        "aac-m4a-cbr32",
        "mp3-cbr32",
    ),
)
def test_real_lossy_derivative_is_frozen(
    tmp_path: Path,
    profile: str,
    case_id: str,
    output_relative_path: str,
    recipe: ASRAdversarialFFmpegRecipe,
    expected_transformation_sha256: str,
    expected_environment_sha256: str,
    expected_audio_sha256: str,
    expected_byte_length: int,
    expected_duration_ms: int,
    expected_codec_name: str,
):
    assert profile in {
        "aac_m4a",
        "mp3",
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
        build_asr_adversarial_lossy_codec_methodology_v1()
    )

    assert (
        methodology.sha256
        == EXPECTED_LOSSY_METHODOLOGY_SHA256
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
        == expected_byte_length
    )

    assert (
        output.stat().st_size
        == expected_byte_length
    )

    assert (
        first.duration_ms
        == expected_duration_ms
    )

    assert (
        first.sample_rate_hz
        == 16_000
    )

    assert (
        first.channel_count
        == 1
    )

    assert (
        first.codec_name
        == expected_codec_name
    )

    assert (
        first.parent_manifest_sha256
        == EXPECTED_PARENT_MANIFEST_SHA256
    )

    assert (
        first.transformation_record_sha256
        == expected_transformation_sha256
    )

    assert (
        first.transformer_environment_sha256
        == expected_environment_sha256
    )

    assert (
        first.derivation_plan_sha256
        == EXPECTED_DERIVATION_PLAN_SHA256
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
