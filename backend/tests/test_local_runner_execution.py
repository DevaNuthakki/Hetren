from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

import app.incident_runner_compatibility_execution as incident_compatibility_execution
import app.local_runner_execution as local_runner_execution
from app.local_runner_execution import (
    GENERIC_EXECUTION_ERROR,
    GENERIC_EXECUTION_TIMEOUT_ERROR,
    ASRRunnerExecutionResult,
    ASRRunnerJobExecutor,
    build_default_runner_job_executor,    ExecutionControl,
    JobControlWorker,
    LeaseRenewalWorker,
    LocalRunnerCycleResult,
    LocalRunnerExecutionError,
    PlaceholderRunnerJobExecutor,
    RunnerJobCancelledError,
    run_local_runner_loop,
    run_one_local_runner_cycle,
)
from app.runner_config import LocalRunnerSettings
from app.runner_schemas import (
    RunnerASREvaluationContextResponse,
    RunnerJobClaimResponse,
    RunnerJobControlStatusResponse,
    RunnerJobRead,
)
from app.speech.base import TranscriptionResult


NOW = datetime(
    2026,
    7,
    31,
    22,
    0,
    tzinfo=UTC,
)


def build_settings(
    **overrides,
) -> LocalRunnerSettings:
    values = {
        "OVRIN_RUNNER_API_URL": (
            "https://ovrin.example.com"
        ),
        "OVRIN_RUNNER_CREDENTIAL": (
            "ovrin_runner_test-credential"
        ),
        "OVRIN_RUNNER_VERSION": "0.2.0",
        "OVRIN_RUNNER_CAPABILITIES": [
            "asr",
            "cpu",
        ],
        "OVRIN_RUNNER_LEASE_SECONDS": 600,
    }
    values.update(overrides)

    return LocalRunnerSettings(
        _env_file=None,
        **values,
    )


def build_job(
    *,
    job_type: str = "asr_evaluation",
) -> RunnerJobRead:
    return RunnerJobRead.model_validate(
        {
            "public_id": (
                "20000000-0000-0000-0000-"
                "000000000001"
            ),
            "project_id": 7,
            "name": "ASR evaluation",
            "job_type": job_type,
            "status": "claimed",
            "priority": 10,
            "required_capabilities": ["asr"],
            "input_payload": {
                "evaluation_run_id": 42,
                "test_case_id": 9,
            },
            "attempt_count": 1,
            "max_attempts": 3,
            "available_at": NOW,
            "claimed_at": NOW,
            "lease_expires_at": NOW,
            "started_at": None,
            "completed_at": None,
            "failed_at": None,
            "cancelled_at": None,
            "result_payload": None,
            "error_message": None,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )


class RecordingClient:
    def __init__(
        self,
        claim_response: RunnerJobClaimResponse,
        *,
        control_status: str = "active",
        control_error: Exception | None = None,
    ):
        self.claim_response = claim_response
        self.control_status = control_status
        self.control_error = control_error
        self.calls: list[tuple] = []

    def heartbeat(self, **kwargs):
        self.calls.append(
            (
                "heartbeat",
                kwargs,
            )
        )

    def claim_next_job(self, **kwargs):
        self.calls.append(
            (
                "claim",
                kwargs,
            )
        )
        return self.claim_response

    def start_job(self, **kwargs):
        self.calls.append(
            (
                "start",
                kwargs,
            )
        )

    def get_job_control_status(self, **kwargs):
        self.calls.append(
            (
                "control",
                kwargs,
            )
        )

        if self.control_error is not None:
            raise self.control_error

        return RunnerJobControlStatusResponse(
            status=self.control_status,
        )

    def append_job_logs(self, **kwargs):
        event_type = kwargs["entries"][0][
            "event_type"
        ]
        self.calls.append(
            (
                "log",
                event_type,
                kwargs,
            )
        )

    def submit_asr_evaluation_result(
        self,
        **kwargs,
    ):
        self.calls.append(
            (
                "submit_asr_result",
                kwargs,
            )
        )

        return SimpleNamespace(
            result=SimpleNamespace(
                id=81,
                run_id=42,
                test_case_id=9,
                wer=0.0,
                cer=0.0,
                quality_label="excellent",
            ),
            provider=kwargs["provider"],
            provider_metadata=dict(
                kwargs["provider_metadata"]
            ),
        )

    def complete_job(self, **kwargs):
        self.calls.append(
            (
                "complete",
                kwargs,
            )
        )

    def fail_job(self, **kwargs):
        self.calls.append(
            (
                "fail",
                kwargs,
            )
        )


class RecordingExecutor:
    def __init__(
        self,
        calls: list[tuple],
    ):
        self.calls = calls

    def execute(
        self,
        job: RunnerJobRead,
        control: ExecutionControl,
    ) -> dict[str, object]:
        control.raise_if_stopped()
        self.calls.append(
            (
                "execute",
                job.public_id,
            )
        )

        return {
            "execution_mode": "test",
            "evaluation_run_id": 42,
        }


class FailingExecutor:
    def execute(
        self,
        _job: RunnerJobRead,
        _control: ExecutionControl,
    ) -> dict[str, object]:
        raise RuntimeError(
            "Sensitive executor failure details."
        )


def test_run_one_cycle_returns_idle_without_transition():
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="idle",
            claim_token=None,
            job=None,
        )
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        system_info={"platform": "test"},
    )

    assert result.status == "idle"
    assert result.job_public_id is None

    assert [call[0] for call in client.calls] == [
        "heartbeat",
        "claim",
    ]
    assert client.calls[0][1]["system_info"] == {
        "platform": "test",
    }


