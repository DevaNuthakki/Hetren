from pathlib import Path

from app.speech.base import (
    TranscriptionError,
    TranscriptionResult,
)


class MockASRProvider:
    provider_name = "mock_local"

    def __init__(
        self,
        *,
        default_model_name: str = (
            "mock-asr-foundation"
        ),
    ):
        normalized_model = default_model_name.strip()

        if not normalized_model:
            raise ValueError(
                "Default ASR model must not be empty."
            )

        self._default_model_name = normalized_model

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

        transcript = (
            "mock asr transcript generated from "
            f"{audio_file.stem.replace('-', ' ').replace('_', ' ')}"
        )

        selected_model = (
            model_name.strip()
            if model_name is not None
            and model_name.strip()
            else self._default_model_name
        )

        return TranscriptionResult(
            transcript=transcript,
            provider=self.provider_name,
            model_name=selected_model,
        )
