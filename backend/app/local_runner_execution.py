from __future__ import annotations

import platform
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
from time import monotonic
from typing import Literal, Protocol

from app.incident_runner_compatibility_execution import (
    IncidentCompatibilityRunnerJobExecutor,
)
from app.local_runner_client import (
    LocalRunnerClient,
    LocalRunnerClientError,
)
from app.runner_config import LocalRunnerSettings
from app.runner_schemas import RunnerJobRead
from app.speech import ASRProvider, get_asr_provider


GENERIC_EXECUTION_ERROR = (
    "Local runner execution failed."
)
GENERIC_EXECUTION_TIMEOUT_ERROR = (
    "Local runner execution timed out."
)


class LocalRunnerExecutionError(Exception):
    """Base exception for local runner execution."""


class UnsupportedRunnerJobError(
    LocalRunnerExecutionError
):
    """Raised when no local executor supports a job type."""


class RunnerJobCancelledError(
    LocalRunnerExecutionError
):
    """Raised when remote cancellation stops execution."""


class RunnerJobTimedOutError(
    LocalRunnerExecutionError
):
    """Raised when the configured deadline is reached."""


class RunnerShutdownRequestedError(
    LocalRunnerExecutionError
):
    """Raised when process shutdown stops active execution."""


ExecutionStopReason = Literal[
    "cancelled",
    "timed_out",
    "shutdown",
    "control_failed",
    "lease_renewal_failed",
]


class ExecutionControl:
    """
    Thread-safe cooperative stop signal for an active executor.

    Executors must call raise_if_stopped(), is_set(), or wait() at
    safe checkpoints. Python threads are never forcibly terminated.
    """

    def __init__(self):
        self._stop_event = Event()
        self._reason_lock = Lock()
        self._reason: ExecutionStopReason | None = None

    @property
    def reason(self) -> ExecutionStopReason | None:
        with self._reason_lock:
            return self._reason

    def request_stop(
        self,
        reason: ExecutionStopReason,
    ) -> bool:
        with self._reason_lock:
            if self._reason is not None:
                return False

            self._reason = reason
            self._stop_event.set()
            return True

    def is_set(self) -> bool:
        return self._stop_event.is_set()

    def wait(
        self,
        timeout: float | None = None,
    ) -> bool:
        return self._stop_event.wait(timeout)

    def raise_if_stopped(self) -> None:
        reason = self.reason

        if reason is None:
            return

        if reason == "cancelled":
            raise RunnerJobCancelledError(
                "Runner job was cancelled."
            )

        if reason == "timed_out":
            raise RunnerJobTimedOutError(
                "Runner job execution timed out."
            )

        if reason == "shutdown":
            raise RunnerShutdownRequestedError(
                "Runner shutdown was requested."
            )

        raise LocalRunnerExecutionError(
            "Runner execution control became unavailable."
        )


@dataclass(frozen=True)
class ASRRunnerExecutionResult:
    generated_transcript: str
    provider: str
    provider_metadata: dict[str, object]


RunnerExecutionResult = (
    dict[str, object]
    | ASRRunnerExecutionResult
)


class RunnerJobExecutor(Protocol):
    def execute(
        self,
        job: RunnerJobRead,
        control: ExecutionControl,
    ) -> RunnerExecutionResult:
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
        execution_control: ExecutionControl,
    ) -> LeaseRenewalWorkerProtocol:
        ...


class JobControlWorkerProtocol(Protocol):
    @property
    def failure(self) -> Exception | None:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...


class JobControlWorkerFactory(Protocol):
    def __call__(
        self,
        *,
        client: LocalRunnerClient,
        job_public_id: str,
        execution_control: ExecutionControl,
        poll_interval_seconds: float,
        execution_timeout_seconds: float,
        runner_stop_event: RunnerStopEvent | None,
    ) -> JobControlWorkerProtocol:
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
        "cancelled",
        "stopped",
    ]
    job_public_id: str | None = None
    result_payload: dict[str, object] | None = None
    error_message: str | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class LocalRunnerLoopSummary:
    cycle_count: int
    idle_count: int
    completed_count: int
    failed_count: int
    stopped: bool
    cancelled_count: int = 0
    timed_out_count: int = 0


