import asyncio
from collections.abc import Generator

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
        organization_id=(
            organization.id
            if organization is not None
            else None
        ),
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
) -> models.TestCase:
    test_case = models.TestCase(
        dataset_id=dataset.id,
        title=f"Test case {dataset.id}",
        reference_transcript="hello world",
    )
    db.add(test_case)
    db.flush()
    return test_case


def _create_run(
    db: Session,
    *,
    project: models.Project,
    name: str,
) -> models.EvaluationRun:
    run = models.EvaluationRun(
        project_id=project.id,
        run_name=name,
        model_name=f"{name}-model",
        status="evaluated",
    )
    db.add(run)
    db.flush()
    return run


def _create_result(
    db: Session,
    *,
    run: models.EvaluationRun,
    test_case: models.TestCase,
    wer: float,
    cer: float,
) -> models.EvaluationResult:
    result = models.EvaluationResult(
        run_id=run.id,
        test_case_id=test_case.id,
        generated_transcript="hello there",
        wer=wer,
        cer=cer,
        quality_label="regression",
        error_summary="test",
    )
    db.add(result)
    db.flush()
    return result


def _create_comparison(
    db: Session,
    *,
    baseline_run: models.EvaluationRun,
    current_run: models.EvaluationRun,
) -> models.RunComparison:
    comparison = models.RunComparison(
        baseline_run_id=baseline_run.id,
        current_run_id=current_run.id,
        baseline_average_wer=0.10,
        current_average_wer=0.20,
        wer_delta=0.10,
        baseline_average_cer=0.05,
        current_average_cer=0.10,
        cer_delta=0.05,
        comparison_status="regression",
        summary="Regression detected.",
    )
    db.add(comparison)
    db.flush()
    return comparison


def _create_policy(
    db: Session,
    *,
    project: models.Project,
) -> models.ReleasePolicy:
    policy = models.ReleasePolicy(
        project_id=project.id,
        name="Test release policy",
        version=1,
        is_active=True,
        warn_current_wer=0.15,
        fail_current_wer=0.20,
        warn_current_cer=0.08,
        fail_current_cer=0.12,
        warn_wer_delta=0.01,
        fail_wer_delta=0.03,
        warn_cer_delta=0.005,
        fail_cer_delta=0.02,
    )
    db.add(policy)
    db.flush()
    return policy


def _create_report(
    db: Session,
    *,
    project: models.Project,
    comparison: models.RunComparison,
    policy: models.ReleasePolicy | None,
) -> models.ReleaseReport:
    report = models.ReleaseReport(
        project_id=project.id,
        comparison_id=comparison.id,
        policy_id=policy.id if policy else None,
        status="fail",
        severity="critical",
        headline="Release blocked",
        summary="Regression exceeds policy.",
        recommendation="Do not release.",
        policy_snapshot={
            "policy_id": policy.id if policy else None,
            "version": policy.version if policy else None,
        },
        checks=[],
    )
    db.add(report)
    db.flush()
    return report


def _create_debug_case(
    db: Session,
    *,
    project: models.Project,
    baseline_run: models.EvaluationRun,
    current_run: models.EvaluationRun,
    test_case: models.TestCase,
    baseline_result: models.EvaluationResult,
    current_result: models.EvaluationResult,
) -> models.DebugCase:
    debug_case = models.DebugCase(
        project_id=project.id,
        title="Regression debug case",
        status="open",
        severity="high",
        failure_type="asr_regression",
        baseline_run_id=baseline_run.id,
        current_run_id=current_run.id,
        test_case_id=test_case.id,
        baseline_result_id=baseline_result.id,
        current_result_id=current_result.id,
        summary="Regression detected.",
    )
    db.add(debug_case)
    db.flush()
    return debug_case


