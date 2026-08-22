from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from app.speech.base import TranscriptionError
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
            self.model = SimpleNamespace(
                device=device,
                compute_type=compute_type,
            )
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
            *,
            device: str,
            compute_type: str,
        ):
            self.model = SimpleNamespace(
                device=device,
                compute_type=compute_type,
            )
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


def test_faster_whisper_result_reports_actual_runtime_config(
    monkeypatch,
    tmp_path: Path,
):
    class FakeWhisperModel:
        def __init__(
            self,
            model_name: str,
            *,
            device: str,
            compute_type: str,
        ):
            assert model_name == "small.en"
            assert device == "cuda"
            assert compute_type == "float16"
            self.model = SimpleNamespace(
                device=device,
                compute_type=compute_type,
            )

        def transcribe(
            self,
            _audio_path: str,
            *,
            beam_size: int,
        ):
            assert beam_size == 5

            return (
                [
                    SimpleNamespace(
                        text=" runtime evidence "
                    )
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

    provider = FasterWhisperASRProvider(
        default_model_name="small.en",
        device=" CUDA ",
        compute_type=" FLOAT16 ",
    )

    result = provider.transcribe(
        build_audio_file(tmp_path)
    )

    assert result.provider == "faster_whisper"
    assert result.model_name == "small.en"
    assert result.device == "cuda"
    assert result.compute_type == "float16"


def test_mock_result_does_not_claim_unused_runtime_config(
    tmp_path: Path,
):
    provider = MockASRProvider(
        default_model_name="mock-runtime-test",
    )

    result = provider.transcribe(
        build_audio_file(tmp_path)
    )

    assert result.provider == "mock_local"
    assert result.model_name == "mock-runtime-test"

    # The mock provider does not actually execute on a
    # hardware/runtime backend, so these facts must remain
    # unknown rather than being fabricated from defaults.
    assert result.device is None
    assert result.compute_type is None


def test_faster_whisper_loads_model_lazily_and_reuses_it(
    tmp_path: Path,
):
    constructor_calls: list[dict[str, str]] = []
    transcription_calls: list[str] = []

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
            self.model = SimpleNamespace(
                device=device,
                compute_type=compute_type,
            )

        def transcribe(
            self,
            audio_path: str,
            *,
            beam_size: int,
        ):
            assert beam_size == 5
            transcription_calls.append(audio_path)
            return (
                [SimpleNamespace(text=" reused model ")],
                SimpleNamespace(),
            )

    provider = FasterWhisperASRProvider(
        default_model_name="small.en",
        model_loader=FakeWhisperModel,
    )

    assert constructor_calls == []

    audio_path = build_audio_file(tmp_path)
    first = provider.transcribe(audio_path)
    second = provider.transcribe(audio_path)

    assert first.transcript == "reused model"
    assert second.transcript == "reused model"
    assert constructor_calls == [
        {
            "model_name": "small.en",
            "device": "cpu",
            "compute_type": "int8",
        }
    ]
    assert transcription_calls == [
        str(audio_path),
        str(audio_path),
    ]


def test_faster_whisper_caches_model_overrides_independently(
    tmp_path: Path,
):
    selected_models: list[str] = []

    class FakeWhisperModel:
        def __init__(
            self,
            model_name: str,
            *,
            device: str,
            compute_type: str,
        ):
            selected_models.append(model_name)
            self.model = SimpleNamespace(
                device=device,
                compute_type=compute_type,
            )
            self._model_name = model_name

        def transcribe(self, _audio_path, **_kwargs):
            return (
                [
                    SimpleNamespace(
                        text=self._model_name
                    )
                ],
                SimpleNamespace(),
            )

    provider = FasterWhisperASRProvider(
        default_model_name="small.en",
        model_loader=FakeWhisperModel,
    )
    audio_path = build_audio_file(tmp_path)

    default_first = provider.transcribe(audio_path)
    override_first = provider.transcribe(
        audio_path,
        model_name="large-v3-turbo",
    )
    default_second = provider.transcribe(audio_path)
    override_second = provider.transcribe(
        audio_path,
        model_name="large-v3-turbo",
    )

    assert selected_models == [
        "small.en",
        "large-v3-turbo",
    ]
    assert default_first.model_name == "small.en"
    assert default_second.model_name == "small.en"
    assert override_first.model_name == (
        "large-v3-turbo"
    )
    assert override_second.model_name == (
        "large-v3-turbo"
    )


def test_faster_whisper_model_cache_is_provider_local(
    tmp_path: Path,
):
    constructed_models: list[object] = []

    class FakeWhisperModel:
        def __init__(
            self,
            _model_name: str,
            *,
            device: str,
            compute_type: str,
        ):
            constructed_models.append(self)
            self.model = SimpleNamespace(
                device=device,
                compute_type=compute_type,
            )

        def transcribe(self, _audio_path, **_kwargs):
            return (
                [SimpleNamespace(text=" isolated ")],
                SimpleNamespace(),
            )

    baseline_provider = FasterWhisperASRProvider(
        default_model_name="small.en",
        model_loader=FakeWhisperModel,
    )
    candidate_provider = FasterWhisperASRProvider(
        default_model_name="small.en",
        model_loader=FakeWhisperModel,
    )
    audio_path = build_audio_file(tmp_path)

    baseline_provider.transcribe(audio_path)
    baseline_provider.transcribe(audio_path)
    candidate_provider.transcribe(audio_path)
    candidate_provider.transcribe(audio_path)

    assert len(constructed_models) == 2
    assert (
        constructed_models[0]
        is not constructed_models[1]
    )


def test_faster_whisper_does_not_cache_failed_model_load(
    tmp_path: Path,
):
    attempts = 0

    def failing_loader(
        _model_name: str,
        **_kwargs,
    ):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("loader failure")

    provider = FasterWhisperASRProvider(
        model_loader=failing_loader,
    )
    audio_path = build_audio_file(tmp_path)

    for _attempt in range(2):
        with pytest.raises(
            TranscriptionError,
            match="model loading failed",
        ):
            provider.transcribe(audio_path)

    assert attempts == 2


def test_faster_whisper_rejects_invalid_loaded_model(
    tmp_path: Path,
):
    provider = FasterWhisperASRProvider(
        model_loader=lambda *_args, **_kwargs: (
            object()
        ),
    )

    with pytest.raises(
        TranscriptionError,
        match="invalid model",
    ):
        provider.transcribe(
            build_audio_file(tmp_path)
        )


@pytest.mark.parametrize(
    ("observed_device", "observed_compute_type", "message"),
    [
        (
            "cpu",
            "float16",
            "compute type does not match",
        ),
        (
            "cuda",
            "int8",
            "device does not match",
        ),
    ],
)
def test_faster_whisper_rejects_runtime_identity_mismatch(
    tmp_path: Path,
    observed_device: str,
    observed_compute_type: str,
    message: str,
):
    class FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            self.model = SimpleNamespace(
                device=observed_device,
                compute_type=observed_compute_type,
            )

        def transcribe(self, _audio_path, **_kwargs):
            raise AssertionError(
                "mismatched runtime must not execute"
            )

    provider = FasterWhisperASRProvider(
        device="cpu",
        compute_type="int8",
        model_loader=FakeWhisperModel,
    )

    with pytest.raises(
        TranscriptionError,
        match=message,
    ):
        provider.transcribe(
            build_audio_file(tmp_path)
        )


def test_faster_whisper_requires_observed_runtime_identity(
    tmp_path: Path,
):
    class FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, _audio_path, **_kwargs):
            raise AssertionError(
                "unidentified runtime must not execute"
            )

    provider = FasterWhisperASRProvider(
        model_loader=FakeWhisperModel,
    )

    with pytest.raises(
        TranscriptionError,
        match="device runtime identity",
    ):
        provider.transcribe(
            build_audio_file(tmp_path)
        )


def test_faster_whisper_wraps_transcription_failure(
    tmp_path: Path,
):
    class FakeWhisperModel:
        def __init__(
            self,
            _model_name: str,
            *,
            device: str,
            compute_type: str,
        ):
            self.model = SimpleNamespace(
                device=device,
                compute_type=compute_type,
            )

        def transcribe(self, _audio_path, **_kwargs):
            raise RuntimeError("transcription failure")

    provider = FasterWhisperASRProvider(
        model_loader=FakeWhisperModel,
    )

    with pytest.raises(
        TranscriptionError,
        match="transcription failed",
    ):
        provider.transcribe(
            build_audio_file(tmp_path)
        )
