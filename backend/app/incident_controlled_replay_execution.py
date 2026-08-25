"""Customer-controlled Incident Mode replay execution.

This module is the execution side of Stage 7.

Trust boundaries:

- Incident evidence defines the expected artifact commitments.
- Artifact bytes are supplied independently by a customer-controlled
  runner-local provider.
- Those bytes are SHA-256 and length verified again before execution.
- Raw artifact bytes and raw transcripts remain transient.
- Only commitment-only controlled replay evidence is returned.
- Behavior comparison and reproduction remain deferred to Stage 8.

The basic ASR replay adapter intentionally refuses prepared transport traces.
A trace may only be accepted by a future adapter that can actually apply it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from app.incident_controlled_replay_service import (
    INCIDENT_CONTROLLED_REPLAY_JOB_TYPE,
    INCIDENT_CONTROLLED_REPLAY_REQUIRED_CAPABILITIES,
    parse_incident_controlled_replay_request,
)
from app.incident_environment_materialization_execution import (
    IncidentRunnerMaterializedContext,
    build_incident_materialization_compatibility_observation,
)
from app.incident_runner_compatibility_service import (
    INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES,
)
from app.runner_config import LocalRunnerSettings
from app.runner_schemas import RunnerJobRead
from app.speech import ASRProvider, TranscriptionResult
from hvee.core.contracts import HveeContractError
from hvee.core.incident_environment_materialization import (
    verify_incident_environment_materialization_bundle,
)
from hvee.core.incident_controlled_replay import (
    IncidentControlledReplayArtifactObservation,
    IncidentControlledReplayBundle,
    IncidentControlledReplayExecutionObservation,
    IncidentControlledReplayOutputObservation,
    build_incident_controlled_replay_bundle,
    calculate_incident_generated_transcript_sha256,
)


class IncidentControlledReplayExecutionError(Exception):
    """Safe bounded Incident Mode replay failure."""


@dataclass(frozen=True, slots=True)
class IncidentReplayArtifactRequirement:
    kind: str
    reference_sha256: str
    expected_byte_length: int
    media_type: str

    def __post_init__(self) -> None:
        if self.kind not in {
            "source_audio",
            "transport_trace",
        }:
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact kind is unsupported."
            )

        if (
            not isinstance(self.reference_sha256, str)
            or len(self.reference_sha256) != 64
            or any(
                value not in "0123456789abcdef"
                for value in self.reference_sha256
            )
        ):
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact SHA-256 is invalid."
            )

        if (
            not isinstance(self.expected_byte_length, int)
            or isinstance(self.expected_byte_length, bool)
            or self.expected_byte_length <= 0
        ):
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact byte length is invalid."
            )

        if (
            not isinstance(self.media_type, str)
            or not self.media_type.strip()
        ):
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact media type is invalid."
            )


@dataclass(frozen=True, slots=True)
class IncidentReplayArtifact:
    requirement: IncidentReplayArtifactRequirement
    data: bytes

    def __post_init__(self) -> None:
        if not isinstance(
            self.requirement,
            IncidentReplayArtifactRequirement,
        ):
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact requirement is invalid."
            )

        if not isinstance(self.data, bytes):
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact data must be bytes."
            )

        if not self.data:
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact data must not be empty."
            )


class IncidentReplayArtifactProvider(Protocol):
    def __call__(
        self,
        requirement: IncidentReplayArtifactRequirement,
        control,
    ) -> IncidentReplayArtifact:
        ...


class IncidentReplayMaterializedContextProvider(Protocol):
    def __call__(
        self,
        control,
    ) -> IncidentRunnerMaterializedContext:
        ...


class IncidentReplayAdapter(Protocol):
    def execute(
        self,
        *,
        source_audio_path: Path,
        transport_trace_path: Path | None,
        model_name: str,
        control,
    ) -> TranscriptionResult:
        ...


class ASRProviderIncidentReplayAdapter:
    """Bounded replay adapter using Hetren's existing ASRProvider contract."""

    def __init__(
        self,
        provider: ASRProvider,
    ) -> None:
        self._provider = provider

    def execute(
        self,
        *,
        source_audio_path: Path,
        transport_trace_path: Path | None,
        model_name: str,
        control,
    ) -> TranscriptionResult:
        if transport_trace_path is not None:
            raise IncidentControlledReplayExecutionError(
                "The basic ASR replay adapter cannot apply "
                "a transport trace."
            )

        control.raise_if_stopped()

        result = self._provider.transcribe(
            source_audio_path,
            model_name=model_name,
        )

        control.raise_if_stopped()

        return result


