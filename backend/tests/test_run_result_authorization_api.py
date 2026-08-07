import asyncio
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth.dependencies import get_current_user
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(
        dbapi_connection,
        _connection_record,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_user(
    db: Session,
    email: str,
) -> models.User:
    user = models.User(email=email)
    db.add(user)
    db.flush()
    return user


def _create_organization(
    db: Session,
    name: str,
) -> models.Organization:
    organization = models.Organization(name=name)
    db.add(organization)
    db.flush()
    return organization


def _add_membership(
    db: Session,
    *,
    user: models.User,
    organization: models.Organization,
    role: str,
) -> None:
    db.add(
        models.OrganizationMembership(
            user_id=user.id,
            organization_id=organization.id,
            role=role,
        )
    )
    db.flush()


def _create_project(
    db: Session,
    *,
    organization: models.Organization | None,
    name: str,
) -> models.Project:
    project = models.Project(
        organization=organization,
        name=name,
    )
    db.add(project)
    db.flush()
    return project


def _create_dataset(
    db: Session,
    *,
    project: models.Project,
) -> models.Dataset:
    dataset = models.Dataset(
        project_id=project.id,
        name=f"Dataset {project.id}",
    )
    db.add(dataset)
    db.flush()
    return dataset


def _create_test_case(
    db: Session,
    *,
    dataset: models.Dataset,
    audio_file_path: str | None = None,
) -> models.TestCase:
    test_case = models.TestCase(
        dataset_id=dataset.id,
        title=f"Test case {dataset.id}",
        audio_file_path=audio_file_path,
        reference_transcript="hello world",
    )
    db.add(test_case)
    db.flush()
    return test_case


def _create_run(
    db: Session,
    *,
    project: models.Project,
) -> models.EvaluationRun:
    run = models.EvaluationRun(
        project_id=project.id,
        run_name=f"Run {project.id}",
        model_name="mock-model",
        status="created",
    )
    db.add(run)
    db.flush()
    return run


def _create_result(
    db: Session,
    *,
    run: models.EvaluationRun,
    test_case: models.TestCase,
) -> models.EvaluationResult:
    result = models.EvaluationResult(
        run_id=run.id,
        test_case_id=test_case.id,
        generated_transcript="hello there",
        wer=0.5,
        cer=0.2,
        quality_label="regression",
        error_summary="test",
    )
    db.add(result)
    db.flush()
    return result


def _create_hierarchy(
    db: Session,
    *,
    email: str,
    role: str,
    audio_file_path: str | None = None,
):
    user = _create_user(db, email)
    organization = _create_organization(
        db,
        f"{role} organization",
    )
    _add_membership(
        db,
        user=user,
        organization=organization,
        role=role,
    )
    project = _create_project(
        db,
        organization=organization,
        name=f"{role} project",
    )
    dataset = _create_dataset(
        db,
        project=project,
    )
    test_case = _create_test_case(
        db,
        dataset=dataset,
        audio_file_path=audio_file_path,
    )
    run = _create_run(
        db,
        project=project,
    )
    result = _create_result(
        db,
        run=run,
        test_case=test_case,
    )

    return (
        user,
        organization,
        project,
        dataset,
        test_case,
        run,
        result,
    )


def _request(
    db: Session,
    method: str,
    path: str,
    *,
    current_user: models.User | None = None,
    json: dict | None = None,
    files: dict | None = None,
):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    if current_user is not None:

        def override_current_user():
            return current_user

        app.dependency_overrides[
            get_current_user
        ] = override_current_user

    async def send_request():
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(
                method,
                path,
                json=json,
                files=files,
            )

    try:
        return asyncio.run(send_request())
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


def _generated_file():
    return {
        "generated_file": (
            "generated.txt",
            b"hello there",
            "text/plain",
        )
    }


def _run_upload_files():
    return {
        "audio_file": (
            "sample.wav",
            b"audio-content",
            "audio/wav",
        ),
        "reference_file": (
            "reference.txt",
            b"hello world",
            "text/plain",
        ),
        "generated_file": (
            "generated.txt",
            b"hello there",
            "text/plain",
        ),
    }


@pytest.mark.parametrize(
    ("method", "path", "json", "files"),
    [
        (
            "POST",
            "/projects/1/runs",
            {
                "run_name": "Unauthorized",
                "model_name": "mock",
            },
            None,
        ),
        ("GET", "/projects/1/runs", None, None),
        ("GET", "/runs/1", None, None),
        (
            "POST",
            "/runs/1/test-cases/1/evaluate",
            None,
            _generated_file(),
        ),
        (
            "POST",
            "/runs/1/test-cases/1/transcribe-and-evaluate",
            None,
            None,
        ),
        ("GET", "/runs/1/results", None, None),
        ("GET", "/results/1", None, None),
        ("GET", "/results/1/transcript-diff", None, None),
        (
            "POST",
            "/runs/1/upload",
            None,
            _run_upload_files(),
        ),
    ],
)
def test_run_result_routes_require_authentication(
    db_session: Session,
    method: str,
    path: str,
    json: dict | None,
    files: dict | None,
) -> None:
    response = _request(
        db_session,
        method,
        path,
        json=json,
        files=files,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication is required."
    }


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "engineer",
        "viewer",
    ],
)
def test_product_read_roles_can_read_runs_and_results(
    db_session: Session,
    role: str,
) -> None:
    (
        user,
        _organization,
        project,
        _dataset,
        _test_case,
        run,
        result,
    ) = _create_hierarchy(
        db_session,
        email=f"read-run-{role}@example.com",
        role=role,
    )

    responses = [
        _request(
            db_session,
            "GET",
            f"/projects/{project.id}/runs",
            current_user=user,
        ),
        _request(
            db_session,
            "GET",
            f"/runs/{run.id}",
            current_user=user,
        ),
        _request(
            db_session,
            "GET",
            f"/runs/{run.id}/results",
            current_user=user,
        ),
        _request(
            db_session,
            "GET",
            f"/results/{result.id}",
            current_user=user,
        ),
        _request(
            db_session,
            "GET",
            f"/results/{result.id}/transcript-diff",
            current_user=user,
        ),
    ]

    assert all(
        response.status_code == 200
        for response in responses
    )

    assert responses[0].json()[0]["id"] == run.id
    assert responses[1].json()["id"] == run.id
    assert responses[2].json()[0]["id"] == result.id
    assert responses[3].json()["id"] == result.id
    assert responses[4].json()["result_id"] == result.id