LocalRunnerCycleRunner = Callable[
    ...,
    LocalRunnerCycleResult,
]


class ASRRunnerJobExecutor:
    """
    Execute one claimed ASR evaluation in an isolated workspace.

    The executor receives only the safe evaluation context and audio
    stream exposed by the runner API. Backend paths and reference
    transcripts are never available to the local runner.
    """

    supported_job_types = frozenset(
        {
            "asr_evaluation",
        }
    )
    supported_audio_suffixes = frozenset(
        {
            ".wav",
            ".mp3",
            ".m4a",
        }
    )

    def __init__(
        self,
        *,
        client: LocalRunnerClient,
        claim_token: str,
        provider: ASRProvider,
    ):
        normalized_claim_token = claim_token.strip()

        if not normalized_claim_token:
            raise ValueError(
                "Runner claim token must not be empty."
            )

        self._client = client
        self._claim_token = normalized_claim_token
        self._provider = provider

    def execute(
        self,
        job: RunnerJobRead,
        control: ExecutionControl,
    ) -> ASRRunnerExecutionResult:
        control.raise_if_stopped()

        if job.job_type not in self.supported_job_types:
            raise UnsupportedRunnerJobError(
                "Runner job type is not supported."
            )

        context = (
            self._client.get_asr_evaluation_context(
                job_public_id=job.public_id,
                claim_token=self._claim_token,
            )
        )

        control.raise_if_stopped()

        audio_suffix = Path(
            context.audio_file_name
        ).suffix.lower()

        if (
            audio_suffix
            not in self.supported_audio_suffixes
        ):
            raise LocalRunnerExecutionError(
                "Runner ASR audio format is unsupported."
            )

        with TemporaryDirectory(
            prefix="hetren-runner-asr-",
        ) as workspace:
            audio_destination = (
                Path(workspace)
                / f"input{audio_suffix}"
            )

            audio_path = (
                self._client
                .download_asr_evaluation_audio(
                    job_public_id=job.public_id,
                    claim_token=self._claim_token,
                    destination=audio_destination,
                )
            )

            if Path(audio_path) != audio_destination:
                raise LocalRunnerExecutionError(
                    "Runner ASR audio destination "
                    "was invalid."
                )

            control.raise_if_stopped()

            transcription = self._provider.transcribe(
                audio_path,
                model_name=context.model_name,
            )

            control.raise_if_stopped()

        generated_transcript = (
            transcription.transcript.strip()
        )
        provider_name = transcription.provider.strip()
        model_name = transcription.model_name.strip()

        if not generated_transcript:
            raise LocalRunnerExecutionError(
                "ASR provider returned an empty transcript."
            )

        if not provider_name:
            raise LocalRunnerExecutionError(
                "ASR provider name was unavailable."
            )

        if not model_name:
            raise LocalRunnerExecutionError(
                "ASR model name was unavailable."
            )

        return ASRRunnerExecutionResult(
            generated_transcript=generated_transcript,
            provider=provider_name,
            provider_metadata={
                "model_name": model_name,
                "execution_config": {
                    "provider": provider_name,
                    "model_name": model_name,
                    "device": transcription.device,
                    "compute_type": (
                        transcription.compute_type
                    ),
                },
            },
        )


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
        control: ExecutionControl,
    ) -> dict[str, object]:
        control.raise_if_stopped()

        if job.job_type not in self.supported_job_types:
            raise UnsupportedRunnerJobError(
                "Runner job type is not supported."
            )

        result = {
            "execution_mode": "placeholder",
            "job_type": job.job_type,
            "accepted_input_keys": sorted(
                job.input_payload.keys()
            ),
        }

        control.raise_if_stopped()
        return result


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
        execution_control: ExecutionControl,
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
        self._execution_control = execution_control

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
            name="hetren-runner-lease-renewal",
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

                self._execution_control.request_stop(
                    "lease_renewal_failed"
                )
                self._stop_event.set()
                return


