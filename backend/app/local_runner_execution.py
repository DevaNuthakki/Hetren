from __future__ import annotations

import platform
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, Lock, Thread
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


class LeaseRenewalWorkerProtocol(Protocol):
    @property
    def failure(self) -> Exception | None:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...


class LeaseRenewalWorkerFactory(Protocol):
    def __call__(
        self,
        *,
        client: LocalRunnerClient,
        job_public_id: str,
        claim_token: str,
        lease_seconds: int,
        interval_seconds: float,
    ) -> LeaseRenewalWorkerProtocol:
        ...


class RunnerStopEvent(Protocol):
    def is_set(self) -> bool:
        ...

    def wait(
        self,
        timeout: float | None = None,
    ) -> bool:
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


@dataclass(frozen=True)
class LocalRunnerLoopSummary:
    cycle_count: int
    idle_count: int
    completed_count: int
    failed_count: int
    stopped: bool


LocalRunnerCycleRunner = Callable[
    ...,
    LocalRunnerCycleResult,
]


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


class LeaseRenewalWorker:
    """
    Renew an active job lease while its executor is running.

    Renewal failures are retained for the coordinating thread. The
    worker never performs completion or failure transitions itself.
    """

    def __init__(
        self,
        *,
        client: LocalRunnerClient,
        job_public_id: str,
        claim_token: str,
        lease_seconds: int,
        interval_seconds: float,
    ):
        if lease_seconds <= 0:
            raise ValueError(
                "Runner job lease duration must be positive."
            )

        if interval_seconds <= 0:
            raise ValueError(
                "Lease-renewal interval must be positive."
            )

        if interval_seconds >= lease_seconds:
            raise ValueError(
                "Lease-renewal interval must be shorter "
                "than the job lease duration."
            )

        self._client = client
        self._job_public_id = job_public_id
        self._claim_token = claim_token
        self._lease_seconds = lease_seconds
        self._interval_seconds = interval_seconds

        self._stop_event = Event()
        self._failure_lock = Lock()
        self._failure: Exception | None = None
        self._thread: Thread | None = None

    @property
    def failure(self) -> Exception | None:
        with self._failure_lock:
            return self._failure

    def start(self) -> None:
        if self._thread is not None:
            raise LocalRunnerExecutionError(
                "Lease-renewal worker has already started."
            )

        thread = Thread(
            target=self._run,
            name="ovrin-runner-lease-renewal",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join()

    def _run(self) -> None:
        while not self._stop_event.wait(
            self._interval_seconds
        ):
            try:
                self._client.renew_job_lease(
                    job_public_id=self._job_public_id,
                    claim_token=self._claim_token,
                    lease_seconds=self._lease_seconds,
                )
            except Exception as exc:
                with self._failure_lock:
                    self._failure = exc

                self._stop_event.set()
                return


def build_lease_renewal_worker(
    *,
    client: LocalRunnerClient,
    job_public_id: str,
    claim_token: str,
    lease_seconds: int,
    interval_seconds: float,
) -> LeaseRenewalWorker:
    return LeaseRenewalWorker(
        client=client,
        job_public_id=job_public_id,
        claim_token=claim_token,
        lease_seconds=lease_seconds,
        interval_seconds=interval_seconds,
    )


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
    renewal_worker_factory: LeaseRenewalWorkerFactory = (
        build_lease_renewal_worker
    ),
) -> LocalRunnerCycleResult:
    """
    Heartbeat, claim, and execute at most one runner job.

    The active claim is renewed in the background while execution is
    running. A renewal failure prevents successful job completion.

    API or protocol failures are allowed to propagate because the runner
    may not safely know the remote job state after such failures.
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

    renewal_worker = renewal_worker_factory(
        client=client,
        job_public_id=job.public_id,
        claim_token=claim_token,
        lease_seconds=settings.lease_seconds,
        interval_seconds=(
            settings.lease_renewal_interval_seconds
        ),
    )

    execution_error: Exception | None = None
    result_payload: dict[str, object] | None = None

    renewal_worker.start()

    try:
        result_payload = selected_executor.execute(
            job
        )

        if not isinstance(result_payload, dict):
            raise LocalRunnerExecutionError(
                "Runner executor returned an invalid result."
            )
    except Exception as exc:
        execution_error = exc
    finally:
        renewal_worker.stop()

    renewal_error = renewal_worker.failure

    if (
        execution_error is not None
        or renewal_error is not None
    ):
        failure = execution_error or renewal_error

        event_type = (
            "execution_failed"
            if execution_error is not None
            else "lease_renewal_failed"
        )

        failure_context = {
            "job_type": job.job_type,
            "error_type": failure.__class__.__name__,
            "lease_renewal_failed": (
                renewal_error is not None
            ),
        }

        try:
            client.append_job_logs(
                job_public_id=job.public_id,
                claim_token=claim_token,
                entries=[
                    {
                        "level": "error",
                        "event_type": event_type,
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
            # The terminal failure transition is still attempted when
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

    if result_payload is None:
        raise LocalRunnerExecutionError(
            "Runner execution result was unavailable."
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


def run_local_runner_loop(
    *,
    client: LocalRunnerClient,
    settings: LocalRunnerSettings,
    executor: RunnerJobExecutor | None = None,
    system_info: dict[str, object] | None = None,
    stop_event: RunnerStopEvent | None = None,
    max_cycles: int | None = None,
    renewal_worker_factory: LeaseRenewalWorkerFactory = (
        build_lease_renewal_worker
    ),
    cycle_runner: LocalRunnerCycleRunner = (
        run_one_local_runner_cycle
    ),
) -> LocalRunnerLoopSummary:
    """
    Continuously poll for and execute runner jobs.

    The polling interval is applied only after an idle queue response.
    Successful or failed jobs are followed immediately by another
    heartbeat and claim attempt.

    The stop event is cooperative. It stops the runner between cycles
    or during idle waiting, but it does not interrupt an active
    executor. Active interruption and cancellation are separate work.
    """

    if max_cycles is not None:
        if (
            isinstance(max_cycles, bool)
            or max_cycles <= 0
        ):
            raise ValueError(
                "Maximum runner cycles must be a "
                "positive integer."
            )

    selected_stop_event = stop_event or Event()

    resolved_system_info = (
        dict(system_info)
        if system_info is not None
        else collect_runner_system_info()
    )

    cycle_count = 0
    idle_count = 0
    completed_count = 0
    failed_count = 0

    while not selected_stop_event.is_set():
        cycle_result = cycle_runner(
            client=client,
            settings=settings,
            executor=executor,
            system_info=resolved_system_info,
            renewal_worker_factory=(
                renewal_worker_factory
            ),
        )

        cycle_count += 1

        if cycle_result.status == "idle":
            idle_count += 1
        elif cycle_result.status == "completed":
            completed_count += 1
        elif cycle_result.status == "failed":
            failed_count += 1
        else:
            raise LocalRunnerExecutionError(
                "Local runner cycle returned an "
                "unsupported status."
            )

        if (
            max_cycles is not None
            and cycle_count >= max_cycles
        ):
            break

        if cycle_result.status == "idle":
            should_stop = selected_stop_event.wait(
                settings.poll_interval_seconds
            )

            if should_stop:
                break

    return LocalRunnerLoopSummary(
        cycle_count=cycle_count,
        idle_count=idle_count,
        completed_count=completed_count,
        failed_count=failed_count,
        stopped=selected_stop_event.is_set(),
    )
