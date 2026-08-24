from __future__ import annotations

from pathlib import Path

import pytest

from app.adversarial_asr_ffmpeg import (
    ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV,
    ASRAdversarialFFmpeg,
    ASRAdversarialFFmpegError,
)


def _make_executable(
    path: Path,
    body: str,
) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        + body,
        encoding="utf-8",
    )

    path.chmod(
        0o755
    )

    return path


def _fake_ffmpeg(
    tmp_path: Path,
) -> Path:
    return _make_executable(
        tmp_path
        / "ffmpeg",
        r'''
if [ "${1:-}" = "-version" ]; then
    printf '%s\n' \
      'ffmpeg version 5.1.9-test Copyright fake'
    exit 0
fi

output=''

for argument in "$@"; do
    output="$argument"
done

printf '%s' 'deterministic-output' > "$output"
''',
    )


def _adapter(
    tmp_path: Path,
) -> ASRAdversarialFFmpeg:
    return ASRAdversarialFFmpeg(
        executable_path=_fake_ffmpeg(
            tmp_path
        )
    )


def _input(
    tmp_path: Path,
) -> Path:
    path = (
        tmp_path
        / "source.wav"
    )

    path.write_bytes(
        b"source-audio"
    )

    return path


def test_environment_identity_is_deterministic(
    tmp_path: Path,
):
    executable = _fake_ffmpeg(
        tmp_path
    )

    first = ASRAdversarialFFmpeg(
        executable_path=executable
    )
    second = ASRAdversarialFFmpeg(
        executable_path=executable
    )

    assert (
        first.transform_environment_sha256
        == second.transform_environment_sha256
    )

    assert (
        first.reported_version
        == "5.1.9-test"
    )

    transformation = (
        first.transform_environment_payload[
            "transformation"
        ]
    )

    assert (
        transformation["argv"]
        == list(
            ASR_ADVERSARIAL_FFMPEG_PCM16K_ARGV
        )
    )
    assert (
        transformation["sample_rate_hz"]
        == 16_000
    )
    assert (
        transformation["channel_count"]
        == 1
    )
    assert (
        transformation["codec_name"]
        == "pcm_s16le"
    )

    assert "{input}" in transformation[
        "argv"
    ]
    assert "{output}" in transformation[
        "argv"
    ]


def test_transform_returns_parent_and_output_identity(
    tmp_path: Path,
):
    adapter = _adapter(
        tmp_path
    )

    source = _input(
        tmp_path
    )
    source_before = (
        source.read_bytes()
    )

    output = (
        tmp_path
        / "output.wav"
    )

    result = adapter.transform_pcm16k(
        input_path=source,
        output_path=output,
    )

    assert (
        source.read_bytes()
        == source_before
    )
    assert (
        output.read_bytes()
        == b"deterministic-output"
    )

    assert (
        result.parent_byte_length
        == len(
            source_before
        )
    )
    assert (
        result.output_byte_length
        == len(
            b"deterministic-output"
        )
    )


def test_existing_output_is_rejected(
    tmp_path: Path,
):
    adapter = _adapter(
        tmp_path
    )

    source = _input(
        tmp_path
    )

    output = (
        tmp_path
        / "output.wav"
    )
    output.write_bytes(
        b"existing"
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="must not already exist",
    ):
        adapter.transform_pcm16k(
            input_path=source,
            output_path=output,
        )

    assert (
        output.read_bytes()
        == b"existing"
    )


def test_relative_executable_is_rejected():
    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="must be absolute",
    ):
        ASRAdversarialFFmpeg(
            executable_path=Path(
                "ffmpeg"
            )
        )


def test_input_symlink_is_rejected(
    tmp_path: Path,
):
    adapter = _adapter(
        tmp_path
    )

    source = _input(
        tmp_path
    )

    link = (
        tmp_path
        / "source-link.wav"
    )
    link.symlink_to(
        source
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="input cannot be a symlink",
    ):
        adapter.transform_pcm16k(
            input_path=link,
            output_path=(
                tmp_path
                / "output.wav"
            ),
        )


def test_output_parent_symlink_is_rejected(
    tmp_path: Path,
):
    adapter = _adapter(
        tmp_path
    )

    source = _input(
        tmp_path
    )

    real_parent = (
        tmp_path
        / "real-output"
    )
    real_parent.mkdir()

    linked_parent = (
        tmp_path
        / "linked-output"
    )
    linked_parent.symlink_to(
        real_parent,
        target_is_directory=True,
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="output parent cannot be a symlink",
    ):
        adapter.transform_pcm16k(
            input_path=source,
            output_path=(
                linked_parent
                / "output.wav"
            ),
        )


def test_invalid_version_output_is_rejected(
    tmp_path: Path,
):
    executable = _make_executable(
        tmp_path
        / "ffmpeg",
        '''
printf '%s\n' 'unexpected executable'
''',
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="not FFmpeg",
    ):
        ASRAdversarialFFmpeg(
            executable_path=executable
        )


def test_tool_failure_does_not_leak_stderr(
    tmp_path: Path,
):
    executable = _make_executable(
        tmp_path
        / "ffmpeg",
        r'''
if [ "${1:-}" = "-version" ]; then
    printf '%s\n' \
      'ffmpeg version 5.1.9-test Copyright fake'
    exit 0
fi

printf '%s\n' 'sensitive-ffmpeg-stderr' >&2
exit 7
''',
    )

    adapter = ASRAdversarialFFmpeg(
        executable_path=executable
    )

    source = _input(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="execution failed",
    ) as error:
        adapter.transform_pcm16k(
            input_path=source,
            output_path=(
                tmp_path
                / "output.wav"
            ),
        )

    assert (
        "sensitive-ffmpeg-stderr"
        not in str(
            error.value
        )
    )


def test_executable_mutation_during_transform_is_rejected(
    tmp_path: Path,
):
    executable = _make_executable(
        tmp_path
        / "ffmpeg",
        r'''
if [ "${1:-}" = "-version" ]; then
    printf '%s\n' \
      'ffmpeg version 5.1.9-test Copyright fake'
    exit 0
fi

output=''

for argument in "$@"; do
    output="$argument"
done

printf '%s\n' '# mutation' >> "$0"
printf '%s' 'output' > "$output"
''',
    )

    adapter = ASRAdversarialFFmpeg(
        executable_path=executable
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="executable changed",
    ):
        adapter.transform_pcm16k(
            input_path=_input(
                tmp_path
            ),
            output_path=(
                tmp_path
                / "output.wav"
            ),
        )


def test_input_mutation_during_transform_is_rejected(
    tmp_path: Path,
):
    executable = _make_executable(
        tmp_path
        / "ffmpeg",
        r'''
if [ "${1:-}" = "-version" ]; then
    printf '%s\n' \
      'ffmpeg version 5.1.9-test Copyright fake'
    exit 0
fi

input=''
output=''
expect_input='false'

for argument in "$@"; do
    if [ "$expect_input" = 'true' ]; then
        input="$argument"
        expect_input='false'
    elif [ "$argument" = '-i' ]; then
        expect_input='true'
    fi

    output="$argument"
done

printf '%s' 'mutation' >> "$input"
printf '%s' 'output' > "$output"
''',
    )

    adapter = ASRAdversarialFFmpeg(
        executable_path=executable
    )

    source = _input(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialFFmpegError,
        match="input changed",
    ):
        adapter.transform_pcm16k(
            input_path=source,
            output_path=(
                tmp_path
                / "output.wav"
            ),
        )
