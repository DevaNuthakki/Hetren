from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.runner_security import (
    REGISTRATION_TOKEN_PREFIX,
    RUNNER_CREDENTIAL_PREFIX,
    hash_registration_token,
    hash_runner_credential,
)
from app.runner_service import (
    RegistrationTokenUnavailableError,
    RunnerAuthenticationError,
    RunnerNotFoundError,
    RunnerProjectNotFoundError,
    RunnerRegistrationConflictError,
    issue_registration_token,
    record_runner_heartbeat,
    register_runner,
    revoke_runner,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(
        database_connection,
        _connection_record,
    ):
        cursor = database_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(bind=engine)

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_project(
    db: Session,
    name: str = "Runner service project",
) -> models.Project:
    project = models.Project(name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def test_issue_registration_token_returns_plaintext_once(
    db: Session,
):
    project = create_project(db)
    issued_at = datetime(2026, 7, 28, 20, 0, tzinfo=UTC)

    issued = issue_registration_token(
        db,
        project_id=project.id,
        label="Local Mac runner",
        ttl=timedelta(minutes=45),
        now=issued_at,
    )

    assert issued.token.startswith(REGISTRATION_TOKEN_PREFIX)
    assert issued.record.project_id == project.id
    assert issued.record.label == "Local Mac runner"
    assert issued.record.token_hash == hash_registration_token(
        issued.token
    )
    assert issued.record.token_hash != issued.token
    assert issued.record.expires_at.replace(
        tzinfo=UTC
    ) == issued_at + timedelta(minutes=45)
    assert issued.record.consumed_at is None
    assert issued.record.revoked_at is None


def test_issue_registration_token_rejects_missing_project(
    db: Session,
):
    with pytest.raises(
        RunnerProjectNotFoundError,
        match="was not found",
    ):
        issue_registration_token(
            db,
            project_id=2_147_483_647,
        )


@pytest.mark.parametrize(
    "ttl",
    [
        timedelta(0),
        timedelta(seconds=-1),
    ],
)
def test_issue_registration_token_rejects_invalid_ttl(
    db: Session,
    ttl: timedelta,
):
    project = create_project(db)

    with pytest.raises(ValueError, match="greater than zero"):
        issue_registration_token(
            db,
            project_id=project.id,
            ttl=ttl,
        )


def test_register_runner_consumes_token_and_returns_credential(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )

    registered_at = datetime(
        2026,
        7,
        28,
        20,
        30,
        tzinfo=UTC,
    )

    registered = register_runner(
        db,
        registration_token=issued.token,
        name="  Local ASR Runner  ",
        runner_version=" 0.1.0 ",
        capabilities=["asr", "cpu", "asr"],
        system_info={
            "platform": "darwin",
            "architecture": "arm64",
        },
        now=registered_at,
    )

    runner = registered.runner
    token_record = db.get(
        models.RunnerRegistrationToken,
        issued.record.id,
    )

    assert registered.credential.startswith(
        RUNNER_CREDENTIAL_PREFIX
    )
    assert runner.project_id == project.id
    assert runner.registration_token_id == issued.record.id
    assert runner.name == "Local ASR Runner"
    assert runner.runner_version == "0.1.0"
    assert runner.capabilities == ["asr", "cpu"]
    assert runner.system_info["platform"] == "darwin"
    assert runner.status == "active"
    assert runner.revoked_at is None

    assert runner.credential_hash == hash_runner_credential(
        registered.credential
    )
    assert runner.credential_hash != registered.credential

    assert token_record is not None
    assert token_record.consumed_at is not None


def test_registration_token_can_only_be_used_once(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )

    register_runner(
        db,
        registration_token=issued.token,
        name="First runner",
    )

    with pytest.raises(
        RegistrationTokenUnavailableError,
        match="invalid or unavailable",
    ):
        register_runner(
            db,
            registration_token=issued.token,
            name="Second runner",
        )

    assert db.query(models.Runner).count() == 1


def test_expired_registration_token_is_rejected(
    db: Session,
):
    project = create_project(db)
    issued_at = datetime(2026, 7, 28, 20, 0, tzinfo=UTC)

    issued = issue_registration_token(
        db,
        project_id=project.id,
        ttl=timedelta(minutes=5),
        now=issued_at,
    )

    with pytest.raises(RegistrationTokenUnavailableError):
        register_runner(
            db,
            registration_token=issued.token,
            name="Expired token runner",
            now=issued_at + timedelta(minutes=5),
        )

    token_record = db.get(
        models.RunnerRegistrationToken,
        issued.record.id,
    )
    assert token_record is not None
    assert token_record.consumed_at is None


def test_revoked_registration_token_is_rejected(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )

    token_record = db.get(
        models.RunnerRegistrationToken,
        issued.record.id,
    )
    assert token_record is not None

    token_record.revoked_at = datetime.now(UTC)
    db.commit()

    with pytest.raises(RegistrationTokenUnavailableError):
        register_runner(
            db,
            registration_token=issued.token,
            name="Revoked token runner",
        )

    assert db.query(models.Runner).count() == 0


def test_registration_conflict_does_not_consume_second_token(
    db: Session,
):
    project = create_project(db)

    first_token = issue_registration_token(
        db,
        project_id=project.id,
        label="First token",
    )
    second_token = issue_registration_token(
        db,
        project_id=project.id,
        label="Second token",
    )

    register_runner(
        db,
        registration_token=first_token.token,
        name="Shared runner name",
    )

    with pytest.raises(RunnerRegistrationConflictError):
        register_runner(
            db,
            registration_token=second_token.token,
            name="Shared runner name",
        )

    second_token_record = db.get(
        models.RunnerRegistrationToken,
        second_token.record.id,
    )

    assert second_token_record is not None
    assert second_token_record.consumed_at is None
    assert db.query(models.Runner).count() == 1


def test_registration_rejects_non_json_system_info(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )

    with pytest.raises(
        ValueError,
        match="JSON-serializable",
    ):
        register_runner(
            db,
            registration_token=issued.token,
            name="Invalid metadata runner",
            system_info={"invalid": object()},
        )

    token_record = db.get(
        models.RunnerRegistrationToken,
        issued.record.id,
    )

    assert token_record is not None
    assert token_record.consumed_at is None


def test_heartbeat_authenticates_runner_and_updates_last_seen(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )
    registered = register_runner(
        db,
        registration_token=issued.token,
        name="Heartbeat runner",
        runner_version="0.1.0",
        capabilities=["asr"],
        system_info={"platform": "darwin"},
    )

    heartbeat_at = datetime(
        2026,
        7,
        28,
        21,
        0,
        tzinfo=UTC,
    )

    runner = record_runner_heartbeat(
        db,
        credential=registered.credential,
        runner_version="0.2.0",
        capabilities=["asr", "cpu"],
        system_info={
            "platform": "linux",
            "architecture": "x86_64",
        },
        now=heartbeat_at,
    )

    assert runner.id == registered.runner.id
    assert runner.runner_version == "0.2.0"
    assert runner.capabilities == ["asr", "cpu"]
    assert runner.system_info["platform"] == "linux"
    assert runner.last_seen_at is not None
    assert runner.last_seen_at.replace(
        tzinfo=UTC
    ) == heartbeat_at


def test_heartbeat_preserves_metadata_when_not_supplied(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )
    registered = register_runner(
        db,
        registration_token=issued.token,
        name="Metadata runner",
        runner_version="0.1.0",
        capabilities=["asr"],
        system_info={"platform": "darwin"},
    )

    runner = record_runner_heartbeat(
        db,
        credential=registered.credential,
    )

    assert runner.runner_version == "0.1.0"
    assert runner.capabilities == ["asr"]
    assert runner.system_info == {"platform": "darwin"}
    assert runner.last_seen_at is not None


def test_heartbeat_rejects_invalid_credential(
    db: Session,
):
    with pytest.raises(
        RunnerAuthenticationError,
        match="invalid or unavailable",
    ):
        record_runner_heartbeat(
            db,
            credential="ovrin_runner_invalid",
        )


def test_heartbeat_rejects_revoked_runner(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )
    registered = register_runner(
        db,
        registration_token=issued.token,
        name="Revoked heartbeat runner",
    )

    registered.runner.status = "revoked"
    registered.runner.revoked_at = datetime.now(UTC)
    db.commit()

    with pytest.raises(RunnerAuthenticationError):
        record_runner_heartbeat(
            db,
            credential=registered.credential,
        )

def test_revoke_runner_invalidates_credential(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )
    registered = register_runner(
        db,
        registration_token=issued.token,
        name="Runner to revoke",
    )

    revoked_at = datetime(
        2026,
        7,
        28,
        22,
        0,
        tzinfo=UTC,
    )

    runner = revoke_runner(
        db,
        public_id=registered.runner.public_id,
        now=revoked_at,
    )

    assert runner.status == "revoked"
    assert runner.revoked_at is not None
    assert runner.revoked_at.replace(tzinfo=UTC) == revoked_at

    with pytest.raises(RunnerAuthenticationError):
        record_runner_heartbeat(
            db,
            credential=registered.credential,
        )


def test_revoke_runner_is_idempotent(
    db: Session,
):
    project = create_project(db)
    issued = issue_registration_token(
        db,
        project_id=project.id,
    )
    registered = register_runner(
        db,
        registration_token=issued.token,
        name="Idempotent revocation runner",
    )

    first_revocation_time = datetime(
        2026,
        7,
        28,
        22,
        15,
        tzinfo=UTC,
    )

    first_result = revoke_runner(
        db,
        public_id=registered.runner.public_id,
        now=first_revocation_time,
    )

    second_result = revoke_runner(
        db,
        public_id=registered.runner.public_id,
        now=first_revocation_time + timedelta(hours=1),
    )

    assert first_result.status == "revoked"
    assert second_result.status == "revoked"
    assert second_result.revoked_at == first_result.revoked_at


def test_revoke_runner_rejects_unknown_public_id(
    db: Session,
):
    with pytest.raises(
        RunnerNotFoundError,
        match="was not found",
    ):
        revoke_runner(
            db,
            public_id="00000000-0000-0000-0000-000000000000",
        )
