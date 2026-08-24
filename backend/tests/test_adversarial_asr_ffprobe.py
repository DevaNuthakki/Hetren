from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.adversarial_asr_ffprobe import (
    ASR_ADVERSARIAL_FFPROBE_DURATION_POLICY,
    ASR_ADVERSARIAL_FFPROBE_KEY,
    ASR_ADVERSARIAL_FFPROBE_VERSION,
    ASRAdversarialFFprobe,
    ASRAdversarialFFprobeError,
)


def _write_fake_ffprobe(
    tmp_path: Path,
    *,
    version_line: str = (
        "ffprobe version 7.1.1-test"
    ),
) -> Path:
    executable = (
        tmp_path / "fake-ffprobe"
    )

    script = f"""#!{sys.executable}
import json
import os
import sys
import time

VERSION_LINE = {version_line!r}

if sys.argv[1:] == ["-version"]:
    print(VERSION_LINE)
    print("fake build configuration")
    raise SystemExit(0)

expected = [
    "-v",
    "error",
    "-show_entries",
    "stream=codec_type,codec_name,sample_rate,channels:format=duration",
    "-of",
    "json",
]

if sys.argv[1:7] != expected:
    raise SystemExit(12)

path = sys.argv[7]
name = os.path.basename(path)

if "timeout" in name:
    time.sleep(2)

if "nonzero" in name:
    sys.stderr.write(
        "SECRET-FFPROBE-ERROR-CONTENT"
    )
    raise SystemExit(9)

if "large-output" in name:
    sys.stdout.write("x" * 100000)
    raise SystemExit(0)

if "invalid-utf8" in name:
    os.write(1, b"\\xff\\xfe")
    raise SystemExit(0)

if "malformed-json" in name:
    sys.stdout.write("{{not-json")
    raise SystemExit(0)

if "nan-json" in name:
    sys.stdout.write(
        '{{"streams":[],"format":{{"duration":NaN}}}}'
    )
    raise SystemExit(0)

if "multiple-streams" in name:
    payload = {{
        "streams": [
            {{
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "16000",
                "channels": 1,
            }},
            {{
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "16000",
                "channels": 1,
            }},
        ],
        "format": {{
            "duration": "2.500000",
        }},
    }}
elif "video-stream" in name:
    payload = {{
        "streams": [
            {{
                "codec_type": "video",
                "codec_name": "h264",
                "sample_rate": "16000",
                "channels": 1,
            }},
        ],
        "format": {{
            "duration": "2.500000",
        }},
    }}
elif "bad-rate" in name:
    payload = {{
        "streams": [
            {{
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "N/A",
                "channels": 1,
            }},
        ],
        "format": {{
            "duration": "2.500000",
        }},
    }}
elif "bad-channels" in name:
    payload = {{
        "streams": [
            {{
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "16000",
                "channels": 0,
            }},
        ],
        "format": {{
            "duration": "2.500000",
        }},
    }}
elif "bad-codec" in name:
    payload = {{
        "streams": [
            {{
                "codec_type": "audio",
                "codec_name": "PCM S16LE",
                "sample_rate": "16000",
                "channels": 1,
            }},
        ],
        "format": {{
            "duration": "2.500000",
        }},
    }}
elif "bad-duration" in name:
    payload = {{
        "streams": [
            {{
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "16000",
                "channels": 1,
            }},
        ],
        "format": {{
            "duration": "N/A",
        }},
    }}
elif "round-up" in name:
    payload = {{
        "streams": [
            {{
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "16000",
                "channels": 1,
            }},
        ],
        "format": {{
            "duration": "2.5005",
        }},
    }}
else:
    payload = {{
        "streams": [
            {{
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "16000",
                "channels": 1,
            }},
        ],
        "format": {{
            "duration": "2.5004",
        }},
    }}

if "programmed-audio" in name:
    payload["programs"] = [
        {{
            "program_id": 1,
        }}
    ]
else:
    payload["programs"] = []

print(
    json.dumps(
        payload,
        separators=(",", ":"),
    )
)
"""

    executable.write_text(
        script
    )
    executable.chmod(
        0o700
    )

    return executable


def _audio(
    tmp_path: Path,
    name: str = "audio.wav",
) -> Path:
    path = tmp_path / name
    path.write_bytes(
        b"audio-fixture"
    )
    return path


def _probe(
    tmp_path: Path,
    **kwargs,
):
    executable = kwargs.pop(
        "executable_path",
        _write_fake_ffprobe(
            tmp_path
        ),
    )

    return ASRAdversarialFFprobe(
        executable_path=executable,
        **kwargs,
    )