def test_run_one_cycle_completes_claimed_job_in_order():
    job = build_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )
    executor = RecordingExecutor(client.calls)

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        executor=executor,
        system_info={"platform": "test"},
    )

    assert result.status == "completed"
    assert result.job_public_id == job.public_id
    assert result.result_payload == {
        "execution_mode": "test",
        "evaluation_run_id": 42,
    }

    assert [call[0] for call in client.calls] == [
        "heartbeat",
        "claim",
        "start",
        "log",
        "execute",
        "control",
        "log",
        "complete",
    ]
    assert client.calls[3][1] == "execution_started"
    assert client.calls[6][1] == (
        "execution_completed"
    )


def test_placeholder_executor_returns_controlled_result():
    job = build_job()

    result = PlaceholderRunnerJobExecutor().execute(
        job,
        ExecutionControl(),
    )

    assert result == {
        "execution_mode": "placeholder",
        "job_type": "asr_evaluation",
        "accepted_input_keys": [
            "evaluation_run_id",
            "test_case_id",
        ],
    }
    assert "evaluation_run_id" not in result


def test_run_one_cycle_reports_executor_failure():
    job = build_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        executor=FailingExecutor(),
        system_info={"platform": "test"},
    )

    assert result.status == "failed"
    assert result.error_message == (
        GENERIC_EXECUTION_ERROR
    )

    assert [call[0] for call in client.calls] == [
        "heartbeat",
        "claim",
        "start",
        "log",
        "control",
        "log",
        "fail",
    ]

    failure_log = client.calls[5][2]["entries"][0]
    assert failure_log["context_payload"] == {
        "job_type": "asr_evaluation",
        "error_type": "RuntimeError",
        "lease_renewal_failed": False,
    }

    fail_request = client.calls[6][1]
    assert fail_request["error_message"] == (
        GENERIC_EXECUTION_ERROR
    )
    assert "Sensitive executor" not in str(
        client.calls
    )


def test_unsupported_job_type_is_failed_safely():
    job = build_job(
        job_type="unsupported_job",
    )
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        system_info={"platform": "test"},
    )

    assert result.status == "failed"
    assert client.calls[-1][0] == "fail"
    assert client.calls[-1][1]["error_message"] == (
        GENERIC_EXECUTION_ERROR
    )


class RenewalRecordingClient:
    def __init__(
        self,
        *,
        failure: Exception | None = None,
    ):
        self.failure = failure
        self.calls: list[dict[str, object]] = []
        self.renewal_called = Event()

    def renew_job_lease(self, **kwargs):
        self.calls.append(kwargs)
        self.renewal_called.set()

        if self.failure is not None:
            raise self.failure


class RecordingRenewalWorker:
    def __init__(
        self,
        calls: list[tuple],
        *,
        failure: Exception | None = None,
    ):
        self.calls = calls
        self._failure = failure

    @property
    def failure(self) -> Exception | None:
        return self._failure

    def start(self) -> None:
        self.calls.append(
            (
                "renewal_start",
            )
        )

    def stop(self) -> None:
        self.calls.append(
            (
                "renewal_stop",
            )
        )


def test_lease_renewal_worker_renews_active_claim():
    client = RenewalRecordingClient()

    worker = LeaseRenewalWorker(
        client=client,
        job_public_id=(
            "20000000-0000-0000-0000-000000000001"
        ),
        claim_token="ovrin_claim_test-token",
        lease_seconds=60,
        interval_seconds=0.01,
        execution_control=ExecutionControl(),
    )

    worker.start()

    assert client.renewal_called.wait(timeout=1)

    worker.stop()

    assert worker.failure is None
    assert len(client.calls) >= 1
    assert client.calls[0] == {
        "job_public_id": (
            "20000000-0000-0000-0000-000000000001"
        ),
        "claim_token": "ovrin_claim_test-token",
        "lease_seconds": 60,
    }


def test_lease_renewal_worker_records_failure():
    sensitive_failure = RuntimeError(
        "Sensitive renewal failure details."
    )
    client = RenewalRecordingClient(
        failure=sensitive_failure,
    )
    execution_control = ExecutionControl()

    worker = LeaseRenewalWorker(
        client=client,
        job_public_id=(
            "20000000-0000-0000-0000-000000000001"
        ),
        claim_token="ovrin_claim_test-token",
        lease_seconds=60,
        interval_seconds=0.01,
        execution_control=execution_control,
    )

    worker.start()

    assert client.renewal_called.wait(timeout=1)
    assert execution_control.wait(timeout=1)

    worker.stop()

    assert worker.failure is sensitive_failure
    assert (
        execution_control.reason
        == "lease_renewal_failed"
    )


