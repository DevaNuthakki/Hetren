from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TranscriptionResult:
    transcript: str
    provider: str
    model_name: str
    device: str | None = None
    compute_type: str | None = None


class TranscriptionError(Exception):
    pass


class ASRProvider(Protocol):
    provider_name: str

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        ...
