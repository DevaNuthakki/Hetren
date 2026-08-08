from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class HveeMetricDefinition(Base):
    __tablename__ = "hvee_metric_definitions"

    __table_args__ = (
        UniqueConstraint(
            "key",
            "version",
            name="uq_hvee_metric_definitions_key_version",
        ),
        CheckConstraint(
            (
                "value_type IN ("
                "'number', "
                "'integer', "
                "'boolean', "
                "'string', "
                "'json'"
                ")"
            ),
            name="ck_hvee_metric_definitions_value_type",
        ),
        CheckConstraint(
            (
                "direction IN ("
                "'lower_is_better', "
                "'higher_is_better', "
                "'target_is_better', "
                "'informational'"
                ")"
            ),
            name="ck_hvee_metric_definitions_direction",
        ),
        CheckConstraint(
            "length(trim(key)) > 0",
            name="ck_hvee_metric_definitions_key_not_blank",
        ),
        CheckConstraint(
            "length(trim(version)) > 0",
            name="ck_hvee_metric_definitions_version_not_blank",
        ),
        CheckConstraint(
            "length(trim(evaluation_type)) > 0",
            name="ck_hvee_metric_definitions_evaluation_type_not_blank",
        ),
        CheckConstraint(
            "length(trim(description)) > 0",
            name="ck_hvee_metric_definitions_description_not_blank",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
    )

    key = Column(
        String(128),
        nullable=False,
    )
    version = Column(
        String(100),
        nullable=False,
    )
    evaluation_type = Column(
        String(50),
        nullable=False,
        index=True,
    )

    value_type = Column(
        String(32),
        nullable=False,
    )
    direction = Column(
        String(32),
        nullable=False,
    )

    unit = Column(
        String(64),
        nullable=True,
    )
    description = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class HveeEvaluatorVersion(Base):
    __tablename__ = "hvee_evaluator_versions"

    __table_args__ = (
        UniqueConstraint(
            "key",
            "version",
            name="uq_hvee_evaluator_versions_key_version",
        ),
        CheckConstraint(
            "length(trim(key)) > 0",
            name="ck_hvee_evaluator_versions_key_not_blank",
        ),
        CheckConstraint(
            "length(trim(version)) > 0",
            name="ck_hvee_evaluator_versions_version_not_blank",
        ),
        CheckConstraint(
            "length(trim(evaluation_type)) > 0",
            name="ck_hvee_evaluator_versions_evaluation_type_not_blank",
        ),
        CheckConstraint(
            "length(trim(description)) > 0",
            name="ck_hvee_evaluator_versions_description_not_blank",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
    )

    key = Column(
        String(128),
        nullable=False,
    )
    version = Column(
        String(100),
        nullable=False,
    )
    evaluation_type = Column(
        String(50),
        nullable=False,
        index=True,
    )

    description = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
