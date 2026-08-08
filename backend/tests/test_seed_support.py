from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.evaluation_provenance import (
    stage_evaluation_run_with_manifest,
    verify_evaluation_result_provenance,
)
from scripts.seed_support import (
    resolve_seed_organization_id,
    stage_seed_fixture_result,
)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_preserves_existing_demo_organization(
    db: Session,
):
    first = models.Organization(name="First")
    second = models.Organization(name="Second")
    db.add_all([first, second])
    db.flush()

    db.add(
        models.Project(
            organization_id=second.id,
            name="Hetren Demo",
        )
    )
    db.flush()

    assert resolve_seed_organization_id(
        db,
        project_names=["Hetren Demo"],
    ) == second.id


def test_uses_single_organization_fallback(
    db: Session,
):
    organization = models.Organization(
        name="Only organization",
    )
    db.add(organization)
    db.flush()

    assert resolve_seed_organization_id(
        db,
        project_names=["Missing demo"],
    ) == organization.id


def test_rejects_missing_organization(
    db: Session,
):
    with pytest.raises(
        RuntimeError,
        match="No organization exists",
    ):
        resolve_seed_organization_id(
            db,
            project_names=["Hetren Demo"],
        )


def test_rejects_ambiguous_fallback(
    db: Session,
):
    db.add_all(
        [
            models.Organization(name="First"),
            models.Organization(name="Second"),
        ]
    )
    db.flush()

    with pytest.raises(
        RuntimeError,
        match="Multiple organizations exist",
    ):
        resolve_seed_organization_id(
            db,
            project_names=["Hetren Demo"],
        )


def test_rejects_conflicting_existing_ownership(
    db: Session,
):
    first = models.Organization(name="First")
    second = models.Organization(name="Second")
    db.add_all([first, second])
    db.flush()

    db.add_all(
        [
            models.Project(
                organization_id=first.id,
                name="Demo A",
            ),
            models.Project(
                organization_id=second.id,
                name="Demo B",
            ),
        ]
    )
    db.flush()

    with pytest.raises(
        RuntimeError,
        match="multiple organizations",
    ):
        resolve_seed_organization_id(
            db,
            project_names=[
                "Demo A",
                "Demo B",
            ],
        )


def test_stages_seed_fixture_result_with_provenance(
    db: Session,
):
    organization = models.Organization(
        name="Fixture organization",
    )
    db.add(organization)
    db.flush()

    project = models.Project(
        organization_id=organization.id,
        name="Fixture project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Fixture dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="Fixture test case",
        reference_transcript="reference transcript",
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Fixture run",
        model_name="fixture-model",
        status="created",
    )

    result = stage_seed_fixture_result(
        db,
        run=run,
        test_case=test_case,
        generated_text="controlled output",
        generated_file_path="fixture/generated.txt",
        wer_score=0.321,
        cer_score=0.123,
        quality_label="regression",
        error_summary="Controlled fixture metrics.",
        seed_source="phase_two_release_safety",
    )

    assert result.wer == pytest.approx(0.321)
    assert result.cer == pytest.approx(0.123)
    assert result.quality_label == "regression"
    assert result.generated_transcript == (
        "controlled output"
    )

    assert result.provenance is not None
    assert result.provenance.execution_mode == (
        "seed_fixture"
    )
    assert verify_evaluation_result_provenance(
        result.provenance
    )

    payload = result.provenance.provenance_payload
    execution = payload["execution"]

    assert payload["run_manifest"]["status"] == (
        "sealed"
    )
    assert execution["mode"] == "seed_fixture"
    assert execution["requested_model"] == (
        "fixture-model"
    )
    assert execution["server_observed"] == {
        "fixture": True,
        "seed_source": "phase_two_release_safety",
    }
    assert execution["external_reported"] == {}

    assert run.status == "evaluated"
    assert run.wer == pytest.approx(0.321)
    assert run.cer == pytest.approx(0.123)


def test_seed_fixture_result_requires_source(
    db: Session,
):
    project = models.Project(
        name="Missing-source fixture project",
    )
    db.add(project)
    db.flush()

    dataset = models.Dataset(
        project_id=project.id,
        name="Missing-source fixture dataset",
    )
    db.add(dataset)
    db.flush()

    test_case = models.TestCase(
        dataset_id=dataset.id,
        title="Missing-source fixture test",
        reference_transcript="reference",
    )
    db.add(test_case)
    db.flush()

    run = stage_evaluation_run_with_manifest(
        db,
        project_id=project.id,
        run_name="Missing-source fixture run",
        model_name="fixture-model",
        status="created",
    )

    with pytest.raises(
        ValueError,
        match="Seed fixture source is required",
    ):
        stage_seed_fixture_result(
            db,
            run=run,
            test_case=test_case,
            generated_text="generated",
            generated_file_path=None,
            wer_score=0.1,
            cer_score=0.05,
            quality_label="good",
            error_summary="fixture",
            seed_source="   ",
        )

    assert (
        db.query(models.EvaluationResult).count()
        == 0
    )
