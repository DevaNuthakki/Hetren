from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    datasets = relationship(
        "Dataset",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    runs = relationship(
        "EvaluationRun",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    debug_cases = relationship(
        "DebugCase",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    release_policies = relationship(
        "ReleasePolicy",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    release_reports = relationship(
        "ReleaseReport",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    runner_registration_tokens = relationship(
        "RunnerRegistrationToken",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    runners = relationship(
        "Runner",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    project = relationship("Project", back_populates="datasets")

    test_cases = relationship(
        "TestCase",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False, index=True)

    title = Column(String(300), nullable=False)
    audio_file_path = Column(String(500), nullable=True)
    reference_file_path = Column(String(500), nullable=True)
    reference_transcript = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    dataset = relationship("Dataset", back_populates="test_cases")

    evaluation_results = relationship(
        "EvaluationResult",
        back_populates="test_case",
        cascade="all, delete-orphan",
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    run_name = Column(String(200), nullable=False)
    model_name = Column(String(100), nullable=False, default="not_configured")
    status = Column(String(50), nullable=False, default="created")

    audio_file_path = Column(String(500), nullable=True)
    reference_transcript = Column(Text, nullable=True)
    generated_transcript = Column(Text, nullable=True)

    wer = Column(Float, nullable=True)
    cer = Column(Float, nullable=True)
    quality_label = Column(String(50), nullable=True)
    error_summary = Column(Text, nullable=True)

    latency_seconds = Column(Float, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    project = relationship("Project", back_populates="runs")

    evaluation_results = relationship(
        "EvaluationResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True)

    generated_transcript = Column(Text, nullable=False)
    generated_file_path = Column(String(500), nullable=True)

    wer = Column(Float, nullable=True)
    cer = Column(Float, nullable=True)
    quality_label = Column(String(50), nullable=True)
    error_summary = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    run = relationship("EvaluationRun", back_populates="evaluation_results")
    test_case = relationship("TestCase", back_populates="evaluation_results")


class RunComparison(Base):
    __tablename__ = "run_comparisons"

    id = Column(Integer, primary_key=True)

    baseline_run_id = Column(Integer, ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    current_run_id = Column(Integer, ForeignKey("evaluation_runs.id"), nullable=False, index=True)

    baseline_average_wer = Column(Float, nullable=True)
    current_average_wer = Column(Float, nullable=True)
    wer_delta = Column(Float, nullable=True)

    baseline_average_cer = Column(Float, nullable=True)
    current_average_cer = Column(Float, nullable=True)
    cer_delta = Column(Float, nullable=True)

    comparison_status = Column(String(50), nullable=False)
    summary = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    release_report = relationship(
        "ReleaseReport",
        back_populates="comparison",
        cascade="all, delete-orphan",
        uselist=False,
    )


class DebugCase(Base):
    __tablename__ = "debug_cases"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    title = Column(String(300), nullable=False)
    status = Column(String(50), nullable=False, default="open")
    severity = Column(String(50), nullable=False, default="medium")
    failure_type = Column(String(100), nullable=False, default="asr_regression")

    baseline_run_id = Column(Integer, ForeignKey("evaluation_runs.id"), nullable=True, index=True)
    current_run_id = Column(Integer, ForeignKey("evaluation_runs.id"), nullable=True, index=True)

    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True, index=True)
    baseline_result_id = Column(Integer, ForeignKey("evaluation_results.id"), nullable=True, index=True)
    current_result_id = Column(Integer, ForeignKey("evaluation_results.id"), nullable=True, index=True)

    summary = Column(Text, nullable=True)
    engineer_notes = Column(Text, nullable=True)
    ai_suggestion = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    project = relationship("Project", back_populates="debug_cases")


class ReleasePolicy(Base):
    __tablename__ = "release_policies"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False, default="Default release policy")
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    warn_current_wer = Column(Float, nullable=False, default=0.15)
    fail_current_wer = Column(Float, nullable=False, default=0.20)

    warn_current_cer = Column(Float, nullable=False, default=0.08)
    fail_current_cer = Column(Float, nullable=False, default=0.12)

    warn_wer_delta = Column(Float, nullable=False, default=0.01)
    fail_wer_delta = Column(Float, nullable=False, default=0.03)

    warn_cer_delta = Column(Float, nullable=False, default=0.005)
    fail_cer_delta = Column(Float, nullable=False, default=0.02)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    project = relationship("Project", back_populates="release_policies")
    release_reports = relationship(
        "ReleaseReport",
        back_populates="policy",
    )


class ReleaseReport(Base):
    __tablename__ = "release_reports"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    comparison_id = Column(
        Integer,
        ForeignKey("run_comparisons.id"),
        nullable=False,
        unique=True,
    )
    policy_id = Column(
        Integer,
        ForeignKey("release_policies.id"),
        nullable=True,
        index=True,
    )

    status = Column(String(50), nullable=False)
    severity = Column(String(50), nullable=False)

    headline = Column(String(300), nullable=False)
    summary = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)

    policy_snapshot = Column(JSON, nullable=False)
    checks = Column(JSON, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    project = relationship("Project", back_populates="release_reports")
    comparison = relationship(
        "RunComparison",
        back_populates="release_report",
    )
    policy = relationship(
        "ReleasePolicy",
        back_populates="release_reports",
    )


class RunnerRegistrationToken(Base):
    __tablename__ = "runner_registration_tokens"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "project_id",
            name="uq_runner_registration_tokens_id_project_id",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_runner_registration_tokens_expiry_after_creation",
        ),
        CheckConstraint(
            "NOT (consumed_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="ck_runner_registration_tokens_lifecycle",
        ),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    label = Column(
        String(200),
        nullable=False,
        default="Runner registration token",
    )
    token_hash = Column(
        String(64),
        nullable=False,
        unique=True,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    project = relationship(
        "Project",
        back_populates="runner_registration_tokens",
    )
    runner = relationship(
        "Runner",
        back_populates="registration_token",
        uselist=False,
        foreign_keys="Runner.registration_token_id",
    )


class Runner(Base):
    __tablename__ = "runners"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "name",
            name="uq_runners_project_name",
        ),
        ForeignKeyConstraint(
            ["registration_token_id", "project_id"],
            [
                "runner_registration_tokens.id",
                "runner_registration_tokens.project_id",
            ],
            name="fk_runners_registration_token_project",
        ),
        CheckConstraint(
            "(status = 'active' AND revoked_at IS NULL) OR "
            "(status = 'revoked' AND revoked_at IS NOT NULL)",
            name="ck_runners_status_matches_revocation",
        ),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    registration_token_id = Column(
        Integer,
        nullable=False,
        unique=True,
    )

    public_id = Column(
        String(36),
        nullable=False,
        unique=True,
    )
    name = Column(
        String(200),
        nullable=False,
    )
    status = Column(
        String(50),
        nullable=False,
        default="active",
    )

    runner_version = Column(
        String(100),
        nullable=True,
    )
    capabilities = Column(
        JSON,
        nullable=False,
        default=list,
    )
    system_info = Column(
        JSON,
        nullable=False,
        default=dict,
    )

    credential_hash = Column(
        String(64),
        nullable=False,
        unique=True,
    )

    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    project = relationship(
        "Project",
        back_populates="runners",
    )
    registration_token = relationship(
        "RunnerRegistrationToken",
        back_populates="runner",
        foreign_keys=[registration_token_id],
    )