def test_run_one_cycle_does_not_complete_after_renewal_failure():
    job = build_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )
    executor = RecordingExecutor(client.calls)

    renewal_failure = RuntimeError(
        "Sensitive renewal failure details."
    )

    def build_failing_worker(**kwargs):
        assert kwargs["job_public_id"] == job.public_id
        assert kwargs["claim_token"] == (
            "ovrin_claim_test-token"
        )
        assert kwargs["lease_seconds"] == 600
        assert kwargs["interval_seconds"] == 60
        assert isinstance(
            kwargs["execution_control"],
            ExecutionControl,
        )

        return RecordingRenewalWorker(
            client.calls,
            failure=renewal_failure,
        )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        executor=executor,
        system_info={"platform": "test"},
        renewal_worker_factory=build_failing_worker,
    )

    assert result.status == "failed"
    assert result.error_message == (
        GENERIC_EXECUTION_ERROR
    )

    call_names = [
        call[0]
        for call in client.calls
    ]

    assert call_names == [
        "heartbeat",
        "claim",
        "start",
        "log",
        "renewal_start",
        "execute",
        "renewal_stop",
        "control",
        "log",
        "fail",
    ]
    assert "complete" not in call_names

    failure_log = client.calls[8][2]["entries"][0]

    assert failure_log["event_type"] == (
        "lease_renewal_failed"
    )
    assert failure_log["context_payload"] == {
        "job_type": "asr_evaluation",
        "error_type": "RuntimeError",
        "lease_renewal_failed": True,
    }
    assert "Sensitive renewal" not in str(
        client.calls
    )


class RecordingStopEvent:
    def __init__(
        self,
        *,
        initially_set: bool = False,
        wait_results: list[bool] | None = None,
    ):
        self._is_set = initially_set
        self._wait_results = list(
            wait_results or []
        )
        self.wait_calls: list[float | None] = []

    def is_set(self) -> bool:
        return self._is_set

    def wait(
        self,
        timeout: float | None = None,
    ) -> bool:
        self.wait_calls.append(timeout)

        should_stop = (
            self._wait_results.pop(0)
            if self._wait_results
            else False
        )

        if should_stop:
            self._is_set = True

        return should_stop


def test_local_runner_loop_counts_bounded_cycles():
    cycle_results = iter(
        [
            LocalRunnerCycleResult(
                status="completed",
                job_public_id="job-completed",
            ),
            LocalRunnerCycleResult(
                status="idle",
            ),
            LocalRunnerCycleResult(
                status="failed",
                job_public_id="job-failed",
                error_message=GENERIC_EXECUTION_ERROR,
            ),
        ]
    )
    cycle_calls: list[dict[str, object]] = []
    stop_event = RecordingStopEvent()

    def cycle_runner(**kwargs):
        cycle_calls.append(kwargs)
        return next(cycle_results)

    summary = run_local_runner_loop(
        client=object(),
        settings=build_settings(),
        executor=object(),
        system_info={"platform": "test"},
        stop_event=stop_event,
        max_cycles=3,
        cycle_runner=cycle_runner,
    )

    assert summary.cycle_count == 3
    assert summary.completed_count == 1
    assert summary.idle_count == 1
    assert summary.failed_count == 1
    assert summary.cancelled_count == 0
    assert summary.timed_out_count == 0
    assert summary.stopped is False

    assert len(cycle_calls) == 3
    assert stop_event.wait_calls == [5.0]

    for call in cycle_calls:
        assert call["system_info"] == {
            "platform": "test",
        }


def test_local_runner_loop_stops_before_first_cycle():
    stop_event = RecordingStopEvent(
        initially_set=True,
    )

    def cycle_runner(**_kwargs):
        raise AssertionError(
            "Runner cycle must not execute."
        )

    summary = run_local_runner_loop(
        client=object(),
        settings=build_settings(),
        stop_event=stop_event,
        cycle_runner=cycle_runner,
    )

    assert summary.cycle_count == 0
    assert summary.idle_count == 0
    assert summary.completed_count == 0
    assert summary.failed_count == 0
    assert summary.cancelled_count == 0
    assert summary.timed_out_count == 0
    assert summary.stopped is True


def test_local_runner_loop_stops_during_idle_wait():
    stop_event = RecordingStopEvent(
        wait_results=[True],
    )
    cycle_calls: list[dict[str, object]] = []

    def cycle_runner(**kwargs):
        cycle_calls.append(kwargs)

        return LocalRunnerCycleResult(
            status="idle",
        )

    summary = run_local_runner_loop(
        client=object(),
        settings=build_settings(),
        stop_event=stop_event,
        cycle_runner=cycle_runner,
    )

    assert summary.cycle_count == 1
    assert summary.idle_count == 1
    assert summary.stopped is True
    assert len(cycle_calls) == 1
    assert stop_event.wait_calls == [5.0]


@pytest.mark.parametrize(
    "max_cycles",
    [
        0,
        -1,
        True,
    ],
)
def test_local_runner_loop_rejects_invalid_max_cycles(
    max_cycles,
):
    with pytest.raises(ValueError):
        run_local_runner_loop(
            client=object(),
            settings=build_settings(),
            max_cycles=max_cycles,
        )



class CooperativeBlockingExecutor:
    def __init__(
        self,
        *,
        runner_stop_event: Event | None = None,
    ):
        self.runner_stop_event = runner_stop_event

    def execute(
        self,
        _job: RunnerJobRead,
        control: ExecutionControl,
    ) -> dict[str, object]:
        if self.runner_stop_event is not None:
            self.runner_stop_event.set()

        if not control.wait(timeout=2):
            raise AssertionError(
                "Execution control signal was not received."
            )

        control.raise_if_stopped()

        raise AssertionError(
            "Stopped execution must not continue."
        )