def test_billing_admin_cannot_read_runs_or_results(
    db_session: Session,
) -> None:
    (
        user,
        _organization,
        project,
        _dataset,
        _test_case,
        run,
        result,
    ) = _create_hierarchy(
        db_session,
        email="billing-run@example.com",
        role="billing_admin",
    )

    paths = [
        f"/projects/{project.id}/runs",
        f"/runs/{run.id}",
        f"/runs/{run.id}/results",
        f"/results/{result.id}",
        f"/results/{result.id}/transcript-diff",
    ]

    for path in paths:
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )
        assert response.status_code == 403


def test_other_tenant_runs_and_results_are_not_disclosed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "tenant-a-run@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Tenant A",
    )
    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )

    other_org = _create_organization(
        db_session,
        "Tenant B",
    )
    other_project = _create_project(
        db_session,
        organization=other_org,
        name="Tenant B project",
    )
    other_dataset = _create_dataset(
        db_session,
        project=other_project,
    )
    other_test_case = _create_test_case(
        db_session,
        dataset=other_dataset,
    )
    other_run = _create_run(
        db_session,
        project=other_project,
    )
    other_result = _create_result(
        db_session,
        run=other_run,
        test_case=other_test_case,
    )

    paths = [
        f"/projects/{other_project.id}/runs",
        f"/runs/{other_run.id}",
        f"/runs/{other_run.id}/results",
        f"/results/{other_result.id}",
        f"/results/{other_result.id}/transcript-diff",
    ]

    for path in paths:
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )
        assert response.status_code == 404


