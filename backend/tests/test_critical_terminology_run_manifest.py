from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.critical_terminology_vocabulary_service import (
    CriticalTerminologyVocabularyIntegrityError,
    stage_critical_terminology_vocabulary_version,
)
from app.database import Base
from app.evaluation_provenance import (
    CRITICAL_TERMINOLOGY_MANIFEST_STATUS_CONFIGURED,
    CRITICAL_TERMINOLOGY_MANIFEST_STATUS_NOT_CONFIGURED,
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    LEGACY_EVALUATION_MANIFEST_SCHEMA_VERSION,
    calculate_manifest_sha256,
    resolve_evaluation_run_critical_terminology_profile,
    stage_evaluation_run_with_manifest,
    verify_evaluation_run_manifest,
)


def _session() -> tuple[
    Session,
    object,
]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        autoflush=False,
    )

    return factory(), engine


def _create_project_context(
    db: Session,
) -> tuple[
    models.User,
    models.Project,
]:
    user = models.User(
        email="terminology-run@example.com",
    )

    organization = models.Organization(
        name="Terminology run organization",
    )

    db.add_all(
        [
            user,
            organization,
        ]
    )
    db.flush()

    project = models.Project(
        organization_id=organization.id,
        name="Terminology run project",
    )

    db.add(project)
    db.flush()

    return user, project


def _terms(
    text: str,
) -> list[dict[str, object]]:
    key = text.lower()

    return [
        {
            "term_key": key,
            "canonical_text": text,
            "accepted_surfaces": [
                text,
            ],
        }
    ]