@dataclass(frozen=True, slots=True)
class IncidentControlledReplayExecutionResult:
    bundle: IncidentControlledReplayBundle


def _artifact_requirements(
    replay_preparation_payload: object,
) -> tuple[
    IncidentReplayArtifactRequirement,
    ...,
]:
    if not isinstance(
        replay_preparation_payload,
        dict,
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay preparation must be a JSON object."
        )

    artifact_verification = (
        replay_preparation_payload.get(
            "artifact_verification"
        )
    )

    if not isinstance(
        artifact_verification,
        dict,
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay artifact verification is unavailable."
        )

    receipts = artifact_verification.get(
        "receipts"
    )

    if not isinstance(receipts, list):
        raise IncidentControlledReplayExecutionError(
            "Incident replay artifact receipts are unavailable."
        )

    requirements: list[
        IncidentReplayArtifactRequirement
    ] = []

    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact receipt is invalid."
            )

        if receipt.get("status") != "verified":
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact receipt is not verified."
            )

        requirement = (
            IncidentReplayArtifactRequirement(
                kind=receipt.get("kind"),
                reference_sha256=(
                    receipt.get(
                        "reference_sha256"
                    )
                ),
                expected_byte_length=(
                    receipt.get(
                        "expected_byte_length"
                    )
                ),
                media_type=receipt.get(
                    "media_type"
                ),
            )
        )

        requirements.append(requirement)

    ordered = tuple(
        sorted(
            requirements,
            key=lambda value: (
                value.kind,
                value.reference_sha256,
            ),
        )
    )

    identities = tuple(
        (
            value.kind,
            value.reference_sha256,
        )
        for value in ordered
    )

    if len(identities) != len(
        set(identities)
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay artifact requirements are ambiguous."
        )

    if not any(
        value.kind == "source_audio"
        for value in ordered
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay source audio is unavailable."
        )

    return ordered


def _verify_artifact(
    *,
    requirement: IncidentReplayArtifactRequirement,
    artifact: IncidentReplayArtifact,
) -> (
    IncidentControlledReplayArtifactObservation
):
    if artifact.requirement != requirement:
        raise IncidentControlledReplayExecutionError(
            "Incident replay artifact provider returned "
            "the wrong artifact."
        )

    observed_sha256 = hashlib.sha256(
        artifact.data
    ).hexdigest()

    observed_byte_length = len(
        artifact.data
    )

    if (
        observed_sha256
        != requirement.reference_sha256
        or observed_byte_length
        != requirement.expected_byte_length
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay artifact failed digest "
            "or byte-length reverification."
        )

    return (
        IncidentControlledReplayArtifactObservation(
            kind=requirement.kind,
            reference_sha256=(
                requirement.reference_sha256
            ),
            expected_byte_length=(
                requirement.expected_byte_length
            ),
            media_type=requirement.media_type,
            observed_sha256=observed_sha256,
            observed_byte_length=(
                observed_byte_length
            ),
        )
    )


def _source_audio_suffix(
    media_type: str,
) -> str:
    mapping = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/wave": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
    }

    suffix = mapping.get(
        media_type.strip().lower()
    )

    if suffix is None:
        raise IncidentControlledReplayExecutionError(
            "Incident replay source audio media type "
            "is unsupported."
        )

    return suffix


def _transcript_output(
    *,
    transcription: TranscriptionResult,
    settings: LocalRunnerSettings,
) -> IncidentControlledReplayOutputObservation:
    transcript = transcription.transcript

    if (
        not isinstance(transcript, str)
        or not transcript.strip()
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay returned an empty transcript."
        )

    provider = transcription.provider.strip()
    model_name = transcription.model_name.strip()

    if not provider:
        raise IncidentControlledReplayExecutionError(
            "Incident replay provider identity is unavailable."
        )

    if not model_name:
        raise IncidentControlledReplayExecutionError(
            "Incident replay model identity is unavailable."
        )

    if provider != settings.asr_provider:
        raise IncidentControlledReplayExecutionError(
            "Incident replay provider identity changed "
            "during execution."
        )

    if model_name != settings.asr_model:
        raise IncidentControlledReplayExecutionError(
            "Incident replay model identity changed "
            "during execution."
        )

    return (
        IncidentControlledReplayOutputObservation(
            generated_transcript_sha256=(
                calculate_incident_generated_transcript_sha256(
                    transcript
                )
            ),
            generated_transcript_utf8_bytes=len(
                transcript.encode("utf-8")
            ),
            provider=provider,
            model_name=model_name,
            device=transcription.device,
            compute_type=(
                transcription.compute_type
            ),
        )
    )