class JobControlRecordingClient:
    def __init__(
        self,
        *,
        status: str = "active",
        failure: Exception | None = None,
    ):
        self.status = status
        self.failure = failure
        self.checked = Event()

    def get_job_control_status(self, **_kwargs):
        self.checked.set()

        if self.failure is not None:
            raise self.failure

        return RunnerJobControlStatusResponse(
            status=self.status,
        )


def test_job_control_worker_requests_remote_cancellation():
    control = ExecutionControl()
    client = JobControlRecordingClient(
        status="cancelled",
    )

    worker = JobControlWorker(
        client=client,
        job_public_id=(
            "20000000-0000-0000-0000-000000000001"
        ),
        execution_control=control,
        poll_interval_seconds=0.01,
        execution_timeout_seconds=1,
    )

    worker.start()

    assert control.wait(timeout=1)

    worker.stop()

    assert control.reason == "cancelled"
    assert worker.failure is None
    assert client.checked.is_set()


def test_job_control_worker_enforces_execution_timeout():
    control = ExecutionControl()
    client = JobControlRecordingClient()

    worker = JobControlWorker(
        client=client,
        job_public_id=(
            "20000000-0000-0000-0000-000000000001"
        ),
        execution_control=control,
        poll_interval_seconds=1,
        execution_timeout_seconds=0.01,
    )

    worker.start()

    assert control.wait(timeout=1)

    worker.stop()

    assert control.reason == "timed_out"
    assert worker.failure is None


def test_job_control_worker_records_api_failure():
    control = ExecutionControl()
    sensitive_failure = RuntimeError(
        "Sensitive control API failure."
    )
    client = JobControlRecordingClient(
        failure=sensitive_failure,
    )

    worker = JobControlWorker(
        client=client,
        job_public_id=(
            "20000000-0000-0000-0000-000000000001"
        ),
        execution_control=control,
        poll_interval_seconds=0.01,
        execution_timeout_seconds=1,
    )

    worker.start()

    assert control.wait(timeout=1)

    worker.stop()

    assert control.reason == "control_failed"
    assert worker.failure is sensitive_failure


def test_run_one_cycle_stops_after_remote_cancellation():
    job = build_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        ),
        control_status="cancelled",
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(
            OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS=(
                0.01
            ),
            OVRIN_RUNNER_EXECUTION_TIMEOUT_SECONDS=1,
        ),
        executor=CooperativeBlockingExecutor(),
        system_info={"platform": "test"},
    )

    assert result.status == "cancelled"
    assert result.job_public_id == job.public_id

    call_names = [call[0] for call in client.calls]

    assert "control" in call_names
    assert "complete" not in call_names
    assert "fail" not in call_names

    assert [
        call[1]
        for call in client.calls
        if call[0] == "log"
    ] == [
        "execution_started",
    ]


def test_run_one_cycle_fails_timed_out_execution():
    job = build_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(
            OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS=(
                0.01
            ),
            OVRIN_RUNNER_EXECUTION_TIMEOUT_SECONDS=0.02,
        ),
        executor=CooperativeBlockingExecutor(),
        system_info={"platform": "test"},
    )

    assert result.status == "failed"
    assert result.timed_out is True
    assert result.error_message == (
        GENERIC_EXECUTION_TIMEOUT_ERROR
    )

    call_names = [call[0] for call in client.calls]

    assert "complete" not in call_names
    assert call_names[-1] == "fail"
    assert client.calls[-1][1]["error_message"] == (
        GENERIC_EXECUTION_TIMEOUT_ERROR
    )

    event_types = [
        call[1]
        for call in client.calls
        if call[0] == "log"
    ]

    assert event_types == [
        "execution_started",
        "execution_timed_out",
    ]


def test_run_one_cycle_stops_active_execution_on_shutdown():
    job = build_job()
    runner_stop_event = Event()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(
            OVRIN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS=(
                0.01
            ),
            OVRIN_RUNNER_EXECUTION_TIMEOUT_SECONDS=1,
        ),
        executor=CooperativeBlockingExecutor(
            runner_stop_event=runner_stop_event,
        ),
        system_info={"platform": "test"},
        stop_event=runner_stop_event,
    )

    assert result.status == "stopped"
    assert runner_stop_event.is_set()

    call_names = [call[0] for call in client.calls]

    assert "complete" not in call_names
    assert "fail" not in call_names


def test_local_runner_loop_counts_cancelled_and_timed_out_jobs():
    cycle_results = iter(
        [
            LocalRunnerCycleResult(
                status="cancelled",
                job_public_id="job-cancelled",
            ),
            LocalRunnerCycleResult(
                status="failed",
                job_public_id="job-timeout",
                error_message=(
                    GENERIC_EXECUTION_TIMEOUT_ERROR
                ),
                timed_out=True,
            ),
        ]
    )

    summary = run_local_runner_loop(
        client=object(),
        settings=build_settings(),
        stop_event=RecordingStopEvent(),
        max_cycles=2,
        cycle_runner=lambda **_kwargs: next(
            cycle_results
        ),
    )

    assert summary.cycle_count == 2
    assert summary.cancelled_count == 1
    assert summary.failed_count == 1
    assert summary.timed_out_count == 1



class ReturningAfterStopExecutor:
    def __init__(
        self,
        stop_event: Event,
    ):
        self.stop_event = stop_event

    def execute(
        self,
        _job: RunnerJobRead,
        control: ExecutionControl,
    ) -> dict[str, object]:
        control.raise_if_stopped()
        self.stop_event.set()

        return {
            "execution_mode": "test",
        }


