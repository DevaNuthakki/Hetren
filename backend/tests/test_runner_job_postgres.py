import os
import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app import models, runner_job_service
from app.runner_job_service import claim_next_job
from app.runner_security import hash_job_claim_token
from app.runner_service import (
    issue_registration_token,
    register_runner,
)


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason=(
            "Set RUN_POSTGRES_TESTS=1 to run PostgreSQL "
            "integration tests."
        ),
    ),
]


def _register_postgres_runner(
    db: Session,
    *,
    project_id: int,
    name: str,
):
    issued = issue_registration_token(
        db,
        project_id=project_id,
        label=f"{name} registration",
    )

    return register_runner(
        db,
        registration_token=issued.token,
        name=name,
        runner_version="0.1.0-test",
        capabilities=["asr"],
        system_info={"platform": "postgres-pytest"},
    )


def test_postgres_skip_locked_prevents_double_job_claim(
    postgres_test_engine: Engine,
    monkeypatch,
):
    project_id: int | None = None
    first_thread: threading.Thread | None = None
    second_thread: threading.Thread | None = None

    first_claim_locked = threading.Event()
    release_first_claim = threading.Event()

    results: dict[
        str,
        tuple[int, int, str] | None,
    ] = {}
    errors: dict[str, BaseException] = {}

    result_lock = threading.Lock()
    generation_lock = threading.Lock()
    generation_count = 0

    claim_time = datetime(
        2026,
        7,
        29,
        19,
        0,
        tzinfo=UTC,
    )

    try:
        setup_session = Session(bind=postgres_test_engine)

        try:
            project = models.Project(
                name="Concurrent runner-job claim test",
            )
            setup_session.add(project)
            setup_session.commit()
            setup_session.refresh(project)

            project_id = project.id

            first_runner = _register_postgres_runner(
                setup_session,
                project_id=project.id,
                name="Concurrent runner one",
            )
            second_runner = _register_postgres_runner(
                setup_session,
                project_id=project.id,
                name="Concurrent runner two",
            )

            first_runner_id = first_runner.runner.id
            first_credential = first_runner.credential
            second_credential = second_runner.credential

            job = models.RunnerJob(
                public_id=(
                    "10000000-0000-0000-0000-000000000001"
                ),
                project_id=project.id,
                name="Single concurrently claimed job",
                job_type="asr_evaluation",
                status="queued",
                priority=100,
                required_capabilities=["asr"],
                input_payload={"source": "postgres-pytest"},
                available_at=claim_time - timedelta(minutes=1),
            )

            setup_session.add(job)
            setup_session.commit()
            setup_session.refresh(job)

            job_id = job.id
        finally:
            setup_session.close()

        original_generate_claim_token = (
            runner_job_service.generate_job_claim_token
        )

        def controlled_generate_claim_token() -> str:
            nonlocal generation_count

            token = original_generate_claim_token()

            with generation_lock:
                generation_count += 1
                current_generation = generation_count

            # claim_next_job calls this only after selecting and locking
            # the queued job. Keep the first transaction open so that the
            # second runner must use SKIP LOCKED.
            if current_generation == 1:
                first_claim_locked.set()

                if not release_first_claim.wait(timeout=10):
                    raise TimeoutError(
                        "Timed out waiting to release first claim."
                    )

            return token

        monkeypatch.setattr(
            runner_job_service,
            "generate_job_claim_token",
            controlled_generate_claim_token,
        )

        def run_claim(
            label: str,
            credential: str,
        ) -> None:
            session = Session(bind=postgres_test_engine)

            try:
                claimed = claim_next_job(
                    session,
                    credential=credential,
                    now=claim_time,
                )

                result = (
                    None
                    if claimed is None
                    else (
                        claimed.job.id,
                        claimed.job.assigned_runner_id,
                        claimed.claim_token,
                    )
                )

                with result_lock:
                    results[label] = result
            except BaseException as exc:
                with result_lock:
                    errors[label] = exc
            finally:
                session.close()

        first_thread = threading.Thread(
            target=run_claim,
            args=("first", first_credential),
            name="first-runner-claim",
        )
        first_thread.start()

        assert first_claim_locked.wait(timeout=10), (
            "First runner did not lock the queued job."
        )

        second_thread = threading.Thread(
            target=run_claim,
            args=("second", second_credential),
            name="second-runner-claim",
        )
        second_thread.start()
        second_thread.join(timeout=5)

        assert not second_thread.is_alive(), (
            "Second runner blocked instead of skipping the locked job."
        )

        release_first_claim.set()
        first_thread.join(timeout=10)

        assert not first_thread.is_alive(), (
            "First runner did not finish its claim."
        )
        assert errors == {}

        assert results["first"] is not None
        assert results["second"] is None

        claimed_job_id, assigned_runner_id, claim_token = (
            results["first"]
        )

        assert claimed_job_id == job_id
        assert assigned_runner_id == first_runner_id
        assert generation_count == 1

        verification_session = Session(
            bind=postgres_test_engine,
        )

        try:
            persisted_job = verification_session.get(
                models.RunnerJob,
                job_id,
            )

            assert persisted_job is not None
            assert persisted_job.status == "claimed"
            assert persisted_job.assigned_runner_id == (
                first_runner_id
            )
            assert persisted_job.attempt_count == 1
            assert persisted_job.claim_token_hash == (
                hash_job_claim_token(claim_token)
            )

            claimed_count = (
                verification_session.query(models.RunnerJob)
                .filter(
                    models.RunnerJob.project_id == project_id,
                    models.RunnerJob.status == "claimed",
                )
                .count()
            )

            assert claimed_count == 1
        finally:
            verification_session.close()
    finally:
        release_first_claim.set()

        if first_thread is not None and first_thread.is_alive():
            first_thread.join(timeout=10)

        if second_thread is not None and second_thread.is_alive():
            second_thread.join(timeout=10)

        if project_id is not None:
            with postgres_test_engine.begin() as connection:
                parameters = {"project_id": project_id}

                connection.execute(
                    text(
                        "DELETE FROM runner_jobs "
                        "WHERE project_id = :project_id"
                    ),
                    parameters,
                )
                connection.execute(
                    text(
                        "DELETE FROM runners "
                        "WHERE project_id = :project_id"
                    ),
                    parameters,
                )
                connection.execute(
                    text(
                        "DELETE FROM runner_registration_tokens "
                        "WHERE project_id = :project_id"
                    ),
                    parameters,
                )
                connection.execute(
                    text(
                        "DELETE FROM projects "
                        "WHERE id = :project_id"
                    ),
                    parameters,
                )