def _required_completed_operations(
    replay_preparation_payload: object,
) -> tuple[str, ...]:
    if not isinstance(
        replay_preparation_payload,
        dict,
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay preparation is invalid."
        )

    replay_plan = replay_preparation_payload.get(
        "replay_plan"
    )

    if not isinstance(replay_plan, dict):
        raise IncidentControlledReplayExecutionError(
            "Incident replay plan is unavailable."
        )

    steps = replay_plan.get("steps")

    if not isinstance(steps, list):
        raise IncidentControlledReplayExecutionError(
            "Incident replay plan steps are unavailable."
        )

    operations: list[str] = []

    for step in steps:
        if not isinstance(step, dict):
            raise IncidentControlledReplayExecutionError(
                "Incident replay plan step is invalid."
            )

        operation = step.get("operation")

        if not isinstance(operation, str):
            raise IncidentControlledReplayExecutionError(
                "Incident replay operation is invalid."
            )

        if (
            operation
            == "compare_behavior_commitments"
        ):
            break

        operations.append(operation)

    if (
        not operations
        or operations[-1]
        != "capture_replay_output"
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay execution boundary is invalid."
        )

    return tuple(operations)


def _verify_materialization_before_replay(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    runner_compatibility_payload: object,
    expected_runner_compatibility_sha256: object,
    environment_materialization_payload: object,
    expected_environment_materialization_sha256: object,
    compatibility_observation,
) -> None:
    """Fail closed before any artifact access or model execution."""

    if not verify_incident_environment_materialization_bundle(
        payload=environment_materialization_payload,
        expected_sha256=(
            expected_environment_materialization_sha256
        ),
        intake_payload=intake_payload,
        expected_intake_sha256=(
            expected_intake_sha256
        ),
        replay_preparation_payload=(
            replay_preparation_payload
        ),
        expected_replay_preparation_sha256=(
            expected_replay_preparation_sha256
        ),
        environment_manifest_payload=(
            environment_manifest_payload
        ),
        expected_environment_manifest_sha256=(
            expected_environment_manifest_sha256
        ),
        runner_compatibility_payload=(
            runner_compatibility_payload
        ),
        expected_runner_compatibility_sha256=(
            expected_runner_compatibility_sha256
        ),
        required_capabilities=(
            INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
        ),
        compatibility_observation=(
            compatibility_observation
        ),
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident controlled replay requires verified "
            "environment materialization."
        )

    if not isinstance(
        environment_materialization_payload,
        dict,
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident controlled replay materialization "
            "evidence is invalid."
        )

    materialization = (
        environment_materialization_payload.get(
            "materialization"
        )
    )

    evidence_boundary = (
        environment_materialization_payload.get(
            "evidence_boundary"
        )
    )

    if (
        not isinstance(materialization, dict)
        or materialization.get("status")
        != "materialized"
        or materialization.get(
            "environment_materialized"
        )
        is not True
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident controlled replay requires a "
            "materialized environment."
        )

    if (
        not isinstance(evidence_boundary, dict)
        or evidence_boundary.get(
            "operator_authorization_granted"
        )
        is not True
        or evidence_boundary.get(
            "environment_materialized"
        )
        is not True
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident controlled replay requires authorized "
            "materialization evidence."
        )