def test_legacy_unowned_run_and_result_fail_closed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "legacy-run@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Owned organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )

    legacy_project = _create_project(
        db_session,
        organization=None,
        name="Legacy project",
    )
    dataset = _create_dataset(
        db_session,
        project=legacy_project,
    )
    test_case = _create_test_case(
        db_session,
        dataset=dataset,
    )
    run = _create_run(
        db_session,
        project=legacy_project,
    )
    result = _create_result(
        db_session,
        run=run,
        test_case=test_case,
    )

    for path in (
        f"/runs/{run.id}",
        f"/runs/{run.id}/results",
        f"/results/{result.id}",
        f"/results/{result.id}/transcript-diff",
    ):
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )
        assert response.status_code == 404


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "engineer",
    ],
)
def test_write_roles_can_create_run(
    db_session: Session,
    role: str,
) -> None:
    (
        user,
        _organization,
        project,
        _dataset,
        _test_case,
        _run,
        _result,
    ) = _create_hierarchy(
        db_session,
        email=f"create-run-{role}@example.com",
        role=role,
    )

    response = _request(
        db_session,
        "POST",
        f"/projects/{project.id}/runs",
        current_user=user,
        json={
            "run_name": "Authorized run",
            "model_name": "mock-model",
        },
    )

    assert response.status_code == 200
    assert response.json()["project_id"] == project.id
    assert response.json()["run_name"] == "Authorized run"


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "billing_admin",
    ],
)
def test_non_write_roles_cannot_create_run(
    db_session: Session,
    role: str,
) -> None:
    (
        user,
        _organization,
        project,
        _dataset,
        _test_case,
        _run,
        _result,
    ) = _create_hierarchy(
        db_session,
        email=f"deny-run-{role}@example.com",
        role=role,
    )

    response = _request(
        db_session,
        "POST",
        f"/projects/{project.id}/runs",
        current_user=user,
        json={
            "run_name": "Forbidden run",
            "model_name": "mock-model",
        },
    )

    assert response.status_code == 403

    assert (
        db_session.query(models.EvaluationRun)
        .filter(
            models.EvaluationRun.run_name == "Forbidden run"
        )
        .count()
        == 0
    )


