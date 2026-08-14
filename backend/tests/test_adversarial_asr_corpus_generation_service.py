from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adversarial_asr_corpus_generation_service import (
    ASRAdversarialCorpusGenerationError,
    generate_asr_adversarial_synthetic_source_v1,
)
from hvee.packs.asr.adversarial_corpus_records import (
    calculate_asr_adversarial_corpus_record_sha256,
)


CORPUS_ROOT = (
    Path(__file__).resolve()
    .parents[1]
    / "corpora"
    / "asr"
    / "adversarial"
    / "v1"
)

ESPEAK_SHA256 = (
    "0a2f26e328f1dd4cec926987d3dc22bf"
    "841879132fd3aa497dd4fcad0d4d77a3"
)

SOURCE_BYTES = (
    b"deterministic-synthetic-audio-v1"
)


def _sha256(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


class _FakeSynthesizer:
    def __init__(
        self,
        *,
        package_version: str = (
            "1.51+dfsg-10+deb12u2"
        ),
    ) -> None:
        self.environment = SimpleNamespace(
            package_version=package_version,
            executable_sha256=ESPEAK_SHA256,
            platform_key="linux-amd64",
            environment_sha256=(
                hashlib.sha256(
                    b"fake-environment"
                ).hexdigest()
            ),
        )
        self.calls = []

    def synthesize(
        self,
        *,
        transcript_path: Path,
        output_path: Path,
        voice_key: str,
        speed_wpm: int,
        pitch: int,
        amplitude: int,
    ) -> None:
        self.calls.append(
            {
                "transcript_path": transcript_path,
                "voice_key": voice_key,
                "speed_wpm": speed_wpm,
                "pitch": pitch,
                "amplitude": amplitude,
            }
        )

        output_path.write_bytes(
            SOURCE_BYTES
        )


class _FakeProbe:
    def probe(
        self,
        path: Path,
    ):
        assert path.is_file()

        return SimpleNamespace(
            duration_ms=12_604,
            sample_rate_hz=22_050,
            channel_count=1,
            codec_name="pcm_s16le",
        )


def _copy_corpus(
    tmp_path: Path,
) -> Path:
    destination = (
        tmp_path
        / "corpus"
    )

    shutil.copytree(
        CORPUS_ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            "generated"
        ),
    )

    return destination


def _generate(
    *,
    corpus_root: Path,
    output_root: Path,
    synthesizer=None,
):
    return (
        generate_asr_adversarial_synthetic_source_v1(
            corpus_root=corpus_root,
            output_root=output_root,
            case_id="control.clean-critical",
            synthesizer=(
                synthesizer
                or _FakeSynthesizer()
            ),
            media_probe=_FakeProbe(),
        )
    )


def test_generates_verified_source_from_committed_records(
    tmp_path: Path,
):
    synthesizer = (
        _FakeSynthesizer()
    )

    output_root = (
        tmp_path
        / "generated"
    )

    result = _generate(
        corpus_root=CORPUS_ROOT,
        output_root=output_root,
        synthesizer=synthesizer,
    )

    expected = (
        output_root
        / "source"
        / "control.clean-critical.wav"
    )

    assert expected.read_bytes() == SOURCE_BYTES

    assert (
        result.audio_asset_sha256
        == _sha256(
            SOURCE_BYTES
        )
    )
    assert result.byte_length == len(
        SOURCE_BYTES
    )
    assert result.duration_ms == 12_604
    assert result.sample_rate_hz == 22_050
    assert result.channel_count == 1
    assert result.codec_name == "pcm_s16le"

    assert len(
        synthesizer.calls
    ) == 1

    call = synthesizer.calls[0]

    assert call["voice_key"] == "en-us"
    assert call["speed_wpm"] == 150
    assert call["pitch"] == 50
    assert call["amplitude"] == 100


