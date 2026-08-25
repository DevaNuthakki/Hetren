"""Customer-controlled Incident Mode compatibility execution.

This executor performs only the Runner Integration stage.

It validates the fixed Incident Mode runner-job contract, constructs an
honest runner-local observation, re-verifies the upstream Incident Mode
request through the compatibility service, and returns compatibility
evidence through the generic runner-result path.

It deliberately does not:
- materialize the incident environment,
- load or invoke the ASR provider,
- download or execute incident audio,
- execute replay,
- claim reproduction,
- verify model failure,
- promote a contract,
- grant qualification or release authority.

At this stage LocalRunnerSettings establish the runner's declared
capabilities only. They do not prove production deployment identity,
provider/model versions, artifact hashes, source/configuration identity,
runtime-environment identity, or exact audio/transport reconstruction.
Those values therefore remain unobserved until later bounded stages
produce runner-local evidence for them.
"""

from __future__ import annotations

from typing import Protocol

from app.incident_runner_compatibility_service import (
    INCIDENT_REPLAY_COMPATIBILITY_JOB_TYPE,
    INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES,
    evaluate_incident_replay_compatibility_request,
)
from app.runner_config import LocalRunnerSettings
from app.runner_schemas import RunnerJobRead
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
)


INCIDENT_REPLAY_COMPATIBILITY_RESULT_SCHEMA_VERSION = 1


class IncidentCompatibilityRunnerExecutionError(Exception):
    """Safe Incident Mode runner-integration failure."""


class ExecutionControlProtocol(Protocol):
    def raise_if_stopped(self) -> None:
        ...


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


class IncidentCompatibilityRunnerJobExecutor:
    """Evaluate Incident Mode compatibility inside the customer runner."""

    supported_job_type = (
        INCIDENT_REPLAY_COMPATIBILITY_JOB_TYPE
    )

    def __init__(
        self,
        *,
        settings: LocalRunnerSettings,
    ) -> None:
        self._settings = settings

    def _observation(
        self,
    ) -> IncidentRunnerEnvironmentObservation:
        """
        Build the observation that this integration stage can prove.

        Capability declaration is known from runner registration/settings.
        All stronger runtime/materialization observations remain absent.
        """

        return IncidentRunnerEnvironmentObservation(
            capabilities=_canonical_capabilities(
                self._settings.capabilities
            ),
            deployment_key=None,
            deployment_version=None,
            provider_key=None,
            provider_version=None,
            model_key=None,
            model_version=None,
            model_artifact_sha256=None,
            source_code_sha256=None,
            configuration_sha256=None,
            runtime_environment_sha256=None,
            host_environment_sha256=None,
            exact_context_components=(),
            supported_materializations=(),
            unsupported_materializations=(),
        )

    def execute(
        self,
        job: RunnerJobRead,
        control: ExecutionControlProtocol,
    ) -> dict[str, object]:
        control.raise_if_stopped()

        if job.job_type != self.supported_job_type:
            raise IncidentCompatibilityRunnerExecutionError(
                "Incident compatibility runner job type is invalid."
            )

        expected_capabilities = tuple(
            sorted(
                INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
            )
        )
        job_capabilities = _canonical_capabilities(
            job.required_capabilities
        )

        if job_capabilities != expected_capabilities:
            raise IncidentCompatibilityRunnerExecutionError(
                "Incident compatibility runner capability "
                "contract is invalid."
            )

        observation = self._observation()

        control.raise_if_stopped()

        compatibility = (
            evaluate_incident_replay_compatibility_request(
                request_payload=job.input_payload,
                required_capabilities=(
                    INCIDENT_REPLAY_COMPATIBILITY_REQUIRED_CAPABILITIES
                ),
                observation=observation,
            )
        )

        control.raise_if_stopped()

        return {
            "schema_version": (
                INCIDENT_REPLAY_COMPATIBILITY_RESULT_SCHEMA_VERSION
            ),
            "type": "incident_replay_compatibility_result",
            "compatibility": {
                "payload": compatibility.payload,
                "sha256": compatibility.sha256,
            },
        }


__all__ = [
    "INCIDENT_REPLAY_COMPATIBILITY_RESULT_SCHEMA_VERSION",
    "IncidentCompatibilityRunnerExecutionError",
    "IncidentCompatibilityRunnerJobExecutor",
]