def test_builds_deterministic_probe_environment(
    tmp_path: Path,
):
    executable = (
        _write_fake_ffprobe(
            tmp_path
        )
    )

    first = ASRAdversarialFFprobe(
        executable_path=executable,
    )
    second = ASRAdversarialFFprobe(
        executable_path=executable,
    )

    assert first.probe_key == (
        ASR_ADVERSARIAL_FFPROBE_KEY
    )
    assert first.probe_version == (
        ASR_ADVERSARIAL_FFPROBE_VERSION
    )
    assert first.reported_version == (
        "7.1.1-test"
    )

    assert (
        first.probe_environment_sha256
        == second.probe_environment_sha256
    )


def test_environment_commits_binary_without_absolute_path(
    tmp_path: Path,
):
    executable = (
        _write_fake_ffprobe(
            tmp_path
        )
    )

    probe = ASRAdversarialFFprobe(
        executable_path=executable,
    )

    expected_sha256 = hashlib.sha256(
        executable.read_bytes()
    ).hexdigest()

    payload = (
        probe.probe_environment_payload
    )

    assert payload["tool"][
        "executable_sha256"
    ] == expected_sha256

    assert payload["normalization"][
        "duration_ms_policy"
    ] == (
        ASR_ADVERSARIAL_FFPROBE_DURATION_POLICY
    )

    assert str(
        tmp_path.resolve()
    ) not in str(
        payload
    )


def test_same_binary_at_different_paths_has_same_environment_identity(
    tmp_path: Path,
):
    first_path = (
        _write_fake_ffprobe(
            tmp_path
        )
    )

    second_dir = (
        tmp_path / "other"
    )
    second_dir.mkdir()

    second_path = (
        second_dir / "ffprobe"
    )
    second_path.write_bytes(
        first_path.read_bytes()
    )
    second_path.chmod(
        0o700
    )

    first = ASRAdversarialFFprobe(
        executable_path=first_path,
    )
    second = ASRAdversarialFFprobe(
        executable_path=second_path,
    )

    assert (
        first.probe_environment_sha256
        == second.probe_environment_sha256
    )


def test_probes_normalized_media(
    tmp_path: Path,
):
    probe = _probe(
        tmp_path
    )

    measured = probe.probe(
        _audio(
            tmp_path
        )
    )

    assert measured.duration_ms == 2500
    assert measured.sample_rate_hz == 16000
    assert measured.channel_count == 1
    assert measured.codec_name == "pcm_s16le"


def test_duration_normalization_uses_round_half_up(
    tmp_path: Path,
):
    probe = _probe(
        tmp_path
    )

    measured = probe.probe(
        _audio(
            tmp_path,
            "round-up.wav",
        )
    )

    assert measured.duration_ms == 2501


def test_rejects_relative_executable_path(
    tmp_path: Path,
):
    with pytest.raises(
        ASRAdversarialFFprobeError,
        match="must be absolute",
    ):
        ASRAdversarialFFprobe(
            executable_path=Path(
                "ffprobe"
            ),
        )


def test_rejects_non_executable_file(
    tmp_path: Path,
):
    executable = (
        tmp_path / "ffprobe"
    )
    executable.write_text(
        "not executable"
    )
    executable.chmod(
        0o600
    )

    with pytest.raises(
        ASRAdversarialFFprobeError,
        match="unavailable",
    ):
        ASRAdversarialFFprobe(
            executable_path=executable,
        )


def test_rejects_wrong_tool_identity(
    tmp_path: Path,
):
    executable = (
        _write_fake_ffprobe(
            tmp_path,
            version_line=(
                "not-ffprobe version 1.0"
            ),
        )
    )

    with pytest.raises(
        ASRAdversarialFFprobeError,
        match="not FFprobe",
    ):
        ASRAdversarialFFprobe(
            executable_path=executable,
        )


def test_detects_executable_mutation_after_initialization(
    tmp_path: Path,
):
    executable = (
        _write_fake_ffprobe(
            tmp_path
        )
    )

    probe = ASRAdversarialFFprobe(
        executable_path=executable,
    )

    with executable.open(
        "a",
    ) as file:
        file.write(
            "\n# mutation\n"
        )

    with pytest.raises(
        ASRAdversarialFFprobeError,
        match="executable changed",
    ):
        probe.probe(
            _audio(
                tmp_path
            )
        )