def test_new_run_without_vocabulary_is_explicitly_unconfigured():
    db, engine = _session()

    try:
        _, project = _create_project_context(
            db
        )

        run = stage_evaluation_run_with_manifest(
            db,
            project_id=project.id,
            run_name="Unconfigured terminology",
            model_name="mock-asr",
        )

        db.flush()

        manifest = run.manifest

        if manifest is None:
            manifest = (
                db.query(
                    models.EvaluationRunManifest
                )
                .filter(
                    models.EvaluationRunManifest.run_id
                    == run.id
                )
                .one()
            )

        assert manifest.schema_version == (
            EVALUATION_MANIFEST_SCHEMA_VERSION
        )

        assert (
            manifest.manifest_payload[
                "critical_terminology"
            ]
            == {
                "status": (
                    CRITICAL_TERMINOLOGY_MANIFEST_STATUS_NOT_CONFIGURED
                )
            }
        )

        assert verify_evaluation_run_manifest(
            manifest
        )

        assert (
            resolve_evaluation_run_critical_terminology_profile(
                db,
                evaluation_run=run,
            )
            is None
        )

    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_new_run_pins_exact_current_vocabulary_revision():
    db, engine = _session()

    try:
        user, project = _create_project_context(
            db
        )

        vocabulary = (
            stage_critical_terminology_vocabulary_version(
                db,
                project_id=project.id,
                created_by_user_id=user.id,
                terms=_terms("Cardiovex"),
            )
        )

        run = stage_evaluation_run_with_manifest(
            db,
            project_id=project.id,
            run_name="Pinned terminology",
            model_name="mock-asr",
        )

        db.flush()

        manifest = (
            db.query(
                models.EvaluationRunManifest
            )
            .filter(
                models.EvaluationRunManifest.run_id
                == run.id
            )
            .one()
        )

        binding = manifest.manifest_payload[
            "critical_terminology"
        ]

        assert binding["status"] == (
            CRITICAL_TERMINOLOGY_MANIFEST_STATUS_CONFIGURED
        )
        assert binding["revision"] == 1
        assert (
            binding["profile_key"]
            == vocabulary.profile_key
        )
        assert (
            binding["profile_version"]
            == "1"
        )
        assert (
            binding["vocabulary_sha256"]
            == vocabulary.vocabulary_sha256
        )

        profile = (
            resolve_evaluation_run_critical_terminology_profile(
                db,
                evaluation_run=run,
            )
        )

        assert profile is not None
        assert profile.key == vocabulary.profile_key
        assert profile.version == "1"

    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_run_remains_pinned_when_project_gets_new_revision():
    db, engine = _session()

    try:
        user, project = _create_project_context(
            db
        )

        first = (
            stage_critical_terminology_vocabulary_version(
                db,
                project_id=project.id,
                created_by_user_id=user.id,
                terms=_terms("Cardiovex"),
            )
        )

        run = stage_evaluation_run_with_manifest(
            db,
            project_id=project.id,
            run_name="Stable terminology pin",
            model_name="mock-asr",
        )

        db.flush()

        second = (
            stage_critical_terminology_vocabulary_version(
                db,
                project_id=project.id,
                created_by_user_id=user.id,
                terms=_terms("Neurodex"),
            )
        )

        assert first.revision == 1
        assert second.revision == 2

        profile = (
            resolve_evaluation_run_critical_terminology_profile(
                db,
                evaluation_run=run,
            )
        )

        assert profile is not None
        assert profile.version == "1"
        assert (
            profile.key
            == first.profile_key
            == second.profile_key
        )

        assert (
            profile.terms[0].canonical_text
            == "Cardiovex"
        )

    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_run_created_unconfigured_does_not_adopt_later_vocabulary():
    db, engine = _session()

    try:
        user, project = _create_project_context(
            db
        )

        run = stage_evaluation_run_with_manifest(
            db,
            project_id=project.id,
            run_name="Never retroactive",
            model_name="mock-asr",
        )

        db.flush()

        stage_critical_terminology_vocabulary_version(
            db,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_terms("Cardiovex"),
        )

        assert (
            resolve_evaluation_run_critical_terminology_profile(
                db,
                evaluation_run=run,
            )
            is None
        )

    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_legacy_schema_v1_manifest_has_no_terminology_binding():
    db, engine = _session()

    try:
        _, project = _create_project_context(
            db
        )

        run = models.EvaluationRun(
            project_id=project.id,
            run_name="Legacy run",
            model_name="legacy-asr",
            status="created",
        )

        db.add(run)
        db.flush()

        payload = {
            "schema_version": (
                LEGACY_EVALUATION_MANIFEST_SCHEMA_VERSION
            ),
            "evaluation_type": "asr",
            "run": {
                "id": run.id,
                "project_id": project.id,
                "name": "Legacy run",
            },
            "model": {
                "name": "legacy-asr",
            },
            "evaluator": {
                "engine": "hetren",
                "contract_version": "asr-v1",
            },
        }

        manifest = models.EvaluationRunManifest(
            run_id=run.id,
            schema_version=(
                LEGACY_EVALUATION_MANIFEST_SCHEMA_VERSION
            ),
            evaluation_type="asr",
            manifest_payload=payload,
            manifest_sha256=(
                calculate_manifest_sha256(
                    payload
                )
            ),
        )

        db.add(manifest)
        db.flush()

        assert verify_evaluation_run_manifest(
            manifest
        )

        assert (
            resolve_evaluation_run_critical_terminology_profile(
                db,
                evaluation_run=run,
            )
            is None
        )

    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_tampered_configured_binding_fails_closed():
    db, engine = _session()

    try:
        user, project = _create_project_context(
            db
        )

        stage_critical_terminology_vocabulary_version(
            db,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_terms("Cardiovex"),
        )

        run = stage_evaluation_run_with_manifest(
            db,
            project_id=project.id,
            run_name="Tampered terminology",
            model_name="mock-asr",
        )

        db.flush()

        manifest = (
            db.query(
                models.EvaluationRunManifest
            )
            .filter(
                models.EvaluationRunManifest.run_id
                == run.id
            )
            .one()
        )

        manifest.manifest_payload = {
            **manifest.manifest_payload,
            "critical_terminology": {
                **manifest.manifest_payload[
                    "critical_terminology"
                ],
                "revision": 999,
            },
        }

        # Recalculate the outer manifest hash so this test proves
        # exact vocabulary identity checking, not just hash detection.
        manifest.manifest_sha256 = (
            calculate_manifest_sha256(
                manifest.manifest_payload
            )
        )

        assert verify_evaluation_run_manifest(
            manifest
        )

        try:
            resolve_evaluation_run_critical_terminology_profile(
                db,
                evaluation_run=run,
            )
        except (
            CriticalTerminologyVocabularyIntegrityError
        ):
            pass
        else:
            raise AssertionError(
                "Tampered terminology binding "
                "must fail closed"
            )

    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_corrupted_pinned_vocabulary_fails_closed():
    db, engine = _session()

    try:
        user, project = _create_project_context(
            db
        )

        vocabulary = (
            stage_critical_terminology_vocabulary_version(
                db,
                project_id=project.id,
                created_by_user_id=user.id,
                terms=_terms("Cardiovex"),
            )
        )

        run = stage_evaluation_run_with_manifest(
            db,
            project_id=project.id,
            run_name="Corrupted vocabulary",
            model_name="mock-asr",
        )

        db.flush()

        vocabulary.vocabulary_sha256 = "0" * 64
        db.flush()

        try:
            resolve_evaluation_run_critical_terminology_profile(
                db,
                evaluation_run=run,
            )
        except (
            CriticalTerminologyVocabularyIntegrityError
        ):
            pass
        else:
            raise AssertionError(
                "Corrupted pinned vocabulary "
                "must fail closed"
            )

    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