def test_rejects_runtime_generator_environment_mismatch(
    tmp_path: Path,
):
    with pytest.raises(
        ASRAdversarialCorpusGenerationError,
        match="runtime synthetic-speech environment",
    ):
        _generate(
            corpus_root=CORPUS_ROOT,
            output_root=(
                tmp_path
                / "generated"
            ),
            synthesizer=(
                _FakeSynthesizer(
                    package_version="9.9.9",
                )
            ),
        )


def test_rejects_transcript_tampering(
    tmp_path: Path,
):
    corpus = _copy_corpus(
        tmp_path
    )

    transcript = (
        corpus
        / "specification"
        / "transcripts"
        / "control.clean-critical.txt"
    )

    transcript.write_text(
        transcript.read_text(
            encoding="utf-8"
        )
        + "tampered\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ASRAdversarialCorpusGenerationError,
        match="transcript SHA-256",
    ):
        _generate(
            corpus_root=corpus,
            output_root=(
                tmp_path
                / "generated"
            ),
        )


def test_source_generator_rejects_derivative_plan_entry(
    tmp_path: Path,
):
    corpus = _copy_corpus(
        tmp_path
    )

    plan_path = (
        corpus
        / "specification"
        / "generation-plan.json"
    )

    document = json.loads(
        plan_path.read_text(
            encoding="utf-8"
        )
    )

    document["payload"]["record"][
        "entries"
    ][0][
        "transformation_record_sha256"
    ] = "0" * 64

    document["sha256"] = (
        calculate_asr_adversarial_corpus_record_sha256(
            document["payload"]
        )
    )

    plan_path.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ASRAdversarialCorpusGenerationError,
        match="cannot execute a derivative",
    ):
        _generate(
            corpus_root=corpus,
            output_root=(
                tmp_path
                / "generated"
            ),
        )


def test_existing_identical_source_is_idempotent(
    tmp_path: Path,
):
    output_root = (
        tmp_path
        / "generated"
    )

    first = _generate(
        corpus_root=CORPUS_ROOT,
        output_root=output_root,
    )
    second = _generate(
        corpus_root=CORPUS_ROOT,
        output_root=output_root,
    )

    assert first == second

    output = (
        output_root
        / "source"
        / "control.clean-critical.wav"
    )

    assert output.read_bytes() == SOURCE_BYTES


def test_existing_different_source_is_not_overwritten(
    tmp_path: Path,
):
    output_root = (
        tmp_path
        / "generated"
    )

    output = (
        output_root
        / "source"
        / "control.clean-critical.wav"
    )

    output.parent.mkdir(
        parents=True
    )
    output.write_bytes(
        b"tampered-existing-audio"
    )

    with pytest.raises(
        ASRAdversarialCorpusGenerationError,
        match="existing generated source does not match",
    ):
        _generate(
            corpus_root=CORPUS_ROOT,
            output_root=output_root,
        )

    assert (
        output.read_bytes()
        == b"tampered-existing-audio"
    )


@pytest.mark.parametrize(
    "which_root",
    [
        "corpus",
        "output",
    ],
)
def test_symlink_roots_are_rejected(
    tmp_path: Path,
    which_root: str,
):
    real_corpus = _copy_corpus(
        tmp_path
    )

    real_output = (
        tmp_path
        / "real-output"
    )
    real_output.mkdir()

    corpus_root = real_corpus
    output_root = real_output

    if which_root == "corpus":
        corpus_link = (
            tmp_path
            / "corpus-link"
        )
        corpus_link.symlink_to(
            real_corpus,
            target_is_directory=True,
        )
        corpus_root = corpus_link
    else:
        output_link = (
            tmp_path
            / "output-link"
        )
        output_link.symlink_to(
            real_output,
            target_is_directory=True,
        )
        output_root = output_link

    with pytest.raises(
        ASRAdversarialCorpusGenerationError,
        match="cannot be a symlink",
    ):
        _generate(
            corpus_root=corpus_root,
            output_root=output_root,
        )
