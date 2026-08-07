from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Index,
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


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    memberships = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    projects = relationship(
        "Project",
        back_populates="organization",
        passive_deletes="all",
    )


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        sa.UniqueConstraint(
            "email",
            name="uq_users_email",
        ),
        sa.CheckConstraint(
            "email = lower(trim(email))",
            name="ck_users_email_normalized",
        ),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(320), nullable=False)
    display_name = Column(String(200), nullable=True)
    password_hash = Column(String(255), nullable=True)
    is_active = Column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    memberships = relationship(
        "OrganizationMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_sessions = relationship(
        "RefreshSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    __table_args__ = (
        sa.UniqueConstraint(
            "token_hash",
            name="uq_refresh_sessions_token_hash",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_refresh_sessions_expiry_after_creation",
        ),
        sa.CheckConstraint(
            (
                "replaced_by_session_id IS NULL "
                "OR revoked_at IS NOT NULL"
            ),
            name="ck_refresh_sessions_replacement_requires_revocation",
        ),
        sa.CheckConstraint(
            (
                "replaced_by_session_id IS NULL "
                "OR replaced_by_session_id != id"
            ),
            name="ck_refresh_sessions_cannot_replace_self",
        ),
        sa.Index(
            "ix_refresh_sessions_user_id",
            "user_id",
        ),
        sa.Index(
            "ix_refresh_sessions_family_id",
            "family_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id = Column(
        String(36),
        nullable=False,
        default=lambda: str(uuid4()),
    )
    token_hash = Column(
        String(64),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_session_id = Column(
        Integer,
        ForeignKey(
            "refresh_sessions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="refresh_sessions",
    )
    replaced_by_session = relationship(
        "RefreshSession",
        remote_side=[id],
        foreign_keys=[replaced_by_session_id],
        post_update=True,
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name=(
                "uq_organization_memberships_"
                "organization_id_user_id"
            ),
        ),
        sa.CheckConstraint(
            (
                "role IN ("
                "'owner', "
                "'admin', "
                "'engineer', "
                "'viewer', "
                "'billing_admin'"
                ")"
            ),
            name="ck_organization_memberships_role",
        ),
        sa.Index(
            "ix_organization_memberships_user_id",
            "user_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer,
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    role = Column(String(32), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    organization = relationship(
        "Organization",
        back_populates="memberships",
    )
    user = relationship(
        "User",
        back_populates="memberships",
    )


class Project(Base):
    __tablename__ = "projects"


    organization_id = Column(
        Integer,
        ForeignKey(
            "organizations.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    organization = relationship(
        "Organization",
        back_populates="projects",
    )

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

    runner_jobs = relationship(
        "RunnerJob",
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

    manifest = relationship(
        "EvaluationRunManifest",
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
        single_parent=True,
    )


class EvaluationRunManifest(Base):
    __tablename__ = "evaluation_run_manifests"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            name="uq_evaluation_run_manifests_run_id",
        ),
        CheckConstraint(
            "schema_version >= 1",
            name=(
                "ck_evaluation_run_manifests_"
                "positive_schema_version"
            ),
        ),
        CheckConstraint(
            "length(manifest_sha256) = 64",
            name=(
                "ck_evaluation_run_manifests_"
                "sha256_length"
            ),
        ),
    )

    id = Column(Integer, primary_key=True)

    run_id = Column(
        Integer,
        ForeignKey(
            "evaluation_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    schema_version = Column(
        Integer,
        nullable=False,
    )
    evaluation_type = Column(
        String(50),
        nullable=False,
    )

    manifest_payload = Column(
        JSON,
        nullable=False,
    )
    manifest_sha256 = Column(
        String(64),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    run = relationship(
        "EvaluationRun",
        back_populates="manifest",
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "test_case_id",
            name="uq_evaluation_results_run_test_case",
        ),
    )

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

    provenance = relationship(
        "EvaluationResultProvenance",
        back_populates="result",
        cascade="all, delete-orphan",
        uselist=False,
        single_parent=True,
    )


class EvaluationResultProvenance(Base):
    __tablename__ = "evaluation_result_provenances"
    __table_args__ = (
        UniqueConstraint(
            "result_id",
            name="uq_evaluation_result_provenances_result_id",
        ),
        CheckConstraint(
            "schema_version >= 1",
            name=(
                "ck_evaluation_result_provenances_"
                "positive_schema_version"
            ),
        ),
        CheckConstraint(
            "length(provenance_sha256) = 64",
            name=(
                "ck_evaluation_result_provenances_"
                "sha256_length"
            ),
        ),
    )

    id = Column(Integer, primary_key=True)

    result_id = Column(
        Integer,
        ForeignKey(
            "evaluation_results.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    schema_version = Column(
        Integer,
        nullable=False,
    )
    evaluation_type = Column(
        String(50),
        nullable=False,
    )
    execution_mode = Column(
        String(50),
        nullable=False,
    )

    provenance_payload = Column(
        JSON,
        nullable=False,
    )
    provenance_sha256 = Column(
        String(64),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    result = relationship(
        "EvaluationResult",
        back_populates="provenance",
    )


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
            "id",
            "project_id",
            name="uq_runners_id_project_id",
        ),
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

    assigned_jobs = relationship(
        "RunnerJob",
        back_populates="assigned_runner",
        foreign_keys="RunnerJob.assigned_runner_id",
    )

    job_logs = relationship(
        "RunnerJobLog",
        back_populates="runner",
        foreign_keys="RunnerJobLog.runner_id",
    )


class RunnerJob(Base):
    __tablename__ = "runner_jobs"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "project_id",
            name="uq_runner_jobs_id_project_id",
        ),
        ForeignKeyConstraint(
            ["assigned_runner_id", "project_id"],
            ["runners.id", "runners.project_id"],
            name="fk_runner_jobs_assigned_runner_project",
        ),
        CheckConstraint(
            "status IN ("
            "'queued', "
            "'claimed', "
            "'running', "
            "'completed', "
            "'failed', "
            "'cancelled'"
            ")",
            name="ck_runner_jobs_valid_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 "
            "AND max_attempts >= 1 "
            "AND attempt_count <= max_attempts",
            name="ck_runner_jobs_valid_attempt_counts",
        ),
        CheckConstraint(
            "("
            "status = 'queued' "
            "AND assigned_runner_id IS NULL "
            "AND claimed_at IS NULL "
            "AND lease_expires_at IS NULL "
            "AND claim_token_hash IS NULL "
            "AND started_at IS NULL "
            "AND completed_at IS NULL "
            "AND failed_at IS NULL "
            "AND cancelled_at IS NULL "
            "AND result_payload IS NULL "
            "AND error_message IS NULL"
            ") OR ("
            "status = 'claimed' "
            "AND assigned_runner_id IS NOT NULL "
            "AND claimed_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL "
            "AND claim_token_hash IS NOT NULL "
            "AND started_at IS NULL "
            "AND completed_at IS NULL "
            "AND failed_at IS NULL "
            "AND cancelled_at IS NULL "
            "AND result_payload IS NULL "
            "AND error_message IS NULL"
            ") OR ("
            "status = 'running' "
            "AND assigned_runner_id IS NOT NULL "
            "AND claimed_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL "
            "AND claim_token_hash IS NOT NULL "
            "AND started_at IS NOT NULL "
            "AND completed_at IS NULL "
            "AND failed_at IS NULL "
            "AND cancelled_at IS NULL "
            "AND result_payload IS NULL "
            "AND error_message IS NULL"
            ") OR ("
            "status = 'completed' "
            "AND assigned_runner_id IS NOT NULL "
            "AND claimed_at IS NOT NULL "
            "AND lease_expires_at IS NULL "
            "AND claim_token_hash IS NULL "
            "AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL "
            "AND failed_at IS NULL "
            "AND cancelled_at IS NULL "
            "AND error_message IS NULL"
            ") OR ("
            "status = 'failed' "
            "AND assigned_runner_id IS NOT NULL "
            "AND claimed_at IS NOT NULL "
            "AND lease_expires_at IS NULL "
            "AND claim_token_hash IS NULL "
            "AND completed_at IS NULL "
            "AND failed_at IS NOT NULL "
            "AND cancelled_at IS NULL "
            "AND error_message IS NOT NULL"
            ") OR ("
            "status = 'cancelled' "
            "AND lease_expires_at IS NULL "
            "AND claim_token_hash IS NULL "
            "AND completed_at IS NULL "
            "AND failed_at IS NULL "
            "AND cancelled_at IS NOT NULL "
            "AND ("
            "("
            "assigned_runner_id IS NULL "
            "AND claimed_at IS NULL "
            "AND started_at IS NULL"
            ") OR ("
            "assigned_runner_id IS NOT NULL "
            "AND claimed_at IS NOT NULL"
            ")"
            ")"
            ")",
            name="ck_runner_jobs_lifecycle",
        ),
        Index(
            "ix_runner_jobs_queue_poll",
            "project_id",
            "status",
            "available_at",
            "priority",
        ),
        Index(
            "ix_runner_jobs_assigned_status",
            "assigned_runner_id",
            "status",
        ),
    )

    id = Column(Integer, primary_key=True)
    public_id = Column(
        String(36),
        nullable=False,
        unique=True,
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
    )
    assigned_runner_id = Column(
        Integer,
        nullable=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )
    job_type = Column(
        String(100),
        nullable=False,
    )
    status = Column(
        String(50),
        nullable=False,
        default="queued",
    )
    priority = Column(
        Integer,
        nullable=False,
        default=0,
    )

    required_capabilities = Column(
        JSON,
        nullable=False,
        default=list,
    )
    input_payload = Column(
        JSON,
        nullable=False,
        default=dict,
    )
    result_payload = Column(
        JSON(none_as_null=True),
        nullable=True,
    )
    error_message = Column(
        Text,
        nullable=True,
    )

    attempt_count = Column(
        Integer,
        nullable=False,
        default=0,
    )
    max_attempts = Column(
        Integer,
        nullable=False,
        default=3,
    )

    claim_token_hash = Column(
        String(64),
        nullable=True,
        unique=True,
    )

    available_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    claimed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    lease_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    failed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at = Column(
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
        back_populates="runner_jobs",
    )
    assigned_runner = relationship(
        "Runner",
        back_populates="assigned_jobs",
        foreign_keys=[assigned_runner_id],
    )

    logs = relationship(
        "RunnerJobLog",
        back_populates="job",
        foreign_keys="RunnerJobLog.job_id",
        cascade="all, delete-orphan",
        order_by="RunnerJobLog.sequence_number",
    )


class RunnerJobLog(Base):
    __tablename__ = "runner_job_logs"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "sequence_number",
            name="uq_runner_job_logs_job_sequence",
        ),
        ForeignKeyConstraint(
            ["job_id", "project_id"],
            ["runner_jobs.id", "runner_jobs.project_id"],
            name="fk_runner_job_logs_job_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["runner_id", "project_id"],
            ["runners.id", "runners.project_id"],
            name="fk_runner_job_logs_runner_project",
        ),
        CheckConstraint(
            "sequence_number >= 1",
            name="ck_runner_job_logs_positive_sequence",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_runner_job_logs_positive_attempt",
        ),
        CheckConstraint(
            "level IN ("
            "'debug', "
            "'info', "
            "'warning', "
            "'error'"
            ")",
            name="ck_runner_job_logs_valid_level",
        ),
        CheckConstraint(
            "length(message) >= 1 "
            "AND length(message) <= 10000",
            name="ck_runner_job_logs_valid_message_length",
        ),
        Index(
            "ix_runner_job_logs_project_created",
            "project_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True)
    public_id = Column(
        String(36),
        nullable=False,
        unique=True,
    )

    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
    )
    job_id = Column(
        Integer,
        nullable=False,
    )
    runner_id = Column(
        Integer,
        nullable=False,
    )

    sequence_number = Column(
        Integer,
        nullable=False,
    )
    attempt_number = Column(
        Integer,
        nullable=False,
    )

    level = Column(
        String(20),
        nullable=False,
    )
    event_type = Column(
        String(100),
        nullable=False,
    )
    message = Column(
        Text,
        nullable=False,
    )
    context_payload = Column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    job = relationship(
        "RunnerJob",
        back_populates="logs",
        foreign_keys=[job_id],
    )
    runner = relationship(
        "Runner",
        back_populates="job_logs",
        foreign_keys=[runner_id],
    )
