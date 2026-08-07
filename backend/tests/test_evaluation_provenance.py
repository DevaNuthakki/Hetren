from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    ASR_EVALUATION_TYPE,
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    build_evaluation_run_manifest_payload,
    calculate_manifest_sha256,
    canonicalize_json,
    stage_evaluation_run_manifest,
    verify_evaluation_run_manifest,
)


def test_canonical_json_is_deterministic():
    first = {
        "b": 2,
        "a": {
            "y": 2,
            "x": 1,
        },
    }

    second = {
        "a": {
            "x": 1,
            "y": 2,
        },
        "b": 2,
    }

    assert canonicalize_json(first) == (
        canonicalize_json(second)
    )

    assert calculate_manifest_sha256(first) == (
        calculate_manifest_sha256(second)
    )


def test_manifest_hash_changes_when_payload_changes():
    original = build_evaluation_run_manifest_payload(
        run_id=10,
        project_id=20,
        run_name="candidate",
        model_name="model-a",
    )

    changed = build_evaluation_run_manifest_payload(
        run_id=10,
        project_id=20,
        run_name="candidate",
        model_name="model-b",
    )

    assert calculate_manifest_sha256(original) != (
        calculate_manifest_sha256(changed)
    )


def test_stage_and_verify_evaluation_run_manifest():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    try:
        organization = models.Organization(
            name="Manifest test organization",
        )
        db.add(organization)
        db.flush()

        project = models.Project(
            organization_id=organization.id,
            name="Manifest test project",
        )
        db.add(project)
        db.flush()

        run = models.EvaluationRun(
            project_id=project.id,
            run_name="Candidate run",
            model_name="mock-asr",
            status="created",
        )
        db.add(run)
        db.flush()

        manifest = stage_evaluation_run_manifest(
            db,
            evaluation_run=run,
        )

        db.commit()
        db.refresh(manifest)

        assert manifest.run_id == run.id
        assert manifest.schema_version == (
            EVALUATION_MANIFEST_SCHEMA_VERSION
        )
        assert (
            manifest.evaluation_type
            == ASR_EVALUATION_TYPE
        )
        assert manifest.manifest_payload["run"] == {
            "id": run.id,
            "project_id": project.id,
            "name": "Candidate run",
        }
        assert verify_evaluation_run_manifest(
            manifest
        )

        manifest.manifest_payload = {
            **manifest.manifest_payload,
            "model": {
                "name": "tampered-model",
            },
        }

        assert not verify_evaluation_run_manifest(
            manifest
        )
    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_create_run_api_creates_sealed_manifest():
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from app.auth.dependencies import get_current_user
    from app.database import get_db
    from app.main import app

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    try:
        user = models.User(
            email="manifest-owner@example.com",
        )
        db.add(user)
        db.flush()

        organization = models.Organization(
            name="Manifest API organization",
        )
        db.add(organization)
        db.flush()

        db.add(
            models.OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role="owner",
            )
        )

        project = models.Project(
            organization_id=organization.id,
            name="Manifest API project",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        def override_get_db():
            yield db

        def override_current_user():
            return user

        app.dependency_overrides[get_db] = (
            override_get_db
        )
        app.dependency_overrides[get_current_user] = (
            override_current_user
        )

        async def create_run():
            transport = ASGITransport(app=app)

            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.post(
                    f"/projects/{project.id}/runs",
                    json={
                        "run_name": "Manifest API run",
                        "model_name": "mock-asr-v2",
                    },
                )

        response = asyncio.run(create_run())

        assert response.status_code == 200

        run_id = response.json()["id"]

        manifest = (
            db.query(models.EvaluationRunManifest)
            .filter(
                models.EvaluationRunManifest.run_id
                == run_id
            )
            .one()
        )

        assert (
            manifest.manifest_payload["run"]["id"]
            == run_id
        )
        assert (
            manifest.manifest_payload["run"][
                "project_id"
            ]
            == project.id
        )
        assert (
            manifest.manifest_payload["run"]["name"]
            == "Manifest API run"
        )
        assert (
            manifest.manifest_payload["model"]["name"]
            == "mock-asr-v2"
        )
        assert verify_evaluation_run_manifest(
            manifest
        )

    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )

        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