def build_lease_renewal_worker(
    *,
    client: LocalRunnerClient,
    job_public_id: str,
    claim_token: str,
    lease_seconds: int,
    interval_seconds: float,
    execution_control: ExecutionControl,
) -> LeaseRenewalWorker:
    return LeaseRenewalWorker(
        client=client,
        job_public_id=job_public_id,
        claim_token=claim_token,
        lease_seconds=lease_seconds,
        interval_seconds=interval_seconds,
        execution_control=execution_control,
    )


class JobControlWorker:
    """
    Poll assigned-runner control state and enforce a local deadline.

    Remote cancellation, timeout, process shutdown, or control API
    failure sets the shared cooperative execution signal.
    """

    def __init__(
        self,
        *,
        client: LocalRunnerClient,
        job_public_id: str,
        execution_control: ExecutionControl,
        poll_interval_seconds: float,
        execution_timeout_seconds: float,
        runner_stop_event: RunnerStopEvent | None = None,
    ):
        if poll_interval_seconds <= 0:
            raise ValueError(
                "Control polling interval must be positive."
            )

        if execution_timeout_seconds <= 0:
            raise ValueError(
                "Execution timeout must be positive."
            )

        self._client = client
        self._job_public_id = job_public_id
        self._execution_control = execution_control
        self._poll_interval_seconds = (
            poll_interval_seconds
        )
        self._execution_timeout_seconds = (
            execution_timeout_seconds
        )
        self._runner_stop_event = runner_stop_event

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
                "Job-control worker has already started."
            )

        thread = Thread(
            target=self._run,
            name="hetren-runner-job-control",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join()

    def _run(self) -> None:
        deadline = (
            monotonic()
            + self._execution_timeout_seconds
        )

        while not self._stop_event.is_set():
            if (
                self._runner_stop_event is not None
                and self._runner_stop_event.is_set()
            ):
                self._execution_control.request_stop(
                    "shutdown"
                )
                return

            remaining_seconds = deadline - monotonic()

            if remaining_seconds <= 0:
                self._execution_control.request_stop(
                    "timed_out"
                )
                return

            wait_seconds = min(
                self._poll_interval_seconds,
                remaining_seconds,
            )

            if self._stop_event.wait(wait_seconds):
                return

            if (
                self._runner_stop_event is not None
                and self._runner_stop_event.is_set()
            ):
                self._execution_control.request_stop(
                    "shutdown"
                )
                return

            if monotonic() >= deadline:
                self._execution_control.request_stop(
                    "timed_out"
                )
                return

            try:
                response = (
                    self._client.get_job_control_status(
                        job_public_id=self._job_public_id,
                    )
                )
            except Exception as exc:
                with self._failure_lock:
                    self._failure = exc

                self._execution_control.request_stop(
                    "control_failed"
                )
                return

            if response.status == "cancelled":
                self._execution_control.request_stop(
                    "cancelled"
                )
                return


def build_job_control_worker(
    *,
    client: LocalRunnerClient,
    job_public_id: str,
    execution_control: ExecutionControl,
    poll_interval_seconds: float,
    execution_timeout_seconds: float,
    runner_stop_event: RunnerStopEvent | None,
) -> JobControlWorker:
    return JobControlWorker(
        client=client,
        job_public_id=job_public_id,
        execution_control=execution_control,
        poll_interval_seconds=poll_interval_seconds,
        execution_timeout_seconds=(
            execution_timeout_seconds
        ),
        runner_stop_event=runner_stop_event,
    )


def build_default_runner_job_executor(
    *,
    client: LocalRunnerClient,
    settings: LocalRunnerSettings,
    job: RunnerJobRead,
    claim_token: str,
) -> RunnerJobExecutor:
    """
    Build the allowlisted executor for one claimed runner job.

    ASR providers are resolved only after a job is successfully
    claimed. Unsupported job types retain the controlled placeholder
    executor so the existing safe failure path remains active.
    """
    if (
        job.job_type
        == IncidentCompatibilityRunnerJobExecutor.supported_job_type
    ):
        return IncidentCompatibilityRunnerJobExecutor(
            settings=settings,
        )

    if job.job_type == "asr_evaluation":
        return ASRRunnerJobExecutor(
            client=client,
            claim_token=claim_token,
            provider=get_asr_provider(
                settings.asr_provider,
                model_name=settings.asr_model,
                device=settings.asr_device,
                compute_type=(
                    settings.asr_compute_type
                ),
            ),
        )

    return PlaceholderRunnerJobExecutor()


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
    stop_event: RunnerStopEvent | None = None,
    renewal_worker_factory: LeaseRenewalWorkerFactory = (
        build_lease_renewal_worker
    ),
    control_worker_factory: JobControlWorkerFactory = (
        build_job_control_worker
    ),
) -> LocalRunnerCycleResult:
    """
    Heartbeat, claim, and execute at most one runner job.

    Active execution is cooperative. A background worker observes
    administrative cancellation, process shutdown, and the configured
    execution deadline. The lease remains renewed while work runs.

    API or protocol failures propagate when remote state cannot be
    determined safely.
    """
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

    selected_executor = executor

    if selected_executor is None:
        selected_executor = (
            build_default_runner_job_executor(
                client=client,
                settings=settings,
                job=job,
                claim_token=claim_token,
            )
        )

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

    execution_control = ExecutionControl()

    renewal_worker = renewal_worker_factory(
        client=client,
        job_public_id=job.public_id,
        claim_token=claim_token,
        lease_seconds=settings.lease_seconds,
        interval_seconds=(
            settings.lease_renewal_interval_seconds
        ),
        execution_control=execution_control,
    )

    control_worker = control_worker_factory(
        client=client,
        job_public_id=job.public_id,
        execution_control=execution_control,
        poll_interval_seconds=(
            settings.control_poll_interval_seconds
        ),
        execution_timeout_seconds=(
            settings.execution_timeout_seconds
        ),
        runner_stop_event=stop_event,
    )

    execution_error: Exception | None = None
    execution_result: RunnerExecutionResult | None = None

    renewal_worker.start()
    control_worker.start()

    try:
        execution_result = selected_executor.execute(
            job,
            execution_control,
        )

        if not isinstance(
            execution_result,
            (
                dict,
                ASRRunnerExecutionResult,
            ),
        ):
            raise LocalRunnerExecutionError(
                "Runner executor returned an invalid result."
            )
    except Exception as exc:
        execution_error = exc
    finally:
        control_worker.stop()
        renewal_worker.stop()

    # Close the narrow race where process shutdown is requested while
    # the executor is returning, before the control worker observes it.
    if (
        stop_event is not None
        and stop_event.is_set()
    ):
        execution_control.request_stop(
            "shutdown"
        )

    control_reason = execution_control.reason
    control_error = control_worker.failure
    renewal_error = renewal_worker.failure

    if control_reason == "cancelled":
        return LocalRunnerCycleResult(
            status="cancelled",
            job_public_id=job.public_id,
        )

    if control_reason == "shutdown":
        return LocalRunnerCycleResult(
            status="stopped",
            job_public_id=job.public_id,
        )

    if (
        control_reason == "control_failed"
        or control_error is not None
    ):
        raise LocalRunnerExecutionError(
            "Runner job control monitoring failed."
        ) from control_error

    final_control = client.get_job_control_status(
        job_public_id=job.public_id,
    )

    if final_control.status == "cancelled":
        return LocalRunnerCycleResult(
            status="cancelled",
            job_public_id=job.public_id,
        )

    if control_reason == "timed_out":
        try:
            client.append_job_logs(
                job_public_id=job.public_id,
                claim_token=claim_token,
                entries=[
                    {
                        "level": "error",
                        "event_type": "execution_timed_out",
                        "message": (
                            GENERIC_EXECUTION_TIMEOUT_ERROR
                        ),
                        "context_payload": {
                            "job_type": job.job_type,
                            "timeout_seconds": (
                                settings.execution_timeout_seconds
                            ),
                        },
                    }
                ],
            )
        except LocalRunnerClientError:
            pass

        client.fail_job(
            job_public_id=job.public_id,
            claim_token=claim_token,
            error_message=(
                GENERIC_EXECUTION_TIMEOUT_ERROR
            ),
        )

        return LocalRunnerCycleResult(
            status="failed",
            job_public_id=job.public_id,
            error_message=(
                GENERIC_EXECUTION_TIMEOUT_ERROR
            ),
            timed_out=True,
        )

    if (
        execution_error is not None
        or renewal_error is not None
    ):
        # Renewal failure takes precedence because it can also cause a
        # cooperative executor to raise after receiving the stop signal.
        if renewal_error is not None:
            failure = renewal_error
            event_type = "lease_renewal_failed"
        else:
            assert execution_error is not None
            failure = execution_error
            event_type = "execution_failed"

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
                        "message": GENERIC_EXECUTION_ERROR,
                        "context_payload": failure_context,
                    }
                ],
            )
        except LocalRunnerClientError:
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

    if execution_result is None:
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

    if isinstance(
        execution_result,
        ASRRunnerExecutionResult,
    ):
        submission = (
            client.submit_asr_evaluation_result(
                job_public_id=job.public_id,
                claim_token=claim_token,
                generated_transcript=(
                    execution_result.generated_transcript
                ),
                provider=execution_result.provider,
                provider_metadata=(
                    execution_result.provider_metadata
                ),
            )
        )

        result_payload = {
            "evaluation_result_id": (
                submission.result.id
            ),
            "evaluation_run_id": (
                submission.result.run_id
            ),
            "test_case_id": (
                submission.result.test_case_id
            ),
            "provider": submission.provider,
            "provider_metadata": dict(
                submission.provider_metadata
            ),
            "wer": submission.result.wer,
            "cer": submission.result.cer,
            "quality_label": (
                submission.result.quality_label
            ),
        }
    else:
        result_payload = dict(execution_result)

        client.complete_job(
            job_public_id=job.public_id,
            claim_token=claim_token,
            result_payload=result_payload,
        )

    return LocalRunnerCycleResult(
        status="completed",
        job_public_id=job.public_id,
        result_payload=result_payload,
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
    control_worker_factory: JobControlWorkerFactory = (
        build_job_control_worker
    ),
    cycle_runner: LocalRunnerCycleRunner = (
        run_one_local_runner_cycle
    ),
) -> LocalRunnerLoopSummary:
    """
    Continuously poll for and execute runner jobs.

    The shared stop event now reaches active cooperative executors.
    Administrative cancellation is counted separately. Timed-out jobs
    remain failed jobs and are also counted as timed out.
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
    cancelled_count = 0
    timed_out_count = 0

    while not selected_stop_event.is_set():
        cycle_result = cycle_runner(
            client=client,
            settings=settings,
            executor=executor,
            system_info=resolved_system_info,
            stop_event=selected_stop_event,
            renewal_worker_factory=(
                renewal_worker_factory
            ),
            control_worker_factory=(
                control_worker_factory
            ),
        )

        cycle_count += 1

        if cycle_result.status == "idle":
            idle_count += 1
        elif cycle_result.status == "completed":
            completed_count += 1
        elif cycle_result.status == "failed":
            failed_count += 1

            if cycle_result.timed_out:
                timed_out_count += 1
        elif cycle_result.status == "cancelled":
            cancelled_count += 1
        elif cycle_result.status == "stopped":
            break
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
        cancelled_count=cancelled_count,
        timed_out_count=timed_out_count,
    )
