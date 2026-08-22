from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.speech.base import (
    TranscriptionError,
    TranscriptionResult,
)


WhisperModelLoader = Callable[..., object]


@dataclass(frozen=True, slots=True)
class _LoadedWhisperModel:
    model: object
    model_name: str
    device: str
    compute_type: str


def _load_faster_whisper_model(
    model_name: str,
    *,
    device: str,
    compute_type: str,
) -> object:
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise TranscriptionError(
            "faster-whisper is not installed. "
            "Install it in a compatible Python "
            "environment before selecting the "
            "faster_whisper provider."
        ) from error

    return WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
    )


def _require_runtime_text(
    *,
    name: str,
    value: object,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TranscriptionError(
            "faster-whisper did not report a valid "
            f"{name} runtime identity."
        )

    return value.strip().lower()


class FasterWhisperASRProvider:
    provider_name = "faster_whisper"

    def __init__(
        self,
        *,
        default_model_name: str = "large-v3-turbo",
        device: str = "cpu",
        compute_type: str = "int8_float32",
        model_loader: WhisperModelLoader | None = None,
    ):
        normalized_model = default_model_name.strip()
        normalized_device = device.strip().lower()
        normalized_compute_type = (
            compute_type.strip().lower()
        )

        if not normalized_model:
            raise ValueError(
                "Default ASR model must not be empty."
            )

        if not normalized_device:
            raise ValueError(
                "ASR device must not be empty."
            )

        if not normalized_compute_type:
            raise ValueError(
                "ASR compute type must not be empty."
            )

        self._default_model_name = normalized_model
        self._device = normalized_device
        self._compute_type = (
            normalized_compute_type
        )
        self._model_loader = (
            model_loader
            or _load_faster_whisper_model
        )
        self._loaded_models: dict[
            str,
            _LoadedWhisperModel,
        ] = {}
        self._model_load_lock = Lock()

    def _build_loaded_model(
        self,
        *,
        model_name: str,
    ) -> _LoadedWhisperModel:
        try:
            model = self._model_loader(
                model_name,
                device=self._device,
                compute_type=self._compute_type,
            )
        except TranscriptionError:
            raise
        except Exception as error:
            raise TranscriptionError(
                "faster-whisper model loading failed."
            ) from error

        if not callable(
            getattr(model, "transcribe", None)
        ):
            raise TranscriptionError(
                "faster-whisper model loader returned "
                "an invalid model."
            )

        runtime_model = getattr(
            model,
            "model",
            None,
        )
        observed_device = _require_runtime_text(
            name="device",
            value=getattr(
                runtime_model,
                "device",
                None,
            ),
        )
        observed_compute_type = (
            _require_runtime_text(
                name="compute type",
                value=getattr(
                    runtime_model,
                    "compute_type",
                    None,
                ),
            )
        )

        if (
            self._device != "auto"
            and observed_device != self._device
        ):
            raise TranscriptionError(
                "faster-whisper runtime device "
                "does not match the requested device: "
                f"requested={self._device!r}; "
                f"observed={observed_device!r}."
            )

        if (
            self._compute_type
            not in {"auto", "default"}
            and observed_compute_type
            != self._compute_type
        ):
            raise TranscriptionError(
                "faster-whisper runtime compute type "
                "does not match the requested "
                "compute type: "
                f"requested={self._compute_type!r}; "
                f"observed={observed_compute_type!r}."
            )

        return _LoadedWhisperModel(
            model=model,
            model_name=model_name,
            device=observed_device,
            compute_type=observed_compute_type,
        )

    def _get_loaded_model(
        self,
        *,
        model_name: str,
    ) -> _LoadedWhisperModel:
        with self._model_load_lock:
            loaded_model = self._loaded_models.get(
                model_name
            )

            if loaded_model is None:
                loaded_model = self._build_loaded_model(
                    model_name=model_name,
                )
                self._loaded_models[
                    model_name
                ] = loaded_model

            return loaded_model

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        audio_file = Path(audio_path)

        if not audio_file.exists():
            raise TranscriptionError(
                f"Audio file not found: {audio_file}"
            )

        if audio_file.stat().st_size == 0:
            raise TranscriptionError(
                f"Audio file is empty: {audio_file}"
            )

        selected_model = (
            model_name.strip()
            if model_name is not None
            and model_name.strip()
            else self._default_model_name
        )
        loaded_model = self._get_loaded_model(
            model_name=selected_model,
        )

        try:
            segments, _info = (
                loaded_model.model.transcribe(
                    str(audio_file),
                    beam_size=5,
                )
            )
            transcript = " ".join(
                segment.text.strip()
                for segment in segments
            ).strip()
        except Exception as error:
            raise TranscriptionError(
                "faster-whisper transcription failed."
            ) from error

        if not transcript:
            raise TranscriptionError(
                "faster-whisper returned an empty "
                "transcript."
            )

        return TranscriptionResult(
            transcript=transcript,
            provider=self.provider_name,
            model_name=loaded_model.model_name,
            device=loaded_model.device,
            compute_type=(
                loaded_model.compute_type
            ),
        )