def execute_incident_controlled_replay(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    runner_compatibility_payload: object,
    expected_runner_compatibility_sha256: object,
    environment_materialization_payload: object,
    expected_environment_materialization_sha256: object,
    settings: LocalRunnerSettings,
    artifact_provider: IncidentReplayArtifactProvider,
    materialized_context_provider: (
        IncidentReplayMaterializedContextProvider
    ),
    replay_adapter: IncidentReplayAdapter,
    control,
) -> IncidentControlledReplayExecutionResult:
    """
    Execute the frozen Incident replay through capture_replay_output.

    compare_behavior_commitments is intentionally not executed here.
    """

    if artifact_provider is None:
        raise IncidentControlledReplayExecutionError(
            "Incident replay artifact provider is required."
        )

    if materialized_context_provider is None:
        raise IncidentControlledReplayExecutionError(
            "Incident replay materialized context provider "
            "is required."
        )

    if replay_adapter is None:
        raise IncidentControlledReplayExecutionError(
            "Incident replay adapter is required."
        )

    control.raise_if_stopped()

    materialized_context = (
        materialized_context_provider(
            control
        )
    )

    if not isinstance(
        materialized_context,
        IncidentRunnerMaterializedContext,
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay materialized context "
            "provider returned an invalid value."
        )

    compatibility_observation = (
        build_incident_materialization_compatibility_observation(
            settings,
            materialized_context=(
                materialized_context
            ),
        )
    )

    control.raise_if_stopped()

    _verify_materialization_before_replay(
        intake_payload=intake_payload,
        expected_intake_sha256=(
            expected_intake_sha256
        ),
        replay_preparation_payload=(
            replay_preparation_payload
        ),
        expected_replay_preparation_sha256=(
            expected_replay_preparation_sha256
        ),
        environment_manifest_payload=(
            environment_manifest_payload
        ),
        expected_environment_manifest_sha256=(
            expected_environment_manifest_sha256
        ),
        runner_compatibility_payload=(
            runner_compatibility_payload
        ),
        expected_runner_compatibility_sha256=(
            expected_runner_compatibility_sha256
        ),
        environment_materialization_payload=(
            environment_materialization_payload
        ),
        expected_environment_materialization_sha256=(
            expected_environment_materialization_sha256
        ),
        compatibility_observation=(
            compatibility_observation
        ),
    )

    control.raise_if_stopped()

    requirements = _artifact_requirements(
        replay_preparation_payload
    )

    artifacts: dict[
        str,
        IncidentReplayArtifact,
    ] = {}

    observations: list[
        IncidentControlledReplayArtifactObservation
    ] = []

    for requirement in requirements:
        control.raise_if_stopped()

        artifact = artifact_provider(
            requirement,
            control,
        )

        if not isinstance(
            artifact,
            IncidentReplayArtifact,
        ):
            raise IncidentControlledReplayExecutionError(
                "Incident replay artifact provider "
                "returned an invalid value."
            )

        observation = _verify_artifact(
            requirement=requirement,
            artifact=artifact,
        )

        observations.append(
            observation
        )

        artifacts[requirement.kind] = artifact

    control.raise_if_stopped()

    source_audio = artifacts.get(
        "source_audio"
    )

    if source_audio is None:
        raise IncidentControlledReplayExecutionError(
            "Incident replay source audio is unavailable."
        )

    transport_trace = artifacts.get(
        "transport_trace"
    )

    source_suffix = _source_audio_suffix(
        source_audio.requirement.media_type
    )

    with TemporaryDirectory(
        prefix="hetren-incident-replay-",
    ) as workspace:
        root = Path(workspace)

        source_audio_path = (
            root
            / f"source_audio{source_suffix}"
        )

        source_audio_path.write_bytes(
            source_audio.data
        )

        transport_trace_path: Path | None = None

        if transport_trace is not None:
            transport_trace_path = (
                root
                / "transport_trace.bin"
            )

            transport_trace_path.write_bytes(
                transport_trace.data
            )

        control.raise_if_stopped()

        transcription = replay_adapter.execute(
            source_audio_path=(
                source_audio_path
            ),
            transport_trace_path=(
                transport_trace_path
            ),
            model_name=settings.asr_model,
            control=control,
        )

        control.raise_if_stopped()

    if not isinstance(
        transcription,
        TranscriptionResult,
    ):
        raise IncidentControlledReplayExecutionError(
            "Incident replay adapter returned "
            "an invalid transcription result."
        )

    output = _transcript_output(
        transcription=transcription,
        settings=settings,
    )

    execution_observation = (
        IncidentControlledReplayExecutionObservation(
            completed_operations=(
                _required_completed_operations(
                    replay_preparation_payload
                )
            ),
            artifacts=tuple(
                sorted(
                    observations,
                    key=lambda value: (
                        value.identity
                    ),
                )
            ),
            output=output,
        )
    )

    control.raise_if_stopped()

    try:
        bundle = (
            build_incident_controlled_replay_bundle(
                intake_payload=intake_payload,
                expected_intake_sha256=(
                    expected_intake_sha256
                ),
                replay_preparation_payload=(
                    replay_preparation_payload
                ),
                expected_replay_preparation_sha256=(
                    expected_replay_preparation_sha256
                ),
                environment_manifest_payload=(
                    environment_manifest_payload
                ),
                expected_environment_manifest_sha256=(
                    expected_environment_manifest_sha256
                ),
                runner_compatibility_payload=(
                    runner_compatibility_payload
                ),
                expected_runner_compatibility_sha256=(
                    expected_runner_compatibility_sha256
                ),
                required_capabilities=(
                    INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
                ),
                compatibility_observation=(
                    compatibility_observation
                ),
                environment_materialization_payload=(
                    environment_materialization_payload
                ),
                expected_environment_materialization_sha256=(
                    expected_environment_materialization_sha256
                ),
                execution_observation=(
                    execution_observation
                ),
            )
        )
    except HveeContractError as exc:
        raise IncidentControlledReplayExecutionError(
            "Incident replay evidence failed "
            "upstream verification."
        ) from exc

    control.raise_if_stopped()

    return IncidentControlledReplayExecutionResult(
        bundle=bundle
    )



