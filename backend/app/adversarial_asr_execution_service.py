"""Application orchestration for one adversarial ASR execution.

This service connects a sealed adversarial laboratory case to the existing
ASR provider contract and pure HVEE semantic/evidence layers.

The application layer owns audio-file access and provider invocation.
Scientific evaluator methodology remains inside HVEE.

This service does not persist database state, calculate qualification
thresholds, issue certification, authorize production use, or modify
release authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.content_hashing import (
    calculate_content_sha256,
)
from app.speech import (
    ASRProvider,
    TranscriptionResult,
)
from hvee.core.contracts import HveeContractError
from hvee.packs.asr import (
    ASRAdversarialEvidenceBundle,
    ASRAdversarialExecutionDefinition,
    ASRAdversarialExecutionEvidenceBundle,
    ASRAdversarialExecutionStatus,
    ASRAdversarialSemanticObservations,
    ASRAdversarialSuiteDefinition,
    ASRAdversarialTerminologyBinding,
    build_asr_adversarial_execution_evidence_v1,
    calculate_asr_adversarial_transcript_sha256,
    evaluate_asr_adversarial_semantics,
    verify_asr_adversarial_evidence_v1,
)


ASR_ADVERSARIAL_EXECUTION_ENVIRONMENT_SCHEMA_VERSION = 1
ASR_ADVERSARIAL_EXECUTION_ENVIRONMENT_KEY = (
    "hetren.asr.adversarial-execution-environment"
)
ASR_ADVERSARIAL_EXECUTION_ENVIRONMENT_VERSION = "1.0.0"


class ASRAdversarialExecutionServiceError(ValueError):
    """Raised when a qualification execution cannot be trusted."""


def _require_non_empty_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ASRAdversarialExecutionServiceError(
            f"{name} must be non-empty text."
        )

    return value.strip()


def _normalize_runtime_value(
    *,
    name: str,
    value: object,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ASRAdversarialExecutionServiceError(
            f"{name} must be text or null."
        )

    normalized = value.strip().lower()

    if not normalized:
        raise ASRAdversarialExecutionServiceError(
            f"{name} must not be empty."
        )

    return normalized


def _canonical_json(
    value: object,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ASRAdversarialExecutionServiceError(
            "ASR execution environment must contain "
            "deterministic JSON."
        ) from exc


@dataclass(frozen=True, slots=True)
class ASRAdversarialExecutionEnvironment:
    """Observed provider/model/runtime identity for one execution."""

    provider: str
    model_name: str
    device: str | None
    compute_type: str | None

    def __post_init__(self) -> None:
        if (
            _require_non_empty_string(
                name="observed ASR provider",
                value=self.provider,
            )
            != self.provider
        ):
            raise ASRAdversarialExecutionServiceError(
                "observed ASR provider must already "
                "be normalized."
            )

        if (
            _require_non_empty_string(
                name="observed ASR model",
                value=self.model_name,
            )
            != self.model_name
        ):
            raise ASRAdversarialExecutionServiceError(
                "observed ASR model must already "
                "be normalized."
            )

        normalized_device = _normalize_runtime_value(
            name="observed ASR device",
            value=self.device,
        )

        normalized_compute_type = (
            _normalize_runtime_value(
                name="observed ASR compute type",
                value=self.compute_type,
            )
        )

        if normalized_device != self.device:
            raise ASRAdversarialExecutionServiceError(
                "observed ASR device must already "
                "be normalized."
            )

        if (
            normalized_compute_type
            != self.compute_type
        ):
            raise ASRAdversarialExecutionServiceError(
                "observed ASR compute type must already "
                "be normalized."
            )

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema_version": (
                ASR_ADVERSARIAL_EXECUTION_ENVIRONMENT_SCHEMA_VERSION
            ),
            "artifact": {
                "key": (
                    ASR_ADVERSARIAL_EXECUTION_ENVIRONMENT_KEY
                ),
                "version": (
                    ASR_ADVERSARIAL_EXECUTION_ENVIRONMENT_VERSION
                ),
            },
            "execution_config": {
                "provider": self.provider,
                "model_name": self.model_name,
                "device": self.device,
                "compute_type": self.compute_type,
            },
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            _canonical_json(
                self.payload
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class ASRAdversarialExecutionServiceResult:
    """Successful in-memory result of one adversarial ASR execution."""

    case_id: str
    audio_asset_sha256: str
    audio_byte_length: int
    generated_transcript: str
    environment: ASRAdversarialExecutionEnvironment
    semantic_observations: (
        ASRAdversarialSemanticObservations
    )
    execution_definition: (
        ASRAdversarialExecutionDefinition
    )
    execution_evidence: (
        ASRAdversarialExecutionEvidenceBundle
    )


def _find_case(
    *,
    suite: ASRAdversarialSuiteDefinition,
    case_id: str,
):
    for case in suite.cases:
        if case.case_id == case_id:
            return case

    raise ASRAdversarialExecutionServiceError(
        "adversarial execution case does not "
        "exist in the sealed suite."
    )


def _resolve_audio_path(
    audio_path: str | Path,
) -> Path:
    if not isinstance(
        audio_path,
        (str, Path),
    ):
        raise ASRAdversarialExecutionServiceError(
            "adversarial audio path is invalid."
        )

    path = Path(audio_path)

    if not path.exists():
        raise ASRAdversarialExecutionServiceError(
            "adversarial audio file does not exist."
        )

    if not path.is_file():
        raise ASRAdversarialExecutionServiceError(
            "adversarial audio path must reference a file."
        )

    return path


def _verify_audio_content(
    *,
    audio_path: Path,
    expected_sha256: str,
    expected_byte_length: int | None = None,
) -> tuple[str, int]:
    try:
        observed_sha256, observed_byte_length = (
            calculate_content_sha256(
                audio_path
            )
        )
    except OSError as exc:
        raise ASRAdversarialExecutionServiceError(
            "adversarial audio could not be read."
        ) from exc

    if observed_byte_length <= 0:
        raise ASRAdversarialExecutionServiceError(
            "adversarial audio file must not be empty."
        )

    if observed_sha256 != expected_sha256:
        if expected_byte_length is not None:
            raise ASRAdversarialExecutionServiceError(
                "adversarial audio changed during execution."
            )

        raise ASRAdversarialExecutionServiceError(
            "adversarial audio does not match "
            "the sealed case."
        )

    if (
        expected_byte_length is not None
        and observed_byte_length
        != expected_byte_length
    ):
        raise ASRAdversarialExecutionServiceError(
            "adversarial audio changed during execution."
        )

    return (
        observed_sha256,
        observed_byte_length,
    )


def _normalize_transcription_result(
    *,
    result: object,
    declared_provider: str,
    requested_model_name: str,
) -> tuple[
    str,
    ASRAdversarialExecutionEnvironment,
]:
    if not isinstance(
        result,
        TranscriptionResult,
    ):
        raise ASRAdversarialExecutionServiceError(
            "ASR provider returned an invalid "
            "transcription result."
        )

    transcript = _require_non_empty_string(
        name="generated transcript",
        value=result.transcript,
    )

    observed_provider = (
        _require_non_empty_string(
            name="observed ASR provider",
            value=result.provider,
        )
    )

    observed_model = (
        _require_non_empty_string(
            name="observed ASR model",
            value=result.model_name,
        )
    )

    if observed_provider != declared_provider:
        raise ASRAdversarialExecutionServiceError(
            "ASR provider identity does not match "
            "the executing provider."
        )

    if observed_model != requested_model_name:
        raise ASRAdversarialExecutionServiceError(
            "ASR model identity does not match "
            "the requested qualification model."
        )

    environment = (
        ASRAdversarialExecutionEnvironment(
            provider=observed_provider,
            model_name=observed_model,
            device=_normalize_runtime_value(
                name="observed ASR device",
                value=result.device,
            ),
            compute_type=(
                _normalize_runtime_value(
                    name="observed ASR compute type",
                    value=result.compute_type,
                )
            ),
        )
    )

    return transcript, environment


def execute_asr_adversarial_case(
    *,
    execution_id: str,
    case_id: str,
    audio_path: str | Path,
    requested_model_name: str,
    provider: ASRProvider,
    terminology: ASRAdversarialTerminologyBinding,
    suite: ASRAdversarialSuiteDefinition,
    suite_evidence: ASRAdversarialEvidenceBundle,
) -> ASRAdversarialExecutionServiceResult:
    """Execute and seal one successful adversarial ASR case."""

    execution_id = _require_non_empty_string(
        name="adversarial execution id",
        value=execution_id,
    )

    case_id = _require_non_empty_string(
        name="adversarial case id",
        value=case_id,
    )

    requested_model_name = (
        _require_non_empty_string(
            name="requested ASR model",
            value=requested_model_name,
        )
    )

    if not isinstance(
        terminology,
        ASRAdversarialTerminologyBinding,
    ):
        raise ASRAdversarialExecutionServiceError(
            "adversarial execution requires "
            "terminology configuration."
        )

    # Reverify the source-visible suite before touching
    # audio or invoking an expensive provider.
    verify_asr_adversarial_evidence_v1(
        payload=suite_evidence.payload,
        expected_sha256=suite_evidence.sha256,
        definition=suite,
    )

    case = _find_case(
        suite=suite,
        case_id=case_id,
    )

    if (
        case.semantic_load.critical_terminology_count
        > 0
        and terminology.profile is None
    ):
        raise ASRAdversarialExecutionServiceError(
            "adversarial case declaring critical "
            "terminology requires a configured profile."
        )

    path = _resolve_audio_path(
        audio_path
    )

    (
        audio_sha256,
        audio_byte_length,
    ) = _verify_audio_content(
        audio_path=path,
        expected_sha256=(
            case.audio_asset_sha256
        ),
    )

    declared_provider = (
        _require_non_empty_string(
            name="executing ASR provider",
            value=getattr(
                provider,
                "provider_name",
                None,
            ),
        )
    )

    # Provider exceptions intentionally propagate. A provider
    # failure is not represented as successful execution evidence.
    transcription = provider.transcribe(
        path,
        model_name=requested_model_name,
    )

    # Rehash after inference so evidence is not sealed if the input
    # changed while the provider was executing.
    _verify_audio_content(
        audio_path=path,
        expected_sha256=audio_sha256,
        expected_byte_length=(
            audio_byte_length
        ),
    )

    (
        generated_transcript,
        environment,
    ) = _normalize_transcription_result(
        result=transcription,
        declared_provider=declared_provider,
        requested_model_name=(
            requested_model_name
        ),
    )

    semantic_observations = (
        evaluate_asr_adversarial_semantics(
            reference_text=(
                case.reference_transcript
            ),
            generated_text=(
                generated_transcript
            ),
            terminology=terminology,
        )
    )

    execution_definition = (
        ASRAdversarialExecutionDefinition(
            execution_id=execution_id,
            case_id=case.case_id,
            provider_key=environment.provider,
            model_key=environment.model_name,
            execution_environment_sha256=(
                environment.sha256
            ),
            status=(
                ASRAdversarialExecutionStatus
                .COMPLETED
            ),
            terminology=terminology,
            generated_transcript_sha256=(
                calculate_asr_adversarial_transcript_sha256(
                    generated_transcript
                )
            ),
            semantic_observations=(
                semantic_observations
            ),
        )
    )

    execution_evidence = (
        build_asr_adversarial_execution_evidence_v1(
            execution_definition,
            suite=suite,
            suite_evidence=suite_evidence,
        )
    )

    return ASRAdversarialExecutionServiceResult(
        case_id=case.case_id,
        audio_asset_sha256=audio_sha256,
        audio_byte_length=audio_byte_length,
        generated_transcript=(
            generated_transcript
        ),
        environment=environment,
        semantic_observations=(
            semantic_observations
        ),
        execution_definition=(
            execution_definition
        ),
        execution_evidence=(
            execution_evidence
        ),
    )