def test_run_one_cycle_does_not_complete_after_late_shutdown():
    job = build_job()
    runner_stop_event = Event()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        executor=ReturningAfterStopExecutor(
            runner_stop_event
        ),
        system_info={"platform": "test"},
        stop_event=runner_stop_event,
    )

    assert result.status == "stopped"

    call_names = [
        call[0]
        for call in client.calls
    ]

    assert "complete" not in call_names
    assert "fail" not in call_names


class SignallingRenewalWorker:
    def __init__(
        self,
        execution_control: ExecutionControl,
        failure: Exception,
    ):
        self.execution_control = execution_control
        self._failure = failure

    @property
    def failure(self) -> Exception | None:
        return self._failure

    def start(self) -> None:
        self.execution_control.request_stop(
            "lease_renewal_failed"
        )

    def stop(self) -> None:
        return None


def test_run_one_cycle_classifies_signalled_renewal_failure():
    job = build_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )
    renewal_failure = RuntimeError(
        "Sensitive renewal failure."
    )

    def build_signalling_worker(**kwargs):
        return SignallingRenewalWorker(
            kwargs["execution_control"],
            renewal_failure,
        )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        executor=RecordingExecutor(
            client.calls
        ),
        system_info={"platform": "test"},
        renewal_worker_factory=(
            build_signalling_worker
        ),
    )

    assert result.status == "failed"

    failure_logs = [
        call
        for call in client.calls
        if (
            call[0] == "log"
            and call[1] == "lease_renewal_failed"
        )
    ]

    assert len(failure_logs) == 1
    assert "Sensitive renewal" not in str(
        client.calls
    )



class ASRExecutorRecordingClient:
    def __init__(
        self,
        *,
        audio_file_name: str = "support-call.wav",
    ):
        self.audio_file_name = audio_file_name
        self.calls: list[tuple] = []
        self.downloaded_path: Path | None = None

    def get_asr_evaluation_context(
        self,
        **kwargs,
    ) -> RunnerASREvaluationContextResponse:
        self.calls.append(
            (
                "context",
                kwargs,
            )
        )

        return RunnerASREvaluationContextResponse(
            project_id=7,
            evaluation_run_id=42,
            test_case_id=9,
            run_name="Candidate evaluation",
            model_name="large-v3-turbo",
            test_case_title="Support call",
            audio_file_name=self.audio_file_name,
        )

    def download_asr_evaluation_audio(
        self,
        **kwargs,
    ) -> Path:
        destination = Path(kwargs["destination"])
        destination.write_bytes(
            b"runner-asr-audio"
        )
        self.downloaded_path = destination

        self.calls.append(
            (
                "download",
                kwargs,
            )
        )

        return destination


class RecordingASRProvider:
    provider_name = "test_provider"

    def __init__(
        self,
        *,
        failure: Exception | None = None,
    ):
        self.failure = failure
        self.calls: list[dict[str, object]] = []
        self.audio_path: Path | None = None

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        self.audio_path = Path(audio_path)
        self.calls.append(
            {
                "audio_path": self.audio_path,
                "model_name": model_name,
            }
        )

        assert self.audio_path.exists()
        assert self.audio_path.read_bytes() == (
            b"runner-asr-audio"
        )

        if self.failure is not None:
            raise self.failure

        return TranscriptionResult(
            transcript="  thank you for calling  ",
            provider="test_provider",
            model_name=model_name or "test-model",
        )


def test_asr_executor_transcribes_downloaded_audio():
    job = build_job()
    client = ASRExecutorRecordingClient()
    provider = RecordingASRProvider()

    result = ASRRunnerJobExecutor(
        client=client,
        claim_token="ovrin_claim_test-token",
        provider=provider,
    ).execute(
        job,
        ExecutionControl(),
    )

    assert result == ASRRunnerExecutionResult(
        generated_transcript=(
            "thank you for calling"
        ),
        provider="test_provider",
        provider_metadata={
            "model_name": "large-v3-turbo",
            "execution_config": {
                "provider": "test_provider",
                "model_name": "large-v3-turbo",
                "device": None,
                "compute_type": None,
            },
        },
    )

    assert [
        call[0]
        for call in client.calls
    ] == [
        "context",
        "download",
    ]

    assert client.calls[0][1] == {
        "job_public_id": job.public_id,
        "claim_token": "ovrin_claim_test-token",
    }

    assert client.calls[1][1][
        "job_public_id"
    ] == job.public_id
    assert client.calls[1][1][
        "claim_token"
    ] == "ovrin_claim_test-token"

    assert provider.calls[0][
        "model_name"
    ] == "large-v3-turbo"

    assert provider.audio_path is not None
    assert not provider.audio_path.exists()
    assert client.downloaded_path is not None
    assert not client.downloaded_path.exists()


