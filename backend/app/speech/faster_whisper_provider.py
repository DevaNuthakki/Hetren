from pathlib import Path

from app.speech.base import (
    TranscriptionError,
    TranscriptionResult,
)


class FasterWhisperASRProvider:
    provider_name = "faster_whisper"

    def __init__(
        self,
        *,
        default_model_name: str = "large-v3-turbo",
        device: str = "cpu",
        compute_type: str = "int8",
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

        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise TranscriptionError(
                "faster-whisper is not installed. "
                "Install it in a compatible Python "
                "environment before selecting the "
                "faster_whisper provider."
            ) from error

        selected_model = (
            model_name.strip()
            if model_name is not None
            and model_name.strip()
            else self._default_model_name
        )

        try:
            model = WhisperModel(
                selected_model,
                device=self._device,
                compute_type=self._compute_type,
            )
            segments, _info = model.transcribe(
                str(audio_file),
                beam_size=5,
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
            model_name=selected_model,
        )
