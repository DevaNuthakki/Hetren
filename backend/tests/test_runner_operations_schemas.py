from datetime import UTC, datetime

from app.runner_operations_service import (
    RunnerOperationsJob,
    RunnerOperationsLog,
    RunnerOperationsLogPage,
    RunnerOperationsRunner,
    RunnerOperationsSnapshot,
)
from app.runner_schemas import (
    RunnerOperationsLogPageResponse,
    RunnerOperationsSnapshotResponse,
)


def test_runner_operations_snapshot_serializes_safe_fields():
    now = datetime(
        2026,
        8,
        2,
        1,
        30,
        tzinfo=UTC,
    )

    snapshot = RunnerOperationsSnapshot(
        project_id=7,
        runners=(
            RunnerOperationsRunner(
                project_id=7,
                public_id="runner-public-id",
                name="Local ASR Runner",
                status="active",
                runner_version="0.1.0",
                capabilities=("asr", "cpu"),
                last_seen_at=now,
                revoked_at=None,
                created_at=now,
                updated_at=now,
            ),
        ),
        jobs=(
            RunnerOperationsJob(
                project_id=7,
                public_id="job-public-id",
                name="ASR evaluation",
                job_type="asr_evaluation",
                status="running",
                priority=10,
                required_capabilities=("asr",),
                assigned_runner_public_id=(
                    "runner-public-id"
                ),
                assigned_runner_name="Local ASR Runner",
                attempt_count=1,
                max_attempts=3,
                error_message=None,
                available_at=now,
                claimed_at=now,
                lease_expires_at=now,
                started_at=now,
                completed_at=None,
                failed_at=None,
                cancelled_at=None,
                created_at=now,
                updated_at=now,
            ),
        ),
    )

    response = (
        RunnerOperationsSnapshotResponse.model_validate(
            snapshot
        )
    )
    payload = response.model_dump()

    assert payload["project_id"] == 7
    assert payload["runners"][0]["capabilities"] == [
        "asr",
        "cpu",
    ]
    assert payload["jobs"][0]["required_capabilities"] == [
        "asr"
    ]

    assert "system_info" not in payload["runners"][0]
    assert "credential_hash" not in payload["runners"][0]
    assert "registration_token_id" not in payload[
        "runners"
    ][0]

    assert "input_payload" not in payload["jobs"][0]
    assert "result_payload" not in payload["jobs"][0]
    assert "claim_token_hash" not in payload["jobs"][0]


def test_runner_operations_log_page_hides_context():
    now = datetime(
        2026,
        8,
        2,
        1,
        31,
        tzinfo=UTC,
    )

    page = RunnerOperationsLogPage(
        project_id=7,
        job_public_id="job-public-id",
        logs=(
            RunnerOperationsLog(
                public_id="log-public-id",
                sequence_number=1,
                attempt_number=1,
                level="info",
                event_type="runner_started",
                message="Runner started the job.",
                created_at=now,
            ),
        ),
        has_more=False,
        next_after_sequence=1,
    )

    response = (
        RunnerOperationsLogPageResponse.model_validate(
            page
        )
    )
    payload = response.model_dump()

    assert payload["job_public_id"] == "job-public-id"
    assert payload["logs"][0]["message"] == (
        "Runner started the job."
    )
    assert "context_payload" not in payload["logs"][0]


def test_operations_schema_fields_exclude_secrets():
    runner_fields = set(
        RunnerOperationsSnapshotResponse.model_fields[
            "runners"
        ].annotation.__args__[0].model_fields
    )
    job_fields = set(
        RunnerOperationsSnapshotResponse.model_fields[
            "jobs"
        ].annotation.__args__[0].model_fields
    )
    log_fields = set(
        RunnerOperationsLogPageResponse.model_fields[
            "logs"
        ].annotation.__args__[0].model_fields
    )

    assert runner_fields.isdisjoint(
        {
            "credential_hash",
            "registration_token_id",
            "system_info",
        }
    )
    assert job_fields.isdisjoint(
        {
            "claim_token_hash",
            "input_payload",
            "result_payload",
        }
    )
    assert "context_payload" not in log_fields
