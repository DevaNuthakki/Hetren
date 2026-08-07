from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
)
from app.database import Base


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


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _create_user(
    db_session: Session,
    *,
    email: str,
) -> models.User:
    user = models.User(email=email)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_refresh_session(
    db_session: Session,
    *,
    user: models.User,
    token_hash: str | None = None,
) -> object:
    created_at = _now()
    session = models.RefreshSession(
        user_id=user.id,
        token_hash=(
            token_hash
            or hash_refresh_token(generate_refresh_token())
        ),
        created_at=created_at,
        expires_at=created_at + timedelta(days=30),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def test_existing_user_can_remain_without_password_hash(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="existing-user@example.com",
    )

    assert user.password_hash is None


def test_user_can_store_password_hash(
    db_session: Session,
) -> None:
    password_hash = hash_password("Hetren-secure-password-123")
    user = models.User(
        email="password-user@example.com",
        password_hash=password_hash,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.password_hash == password_hash


def test_refresh_session_stores_only_token_hash_and_belongs_to_user(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="refresh-owner@example.com",
    )
    plaintext_token = generate_refresh_token()
    session = _create_refresh_session(
        db_session,
        user=user,
        token_hash=hash_refresh_token(plaintext_token),
    )

    assert session.user_id == user.id
    assert session.user is user
    assert session in user.refresh_sessions
    assert session.token_hash == hash_refresh_token(plaintext_token)
    assert session.token_hash != plaintext_token
    assert not hasattr(session, "token")
    assert session.revoked_at is None
    assert session.replaced_by_session_id is None


def test_refresh_session_token_hash_is_unique(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="unique-refresh@example.com",
    )
    shared_hash = hash_refresh_token(generate_refresh_token())
    _create_refresh_session(
        db_session,
        user=user,
        token_hash=shared_hash,
    )
    created_at = _now()
    duplicate = models.RefreshSession(
        user_id=user.id,
        token_hash=shared_hash,
        created_at=created_at,
        expires_at=created_at + timedelta(days=30),
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_refresh_session_expiry_must_follow_creation(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="invalid-expiry@example.com",
    )
    created_at = _now()
    session = models.RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(generate_refresh_token()),
        created_at=created_at,
        expires_at=created_at,
    )
    db_session.add(session)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_refresh_session_replacement_requires_revocation(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="unrevoked-rotation@example.com",
    )
    original = _create_refresh_session(
        db_session,
        user=user,
    )
    replacement = _create_refresh_session(
        db_session,
        user=user,
    )

    original.replaced_by_session_id = replacement.id

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_refresh_session_cannot_replace_itself(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="self-replacement@example.com",
    )
    session = _create_refresh_session(
        db_session,
        user=user,
    )
    session.revoked_at = _now()
    session.replaced_by_session_id = session.id

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_refresh_session_records_rotation_chain(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="rotation-chain@example.com",
    )
    original = _create_refresh_session(
        db_session,
        user=user,
    )
    replacement = _create_refresh_session(
        db_session,
        user=user,
    )

    original.revoked_at = _now()
    original.replaced_by_session_id = replacement.id
    db_session.commit()
    db_session.refresh(original)

    assert original.revoked_at is not None
    assert original.replaced_by_session_id == replacement.id


def test_deleting_user_deletes_refresh_sessions(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="deleted-user@example.com",
    )
    session = _create_refresh_session(
        db_session,
        user=user,
    )
    session_id = session.id

    db_session.delete(user)
    db_session.commit()

    assert db_session.get(models.RefreshSession, session_id) is None
