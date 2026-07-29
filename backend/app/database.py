from collections.abc import Generator
from typing import Any

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings


settings = get_settings()


def create_database_engine() -> Engine:
    engine_options: dict[str, Any] = {
        "pool_pre_ping": True,
        "echo": settings.database_echo,
    }

    # Temporary compatibility for isolated SQLite tests or migration tools.
    # Development, CI, staging, and production will use PostgreSQL.
    if settings.database_url.startswith("sqlite"):
        engine_options["connect_args"] = {
            "check_same_thread": False,
        }

    return create_engine(
        settings.database_url,
        **engine_options,
    )


engine = create_database_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": (
        "fk_%(table_name)s_%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}

Base = declarative_base(
    metadata=MetaData(naming_convention=NAMING_CONVENTION),
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
