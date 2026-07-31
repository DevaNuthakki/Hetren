from __future__ import annotations

from datetime import UTC, datetime

from app.local_runner_execution import (
    GENERIC_EXECUTION_ERROR,
    PlaceholderRunnerJobExecutor,
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
