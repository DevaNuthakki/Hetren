from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.critical_terminology_vocabulary_service import (
    CriticalTerminologyVocabularyIntegrityError,
    CriticalTerminologyVocabularyProjectNotFoundError,
    CriticalTerminologyVocabularyValidationError,
    build_profile_from_vocabulary_version,
    stage_critical_terminology_vocabulary_version,
)
from app.database import Base
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_PROFILE_SCHEMA_VERSION,
    calculate_critical_terminology_vocabulary_sha256,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
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


def _create_project_context(
    db: Session,
) -> tuple[
    models.Project,
    models.User,
]:
    organization = models.Organization(
        name="Terminology organization",
    )
    user = models.User(
        email="terminology-service@example.com",
    )

    db.add_all(
        [
            organization,
            user,
        ]
    )
    db.flush()

    project = models.Project(
        organization_id=organization.id,
        name="Terminology project",
    )
    db.add(project)
    db.flush()

    return project, user


def _v1_terms() -> list[dict[str, object]]:
    return [
        {
            "term_key": "cardiovex",
            "canonical_text": "Cardiovex",
            "accepted_surfaces": [
                "Cardiovex",
                "Cardio Vex",
            ],
        },
        {
            "term_key": "neurodex",
            "canonical_text": "Neurodex",
            "accepted_surfaces": [
                "Neurodex",
            ],
        },
    ]


def _v2_terms() -> list[dict[str, object]]:
    return [
        *_v1_terms(),
        {
            "term_key": "zenthora",
            "canonical_text": "Zenthora",
            "accepted_surfaces": [
                "Zenthora",
            ],
        },
    ]


def test_first_vocabulary_revision_uses_hvee_identity(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    vocabulary = (
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_v1_terms(),
        )
    )

    assert vocabulary.revision == 1
    assert vocabulary.profile_version == "1"

    assert (
        vocabulary.profile_schema_version
        == CRITICAL_TERMINOLOGY_PROFILE_SCHEMA_VERSION
    )

    assert vocabulary.language == "en"
    assert vocabulary.locale == "en-US"

    assert vocabulary.profile_key.startswith(
        "project-critical-terminology-"
    )

    assert len(vocabulary.vocabulary_sha256) == 64

    profile = build_profile_from_vocabulary_version(
        vocabulary
    )

    assert profile.key == vocabulary.profile_key
    assert profile.version == "1"

    assert (
        calculate_critical_terminology_vocabulary_sha256(
            profile
        )
        == vocabulary.vocabulary_sha256
    )