def test_authorized_evaluation_writes_result_only_after_checks(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    (
        user,
        _organization,
        _project,
        _dataset,
        test_case,
        run,
        existing_result,
    ) = _create_hierarchy(
        db_session,
        email="evaluate-owner@example.com",
        role="owner",
    )

    db_session.delete(existing_result)
    db_session.flush()

    response = _request(
        db_session,
        "POST",
        f"/runs/{run.id}/test-cases/{test_case.id}/evaluate",
        current_user=user,
        files=_generated_file(),
    )

    assert response.status_code == 200

    result = (
        db_session.query(models.EvaluationResult)
        .filter(
            models.EvaluationResult.run_id == run.id,
            models.EvaluationResult.test_case_id
            == test_case.id,
        )
        .one()
    )

    assert result.generated_transcript == "hello there"

    generated_path = (
        tmp_path
        / result.generated_file_path
    )
    assert generated_path.exists()


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "billing_admin",
    ],
)
def test_non_write_roles_cannot_evaluate_or_write_files(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    (
        user,
        _organization,
        _project,
        _dataset,
        test_case,
        run,
        existing_result,
    ) = _create_hierarchy(
        db_session,
        email=f"deny-evaluate-{role}@example.com",
        role=role,
    )

    before_count = (
        db_session.query(models.EvaluationResult).count()
    )
    original_status = run.status

    response = _request(
        db_session,
        "POST",
        f"/runs/{run.id}/test-cases/{test_case.id}/evaluate",
        current_user=user,
        files=_generated_file(),
    )

    assert response.status_code == 403
    assert not (tmp_path / "uploads").exists()
    assert (
        db_session.query(models.EvaluationResult).count()
        == before_count
    )
    assert run.status == original_status
    assert existing_result.id is not None


def test_cross_tenant_test_case_is_hidden_before_evaluation_side_effects(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    (
        user,
        _organization,
        _project,
        _dataset,
        _own_test_case,
        run,
        _result,
    ) = _create_hierarchy(
        db_session,
        email="cross-tenant-evaluate@example.com",
        role="owner",
    )

    other_org = _create_organization(
        db_session,
        "Other tenant",
    )
    other_project = _create_project(
        db_session,
        organization=other_org,
        name="Other tenant project",
    )
    other_dataset = _create_dataset(
        db_session,
        project=other_project,
    )
    other_test_case = _create_test_case(
        db_session,
        dataset=other_dataset,
    )

    before_count = (
        db_session.query(models.EvaluationResult).count()
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/runs/{run.id}/test-cases/"
            f"{other_test_case.id}/evaluate"
        ),
        current_user=user,
        files=_generated_file(),
    )

    assert response.status_code == 404
    assert not (tmp_path / "uploads").exists()
    assert (
        db_session.query(models.EvaluationResult).count()
        == before_count
    )


def test_same_user_cross_project_evaluation_is_rejected(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    (
        user,
        organization,
        _project,
        _dataset,
        _test_case,
        run,
        _result,
    ) = _create_hierarchy(
        db_session,
        email="cross-project-evaluate@example.com",
        role="owner",
    )

    second_project = _create_project(
        db_session,
        organization=organization,
        name="Second authorized project",
    )
    second_dataset = _create_dataset(
        db_session,
        project=second_project,
    )
    second_test_case = _create_test_case(
        db_session,
        dataset=second_dataset,
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/runs/{run.id}/test-cases/"
            f"{second_test_case.id}/evaluate"
        ),
        current_user=user,
        files=_generated_file(),
    )

    assert response.status_code == 400
    assert not (tmp_path / "uploads").exists()


def test_unauthorized_transcribe_does_not_invoke_asr(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        user,
        _organization,
        _project,
        _dataset,
        test_case,
        run,
        _result,
    ) = _create_hierarchy(
        db_session,
        email="viewer-transcribe@example.com",
        role="viewer",
        audio_file_path="never-read.wav",
    )

    called = False

    def forbidden_provider():
        nonlocal called
        called = True
        raise AssertionError(
            "ASR provider must not be invoked"
        )

    monkeypatch.setattr(
        "app.routes.get_asr_provider",
        forbidden_provider,
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/runs/{run.id}/test-cases/"
            f"{test_case.id}/transcribe-and-evaluate"
        ),
        current_user=user,
    )

    assert response.status_code == 403
    assert called is False


def test_cross_project_transcribe_does_not_invoke_asr(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        user,
        organization,
        _project,
        _dataset,
        _test_case,
        run,
        _result,
    ) = _create_hierarchy(
        db_session,
        email="cross-project-transcribe@example.com",
        role="engineer",
    )

    second_project = _create_project(
        db_session,
        organization=organization,
        name="Second transcribe project",
    )
    second_dataset = _create_dataset(
        db_session,
        project=second_project,
    )
    second_test_case = _create_test_case(
        db_session,
        dataset=second_dataset,
        audio_file_path="never-read.wav",
    )

    called = False

    def forbidden_provider():
        nonlocal called
        called = True
        raise AssertionError(
            "ASR provider must not be invoked"
        )

    monkeypatch.setattr(
        "app.routes.get_asr_provider",
        forbidden_provider,
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/runs/{run.id}/test-cases/"
            f"{second_test_case.id}/transcribe-and-evaluate"
        ),
        current_user=user,
    )

    assert response.status_code == 400
    assert called is False