def _seed_project_resources(
    db: Session,
    *,
    project: models.Project,
    include_policy: bool = True,
    include_report: bool = True,
    include_debug_case: bool = True,
):
    dataset = _create_dataset(
        db,
        project=project,
    )
    test_case = _create_test_case(
        db,
        dataset=dataset,
    )
    baseline_run = _create_run(
        db,
        project=project,
        name=f"baseline-{project.id}",
    )
    current_run = _create_run(
        db,
        project=project,
        name=f"current-{project.id}",
    )
    baseline_result = _create_result(
        db,
        run=baseline_run,
        test_case=test_case,
        wer=0.10,
        cer=0.05,
    )
    current_result = _create_result(
        db,
        run=current_run,
        test_case=test_case,
        wer=0.20,
        cer=0.10,
    )
    comparison = _create_comparison(
        db,
        baseline_run=baseline_run,
        current_run=current_run,
    )

    policy = (
        _create_policy(
            db,
            project=project,
        )
        if include_policy
        else None
    )

    report = (
        _create_report(
            db,
            project=project,
            comparison=comparison,
            policy=policy,
        )
        if include_report
        else None
    )

    debug_case = (
        _create_debug_case(
            db,
            project=project,
            baseline_run=baseline_run,
            current_run=current_run,
            test_case=test_case,
            baseline_result=baseline_result,
            current_result=current_result,
        )
        if include_debug_case
        else None
    )

    db.flush()

    return {
        "dataset": dataset,
        "test_case": test_case,
        "baseline_run": baseline_run,
        "current_run": current_run,
        "baseline_result": baseline_result,
        "current_result": current_result,
        "comparison": comparison,
        "policy": policy,
        "report": report,
        "debug_case": debug_case,
    }


def _seed_tenant(
    db: Session,
    *,
    email: str,
    role: str,
    include_policy: bool = True,
    include_report: bool = True,
    include_debug_case: bool = True,
):
    user = _create_user(db, email)
    organization = _create_organization(
        db,
        f"{role} organization {user.id}",
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
        name=f"{role} project {user.id}",
    )
    resources = _seed_project_resources(
        db,
        project=project,
        include_policy=include_policy,
        include_report=include_report,
        include_debug_case=include_debug_case,
    )
    db.commit()

    return user, organization, project, resources


def _request(
    db: Session,
    method: str,
    path: str,
    *,
    current_user: models.User | None = None,
    json: dict | None = None,
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
            )

    try:
        return asyncio.run(send_request())
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


def _policy_payload() -> dict:
    return {
        "name": "Updated policy",
        "warn_current_wer": 0.30,
        "fail_current_wer": 0.40,
        "warn_current_cer": 0.20,
        "fail_current_cer": 0.30,
        "warn_wer_delta": 0.10,
        "fail_wer_delta": 0.20,
        "warn_cer_delta": 0.10,
        "fail_cer_delta": 0.20,
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "POST",
            "/runs/compare",
            {
                "baseline_run_id": 1,
                "current_run_id": 2,
            },
        ),
        ("GET", "/comparisons/1", None),
        ("GET", "/projects/1/comparisons", None),
        ("GET", "/projects/1/release-policy", None),
        (
            "PUT",
            "/projects/1/release-policy",
            _policy_payload(),
        ),
        (
            "POST",
            "/comparisons/1/release-report",
            None,
        ),
        (
            "GET",
            "/comparisons/1/release-report",
            None,
        ),
        (
            "POST",
            "/comparisons/1/debug-case",
            None,
        ),
        ("GET", "/projects/1/debug-cases", None),
        ("GET", "/debug-cases/1", None),
        ("GET", "/debug-cases/1/details", None),
    ],
)
def test_comparison_release_debug_routes_require_authentication(
    db_session: Session,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    response = _request(
        db_session,
        method,
        path,
        json=payload,
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "engineer",
        "viewer",
    ],
)
def test_product_read_roles_can_read_release_and_debug_data(
    db_session: Session,
    role: str,
) -> None:
    user, _organization, project, resources = (
        _seed_tenant(
            db_session,
            email=f"read-{role}@example.com",
            role=role,
        )
    )

    comparison = resources["comparison"]
    debug_case = resources["debug_case"]

    paths = [
        f"/comparisons/{comparison.id}",
        f"/projects/{project.id}/comparisons",
        f"/projects/{project.id}/release-policy",
        f"/comparisons/{comparison.id}/release-report",
        f"/projects/{project.id}/debug-cases",
        f"/debug-cases/{debug_case.id}",
        f"/debug-cases/{debug_case.id}/details",
    ]

    for path in paths:
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )
        assert response.status_code == 200