def test_asr_executor_removes_audio_after_provider_failure():
    client = ASRExecutorRecordingClient()
    provider = RecordingASRProvider(
        failure=RuntimeError(
            "Sensitive provider failure details."
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Sensitive provider failure",
    ):
        ASRRunnerJobExecutor(
            client=client,
            claim_token="ovrin_claim_test-token",
            provider=provider,
        ).execute(
            build_job(),
            ExecutionControl(),
        )

    assert provider.audio_path is not None
    assert not provider.audio_path.exists()
    assert client.downloaded_path is not None
    assert not client.downloaded_path.exists()


def test_asr_executor_rejects_unsupported_job_type():
    client = ASRExecutorRecordingClient()
    provider = RecordingASRProvider()

    with pytest.raises(
        LocalRunnerExecutionError,
    ):
        ASRRunnerJobExecutor(
            client=client,
            claim_token="ovrin_claim_test-token",
            provider=provider,
        ).execute(
            build_job(
                job_type="unsupported_job",
            ),
            ExecutionControl(),
        )

    assert client.calls == []
    assert provider.calls == []


def test_asr_executor_rejects_unsupported_audio_format():
    client = ASRExecutorRecordingClient(
        audio_file_name="support-call.flac",
    )
    provider = RecordingASRProvider()

    with pytest.raises(
        LocalRunnerExecutionError,
        match="audio format",
    ):
        ASRRunnerJobExecutor(
            client=client,
            claim_token="ovrin_claim_test-token",
            provider=provider,
        ).execute(
            build_job(),
            ExecutionControl(),
        )

    assert [
        call[0]
        for call in client.calls
    ] == [
        "context",
    ]
    assert provider.calls == []


def test_asr_executor_checks_control_before_api_access():
    client = ASRExecutorRecordingClient()
    provider = RecordingASRProvider()
    control = ExecutionControl()
    control.request_stop("cancelled")

    with pytest.raises(
        RunnerJobCancelledError,
    ):
        ASRRunnerJobExecutor(
            client=client,
            claim_token="ovrin_claim_test-token",
            provider=provider,
        ).execute(
            build_job(),
            control,
        )

    assert client.calls == []
    assert provider.calls == []


def test_asr_executor_rejects_empty_claim_token():
    with pytest.raises(
        ValueError,
        match="claim token",
    ):
        ASRRunnerJobExecutor(
            client=ASRExecutorRecordingClient(),
            claim_token="   ",
            provider=RecordingASRProvider(),
        )



class RecordingASRResultExecutor:
    def __init__(
        self,
        calls: list[tuple],
    ):
        self.calls = calls

    def execute(
        self,
        job: RunnerJobRead,
        control: ExecutionControl,
    ) -> ASRRunnerExecutionResult:
        control.raise_if_stopped()
        self.calls.append(
            (
                "execute_asr",
                job.public_id,
            )
        )

        return ASRRunnerExecutionResult(
            generated_transcript=(
                "thank you for calling"
            ),
            provider="faster_whisper",
            provider_metadata={
                "model_name": "large-v3-turbo",
            },
        )


def test_run_one_cycle_submits_asr_result_atomically():
    job = build_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        executor=RecordingASRResultExecutor(
            client.calls
        ),
        system_info={"platform": "test"},
    )

    assert result.status == "completed"
    assert result.job_public_id == job.public_id
    assert result.result_payload == {
        "evaluation_result_id": 81,
        "evaluation_run_id": 42,
        "test_case_id": 9,
        "provider": "faster_whisper",
        "provider_metadata": {
            "model_name": "large-v3-turbo",
        },
        "wer": 0.0,
        "cer": 0.0,
        "quality_label": "excellent",
    }

    call_names = [
        call[0]
        for call in client.calls
    ]

    assert call_names == [
        "heartbeat",
        "claim",
        "start",
        "log",
        "execute_asr",
        "control",
        "log",
        "submit_asr_result",
    ]

    assert "complete" not in call_names
    assert "fail" not in call_names

    submission = client.calls[-1][1]

    assert submission == {
        "job_public_id": job.public_id,
        "claim_token": "ovrin_claim_test-token",
        "generated_transcript": (
            "thank you for calling"
        ),
        "provider": "faster_whisper",
        "provider_metadata": {
            "model_name": "large-v3-turbo",
        },
    }



class DefaultASRRecordingClient(RecordingClient):
    def __init__(
        self,
        claim_response: RunnerJobClaimResponse,
    ):
        super().__init__(claim_response)
        self.downloaded_path: Path | None = None

    def get_asr_evaluation_context(
        self,
        **kwargs,
    ) -> RunnerASREvaluationContextResponse:
        self.calls.append(
            (
                "context",
                kwargs,
            )
        )

        return RunnerASREvaluationContextResponse(
            project_id=7,
            evaluation_run_id=42,
            test_case_id=9,
            run_name="Candidate evaluation",
            model_name="large-v3-turbo",
            test_case_title="Support call",
            audio_file_name="support-call.wav",
        )

    def download_asr_evaluation_audio(
        self,
        **kwargs,
    ) -> Path:
        destination = Path(kwargs["destination"])
        destination.write_bytes(
            b"default-runner-asr-audio"
        )
        self.downloaded_path = destination

        self.calls.append(
            (
                "download",
                kwargs,
            )
        )

        return destination


class DefaultRecordingASRProvider:
    provider_name = "mock_local"

    def __init__(self):
        self.calls: list[dict[str, object]] = []
        self.audio_path: Path | None = None

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str | None = None,
    ) -> TranscriptionResult:
        self.audio_path = Path(audio_path)

        assert self.audio_path.exists()
        assert self.audio_path.read_bytes() == (
            b"default-runner-asr-audio"
        )

        self.calls.append(
            {
                "audio_path": self.audio_path,
                "model_name": model_name,
            }
        )

        return TranscriptionResult(
            transcript="default runner transcript",
            provider=self.provider_name,
            model_name=model_name or "mock-model",
        )


