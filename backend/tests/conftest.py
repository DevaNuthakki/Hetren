from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.config import get_settings


@pytest.fixture(scope="session")
def postgres_test_engine() -> Generator[Engine, None, None]:
    settings = get_settings()

    if settings.test_database_url is None:
        pytest.fail("TEST_DATABASE_URL is not configured.")

    database_url = make_url(settings.test_database_url)

    if database_url.get_backend_name() != "postgresql":
        pytest.fail(
            "PostgreSQL integration tests require a PostgreSQL URL."
        )

    if database_url.database != "ovrin_test":
        pytest.fail(
            "Safety check failed: TEST_DATABASE_URL must use ovrin_test."
        )

    engine = create_engine(
        settings.test_database_url,
        pool_pre_ping=True,
    )

    with engine.connect() as connection:
        actual_database = connection.scalar(
            text("SELECT current_database()")
        )

    if actual_database != "ovrin_test":
        engine.dispose()
        pytest.fail(
            "Safety check failed: connected database is "
            f"{actual_database!r}, not 'ovrin_test'."
        )

    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session(
    postgres_test_engine: Engine,
) -> Generator[Session, None, None]:
    connection = postgres_test_engine.connect()
    outer_transaction = connection.begin()

    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()

        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()