def test_billing_admin_cannot_read_release_or_debug_product_data(
    db_session: Session,
) -> None:
    user, _organization, project, resources = (
        _seed_tenant(
            db_session,
            email="billing-release@example.com",
            role="billing_admin",
        )
    )

    comparison = resources["comparison"]
    debug_case = resources["debug_case"]

    paths = [
        f"/comparisons/{comparison.id}",
        f"/projects/{project.id}/comparisons",
        f"/projects/{project.id}/release-policy",
        f"/comparisons/{comparison.id}/release-report",
        f"/projects/{project.id}/debug-cases",
        f"/debug-cases/{debug_case.id}",
        f"/debug-cases/{debug_case.id}/details",
    ]

    for path in paths:
        response = _request(
            db_session,
            "GET",
            path,
            current_user=user,
        )
        assert response.status_code == 403


def test_other_tenant_release_and_debug_resources_are_hidden(
    db_session: Session,
) -> None:
    user, _own_org, _own_project, _own_resources = (
        _seed_tenant(
            db_session,
            email="tenant-a-release@example.com",
            role="owner",
        )
    )

    (
        _other_user,
        _other_org,
        other_project,
        other_resources,
    ) = _seed_tenant(
        db_session,
        email="tenant-b-release@example.com",
        role="owner",
    )

    comparison = other_resources["comparison"]
    debug_case = other_resources["debug_case"]

    paths = [
        f"/comparisons/{comparison.id}",
        f"/projects/{other_project.id}/comparisons",
        f"/projects/{other_project.id}/release-policy",
        f"/comparisons/{comparison.id}/release-report",
        f"/projects/{other_project.id}/debug-cases",
        f"/debug-cases/{debug_case.id}",
        f"/debug-cases/{debug_case.id}/details",
    ]

    for path in paths:
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
def test_write_roles_can_compare_update_policy_report_and_debug(
    db_session: Session,
    role: str,
) -> None:
    user, _organization, project, resources = (
        _seed_tenant(
            db_session,
            email=f"write-{role}@example.com",
            role=role,
            include_report=False,
            include_debug_case=False,
        )
    )

    baseline_run = resources["baseline_run"]
    current_run = resources["current_run"]
    policy = resources["policy"]

    compare_response = _request(
        db_session,
        "POST",
        "/runs/compare",
        current_user=user,
        json={
            "baseline_run_id": baseline_run.id,
            "current_run_id": current_run.id,
        },
    )

    assert compare_response.status_code == 200
    comparison_id = compare_response.json()["id"]

    policy_response = _request(
        db_session,
        "PUT",
        f"/projects/{project.id}/release-policy",
        current_user=user,
        json=_policy_payload(),
    )

    assert policy_response.status_code == 200
    assert policy_response.json()["version"] == (
        policy.version
    )

    report_response = _request(
        db_session,
        "POST",
        f"/comparisons/{comparison_id}/release-report",
        current_user=user,
    )

    assert report_response.status_code == 200
    assert (
        report_response.json()["project_id"]
        == project.id
    )

    debug_response = _request(
        db_session,
        "POST",
        f"/comparisons/{comparison_id}/debug-case",
        current_user=user,
    )

    assert debug_response.status_code == 200
    assert (
        debug_response.json()["project_id"]
        == project.id
    )


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "billing_admin",
    ],
)
def test_non_write_roles_cannot_mutate_release_or_debug_state(
    db_session: Session,
    role: str,
) -> None:
    user, _organization, project, resources = (
        _seed_tenant(
            db_session,
            email=f"deny-write-{role}@example.com",
            role=role,
            include_report=False,
            include_debug_case=False,
        )
    )

    baseline_run = resources["baseline_run"]
    current_run = resources["current_run"]
    comparison = resources["comparison"]
    policy = resources["policy"]

    comparison_count = (
        db_session.query(models.RunComparison).count()
    )
    report_count = (
        db_session.query(models.ReleaseReport).count()
    )
    debug_count = (
        db_session.query(models.DebugCase).count()
    )
    policy_version = policy.version

    responses = [
        _request(
            db_session,
            "POST",
            "/runs/compare",
            current_user=user,
            json={
                "baseline_run_id": baseline_run.id,
                "current_run_id": current_run.id,
            },
        ),
        _request(
            db_session,
            "PUT",
            f"/projects/{project.id}/release-policy",
            current_user=user,
            json=_policy_payload(),
        ),
        _request(
            db_session,
            "POST",
            (
                f"/comparisons/{comparison.id}"
                "/release-report"
            ),
            current_user=user,
        ),
        _request(
            db_session,
            "POST",
            f"/comparisons/{comparison.id}/debug-case",
            current_user=user,
        ),
    ]

    assert all(
        response.status_code == 403
        for response in responses
    )

    db_session.refresh(policy)

    assert (
        db_session.query(models.RunComparison).count()
        == comparison_count
    )
    assert (
        db_session.query(models.ReleaseReport).count()
        == report_count
    )
    assert (
        db_session.query(models.DebugCase).count()
        == debug_count
    )
    assert policy.version == policy_version


