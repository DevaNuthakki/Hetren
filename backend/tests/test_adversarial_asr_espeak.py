from __future__ import annotations

import os
from pathlib import Path

import pytest

import app.adversarial_asr_espeak as espeak_module
from app.adversarial_asr_espeak import (
    ASRAdversarialEspeak,
    ASRAdversarialEspeakError,
)


PACKAGE_VERSION = "1.51+dfsg-10+deb12u2"


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


def _fake_dpkg(
    tmp_path: Path,
) -> Path:
    return _make_executable(
        tmp_path
        / "dpkg-query",
        f'''
printf '%s' '{PACKAGE_VERSION}'
''',
    )


def _fake_espeak(
    tmp_path: Path,
) -> Path:
    return _make_executable(
        tmp_path
        / "espeak-ng",
        r'''
if [ "${1:-}" = "--version" ]; then
    printf '%s\n' \
      'eSpeak NG text-to-speech: 1.51 fake'
    exit 0
fi

output=''
transcript=''

while [ "$#" -gt 0 ]; do
    case "$1" in
        -w)
            shift
            output="$1"
            ;;
        -f)
            shift
            transcript="$1"
            ;;
    esac
    shift
done

while IFS= read -r line || [ -n "$line" ]; do
    printf '%s\n' "$line"
done < "$transcript" > "$output"
''',
    )


@pytest.fixture
def linux_platform(
    monkeypatch,
):
    monkeypatch.setattr(
        espeak_module,
        "_platform_key",
        lambda: "linux-amd64",
    )


def test_environment_identity_is_deterministic(
    tmp_path: Path,
    linux_platform,
):
    executable = _fake_espeak(
        tmp_path
    )
    dpkg = _fake_dpkg(
        tmp_path
    )

    first = ASRAdversarialEspeak(
        executable_path=executable,
        dpkg_query_path=dpkg,
    )
    second = ASRAdversarialEspeak(
        executable_path=executable,
        dpkg_query_path=dpkg,
    )

    assert first.environment == second.environment
    assert (
        first.environment.package_version
        == PACKAGE_VERSION
    )
    assert (
        first.environment.platform_key
        == "linux-amd64"
    )


def test_synthesize_uses_explicit_paths_and_refuses_overwrite(
    tmp_path: Path,
    linux_platform,
):
    adapter = ASRAdversarialEspeak(
        executable_path=_fake_espeak(
            tmp_path
        ),
        dpkg_query_path=_fake_dpkg(
            tmp_path
        ),
    )

    transcript = (
        tmp_path
        / "transcript.txt"
    )
    transcript.write_text(
        "Cardiovex 250 milligrams.\n",
        encoding="utf-8",
    )

    output = (
        tmp_path
        / "output.wav"
    )

    adapter.synthesize(
        transcript_path=transcript,
        output_path=output,
        voice_key="en-us",
        speed_wpm=150,
        pitch=50,
        amplitude=100,
    )

    assert output.is_file()
    assert (
        output.read_text(
            encoding="utf-8"
        )
        == "Cardiovex 250 milligrams.\n"
    )

    with pytest.raises(
        ASRAdversarialEspeakError,
        match="must not already exist",
    ):
        adapter.synthesize(
            transcript_path=transcript,
            output_path=output,
            voice_key="en-us",
            speed_wpm=150,
            pitch=50,
            amplitude=100,
        )


def test_relative_executable_path_is_rejected(
    tmp_path: Path,
    linux_platform,
):
    with pytest.raises(
        ASRAdversarialEspeakError,
        match="must be absolute",
    ):
        ASRAdversarialEspeak(
            executable_path=Path(
                "espeak-ng"
            ),
            dpkg_query_path=_fake_dpkg(
                tmp_path
            ),
        )


def test_symlink_executable_is_rejected(
    tmp_path: Path,
    linux_platform,
):
    real = _fake_espeak(
        tmp_path
    )

    link = (
        tmp_path
        / "espeak-link"
    )
    link.symlink_to(
        real
    )

    with pytest.raises(
        ASRAdversarialEspeakError,
        match="cannot be a symlink",
    ):
        ASRAdversarialEspeak(
            executable_path=link,
            dpkg_query_path=_fake_dpkg(
                tmp_path
            ),
        )


def test_invalid_version_output_is_rejected(
    tmp_path: Path,
    linux_platform,
):
    executable = _make_executable(
        tmp_path
        / "espeak-ng",
        '''
printf '%s\n' 'unexpected tool'
''',
    )

    with pytest.raises(
        ASRAdversarialEspeakError,
        match="version output is invalid",
    ):
        ASRAdversarialEspeak(
            executable_path=executable,
            dpkg_query_path=_fake_dpkg(
                tmp_path
            ),
        )


def test_tool_failure_does_not_leak_stderr(
    tmp_path: Path,
    linux_platform,
):
    executable = _make_executable(
        tmp_path
        / "espeak-ng",
        r'''
if [ "${1:-}" = "--version" ]; then
    printf '%s\n' \
      'eSpeak NG text-to-speech: 1.51 fake'
    exit 0
fi

printf '%s\n' 'sensitive-fake-stderr' >&2
exit 7
''',
    )

    adapter = ASRAdversarialEspeak(
        executable_path=executable,
        dpkg_query_path=_fake_dpkg(
            tmp_path
        ),
    )

    transcript = (
        tmp_path
        / "transcript.txt"
    )
    transcript.write_text(
        "test\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ASRAdversarialEspeakError,
        match="tool failed",
    ) as error:
        adapter.synthesize(
            transcript_path=transcript,
            output_path=(
                tmp_path
                / "output.wav"
            ),
            voice_key="en-us",
            speed_wpm=150,
            pitch=50,
            amplitude=100,
        )

    assert (
        "sensitive-fake-stderr"
        not in str(
            error.value
        )
    )


def test_executable_mutation_during_generation_is_rejected(
    tmp_path: Path,
    linux_platform,
):
    executable = _make_executable(
        tmp_path
        / "espeak-ng",
        r'''
if [ "${1:-}" = "--version" ]; then
    printf '%s\n' \
      'eSpeak NG text-to-speech: 1.51 fake'
    exit 0
fi

output=''

while [ "$#" -gt 0 ]; do
    case "$1" in
        -w)
            shift
            output="$1"
            ;;
    esac
    shift
done

printf '%s\n' '# mutation' >> "$0"
printf '%s' 'audio' > "$output"
''',
    )

    adapter = ASRAdversarialEspeak(
        executable_path=executable,
        dpkg_query_path=_fake_dpkg(
            tmp_path
        ),
    )

    transcript = (
        tmp_path
        / "transcript.txt"
    )
    transcript.write_text(
        "test\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ASRAdversarialEspeakError,
        match="changed during generation",
    ):
        adapter.synthesize(
            transcript_path=transcript,
            output_path=(
                tmp_path
                / "output.wav"
            ),
            voice_key="en-us",
            speed_wpm=150,
            pitch=50,
            amplitude=100,
        )
