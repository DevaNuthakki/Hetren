from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from app.speech.faster_whisper_provider import (
    FasterWhisperASRProvider,
)
from app.speech.mock_provider import MockASRProvider
from app.speech.registry import get_asr_provider


def build_audio_file(tmp_path: Path) -> Path:
    audio_path = tmp_path / "support-call.wav"
    audio_path.write_bytes(b"test-audio")
    return audio_path


def test_registry_builds_configured_mock_provider(
    tmp_path: Path,
):
    provider = get_asr_provider(
        "mock",
        model_name="runner-mock-model",
    )

    assert isinstance(provider, MockASRProvider)

    result = provider.transcribe(
        build_audio_file(tmp_path),
    )

    assert result.provider == "mock_local"
    assert result.model_name == "runner-mock-model"


def test_registry_builds_configured_faster_whisper(
    monkeypatch,
    tmp_path: Path,
):
    constructor_calls: list[dict[str, object]] = []
    transcription_calls: list[dict[str, object]] = []

    class FakeWhisperModel:
        def __init__(
            self,
            model_name: str,
            *,
            device: str,
            compute_type: str,
        ):
            constructor_calls.append(
                {
                    "model_name": model_name,
                    "device": device,
                    "compute_type": compute_type,
                }
            )

        def transcribe(
            self,
            audio_path: str,
            *,
            beam_size: int,
        ):
            transcription_calls.append(
                {
                    "audio_path": audio_path,
                    "beam_size": beam_size,
                }
            )

            return (
                [
                    SimpleNamespace(text=" thank you "),
                    SimpleNamespace(text=" for calling "),
                ],
                SimpleNamespace(),
            )

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(
            WhisperModel=FakeWhisperModel,
        ),
    )

    provider = get_asr_provider(
        "faster-whisper",
        model_name="small.en",
        device="CUDA",
        compute_type="FLOAT16",
    )

    assert isinstance(
        provider,
        FasterWhisperASRProvider,
    )

    audio_path = build_audio_file(tmp_path)
    result = provider.transcribe(audio_path)

    assert constructor_calls == [
        {
            "model_name": "small.en",
            "device": "cuda",
            "compute_type": "float16",
        }
    ]
    assert transcription_calls == [
        {
            "audio_path": str(audio_path),
            "beam_size": 5,
        }
    ]
    assert result.transcript == "thank you for calling"
    assert result.provider == "faster_whisper"
    assert result.model_name == "small.en"


def test_faster_whisper_uses_run_model_override(
    monkeypatch,
    tmp_path: Path,
):
    selected_models: list[str] = []

    class FakeWhisperModel:
        def __init__(
            self,
            model_name: str,
            **_kwargs,
        ):
            selected_models.append(model_name)

        def transcribe(self, _audio_path, **_kwargs):
            return (
                [SimpleNamespace(text=" transcript ")],
                SimpleNamespace(),
            )

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(
            WhisperModel=FakeWhisperModel,
        ),
    )

    provider = FasterWhisperASRProvider(
        default_model_name="small.en",
    )

    result = provider.transcribe(
        build_audio_file(tmp_path),
        model_name="large-v3-turbo",
    )

    assert selected_models == ["large-v3-turbo"]
    assert result.model_name == "large-v3-turbo"


def test_registry_rejects_unsupported_provider():
    with pytest.raises(
        ValueError,
        match="Unsupported ASR provider",
    ):
        get_asr_provider("unknown-provider")


def test_registry_loads_hetren_environment(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.delenv("OVRIN_ASR_PROVIDER", raising=False)
    monkeypatch.delenv("OVRIN_ASR_MODEL", raising=False)
    monkeypatch.setenv("HETREN_ASR_PROVIDER", "mock")
    monkeypatch.setenv("HETREN_ASR_MODEL", "hetren-env-model")

    provider = get_asr_provider()
    result = provider.transcribe(build_audio_file(tmp_path))

    assert isinstance(provider, MockASRProvider)
    assert result.model_name == "hetren-env-model"


def test_registry_accepts_legacy_ovrin_environment(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.delenv("HETREN_ASR_PROVIDER", raising=False)
    monkeypatch.delenv("HETREN_ASR_MODEL", raising=False)
    monkeypatch.setenv("OVRIN_ASR_PROVIDER", "mock")
    monkeypatch.setenv("OVRIN_ASR_MODEL", "legacy-env-model")

    provider = get_asr_provider()
    result = provider.transcribe(build_audio_file(tmp_path))

    assert isinstance(provider, MockASRProvider)
    assert result.model_name == "legacy-env-model"


def test_hetren_asr_environment_takes_precedence(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("HETREN_ASR_PROVIDER", "mock")
    monkeypatch.setenv("OVRIN_ASR_PROVIDER", "unknown")
    monkeypatch.setenv("HETREN_ASR_MODEL", "hetren-primary-model")
    monkeypatch.setenv("OVRIN_ASR_MODEL", "legacy-model")

    provider = get_asr_provider()
    result = provider.transcribe(build_audio_file(tmp_path))

    assert isinstance(provider, MockASRProvider)
    assert result.model_name == "hetren-primary-model"
