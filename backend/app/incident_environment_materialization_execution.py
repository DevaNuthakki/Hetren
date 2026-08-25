"""Runner-local Incident Mode environment materialization.

The Incident request defines the target environment.

Runner settings may establish genuine local runtime identities, but they do
not establish exact audio or transport materialization.

Exact audio/transport observations must come from an independently produced
IncidentRunnerMaterializedContext representing transient runner-local state.
The expected Incident context is never reused as an observed materialized
value.

Durable outputs contain commitments only. Raw materialized values remain
runner-local and transient.

This module does not load the ASR model, transcribe audio, execute replay,
claim reproduction, prove model failure, promote a contract, or grant
qualification authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from app.incident_environment_materialization_service import (
    INCIDENT_ENVIRONMENT_MATERIALIZATION_JOB_TYPE,
    INCIDENT_ENVIRONMENT_MATERIALIZATION_REQUIRED_CAPABILITIES,
)
from app.incident_runner_compatibility_service import (
    INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES,
    IncidentReplayCompatibilityRequest,
    evaluate_incident_replay_compatibility_request,
    parse_incident_replay_compatibility_request,
)
from app.runner_config import LocalRunnerSettings
from app.runner_schemas import RunnerJobRead
from hvee.core.contracts import HveeContractError
from hvee.core.incident_environment_materialization import (
    IncidentEnvironmentMaterializationBundle,
    IncidentMaterializedRequirementObservation,
    IncidentOperatorAuthorization,
    build_incident_environment_materialization_bundle,
    calculate_incident_materialized_value_commitment,
)
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerCompatibilityBundle,
    IncidentRunnerEnvironmentObservation,
)


@dataclass(frozen=True, slots=True)
class IncidentRunnerMaterializedContext:
    """Transient context actually established inside the customer runner."""

    audio: dict[str, object] | None = None
    transport: dict[str, object] | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("audio", self.audio),
            ("transport", self.transport),
        ):
            if value is not None and not isinstance(
                value,
                dict,
            ):
                raise HveeContractError(
                    f"materialized {name} context "
                    "must be a JSON object or null"
                )

            if value is None:
                continue

            try:
                canonical = json.loads(
                    json.dumps(
                        value,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                        allow_nan=False,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise HveeContractError(
                    f"materialized {name} context "
                    "must be deterministic JSON"
                ) from exc

            object.__setattr__(
                self,
                name,
                canonical,
            )

    @property
    def exact_context_components(
        self,
    ) -> tuple[str, ...]:
        values: list[str] = []

        if self.audio is not None:
            values.append("audio")

        if self.transport is not None:
            values.append("transport")

        return tuple(values)


@dataclass(frozen=True, slots=True)
class IncidentRunnerMaterializationResult:
    compatibility: IncidentRunnerCompatibilityBundle
    materialization: IncidentEnvironmentMaterializationBundle


def _canonical_capabilities(
    values: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                value.strip().lower()
                for value in values
            }
        )
    )


def build_incident_materialization_compatibility_observation(
    settings: LocalRunnerSettings,
    *,
    materialized_context: (
        IncidentRunnerMaterializedContext | None
    ) = None,
) -> IncidentRunnerEnvironmentObservation:
    """
    Build only observations genuinely available in the customer runner.

    Runtime identity comes from explicit runner-local configuration.
    Audio/transport exactness comes only from actual transient materialized
    context, never from a configuration declaration.
    """

    exact_context_components = (
        ()
        if materialized_context is None
        else materialized_context.exact_context_components
    )

    return IncidentRunnerEnvironmentObservation(
        capabilities=_canonical_capabilities(
            settings.capabilities
        ),
        deployment_key=settings.incident_deployment_key,
        deployment_version=(
            settings.incident_deployment_version
        ),
        provider_key=settings.asr_provider,
        provider_version=settings.incident_provider_version,
        model_key=settings.asr_model,
        model_version=settings.incident_model_version,
        model_artifact_sha256=(
            settings.incident_model_artifact_sha256
        ),
        source_code_sha256=(
            settings.incident_source_code_sha256
        ),
        configuration_sha256=(
            settings.incident_configuration_sha256
        ),
        runtime_environment_sha256=(
            settings.incident_runtime_environment_sha256
        ),
        host_environment_sha256=(
            settings.incident_host_environment_sha256
        ),
        exact_context_components=(
            exact_context_components
        ),
        supported_materializations=(),
        unsupported_materializations=(),
    )


def _audio_materialized_value(
    audio: dict[str, object],
    requirement: str,
) -> object:
    if requirement == "audio.codec_name":
        codec = audio.get("codec")

        if not isinstance(codec, dict):
            raise HveeContractError(
                "materialized audio codec must be canonical"
            )

        return codec.get("name")

    if requirement == "audio.codec_profile":
        codec = audio.get("codec")

        if not isinstance(codec, dict):
            raise HveeContractError(
                "materialized audio codec must be canonical"
            )

        return codec.get("profile")

    processing_fields = {
        "audio.automatic_gain_control": (
            "automatic_gain_control"
        ),
        "audio.noise_suppression": (
            "noise_suppression"
        ),
        "audio.echo_cancellation": (
            "echo_cancellation"
        ),
    }

    if requirement in processing_fields:
        processing = audio.get(
            "capture_processing"
        )

        if not isinstance(processing, dict):
            raise HveeContractError(
                "materialized capture processing "
                "must be canonical"
            )

        return processing.get(
            processing_fields[requirement]
        )

    field = requirement.removeprefix(
        "audio."
    )

    if not field or field == requirement:
        raise HveeContractError(
            "materialized audio requirement is invalid"
        )

    return audio.get(field)


def _transport_materialized_value(
    transport: dict[str, object],
    requirement: str,
) -> object:
    field = requirement.removeprefix(
        "transport."
    )

    if not field or field == requirement:
        raise HveeContractError(
            "materialized transport requirement is invalid"
        )

    return transport.get(field)


def _materialized_context_commitment(
    *,
    materialized_context: IncidentRunnerMaterializedContext,
    requirement: str,
) -> str:
    if requirement.startswith(
        "audio."
    ):
        audio = materialized_context.audio

        if audio is None:
            raise HveeContractError(
                "runner did not materialize audio context"
            )

        value = _audio_materialized_value(
            audio,
            requirement,
        )

    elif requirement.startswith(
        "transport."
    ):
        transport = (
            materialized_context.transport
        )

        if transport is None:
            raise HveeContractError(
                "runner did not materialize transport context"
            )

        value = _transport_materialized_value(
            transport,
            requirement,
        )

    else:
        raise HveeContractError(
            "context materialization requirement is invalid"
        )

    return (
        calculate_incident_materialized_value_commitment(
            value
        )
    )


def build_incident_materialization_observations(
    *,
    compatibility: IncidentRunnerCompatibilityBundle,
    compatibility_observation: (
        IncidentRunnerEnvironmentObservation
    ),
    materialized_context: (
        IncidentRunnerMaterializedContext | None
    ),
) -> tuple[
    IncidentMaterializedRequirementObservation,
    ...
]:
    summary = compatibility.payload.get(
        "compatibility"
    )

    if not isinstance(summary, dict):
        raise HveeContractError(
            "incident compatibility summary "
            "must be canonical"
        )

    requirements = summary.get(
        "requirements"
    )

    if not isinstance(
        requirements,
        list,
    ):
        raise HveeContractError(
            "incident compatibility requirements "
            "must be canonical"
        )

    exact_components = set(
        compatibility_observation
        .exact_context_components
    )

    observations: list[
        IncidentMaterializedRequirementObservation
    ] = []

    for value in requirements:
        if not isinstance(value, dict):
            raise HveeContractError(
                "incident compatibility requirement "
                "is invalid"
            )

        requirement = value.get(
            "requirement"
        )
        expected = value.get(
            "expected_commitment_sha256"
        )

        if expected is None:
            continue

        if not isinstance(
            requirement,
            str,
        ):
            raise HveeContractError(
                "incident compatibility requirement "
                "is invalid"
            )

        observed: str | None = None

        if requirement.startswith(
            "runtime."
        ):
            candidate = value.get(
                "observed_commitment_sha256"
            )

            if candidate is not None:
                if not isinstance(
                    candidate,
                    str,
                ):
                    raise HveeContractError(
                        "runtime observation commitment "
                        "is invalid"
                    )

                observed = candidate

        elif (
            requirement.startswith(
                "audio."
            )
            and "audio" in exact_components
            and materialized_context is not None
        ):
            observed = (
                _materialized_context_commitment(
                    materialized_context=(
                        materialized_context
                    ),
                    requirement=requirement,
                )
            )

        elif (
            requirement.startswith(
                "transport."
            )
            and "transport" in exact_components
            and materialized_context is not None
        ):
            observed = (
                _materialized_context_commitment(
                    materialized_context=(
                        materialized_context
                    ),
                    requirement=requirement,
                )
            )

        observations.append(
            IncidentMaterializedRequirementObservation(
                requirement=requirement,
                observed_commitment_sha256=(
                    observed
                ),
            )
        )

    return tuple(
        sorted(
            observations,
            key=lambda item: (
                item.requirement
            ),
        )
    )


def _operator_authorization(
    settings: LocalRunnerSettings,
) -> IncidentOperatorAuthorization:
    commitment = (
        settings
        .incident_materialization_authorization_sha256
    )

    return IncidentOperatorAuthorization(
        granted=commitment is not None,
        authorization_sha256=(
            commitment
        ),
    )


def materialize_incident_environment_request(
    *,
    request_payload: object,
    settings: LocalRunnerSettings,
    materialized_context: (
        IncidentRunnerMaterializedContext | None
    ) = None,
) -> IncidentRunnerMaterializationResult:
    """
    Evaluate one runner-local Incident Mode materialization.

    The request supplies targets only. Observed audio/transport values come
    only from materialized_context.
    """

    request = (
        parse_incident_replay_compatibility_request(
            request_payload
        )
    )

    compatibility_observation = (
        build_incident_materialization_compatibility_observation(
            settings,
            materialized_context=(
                materialized_context
            ),
        )
    )

    compatibility = (
        evaluate_incident_replay_compatibility_request(
            request_payload=request.payload,
            required_capabilities=(
                INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
            ),
            observation=(
                compatibility_observation
            ),
        )
    )

    materialization_observations = (
        build_incident_materialization_observations(
            compatibility=compatibility,
            compatibility_observation=(
                compatibility_observation
            ),
            materialized_context=(
                materialized_context
            ),
        )
    )

    materialization = (
        build_incident_environment_materialization_bundle(
            intake_payload=(
                request.intake_payload
            ),
            expected_intake_sha256=(
                request.intake_sha256
            ),
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
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            authorization=(
                _operator_authorization(
                    settings
                )
            ),
            materialization_observations=(
                materialization_observations
            ),
        )
    )

    return IncidentRunnerMaterializationResult(
        compatibility=compatibility,
        materialization=materialization,
    )



INCIDENT_ENVIRONMENT_MATERIALIZATION_RESULT_SCHEMA_VERSION = 1


class IncidentEnvironmentMaterializationRunnerExecutionError(
    Exception
):
    """Safe customer-runner materialization failure."""


class IncidentMaterializedContextProvider(Protocol):
    def __call__(
        self,
        job: RunnerJobRead,
        control,
    ) -> IncidentRunnerMaterializedContext | None:
        ...


class IncidentEnvironmentMaterializationRunnerJobExecutor:
    """Run bounded Incident Mode environment materialization."""

    supported_job_type = (
        INCIDENT_ENVIRONMENT_MATERIALIZATION_JOB_TYPE
    )

    def __init__(
        self,
        *,
        settings: LocalRunnerSettings,
        materialized_context_provider: (
            IncidentMaterializedContextProvider | None
        ) = None,
    ) -> None:
        self._settings = settings
        self._materialized_context_provider = (
            materialized_context_provider
        )

    def execute(
        self,
        job: RunnerJobRead,
        control,
    ) -> dict[str, object]:
        control.raise_if_stopped()

        if job.job_type != self.supported_job_type:
            raise (
                IncidentEnvironmentMaterializationRunnerExecutionError(
                    "Incident materialization runner job type is invalid."
                )
            )

        expected_capabilities = tuple(
            sorted(
                INCIDENT_ENVIRONMENT_MATERIALIZATION_REQUIRED_CAPABILITIES
            )
        )

        observed_job_capabilities = tuple(
            sorted(
                {
                    value.strip().lower()
                    for value in job.required_capabilities
                }
            )
        )

        if observed_job_capabilities != expected_capabilities:
            raise (
                IncidentEnvironmentMaterializationRunnerExecutionError(
                    "Incident materialization runner capability "
                    "contract is invalid."
                )
            )

        control.raise_if_stopped()

        materialized_context = None

        if self._materialized_context_provider is not None:
            materialized_context = (
                self._materialized_context_provider(
                    job,
                    control,
                )
            )

            if (
                materialized_context is not None
                and not isinstance(
                    materialized_context,
                    IncidentRunnerMaterializedContext,
                )
            ):
                raise (
                    IncidentEnvironmentMaterializationRunnerExecutionError(
                        "Incident materialized context provider "
                        "returned an invalid result."
                    )
                )

        control.raise_if_stopped()

        result = materialize_incident_environment_request(
            request_payload=job.input_payload,
            settings=self._settings,
            materialized_context=materialized_context,
        )

        control.raise_if_stopped()

        return {
            "schema_version": (
                INCIDENT_ENVIRONMENT_MATERIALIZATION_RESULT_SCHEMA_VERSION
            ),
            "type": "incident_environment_materialization_result",
            "compatibility": {
                "payload": result.compatibility.payload,
                "sha256": result.compatibility.sha256,
            },
            "materialization": {
                "payload": result.materialization.payload,
                "sha256": result.materialization.sha256,
            },
        }

__all__ = [
    "IncidentMaterializedContextProvider",
    "IncidentEnvironmentMaterializationRunnerJobExecutor",
    "IncidentEnvironmentMaterializationRunnerExecutionError",
    "INCIDENT_ENVIRONMENT_MATERIALIZATION_RESULT_SCHEMA_VERSION",
    "IncidentRunnerMaterializationResult",
    "IncidentRunnerMaterializedContext",
    "build_incident_materialization_compatibility_observation",
    "build_incident_materialization_observations",
    "materialize_incident_environment_request",
]
