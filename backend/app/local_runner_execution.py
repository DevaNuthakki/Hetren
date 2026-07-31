from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Literal, Protocol

from app.local_runner_client import (
    LocalRunnerClient,
    LocalRunnerClientError,
)
from app.runner_config import LocalRunnerSettings
from app.runner_schemas import RunnerJobRead


GENERIC_EXECUTION_ERROR = (
    "Local runner execution failed."
)


class LocalRunnerExecutionError(Exception):
    """Base exception for local runner execution."""


class UnsupportedRunnerJobError(
    LocalRunnerExecutionError
):
    """Raised when no local executor supports a job type."""


class RunnerJobExecutor(Protocol):
    def execute(
        self,
        job: RunnerJobRead,
    ) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class LocalRunnerCycleResult:
    status: Literal[
        "idle",
        "completed",
        "failed",
    ]
    job_public_id: str | None = None
    result_payload: dict[str, object] | None = None
    error_message: str | None = None


class PlaceholderRunnerJobExecutor:
    """
    Controlled Phase 3 placeholder executor.

    It validates the allowlisted job type but does not execute shell
    commands, access arbitrary paths, or invoke the real ASR pipeline.
    """

    supported_job_types = frozenset(
        {
            "asr_evaluation",
        }
    )

    def execute(
        self,
        job: RunnerJobRead,
    ) -> dict[str, object]:
        if job.job_type not in self.supported_job_types:
            raise UnsupportedRunnerJobError(
                "Runner job type is not supported."
            )

        return {
            "execution_mode": "placeholder",
            "job_type": job.job_type,
            "accepted_input_keys": sorted(
                job.input_payload.keys()
            ),
        }


def collect_runner_system_info() -> dict[str, object]:
    """
    Return non-sensitive runner environment information.

    Hostnames, environment variables, credentials, file paths, and
    network addresses are intentionally excluded.
    """

    return {
        "platform": platform.system().lower(),
        "machine": platform.machine().lower(),
        "python_version": platform.python_version(),
    }


def run_one_local_runner_cycle(
    *,
    client: LocalRunnerClient,
    settings: LocalRunnerSettings,
    executor: RunnerJobExecutor | None = None,
    system_info: dict[str, object] | None = None,
) -> LocalRunnerCycleResult:
    """
    Heartbeat, claim, and execute at most one runner job.

    API or protocol failures are allowed to propagate because the runner
    may not safely know the remote job state after such failures.
    Executor failures are reported through the controlled fail endpoint.
    """

    selected_executor = (
        executor or PlaceholderRunnerJobExecutor()
    )

    client.heartbeat(
        runner_version=settings.runner_version,
        capabilities=settings.capabilities,
        system_info=(
            dict(system_info)
            if system_info is not None
            else collect_runner_system_info()
        ),
    )

    claimed = client.claim_next_job(
        lease_seconds=settings.lease_seconds,
    )

    if claimed.status == "idle":
        return LocalRunnerCycleResult(
            status="idle",
        )

    if (
        claimed.job is None
        or claimed.claim_token is None
    ):
        raise LocalRunnerExecutionError(
            "Runner claim response was incomplete."
        )

    job = claimed.job
    claim_token = claimed.claim_token

    client.start_job(
        job_public_id=job.public_id,
        claim_token=claim_token,
    )

    client.append_job_logs(
        job_public_id=job.public_id,
        claim_token=claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "execution_started",
                "message": (
                    "Local runner execution started."
                ),
                "context_payload": {
                    "job_type": job.job_type,
                    "executor": (
                        selected_executor.__class__.__name__
                    ),
                },
            }
        ],
    )

    try:
        result_payload = selected_executor.execute(
            job
        )
    except Exception as exc:
        failure_context = {
            "job_type": job.job_type,
            "error_type": exc.__class__.__name__,
        }

        try:
            client.append_job_logs(
                job_public_id=job.public_id,
                claim_token=claim_token,
                entries=[
                    {
                        "level": "error",
                        "event_type": (
                            "execution_failed"
                        ),
                        "message": (
                            GENERIC_EXECUTION_ERROR
                        ),
                        "context_payload": (
                            failure_context
                        ),
                    }
                ],
            )
        except LocalRunnerClientError:
            # Failure reporting must still be attempted even when the
            # optional structured-log upload is unavailable.
            pass

        client.fail_job(
            job_public_id=job.public_id,
            claim_token=claim_token,
            error_message=GENERIC_EXECUTION_ERROR,
        )

        return LocalRunnerCycleResult(
            status="failed",
            job_public_id=job.public_id,
            error_message=GENERIC_EXECUTION_ERROR,
        )

    client.append_job_logs(
        job_public_id=job.public_id,
        claim_token=claim_token,
        entries=[
            {
                "level": "info",
                "event_type": "execution_completed",
                "message": (
                    "Local runner execution completed."
                ),
                "context_payload": {
                    "job_type": job.job_type,
                    "executor": (
                        selected_executor.__class__.__name__
                    ),
                },
            }
        ],
    )

    client.complete_job(
        job_public_id=job.public_id,
        claim_token=claim_token,
        result_payload=result_payload,
    )

    return LocalRunnerCycleResult(
        status="completed",
        job_public_id=job.public_id,
        result_payload=dict(result_payload),
    )