def test_run_one_cycle_uses_real_asr_executor_by_default(
    monkeypatch,
):
    job = build_job()
    client = DefaultASRRecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )
    provider = DefaultRecordingASRProvider()

    provider_factory_calls: list[
        dict[str, object]
    ] = []

    def build_provider(
        provider_name: str,
        *,
        model_name: str,
        device: str,
        compute_type: str,
    ):
        provider_factory_calls.append(
            {
                "provider_name": provider_name,
                "model_name": model_name,
                "device": device,
                "compute_type": compute_type,
            }
        )
        return provider

    monkeypatch.setattr(
        local_runner_execution,
        "get_asr_provider",
        build_provider,
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        system_info={"platform": "test"},
    )

    assert result.status == "completed"
    assert result.job_public_id == job.public_id
    assert result.result_payload == {
        "evaluation_result_id": 81,
        "evaluation_run_id": 42,
        "test_case_id": 9,
        "provider": "mock_local",
        "provider_metadata": {
            "model_name": "large-v3-turbo",
            "execution_config": {
                "provider": "mock_local",
                "model_name": "large-v3-turbo",
                "device": None,
                "compute_type": None,
            },
        },
        "wer": 0.0,
        "cer": 0.0,
        "quality_label": "excellent",
    }

    call_names = [
        call[0]
        for call in client.calls
    ]

    assert call_names == [
        "heartbeat",
        "claim",
        "start",
        "log",
        "context",
        "download",
        "control",
        "log",
        "submit_asr_result",
    ]

    assert "complete" not in call_names
    assert "fail" not in call_names

    assert provider_factory_calls == [
        {
            "provider_name": "mock_local",
            "model_name": "mock-asr-foundation",
            "device": "cpu",
            "compute_type": "int8_float32",
        }
    ]

    assert provider.calls == [
        {
            "audio_path": provider.audio_path,
            "model_name": "large-v3-turbo",
        }
    ]

    assert provider.audio_path is not None
    assert not provider.audio_path.exists()
    assert client.downloaded_path is not None
    assert not client.downloaded_path.exists()

    start_log = client.calls[3][2]["entries"][0]
    assert start_log["context_payload"]["executor"] == (
        "ASRRunnerJobExecutor"
    )


def test_idle_cycle_does_not_initialize_asr_provider(
    monkeypatch,
):
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="idle",
            claim_token=None,
            job=None,
        )
    )

    def reject_provider_initialization():
        raise AssertionError(
            "ASR provider must not initialize for an idle queue."
        )

    monkeypatch.setattr(
        local_runner_execution,
        "get_asr_provider",
        reject_provider_initialization,
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        system_info={"platform": "test"},
    )

    assert result.status == "idle"
    assert [
        call[0]
        for call in client.calls
    ] == [
        "heartbeat",
        "claim",
    ]


def test_explicit_executor_skips_default_provider_factory(
    monkeypatch,
):
    job = build_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    def reject_provider_initialization():
        raise AssertionError(
            "Explicit executor must bypass provider factory."
        )

    monkeypatch.setattr(
        local_runner_execution,
        "get_asr_provider",
        reject_provider_initialization,
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(),
        executor=RecordingExecutor(client.calls),
        system_info={"platform": "test"},
    )

    assert result.status == "completed"
    assert result.result_payload == {
        "execution_mode": "test",
        "evaluation_run_id": 42,
    }


def _incident_compatibility_job():
    return build_job(
        job_type="incident_replay_compatibility",
    ).model_copy(
        update={
            "required_capabilities": [
                "asr",
                "incident_replay",
            ],
            "input_payload": {
                "schema_version": 1,
                "type": (
                    "incident_replay_compatibility_request"
                ),
                "evidence": {
                    "runner_test_placeholder": True,
                },
            },
        }
    )


def test_default_runner_selects_incident_compatibility_without_asr_provider(
    monkeypatch,
):
    job = _incident_compatibility_job()
    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    def reject_provider_initialization(*args, **kwargs):
        raise AssertionError(
            "Incident compatibility must not initialize "
            "an ASR provider."
        )

    monkeypatch.setattr(
        local_runner_execution,
        "get_asr_provider",
        reject_provider_initialization,
    )

    executor = build_default_runner_job_executor(
        client=client,
        settings=build_settings(
            OVRIN_RUNNER_CAPABILITIES=[
                "incident_replay",
                "asr",
            ],
        ),
        job=job,
        claim_token="ovrin_claim_test-token",
    )

    assert isinstance(
        executor,
        incident_compatibility_execution.IncidentCompatibilityRunnerJobExecutor,
    )


