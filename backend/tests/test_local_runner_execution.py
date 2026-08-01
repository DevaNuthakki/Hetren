from __future__ import annotations

from datetime import UTC, datetime
from threading import Event

import pytest

from app.local_runner_execution import (
    GENERIC_EXECUTION_ERROR,
    LeaseRenewalWorker,
    LocalRunnerCycleResult,
    PlaceholderRunnerJobExecutor,
    run_local_runner_loop,
    run_one_local_runner_cycle,
)
from app.runner_config import LocalRunnerSettings
from app.runner_schemas import (
    RunnerJobClaimResponse,
    RunnerJobRead,
)


NOW = datetime(
    2026,
    7,
    31,
    22,
    0,
    tzinfo=UTC,
)


def build_settings() -> LocalRunnerSettings:
    return LocalRunnerSettings(
        _env_file=None,
        OVRIN_RUNNER_API_URL=(
            "https://ovrin.example.com"
        ),
        OVRIN_RUNNER_CREDENTIAL=(
            "ovrin_runner_test-credential"
        ),
        OVRIN_RUNNER_VERSION="0.2.0",
        OVRIN_RUNNER_CAPABILITIES=[
            "asr",
            "cpu",
        ],
        OVRIN_RUNNER_LEASE_SECONDS=600,
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
    ):
        self.claim_response = claim_response
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
    ) -> dict[str, object]:
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
        "log",
        "complete",
    ]
    assert client.calls[3][1] == "execution_started"
    assert client.calls[5][1] == (
        "execution_completed"
    )


def test_placeholder_executor_returns_controlled_result():
    job = build_job()

    result = PlaceholderRunnerJobExecutor().execute(
        job
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
        "log",
        "fail",
    ]

    failure_log = client.calls[4][2]["entries"][0]
    assert failure_log["context_payload"] == {
        "job_type": "asr_evaluation",
        "error_type": "RuntimeError",
        "lease_renewal_failed": False,
    }

    fail_request = client.calls[5][1]
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

    worker = LeaseRenewalWorker(
        client=client,
        job_public_id=(
            "20000000-0000-0000-0000-000000000001"
        ),
        claim_token="ovrin_claim_test-token",
        lease_seconds=60,
        interval_seconds=0.01,
    )

    worker.start()

    assert client.renewal_called.wait(timeout=1)

    worker.stop()

    assert worker.failure is sensitive_failure


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
        "log",
        "fail",
    ]
    assert "complete" not in call_names

    failure_log = client.calls[7][2]["entries"][0]

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