def test_authorized_transcribe_invokes_asr_and_persists_result(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"audio")

    (
        user,
        _organization,
        _project,
        _dataset,
        test_case,
        run,
        existing_result,
    ) = _create_hierarchy(
        db_session,
        email="engineer-transcribe@example.com",
        role="engineer",
        audio_file_path=str(audio_path),
    )

    db_session.delete(existing_result)
    db_session.flush()

    class FakeProvider:
        def transcribe(
            self,
            *,
            audio_path: str,
            model_name: str,
        ):
            assert audio_path == test_case.audio_file_path
            assert model_name == run.model_name

            return SimpleNamespace(
                provider="mock",
                model_name=model_name,
                transcript="hello there",
            )

    monkeypatch.setattr(
        "app.routes.get_asr_provider",
        lambda: FakeProvider(),
    )

    response = _request(
        db_session,
        "POST",
        (
            f"/runs/{run.id}/test-cases/"
            f"{test_case.id}/transcribe-and-evaluate"
        ),
        current_user=user,
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "mock"
    assert (
        response.json()["generated_transcript"]
        == "hello there"
    )

    result = (
        db_session.query(models.EvaluationResult)
        .filter(
            models.EvaluationResult.run_id == run.id,
            models.EvaluationResult.test_case_id
            == test_case.id,
        )
        .one()
    )

    assert result.generated_transcript == "hello there"


def test_result_with_cross_project_test_case_fails_closed(
    db_session: Session,
) -> None:
    (
        user,
        organization,
        project,
        _dataset,
        _test_case,
        run,
        existing_result,
    ) = _create_hierarchy(
        db_session,
        email="result-integrity@example.com",
        role="owner",
    )

    db_session.delete(existing_result)
    db_session.flush()

    second_project = _create_project(
        db_session,
        organization=organization,
        name="Second result project",
    )
    second_dataset = _create_dataset(
        db_session,
        project=second_project,
    )
    second_test_case = _create_test_case(
        db_session,
        dataset=second_dataset,
    )

    inconsistent_result = _create_result(
        db_session,
        run=run,
        test_case=second_test_case,
    )

    assert run.project_id == project.id
    assert second_dataset.project_id != run.project_id

    for path in (
        f"/results/{inconsistent_result.id}",
        (
            f"/results/{inconsistent_result.id}"
            "/transcript-diff"
        ),
    ):
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )

        assert response.status_code == 404


def test_authorized_run_upload_writes_files_and_updates_run(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    (
        user,
        _organization,
        _project,
        _dataset,
        _test_case,
        run,
        _result,
    ) = _create_hierarchy(
        db_session,
        email="upload-owner@example.com",
        role="owner",
    )

    response = _request(
        db_session,
        "POST",
        f"/runs/{run.id}/upload",
        current_user=user,
        files=_run_upload_files(),
    )

    assert response.status_code == 200

    db_session.refresh(run)

    assert run.status == "evaluated"
    assert run.audio_file_path is not None
    assert (
        tmp_path / run.audio_file_path
    ).read_bytes() == b"audio-content"


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "billing_admin",
    ],
)
def test_non_write_roles_cannot_upload_run_artifacts(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    (
        user,
        _organization,
        _project,
        _dataset,
        _test_case,
        run,
        _result,
    ) = _create_hierarchy(
        db_session,
        email=f"upload-denied-{role}@example.com",
        role=role,
    )

    original_status = run.status

    response = _request(
        db_session,
        "POST",
        f"/runs/{run.id}/upload",
        current_user=user,
        files=_run_upload_files(),
    )

    assert response.status_code == 403
    assert not (tmp_path / "uploads").exists()

    db_session.refresh(run)
    assert run.status == original_status


def test_other_tenant_run_upload_fails_before_filesystem_write(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    user = _create_user(
        db_session,
        "upload-outsider@example.com",
    )
    own_org = _create_organization(
        db_session,
        "Upload own org",
    )
    _add_membership(
        db_session,
        user=user,
        organization=own_org,
        role="owner",
    )

    other_org = _create_organization(
        db_session,
        "Upload other org",
    )
    other_project = _create_project(
        db_session,
        organization=other_org,
        name="Other upload project",
    )
    other_run = _create_run(
        db_session,
        project=other_project,
    )

    response = _request(
        db_session,
        "POST",
        f"/runs/{other_run.id}/upload",
        current_user=user,
        files=_run_upload_files(),
    )

    assert response.status_code == 404
    assert not (tmp_path / "uploads").exists()