def test_incident_compatibility_executor_observes_only_proven_runner_state(
    monkeypatch,
):
    job = _incident_compatibility_job()

    captured = {}

    expected_bundle = SimpleNamespace(
        payload={
            "compatibility": {
                "status": "blocked_unobserved",
                "ready_for_materialization": False,
            },
            "evidence_boundary": {
                "environment_materialized": False,
                "replay_executed": False,
                "reproduction_claimed": False,
                "qualification_authority": False,
            },
        },
        sha256="a" * 64,
    )

    def fake_evaluate(**kwargs):
        captured.update(kwargs)
        return expected_bundle

    monkeypatch.setattr(
        incident_compatibility_execution,
        "evaluate_incident_replay_compatibility_request",
        fake_evaluate,
    )

    executor = (
        incident_compatibility_execution
        .IncidentCompatibilityRunnerJobExecutor(
            settings=build_settings(
                OVRIN_RUNNER_CAPABILITIES=[
                    "incident_replay",
                    "asr",
                ],
            ),
        )
    )

    result = executor.execute(
        job,
        ExecutionControl(),
    )

    observation = captured["observation"]

    assert observation.capabilities == (
        "asr",
        "incident_replay",
    )

    assert observation.deployment_key is None
    assert observation.deployment_version is None
    assert observation.provider_key is None
    assert observation.provider_version is None
    assert observation.model_key is None
    assert observation.model_version is None
    assert observation.model_artifact_sha256 is None
    assert observation.source_code_sha256 is None
    assert observation.configuration_sha256 is None
    assert observation.runtime_environment_sha256 is None
    assert observation.host_environment_sha256 is None
    assert observation.exact_context_components == ()
    assert observation.supported_materializations == ()
    assert observation.unsupported_materializations == ()

    assert captured["required_capabilities"] == (
        "asr",
        "incident_replay",
    )

    assert result == {
        "schema_version": 1,
        "type": "incident_replay_compatibility_result",
        "compatibility": {
            "payload": expected_bundle.payload,
            "sha256": "a" * 64,
        },
    }


def test_incident_compatibility_executor_rejects_modified_capability_contract():
    job = _incident_compatibility_job().model_copy(
        update={
            "required_capabilities": [
                "asr",
            ],
        }
    )

    executor = (
        incident_compatibility_execution
        .IncidentCompatibilityRunnerJobExecutor(
            settings=build_settings(
                OVRIN_RUNNER_CAPABILITIES=[
                    "asr",
                    "incident_replay",
                ],
            ),
        )
    )

    with pytest.raises(
        incident_compatibility_execution
        .IncidentCompatibilityRunnerExecutionError,
        match="capability contract is invalid",
    ):
        executor.execute(
            job,
            ExecutionControl(),
        )


def test_incident_compatibility_executor_honors_cancellation_before_evaluation(
    monkeypatch,
):
    job = _incident_compatibility_job()

    def reject_evaluation(**kwargs):
        raise AssertionError(
            "Cancelled compatibility job must not evaluate."
        )

    monkeypatch.setattr(
        incident_compatibility_execution,
        "evaluate_incident_replay_compatibility_request",
        reject_evaluation,
    )

    control = ExecutionControl()
    control.request_stop("cancelled")

    executor = (
        incident_compatibility_execution
        .IncidentCompatibilityRunnerJobExecutor(
            settings=build_settings(
                OVRIN_RUNNER_CAPABILITIES=[
                    "asr",
                    "incident_replay",
                ],
            ),
        )
    )

    with pytest.raises(
        RunnerJobCancelledError,
    ):
        executor.execute(
            job,
            control,
        )


def test_incident_compatibility_default_cycle_uses_generic_completion(
    monkeypatch,
):
    job = _incident_compatibility_job()

    client = RecordingClient(
        RunnerJobClaimResponse(
            status="claimed",
            claim_token="ovrin_claim_test-token",
            job=job,
        )
    )

    expected_bundle = SimpleNamespace(
        payload={
            "compatibility": {
                "status": "blocked_unobserved",
                "ready_for_materialization": False,
            },
            "evidence_boundary": {
                "environment_materialized": False,
                "models_loaded": False,
                "replay_executed": False,
                "transcriptions_executed": False,
                "reproduction_claimed": False,
                "model_failure_verified": False,
                "contract_promoted": False,
                "qualification_authority": False,
            },
        },
        sha256="b" * 64,
    )

    def fake_evaluate(**kwargs):
        return expected_bundle

    def reject_provider_initialization(*args, **kwargs):
        raise AssertionError(
            "Incident compatibility must not initialize "
            "an ASR provider."
        )

    monkeypatch.setattr(
        incident_compatibility_execution,
        "evaluate_incident_replay_compatibility_request",
        fake_evaluate,
    )
    monkeypatch.setattr(
        local_runner_execution,
        "get_asr_provider",
        reject_provider_initialization,
    )

    result = run_one_local_runner_cycle(
        client=client,
        settings=build_settings(
            OVRIN_RUNNER_CAPABILITIES=[
                "asr",
                "incident_replay",
            ],
        ),
        system_info={
            "platform": "test",
        },
    )

    assert result.status == "completed"
    assert result.job_public_id == job.public_id

    assert result.result_payload == {
        "schema_version": 1,
        "type": "incident_replay_compatibility_result",
        "compatibility": {
            "payload": expected_bundle.payload,
            "sha256": "b" * 64,
        },
    }

    call_names = [
        call[0]
        for call in client.calls
    ]

    assert "complete" in call_names
    assert "submit_asr_result" not in call_names
    assert "context" not in call_names
    assert "download" not in call_names
    assert "fail" not in call_names

    complete_call = next(
        call
        for call in client.calls
        if call[0] == "complete"
    )

    assert complete_call[1]["result_payload"] == (
        result.result_payload
    )

    evidence_boundary = (
        result.result_payload[
            "compatibility"
        ]["payload"]["evidence_boundary"]
    )

    assert evidence_boundary[
        "environment_materialized"
    ] is False
    assert evidence_boundary[
        "replay_executed"
    ] is False
    assert evidence_boundary[
        "reproduction_claimed"
    ] is False
    assert evidence_boundary[
        "qualification_authority"
    ] is False
