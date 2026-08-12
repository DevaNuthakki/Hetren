from __future__ import annotations

import os
import threading
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.critical_terminology_vocabulary_service import (
    build_profile_from_vocabulary_version,
    stage_critical_terminology_vocabulary_version,
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


def _terms(
    *,
    term_key: str,
    canonical_text: str,
) -> list[dict[str, object]]:
    return [
        {
            "term_key": term_key,
            "canonical_text": canonical_text,
            "accepted_surfaces": [
                canonical_text,
            ],
        },
    ]


def _create_case(
    session: Session,
) -> tuple[int, int, int]:
    suffix = uuid4().hex

    organization = models.Organization(
        name=f"Terminology PostgreSQL {suffix}",
    )

    user = models.User(
        email=f"terminology-{suffix}@example.com",
    )

    session.add_all(
        [
            organization,
            user,
        ]
    )
    session.flush()

    project = models.Project(
        organization_id=organization.id,
        name=f"Terminology project {suffix}",
    )

    session.add(project)
    session.flush()

    return (
        organization.id,
        user.id,
        project.id,
    )


def _cleanup_committed_case(
    engine: Engine,
    *,
    organization_id: int | None,
    user_id: int | None,
    project_id: int | None,
) -> None:
    if project_id is None:
        return

    with engine.begin() as connection:
        parameters = {
            "project_id": project_id,
        }

        connection.execute(
            text(
                "DELETE FROM "
                "critical_terminology_vocabulary_versions "
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

        if user_id is not None:
            connection.execute(
                text(
                    "DELETE FROM users "
                    "WHERE id = :user_id"
                ),
                {
                    "user_id": user_id,
                },
            )

        if organization_id is not None:
            connection.execute(
                text(
                    "DELETE FROM organizations "
                    "WHERE id = :organization_id"
                ),
                {
                    "organization_id": (
                        organization_id
                    ),
                },
            )


def test_concurrent_vocabulary_writers_are_serialized(
    postgres_test_engine: Engine,
) -> None:
    organization_id: int | None = None
    user_id: int | None = None
    project_id: int | None = None

    first_session: Session | None = None
    second_thread: threading.Thread | None = None

    second_started = threading.Event()
    second_finished = threading.Event()

    second_results: dict[str, object] = {}
    second_errors: list[BaseException] = []

    setup_session = Session(
        bind=postgres_test_engine,
    )

    try:
        (
            organization_id,
            user_id,
            project_id,
        ) = _create_case(setup_session)

        setup_session.commit()
    finally:
        setup_session.close()

    assert user_id is not None
    assert project_id is not None

    first_session = Session(
        bind=postgres_test_engine,
    )

    def run_second_writer() -> None:
        session = Session(
            bind=postgres_test_engine,
        )

        try:
            second_started.set()

            vocabulary = (
                stage_critical_terminology_vocabulary_version(
                    session,
                    project_id=project_id,
                    created_by_user_id=user_id,
                    terms=_terms(
                        term_key="neurodex",
                        canonical_text="Neurodex",
                    ),
                )
            )

            session.commit()

            second_results["id"] = vocabulary.id
            second_results[
                "revision"
            ] = vocabulary.revision

        except BaseException as exc:
            session.rollback()
            second_errors.append(exc)

        finally:
            session.close()
            second_finished.set()

    try:
        # Deliberately hold the owning Project row lock before
        # the second writer starts. The vocabulary service also
        # acquires this exact row lock before allocating a revision.
        locked_project = first_session.scalar(
            select(models.Project)
            .where(
                models.Project.id == project_id
            )
            .with_for_update()
        )

        assert locked_project is not None

        second_thread = threading.Thread(
            target=run_second_writer,
            name=(
                "critical-terminology-"
                "second-writer"
            ),
        )
        second_thread.start()

        assert second_started.wait(timeout=5), (
            "Second writer did not start."
        )

        # The second transaction must not finish while the
        # first transaction owns the Project row lock.
        assert not second_finished.wait(timeout=1), (
            "Second writer bypassed the owning Project "
            "row lock."
        )

        first_vocabulary = (
            stage_critical_terminology_vocabulary_version(
                first_session,
                project_id=project_id,
                created_by_user_id=user_id,
                terms=_terms(
                    term_key="cardiovex",
                    canonical_text="Cardiovex",
                ),
            )
        )

        assert first_vocabulary.revision == 1

        first_session.commit()

        assert second_finished.wait(timeout=10), (
            "Second writer did not finish after the "
            "first transaction released the lock."
        )

        second_thread.join(timeout=1)

        assert not second_thread.is_alive()
        assert second_errors == []

        assert second_results[
            "revision"
        ] == 2

        verification_session = Session(
            bind=postgres_test_engine,
        )

        try:
            versions = list(
                verification_session.scalars(
                    select(
                        models.CriticalTerminologyVocabularyVersion
                    )
                    .where(
                        (
                            models
                            .CriticalTerminologyVocabularyVersion
                            .project_id
                        )
                        == project_id
                    )
                    .order_by(
                        (
                            models
                            .CriticalTerminologyVocabularyVersion
                            .revision
                        )
                    )
                )
            )

            assert len(versions) == 2

            assert [
                version.revision
                for version in versions
            ] == [1, 2]

            assert [
                version.profile_version
                for version in versions
            ] == ["1", "2"]

            assert (
                versions[0].profile_key
                == versions[1].profile_key
            )

            assert (
                versions[0].vocabulary_sha256
                != versions[1].vocabulary_sha256
            )

            first_profile = (
                build_profile_from_vocabulary_version(
                    versions[0]
                )
            )

            second_profile = (
                build_profile_from_vocabulary_version(
                    versions[1]
                )
            )

            assert first_profile.version == "1"
            assert second_profile.version == "2"

            assert (
                first_profile.key
                == second_profile.key
            )

        finally:
            verification_session.close()

    finally:
        if (
            first_session is not None
            and first_session.in_transaction()
        ):
            first_session.rollback()

        if first_session is not None:
            first_session.close()

        # If an assertion failed while the second transaction
        # was blocked, rolling back first_session above releases
        # its Project lock and allows the thread to terminate.
        if (
            second_thread is not None
            and second_thread.is_alive()
        ):
            second_thread.join(timeout=10)

        assert (
            second_thread is None
            or not second_thread.is_alive()
        ), "Second writer thread failed to terminate."

        _cleanup_committed_case(
            postgres_test_engine,
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
        )


def test_postgres_enforces_project_revision_uniqueness(
    postgres_session: Session,
) -> None:
    _, user_id, project_id = _create_case(
        postgres_session
    )

    first = (
        stage_critical_terminology_vocabulary_version(
            postgres_session,
            project_id=project_id,
            created_by_user_id=user_id,
            terms=_terms(
                term_key="cardiovex",
                canonical_text="Cardiovex",
            ),
        )
    )

    duplicate = (
        models.CriticalTerminologyVocabularyVersion(
            project_id=project_id,
            revision=first.revision,
            profile_schema_version=(
                first.profile_schema_version
            ),
            profile_key=first.profile_key,
            profile_version=first.profile_version,
            language=first.language,
            locale=first.locale,
            terms_snapshot=first.terms_snapshot,
            vocabulary_sha256=(
                first.vocabulary_sha256
            ),
            created_by_user_id=user_id,
        )
    )

    postgres_session.add(duplicate)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "revision": 0,
        },
        {
            "profile_schema_version": 0,
        },
        {
            "profile_key": "   ",
        },
        {
            "profile_version": "   ",
        },
        {
            "language": "   ",
        },
        {
            "locale": "   ",
        },
        {
            "vocabulary_sha256": "0" * 63,
        },
    ],
)
def test_postgres_enforces_vocabulary_check_constraints(
    postgres_session: Session,
    overrides: dict[str, object],
) -> None:
    _, user_id, project_id = _create_case(
        postgres_session
    )

    values: dict[str, object] = {
        "project_id": project_id,
        "revision": 1,
        "profile_schema_version": 1,
        "profile_key": (
            "project-critical-terminology-test"
        ),
        "profile_version": "1",
        "language": "en",
        "locale": "en-US",
        "terms_snapshot": [
            {
                "term_key": "cardiovex",
                "canonical_text": "Cardiovex",
                "accepted_surfaces": [
                    "Cardiovex",
                ],
            },
        ],
        "vocabulary_sha256": "0" * 64,
        "created_by_user_id": user_id,
    }

    values.update(overrides)

    invalid = (
        models.CriticalTerminologyVocabularyVersion(
            **values,
        )
    )

    postgres_session.add(invalid)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()
