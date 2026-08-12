"""Project-owned Critical Terminology vocabulary persistence.

This module is the application boundary between customer/project
configuration and the HVEE Critical Terminology scientific contract.

Vocabulary revisions are immutable and append-only. The application does
not duplicate HVEE terminology validation or hashing rules: submitted terms
are converted into the canonical HVEE profile first, and HVEE owns both
validation and vocabulary identity.

Transaction ownership remains with the caller. This service may flush staged
rows so database constraints are enforced, but it never commits.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_terminology_fidelity import (
    CRITICAL_TERMINOLOGY_PROFILE_SCHEMA_VERSION,
    ASRCriticalTerminologyProfile,
    ASRCriticalTerminologyTerm,
    calculate_critical_terminology_vocabulary_sha256,
)


CRITICAL_TERMINOLOGY_LANGUAGE = "en"
CRITICAL_TERMINOLOGY_LOCALE = "en-US"

_TERM_FIELDS = frozenset(
    {
        "term_key",
        "canonical_text",
        "accepted_surfaces",
    }
)


class CriticalTerminologyVocabularyValidationError(
    ValueError
):
    """Raised when submitted vocabulary violates the HVEE contract."""


class CriticalTerminologyVocabularyProjectNotFoundError(
    LookupError
):
    """Raised when the requested project does not exist."""


class CriticalTerminologyVocabularyIntegrityError(
    RuntimeError
):
    """Raised when persisted vocabulary evidence cannot be verified."""


def _build_terms(
    terms: Sequence[Mapping[str, object]],
) -> tuple[ASRCriticalTerminologyTerm, ...]:
    if (
        isinstance(terms, (str, bytes))
        or not isinstance(terms, Sequence)
        or not terms
    ):
        raise CriticalTerminologyVocabularyValidationError(
            "critical terminology vocabulary requires terms"
        )

    built_terms: list[
        ASRCriticalTerminologyTerm
    ] = []

    for index, raw_term in enumerate(terms):
        if not isinstance(raw_term, Mapping):
            raise CriticalTerminologyVocabularyValidationError(
                "critical terminology term "
                f"{index} must be an object"
            )

        fields = frozenset(raw_term.keys())

        if fields != _TERM_FIELDS:
            missing = sorted(
                _TERM_FIELDS - fields
            )
            unexpected = sorted(
                fields - _TERM_FIELDS
            )

            details: list[str] = []

            if missing:
                details.append(
                    "missing="
                    + ",".join(missing)
                )

            if unexpected:
                details.append(
                    "unexpected="
                    + ",".join(
                        str(value)
                        for value in unexpected
                    )
                )

            suffix = (
                " (" + "; ".join(details) + ")"
                if details
                else ""
            )

            raise (
                CriticalTerminologyVocabularyValidationError(
                    "critical terminology term "
                    f"{index} has invalid fields"
                    f"{suffix}"
                )
            )

        accepted_surfaces = raw_term[
            "accepted_surfaces"
        ]

        if (
            isinstance(
                accepted_surfaces,
                (str, bytes),
            )
            or not isinstance(
                accepted_surfaces,
                Sequence,
            )
        ):
            raise CriticalTerminologyVocabularyValidationError(
                "critical terminology term "
                f"{index} accepted_surfaces "
                "must be an array"
            )

        try:
            built_term = (
                ASRCriticalTerminologyTerm(
                    term_key=raw_term[
                        "term_key"
                    ],
                    canonical_text=raw_term[
                        "canonical_text"
                    ],
                    accepted_surfaces=tuple(
                        accepted_surfaces
                    ),
                )
            )
        except HveeContractError as exc:
            raise (
                CriticalTerminologyVocabularyValidationError(
                    str(exc)
                )
            ) from exc

        built_terms.append(
            built_term
        )

    return tuple(built_terms)


def build_critical_terminology_profile(
    *,
    profile_key: str,
    profile_version: str,
    terms: Sequence[Mapping[str, object]],
) -> ASRCriticalTerminologyProfile:
    """Build and validate the exact HVEE terminology profile."""

    built_terms = _build_terms(terms)

    try:
        return ASRCriticalTerminologyProfile(
            key=profile_key,
            version=profile_version,
            language=(
                CRITICAL_TERMINOLOGY_LANGUAGE
            ),
            locale=(
                CRITICAL_TERMINOLOGY_LOCALE
            ),
            terms=built_terms,
        )
    except HveeContractError as exc:
        raise (
            CriticalTerminologyVocabularyValidationError(
                str(exc)
            )
        ) from exc


def _terms_snapshot(
    profile: ASRCriticalTerminologyProfile,
) -> list[dict[str, object]]:
    return [
        term.to_json()
        for term in profile.terms
    ]


def build_profile_from_vocabulary_version(
    vocabulary: (
        models.CriticalTerminologyVocabularyVersion
    ),
) -> ASRCriticalTerminologyProfile:
    """
    Reconstruct and verify one persisted vocabulary revision.

    This is intentionally strict. A stored row that no longer reproduces
    its recorded HVEE vocabulary SHA-256 is treated as corrupted evidence,
    not silently accepted.
    """

    if (
        vocabulary.profile_schema_version
        != CRITICAL_TERMINOLOGY_PROFILE_SCHEMA_VERSION
    ):
        raise CriticalTerminologyVocabularyIntegrityError(
            "unsupported critical terminology "
            "profile schema version"
        )

    try:
        profile = build_critical_terminology_profile(
            profile_key=vocabulary.profile_key,
            profile_version=(
                vocabulary.profile_version
            ),
            terms=vocabulary.terms_snapshot,
        )
    except (
        CriticalTerminologyVocabularyValidationError
    ) as exc:
        raise CriticalTerminologyVocabularyIntegrityError(
            "persisted critical terminology "
            "vocabulary is invalid"
        ) from exc

    if (
        profile.language
        != vocabulary.language
        or profile.locale
        != vocabulary.locale
    ):
        raise CriticalTerminologyVocabularyIntegrityError(
            "persisted critical terminology "
            "language or locale does not match "
            "the reconstructed HVEE profile"
        )

    calculated_sha256 = (
        calculate_critical_terminology_vocabulary_sha256(
            profile
        )
    )

    if (
        calculated_sha256
        != vocabulary.vocabulary_sha256
    ):
        raise CriticalTerminologyVocabularyIntegrityError(
            "persisted critical terminology "
            "vocabulary SHA-256 does not verify"
        )

    return profile


def _lock_project(
    db: Session,
    *,
    project_id: int,
) -> models.Project:
    """
    Lock the owning project while allocating the next revision.

    PostgreSQL writers using this service serialize on the project row,
    preventing ordinary concurrent vocabulary writers from allocating the
    same project-local revision.
    """

    project = db.scalar(
        select(models.Project)
        .where(
            models.Project.id == project_id
        )
        .with_for_update()
    )

    if project is None:
        raise (
            CriticalTerminologyVocabularyProjectNotFoundError(
                "project does not exist"
            )
        )

    return project


def _current_vocabulary_version(
    db: Session,
    *,
    project_id: int,
) -> (
    models.CriticalTerminologyVocabularyVersion
    | None
):
    return db.scalar(
        select(
            models.CriticalTerminologyVocabularyVersion
        )
        .where(
            models.CriticalTerminologyVocabularyVersion
            .project_id
            == project_id
        )
        .order_by(
            models.CriticalTerminologyVocabularyVersion
            .revision
            .desc()
        )
        .limit(1)
    )


def stage_critical_terminology_vocabulary_version(
    db: Session,
    *,
    project_id: int,
    created_by_user_id: int,
    terms: Sequence[Mapping[str, object]],
) -> models.CriticalTerminologyVocabularyVersion:
    """
    Validate and stage the next immutable project vocabulary revision.

    The caller owns commit/rollback.
    """

    project = _lock_project(
        db,
        project_id=project_id,
    )

    current = _current_vocabulary_version(
        db,
        project_id=project.id,
    )

    if current is None:
        revision = 1
        profile_key = (
            "project-critical-terminology-"
            + uuid4().hex
        )
    else:
        # Refuse to build new evidence on top of a corrupted or
        # unsupported historical current revision.
        build_profile_from_vocabulary_version(
            current
        )

        revision = current.revision + 1
        profile_key = current.profile_key

    profile_version = str(revision)

    profile = build_critical_terminology_profile(
        profile_key=profile_key,
        profile_version=profile_version,
        terms=terms,
    )

    vocabulary_sha256 = (
        calculate_critical_terminology_vocabulary_sha256(
            profile
        )
    )

    vocabulary = (
        models.CriticalTerminologyVocabularyVersion(
            project_id=project.id,
            revision=revision,
            profile_schema_version=(
                CRITICAL_TERMINOLOGY_PROFILE_SCHEMA_VERSION
            ),
            profile_key=profile.key,
            profile_version=profile.version,
            language=profile.language,
            locale=profile.locale,
            terms_snapshot=_terms_snapshot(
                profile
            ),
            vocabulary_sha256=(
                vocabulary_sha256
            ),
            created_by_user_id=(
                created_by_user_id
            ),
        )
    )

    db.add(vocabulary)
    db.flush()

    return vocabulary


def list_critical_terminology_vocabulary_versions(
    db: Session,
    *,
    project_id: int,
) -> list[
    models.CriticalTerminologyVocabularyVersion
]:
    """
    List immutable vocabulary history in revision order.

    Persisted rows are verified against the HVEE scientific contract before
    they are returned.
    """

    vocabularies = list(
        db.scalars(
            select(
                models.CriticalTerminologyVocabularyVersion
            )
            .where(
                models.CriticalTerminologyVocabularyVersion
                .project_id
                == project_id
            )
            .order_by(
                models.CriticalTerminologyVocabularyVersion
                .revision
                .asc()
            )
        ).all()
    )

    for vocabulary in vocabularies:
        build_profile_from_vocabulary_version(
            vocabulary
        )

    return vocabularies


def get_current_critical_terminology_vocabulary_version(
    db: Session,
    *,
    project_id: int,
) -> (
    models.CriticalTerminologyVocabularyVersion
    | None
):
    """Return and verify the latest project vocabulary revision."""

    vocabulary = _current_vocabulary_version(
        db,
        project_id=project_id,
    )

    if vocabulary is not None:
        build_profile_from_vocabulary_version(
            vocabulary
        )

    return vocabulary


def get_critical_terminology_vocabulary_version(
    db: Session,
    *,
    project_id: int,
    revision: int,
) -> (
    models.CriticalTerminologyVocabularyVersion
    | None
):
    """Return and verify one exact historical vocabulary revision."""

    vocabulary = db.scalar(
        select(
            models.CriticalTerminologyVocabularyVersion
        )
        .where(
            models.CriticalTerminologyVocabularyVersion
            .project_id
            == project_id,
            models.CriticalTerminologyVocabularyVersion
            .revision
            == revision,
        )
    )

    if vocabulary is not None:
        build_profile_from_vocabulary_version(
            vocabulary
        )

    return vocabulary
