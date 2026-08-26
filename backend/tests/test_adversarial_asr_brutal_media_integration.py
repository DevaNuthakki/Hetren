"""Pinned real-media proof for the two ASR Brutal Validation v1 cases."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from app.adversarial_asr_brutal_campaign import (
    bind_asr_brutal_validation_media_v1,
)

from app.adversarial_asr_brutal_media import (
    ASRBrutalMediaExpectation,
    ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION,
    ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE,
    ASR_BRUTAL_MEDIA_PARENT_BYTE_LENGTH,
    ASR_BRUTAL_MEDIA_PARENT_RELATIVE_PATH,
    ASR_BRUTAL_MEDIA_PARENT_SHA256,
    ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION,
    ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE,
)
from app.adversarial_asr_ffmpeg import (
    ASRAdversarialFFmpeg,
    ASRAdversarialFFmpegError,
    ASRAdversarialFFmpegRecipe,
)
from app.adversarial_asr_ffprobe import (
    ASRAdversarialFFprobe,
)
from hvee.packs.asr.brutal_validation_plan import (
    ASR_BRUTAL_VALIDATION_CASES_V1,
    ASRBrutalCaseSource,
)


REAL_MEDIA_TEST_ENV = "HETREN_REAL_MEDIA_INTEGRATION"

CORPUS_GENERATED_ROOT = Path(
    "corpora/asr/adversarial/v1/generated"
)

CASES = (
    (
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_EXPECTATION,
        ASR_BRUTAL_TERMINOLOGY_TELEPHONY_NOISE_RECIPE,
    ),
    (
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_EXPECTATION,
        ASR_BRUTAL_COMPOUND_TELEPHONY_NOISE_RECIPE,
    ),
)


pytestmark = pytest.mark.skipif(
    os.environ.get(REAL_MEDIA_TEST_ENV) != "1",
    reason=(
        "real ASR Brutal-v1 media integration runs only "
        "in the pinned Hetren media environment"
    ),
)


def _sha256(file_path: Path) -> str:
    return hashlib.sha256(
        file_path.read_bytes()
    ).hexdigest()


@pytest.mark.parametrize(
    ("expectation", "recipe"),
    CASES,
    ids=(
        "terminology-telephony-noise",
        "compound-critical-telephony-noise",
    ),
)
def test_real_brutal_media_derivative_is_frozen(
    tmp_path: Path,
    expectation: ASRBrutalMediaExpectation,
    recipe: ASRAdversarialFFmpegRecipe,
):
    parent = (
        CORPUS_GENERATED_ROOT
        / ASR_BRUTAL_MEDIA_PARENT_RELATIVE_PATH
    ).resolve(strict=True)

    assert parent.is_absolute()
    assert parent.is_file()
    assert _sha256(parent) == ASR_BRUTAL_MEDIA_PARENT_SHA256
    assert (
        parent.stat().st_size
        == ASR_BRUTAL_MEDIA_PARENT_BYTE_LENGTH
    )

    parent_before = (
        _sha256(parent),
        parent.stat().st_size,
        parent.stat().st_mtime_ns,
    )

    plan_by_id = {
        case.case_id: case
        for case in ASR_BRUTAL_VALIDATION_CASES_V1
    }

    plan_case = plan_by_id[expectation.case_id]

    assert (
        plan_case.source
        is ASRBrutalCaseSource.REQUIRED_NEW_CASE
    )

    output = (
        tmp_path
        / expectation.output_relative_path
    ).resolve(strict=False)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    assert output.is_absolute()
    assert not output.exists()

    transformer = ASRAdversarialFFmpeg(
        executable_path=Path("/usr/bin/ffmpeg"),
        recipe=recipe,
    )

    assert (
        transformer.transform_environment_sha256
        == expectation.transform_environment_sha256
    )

    result = transformer.transform(
        input_path=parent,
        output_path=output,
    )

    assert output.is_file()

    assert (
        result.parent_audio_sha256,
        result.parent_byte_length,
    ) == (
        ASR_BRUTAL_MEDIA_PARENT_SHA256,
        ASR_BRUTAL_MEDIA_PARENT_BYTE_LENGTH,
    )

    assert (
        result.output_audio_sha256,
        result.output_byte_length,
    ) == (
        expectation.audio_asset_sha256,
        expectation.byte_length,
    )

    assert _sha256(output) == expectation.audio_asset_sha256
    assert output.stat().st_size == expectation.byte_length

    measured = ASRAdversarialFFprobe(
        executable_path=Path("/usr/bin/ffprobe"),
    ).probe(output)

    assert (
        measured.duration_ms,
        measured.sample_rate_hz,
        measured.channel_count,
        measured.codec_name,
    ) == (
        expectation.duration_ms,
        expectation.sample_rate_hz,
        expectation.channel_count,
        expectation.codec_name,
    )

    output_before_retry = (
        _sha256(output),
        output.stat().st_size,
        output.stat().st_mtime_ns,
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
    ):
        transformer.transform(
            input_path=parent,
            output_path=output,
        )

    assert (
        _sha256(output),
        output.stat().st_size,
        output.stat().st_mtime_ns,
    ) == output_before_retry

    assert (
        _sha256(parent),
        parent.stat().st_size,
        parent.stat().st_mtime_ns,
    ) == parent_before


def test_real_brutal_media_binds_exact_executable_suite(
    tmp_path: Path,
):
    corpus_root = (
        CORPUS_GENERATED_ROOT.resolve(strict=True)
    )
    brutal_root = tmp_path.resolve(strict=True)
    parent = (
        corpus_root
        / ASR_BRUTAL_MEDIA_PARENT_RELATIVE_PATH
    ).resolve(strict=True)

    for expectation, recipe in CASES:
        output = (
            brutal_root
            / expectation.output_relative_path
        ).resolve(strict=False)
        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result = ASRAdversarialFFmpeg(
            executable_path=Path("/usr/bin/ffmpeg"),
            recipe=recipe,
        ).transform(
            input_path=parent,
            output_path=output,
        )

        assert (
            result.output_audio_sha256
            == expectation.audio_asset_sha256
        )

    bundle = bind_asr_brutal_validation_media_v1(
        corpus_generated_root=corpus_root,
        brutal_generated_root=brutal_root,
    )
    case_ids = tuple(
        case.case_id
        for case in bundle.suite.cases
    )
    brutal_case_ids = {
        expectation.case_id
        for expectation, _recipe in CASES
    }

    assert len(case_ids) == 13
    assert tuple(bundle.audio_paths) == case_ids

    for case in bundle.suite.cases:
        path = bundle.audio_paths[case.case_id]
        expected_root = (
            brutal_root
            if case.case_id in brutal_case_ids
            else corpus_root
        )

        assert path.is_absolute()
        assert path.is_file()
        assert path.is_relative_to(expected_root)
        assert _sha256(path) == case.audio_asset_sha256