def test_new_revision_is_append_only_and_reuses_profile_identity(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    v1 = stage_critical_terminology_vocabulary_version(
        db_session,
        project_id=project.id,
        created_by_user_id=user.id,
        terms=_v1_terms(),
    )

    original_v1_snapshot = [
        dict(term)
        for term in v1.terms_snapshot
    ]
    original_v1_sha256 = v1.vocabulary_sha256

    v2 = stage_critical_terminology_vocabulary_version(
        db_session,
        project_id=project.id,
        created_by_user_id=user.id,
        terms=_v2_terms(),
    )

    assert v1.revision == 1
    assert v2.revision == 2

    assert v1.profile_version == "1"
    assert v2.profile_version == "2"

    assert v2.profile_key == v1.profile_key

    assert (
        v2.vocabulary_sha256
        != v1.vocabulary_sha256
    )

    assert v1.terms_snapshot == original_v1_snapshot
    assert v1.vocabulary_sha256 == original_v1_sha256

    stored = (
        db_session.query(
            models.CriticalTerminologyVocabularyVersion
        )
        .filter(
            models.CriticalTerminologyVocabularyVersion
            .project_id
            == project.id
        )
        .order_by(
            models.CriticalTerminologyVocabularyVersion
            .revision
        )
        .all()
    )

    assert [
        item.revision
        for item in stored
    ] == [1, 2]


def test_service_does_not_commit_caller_transaction(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    stage_critical_terminology_vocabulary_version(
        db_session,
        project_id=project.id,
        created_by_user_id=user.id,
        terms=_v1_terms(),
    )

    assert (
        db_session.query(
            models.CriticalTerminologyVocabularyVersion
        )
        .count()
        == 1
    )

    db_session.rollback()

    assert (
        db_session.query(
            models.CriticalTerminologyVocabularyVersion
        )
        .count()
        == 0
    )


def test_empty_vocabulary_is_rejected(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    with pytest.raises(
        CriticalTerminologyVocabularyValidationError
    ):
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=[],
        )


def test_duplicate_normalized_surfaces_within_term_are_rejected(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    with pytest.raises(
        CriticalTerminologyVocabularyValidationError,
        match=(
            "accepted surfaces must be unique "
            "after normalization"
        ),
    ):
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=[
                {
                    "term_key": "cardiovex",
                    "canonical_text": "Cardiovex",
                    "accepted_surfaces": [
                        "Cardiovex",
                        "CardioVex",
                    ],
                },
            ],
        )


def test_normalized_surface_cannot_belong_to_two_terms(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    with pytest.raises(
        CriticalTerminologyVocabularyValidationError,
        match=(
            "normalized surface cannot map "
            "to multiple terms"
        ),
    ):
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=[
                {
                    "term_key": "first",
                    "canonical_text": "Shared",
                    "accepted_surfaces": [
                        "Shared",
                    ],
                },
                {
                    "term_key": "second",
                    "canonical_text": "shared",
                    "accepted_surfaces": [
                        "shared",
                    ],
                },
            ],
        )


@pytest.mark.parametrize(
    "terms",
    [
        [
            {
                "term_key": "cardiovex",
                "canonical_text": "Cardiovex",
            },
        ],
        [
            {
                "term_key": "cardiovex",
                "canonical_text": "Cardiovex",
                "accepted_surfaces": [
                    "Cardiovex",
                ],
                "automatic_aliases": [
                    "CardioVex",
                ],
            },
        ],
    ],
)
def test_term_shape_is_strict(
    db_session: Session,
    terms: list[dict[str, object]],
) -> None:
    project, user = _create_project_context(
        db_session
    )

    with pytest.raises(
        CriticalTerminologyVocabularyValidationError,
        match="invalid fields",
    ):
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=terms,
        )


def test_canonical_text_must_be_accepted_surface(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    with pytest.raises(
        CriticalTerminologyVocabularyValidationError,
        match=(
            "canonical text must be "
            "an accepted surface"
        ),
    ):
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=[
                {
                    "term_key": "cardiovex",
                    "canonical_text": "Cardiovex",
                    "accepted_surfaces": [
                        "Cardio Vex",
                    ],
                },
            ],
        )


def test_missing_project_fails_closed(
    db_session: Session,
) -> None:
    user = models.User(
        email="missing-project@example.com",
    )
    db_session.add(user)
    db_session.flush()

    with pytest.raises(
        CriticalTerminologyVocabularyProjectNotFoundError
    ):
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=999999,
            created_by_user_id=user.id,
            terms=_v1_terms(),
        )


def test_tampered_vocabulary_sha_is_rejected(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    vocabulary = (
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_v1_terms(),
        )
    )

    vocabulary.vocabulary_sha256 = "0" * 64

    with pytest.raises(
        CriticalTerminologyVocabularyIntegrityError,
        match="SHA-256 does not verify",
    ):
        build_profile_from_vocabulary_version(
            vocabulary
        )


def test_tampered_terms_snapshot_is_rejected(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    vocabulary = (
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_v1_terms(),
        )
    )

    vocabulary.terms_snapshot = [
        {
            "term_key": "cardiovex",
            "canonical_text": "Cardiovex",
            "accepted_surfaces": [
                "Cardiovex",
            ],
        },
    ]

    with pytest.raises(
        CriticalTerminologyVocabularyIntegrityError,
        match="SHA-256 does not verify",
    ):
        build_profile_from_vocabulary_version(
            vocabulary
        )


def test_unsupported_profile_schema_version_is_rejected(
    db_session: Session,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    vocabulary = (
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_v1_terms(),
        )
    )

    vocabulary.profile_schema_version = (
        CRITICAL_TERMINOLOGY_PROFILE_SCHEMA_VERSION
        + 1
    )

    with pytest.raises(
        CriticalTerminologyVocabularyIntegrityError,
        match="unsupported",
    ):
        build_profile_from_vocabulary_version(
            vocabulary
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("language", "fr"),
        ("locale", "en-GB"),
    ],
)
def test_tampered_language_or_locale_is_rejected(
    db_session: Session,
    field: str,
    value: str,
) -> None:
    project, user = _create_project_context(
        db_session
    )

    vocabulary = (
        stage_critical_terminology_vocabulary_version(
            db_session,
            project_id=project.id,
            created_by_user_id=user.id,
            terms=_v1_terms(),
        )
    )

    setattr(
        vocabulary,
        field,
        value,
    )

    with pytest.raises(
        CriticalTerminologyVocabularyIntegrityError,
        match="language or locale",
    ):
        build_profile_from_vocabulary_version(
            vocabulary
        )