def test_cross_tenant_run_cannot_be_mixed_into_comparison(
    db_session: Session,
) -> None:
    user, _org_a, _project_a, resources_a = (
        _seed_tenant(
            db_session,
            email="mixed-tenant-a@example.com",
            role="owner",
        )
    )
    (
        _user_b,
        _org_b,
        _project_b,
        resources_b,
    ) = _seed_tenant(
        db_session,
        email="mixed-tenant-b@example.com",
        role="owner",
    )

    before_count = (
        db_session.query(models.RunComparison).count()
    )

    response = _request(
        db_session,
        "POST",
        "/runs/compare",
        current_user=user,
        json={
            "baseline_run_id": (
                resources_a["baseline_run"].id
            ),
            "current_run_id": (
                resources_b["current_run"].id
            ),
        },
    )

    assert response.status_code == 404
    assert (
        db_session.query(models.RunComparison).count()
        == before_count
    )


def test_authorized_runs_from_different_projects_are_rejected(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "same-tenant-projects@example.com",
    )
    organization = _create_organization(
        db_session,
        "Shared organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="owner",
    )

    project_a = _create_project(
        db_session,
        organization=organization,
        name="Project A",
    )
    project_b = _create_project(
        db_session,
        organization=organization,
        name="Project B",
    )
    resources_a = _seed_project_resources(
        db_session,
        project=project_a,
    )
    resources_b = _seed_project_resources(
        db_session,
        project=project_b,
    )
    db_session.commit()

    before_count = (
        db_session.query(models.RunComparison).count()
    )

    response = _request(
        db_session,
        "POST",
        "/runs/compare",
        current_user=user,
        json={
            "baseline_run_id": (
                resources_a["baseline_run"].id
            ),
            "current_run_id": (
                resources_b["current_run"].id
            ),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Runs must belong to the same project"
    )
    assert (
        db_session.query(models.RunComparison).count()
        == before_count
    )


def test_corrupt_cross_project_comparison_fails_closed(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        "corrupt-comparison@example.com",
    )
    organization = _create_organization(
        db_session,
        "Corrupt comparison organization",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="owner",
    )

    project_a = _create_project(
        db_session,
        organization=organization,
        name="Comparison project A",
    )
    project_b = _create_project(
        db_session,
        organization=organization,
        name="Comparison project B",
    )
    resources_a = _seed_project_resources(
        db_session,
        project=project_a,
    )
    resources_b = _seed_project_resources(
        db_session,
        project=project_b,
    )

    corrupt = _create_comparison(
        db_session,
        baseline_run=resources_a["baseline_run"],
        current_run=resources_b["current_run"],
    )
    db_session.commit()

    for method, path in (
        ("GET", f"/comparisons/{corrupt.id}"),
        (
            "POST",
            f"/comparisons/{corrupt.id}/release-report",
        ),
        (
            "POST",
            f"/comparisons/{corrupt.id}/debug-case",
        ),
    ):
        response = _request(
            db_session,
            method,
            path,
            current_user=user,
        )
        assert response.status_code == 404

    list_response = _request(
        db_session,
        "GET",
        f"/projects/{project_a.id}/comparisons",
        current_user=user,
    )

    assert list_response.status_code == 200
    returned_ids = {
        item["id"]
        for item in list_response.json()
    }
    assert corrupt.id not in returned_ids


def test_release_report_with_wrong_project_fails_closed(
    db_session: Session,
) -> None:
    user, organization, project_a, resources = (
        _seed_tenant(
            db_session,
            email="report-project-integrity@example.com",
            role="owner",
            include_report=False,
        )
    )

    project_b = _create_project(
        db_session,
        organization=organization,
        name="Other report project",
    )

    report = _create_report(
        db_session,
        project=project_b,
        comparison=resources["comparison"],
        policy=resources["policy"],
    )
    db_session.commit()

    for method in ("GET", "POST"):
        response = _request(
            db_session,
            method,
            (
                f"/comparisons/"
                f"{resources['comparison'].id}"
                "/release-report"
            ),
            current_user=user,
        )

        assert response.status_code == 404

    db_session.refresh(report)
    assert report.project_id == project_b.id
    assert report.project_id != project_a.id


def test_release_report_with_wrong_policy_fails_closed(
    db_session: Session,
) -> None:
    user, organization, project_a, resources = (
        _seed_tenant(
            db_session,
            email="report-policy-integrity@example.com",
            role="owner",
            include_report=False,
        )
    )

    project_b = _create_project(
        db_session,
        organization=organization,
        name="Other policy project",
    )
    other_policy = _create_policy(
        db_session,
        project=project_b,
    )

    report = _create_report(
        db_session,
        project=project_a,
        comparison=resources["comparison"],
        policy=other_policy,
    )
    db_session.commit()

    for method in ("GET", "POST"):
        response = _request(
            db_session,
            method,
            (
                f"/comparisons/"
                f"{resources['comparison'].id}"
                "/release-report"
            ),
            current_user=user,
        )

        assert response.status_code == 404

    db_session.refresh(report)
    assert report.policy_id == other_policy.id


@pytest.mark.parametrize(
    "corrupt_field",
    [
        "baseline_run_id",
        "baseline_result_id",
        "test_case_id",
    ],
)
def test_corrupt_debug_case_links_fail_closed(
    db_session: Session,
    corrupt_field: str,
) -> None:
    user = _create_user(
        db_session,
        f"debug-integrity-{corrupt_field}@example.com",
    )
    organization = _create_organization(
        db_session,
        f"Debug integrity {corrupt_field}",
    )
    _add_membership(
        db_session,
        user=user,
        organization=organization,
        role="owner",
    )

    project_a = _create_project(
        db_session,
        organization=organization,
        name="Debug project A",
    )
    project_b = _create_project(
        db_session,
        organization=organization,
        name="Debug project B",
    )
    resources_a = _seed_project_resources(
        db_session,
        project=project_a,
        include_debug_case=False,
    )
    resources_b = _seed_project_resources(
        db_session,
        project=project_b,
        include_debug_case=False,
    )

    debug_case = _create_debug_case(
        db_session,
        project=project_a,
        baseline_run=resources_a["baseline_run"],
        current_run=resources_a["current_run"],
        test_case=resources_a["test_case"],
        baseline_result=resources_a["baseline_result"],
        current_result=resources_a["current_result"],
    )

    replacement_ids = {
        "baseline_run_id": (
            resources_b["baseline_run"].id
        ),
        "baseline_result_id": (
            resources_b["baseline_result"].id
        ),
        "test_case_id": (
            resources_b["test_case"].id
        ),
    }

    setattr(
        debug_case,
        corrupt_field,
        replacement_ids[corrupt_field],
    )
    db_session.commit()

    direct_response = _request(
        db_session,
        "GET",
        f"/debug-cases/{debug_case.id}",
        current_user=user,
    )
    details_response = _request(
        db_session,
        "GET",
        f"/debug-cases/{debug_case.id}/details",
        current_user=user,
    )
    list_response = _request(
        db_session,
        "GET",
        f"/projects/{project_a.id}/debug-cases",
        current_user=user,
    )

    assert direct_response.status_code == 404
    assert details_response.status_code == 404
    assert list_response.status_code == 200

    returned_ids = {
        item["id"]
        for item in list_response.json()
    }
    assert debug_case.id not in returned_ids


def test_same_project_but_mismatched_debug_result_fails_closed(
    db_session: Session,
) -> None:
    user, _organization, project, resources = (
        _seed_tenant(
            db_session,
            email="debug-logical-integrity@example.com",
            role="owner",
            include_debug_case=False,
        )
    )

    second_dataset = _create_dataset(
        db_session,
        project=project,
    )
    second_test_case = _create_test_case(
        db_session,
        dataset=second_dataset,
    )
    mismatched_result = _create_result(
        db_session,
        run=resources["baseline_run"],
        test_case=second_test_case,
        wer=0.30,
        cer=0.15,
    )

    debug_case = _create_debug_case(
        db_session,
        project=project,
        baseline_run=resources["baseline_run"],
        current_run=resources["current_run"],
        test_case=resources["test_case"],
        baseline_result=mismatched_result,
        current_result=resources["current_result"],
    )
    db_session.commit()

    response = _request(
        db_session,
        "GET",
        f"/debug-cases/{debug_case.id}",
        current_user=user,
    )

    assert response.status_code == 404