def test_timeout_is_controlled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    observed_timeouts: list[float] = []

    def controlled_run(
        command: list[str],
        **kwargs,
    ) -> subprocess.CompletedProcess:
        if command[1:] == ["-version"]:
            kwargs["stdout"].write(
                b"ffprobe version 7.1.1-test\n"
                b"fake build configuration\n"
            )

            return subprocess.CompletedProcess(
                command,
                returncode=0,
            )

        timeout = kwargs["timeout"]
        observed_timeouts.append(
            timeout
        )

        raise subprocess.TimeoutExpired(
            command,
            timeout,
        )

    monkeypatch.setattr(
        (
            "app.adversarial_asr_ffprobe."
            "subprocess.run"
        ),
        controlled_run,
    )

    probe = _probe(
        tmp_path,
        timeout_seconds=0.5,
    )

    with pytest.raises(
        ASRAdversarialFFprobeError,
        match="timed out",
    ):
        probe.probe(
            _audio(
                tmp_path,
                "timeout.wav",
            )
        )

    assert observed_timeouts == [
        0.5,
    ]


def test_nonzero_exit_does_not_leak_stderr(
    tmp_path: Path,
):
    probe = _probe(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialFFprobeError,
    ) as exc_info:
        probe.probe(
            _audio(
                tmp_path,
                "nonzero.wav",
            )
        )

    message = str(
        exc_info.value
    )

    assert (
        "SECRET-FFPROBE-ERROR-CONTENT"
        not in message
    )


def test_rejects_oversized_output(
    tmp_path: Path,
):
    probe = _probe(
        tmp_path,
        max_output_bytes=4096,
    )

    with pytest.raises(
        ASRAdversarialFFprobeError,
        match="output exceeded",
    ):
        probe.probe(
            _audio(
                tmp_path,
                "large-output.wav",
            )
        )


def test_rejects_invalid_utf8(
    tmp_path: Path,
):
    probe = _probe(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialFFprobeError,
        match="valid UTF-8",
    ):
        probe.probe(
            _audio(
                tmp_path,
                "invalid-utf8.wav",
            )
        )


@pytest.mark.parametrize(
    (
        "filename",
        "message",
    ),
    [
        (
            "malformed-json.wav",
            "invalid JSON",
        ),
        (
            "nan-json.wav",
            "invalid JSON",
        ),
        (
            "multiple-streams.wav",
            "exactly one stream",
        ),
        (
            "programmed-audio.wav",
            "program metadata",
        ),
        (
            "video-stream.wav",
            "must be audio",
        ),
        (
            "bad-rate.wav",
            "sample rate",
        ),
        (
            "bad-channels.wav",
            "channel count",
        ),
        (
            "bad-codec.wav",
            "codec name",
        ),
        (
            "bad-duration.wav",
            "duration",
        ),
    ],
)
def test_rejects_invalid_media_schema(
    tmp_path: Path,
    filename,
    message,
):
    probe = _probe(
        tmp_path
    )

    with pytest.raises(
        ASRAdversarialFFprobeError,
        match=message,
    ):
        probe.probe(
            _audio(
                tmp_path,
                filename,
            )
        )


def test_shell_metacharacters_in_audio_path_are_not_executed(
    tmp_path: Path,
):
    probe = _probe(
        tmp_path
    )

    marker = (
        tmp_path / "pwned"
    )

    audio = _audio(
        tmp_path,
        "audio;touch pwned.wav",
    )

    measured = probe.probe(
        audio
    )

    assert measured.duration_ms == 2500
    assert not marker.exists()


def test_probe_environment_payload_is_defensive_copy(
    tmp_path: Path,
):
    probe = _probe(
        tmp_path
    )

    payload = (
        probe.probe_environment_payload
    )

    payload["tool"][
        "reported_version"
    ] = "tampered"

    assert (
        probe.probe_environment_payload[
            "tool"
        ]["reported_version"]
        == "7.1.1-test"
    )


@pytest.mark.parametrize(
    (
        "timeout_seconds",
        "max_output_bytes",
    ),
    [
        (
            0,
            1024,
        ),
        (
            -1,
            1024,
        ),
        (
            True,
            1024,
        ),
        (
            1,
            0,
        ),
        (
            1,
            -1,
        ),
        (
            1,
            True,
        ),
    ],
)
def test_rejects_invalid_execution_limits(
    tmp_path: Path,
    timeout_seconds,
    max_output_bytes,
):
    executable = (
        _write_fake_ffprobe(
            tmp_path
        )
    )

    with pytest.raises(
        ASRAdversarialFFprobeError,
    ):
        ASRAdversarialFFprobe(
            executable_path=executable,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