INCIDENT_CONTROLLED_REPLAY_RESULT_SCHEMA_VERSION = 1


class IncidentControlledReplayRunnerJobExecutor:
    """Execute a bounded controlled replay runner job."""

    supported_job_type = (
        INCIDENT_CONTROLLED_REPLAY_JOB_TYPE
    )

    def __init__(
        self,
        *,
        settings: LocalRunnerSettings,
        artifact_provider: (
            IncidentReplayArtifactProvider | None
        ) = None,
        materialized_context_provider: (
            IncidentReplayMaterializedContextProvider | None
        ) = None,
        replay_adapter: (
            IncidentReplayAdapter | None
        ) = None,
    ) -> None:
        self._settings = settings
        self._artifact_provider = artifact_provider
        self._materialized_context_provider = (
            materialized_context_provider
        )
        self._replay_adapter = replay_adapter

    def execute(
        self,
        job: RunnerJobRead,
        control,
    ) -> dict[str, object]:
        control.raise_if_stopped()

        if job.job_type != self.supported_job_type:
            raise IncidentControlledReplayExecutionError(
                "Incident controlled replay runner "
                "job type is invalid."
            )

        expected_capabilities = tuple(
            sorted(
                INCIDENT_CONTROLLED_REPLAY_REQUIRED_CAPABILITIES
            )
        )

        observed_capabilities = tuple(
            sorted(
                {
                    value.strip().lower()
                    for value in job.required_capabilities
                }
            )
        )

        if observed_capabilities != expected_capabilities:
            raise IncidentControlledReplayExecutionError(
                "Incident controlled replay runner "
                "capability contract is invalid."
            )

        if self._artifact_provider is None:
            raise IncidentControlledReplayExecutionError(
                "Incident controlled replay artifact "
                "provider is unavailable."
            )

        if self._materialized_context_provider is None:
            raise IncidentControlledReplayExecutionError(
                "Incident controlled replay materialized "
                "context provider is unavailable."
            )

        if self._replay_adapter is None:
            raise IncidentControlledReplayExecutionError(
                "Incident controlled replay adapter "
                "is unavailable."
            )

        control.raise_if_stopped()

        request = parse_incident_controlled_replay_request(
            job.input_payload
        )

        control.raise_if_stopped()

        result = execute_incident_controlled_replay(
            intake_payload=request.intake_payload,
            expected_intake_sha256=request.intake_sha256,
            replay_preparation_payload=(
                request.replay_preparation_payload
            ),
            expected_replay_preparation_sha256=(
                request.replay_preparation_sha256
            ),
            environment_manifest_payload=(
                request.environment_manifest_payload
            ),
            expected_environment_manifest_sha256=(
                request.environment_manifest_sha256
            ),
            runner_compatibility_payload=(
                request.runner_compatibility_payload
            ),
            expected_runner_compatibility_sha256=(
                request.runner_compatibility_sha256
            ),
            environment_materialization_payload=(
                request.environment_materialization_payload
            ),
            expected_environment_materialization_sha256=(
                request.environment_materialization_sha256
            ),
            settings=self._settings,
            artifact_provider=self._artifact_provider,
            materialized_context_provider=(
                self._materialized_context_provider
            ),
            replay_adapter=self._replay_adapter,
            control=control,
        )

        control.raise_if_stopped()

        return {
            "schema_version": (
                INCIDENT_CONTROLLED_REPLAY_RESULT_SCHEMA_VERSION
            ),
            "type": "incident_controlled_replay_result",
            "controlled_replay": {
                "payload": result.bundle.payload,
                "sha256": result.bundle.sha256,
            },
        }

__all__ = [
    "IncidentControlledReplayRunnerJobExecutor",
    "INCIDENT_CONTROLLED_REPLAY_RESULT_SCHEMA_VERSION",
    "ASRProviderIncidentReplayAdapter",
    "IncidentControlledReplayExecutionError",
    "IncidentControlledReplayExecutionResult",
    "IncidentReplayAdapter",
    "IncidentReplayArtifact",
    "IncidentReplayArtifactProvider",
    "IncidentReplayArtifactRequirement",
    "IncidentReplayMaterializedContextProvider",
    "execute_incident_controlled_replay",
]
