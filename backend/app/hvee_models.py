from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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



class HveeObservation(Base):
    __tablename__ = "hvee_observations"

    __table_args__ = (
        Index(
            "uq_hvee_observations_run_metric_evaluator",
            "evaluation_run_id",
            "metric_definition_id",
            "evaluator_version_id",
            unique=True,
            postgresql_where=text("scope = 'run'"),
            sqlite_where=text("scope = 'run'"),
        ),
        Index(
            "uq_hvee_observations_test_case_metric_evaluator",
            "evaluation_run_id",
            "test_case_id",
            "metric_definition_id",
            "evaluator_version_id",
            unique=True,
            postgresql_where=text("scope = 'test_case'"),
            sqlite_where=text("scope = 'test_case'"),
        ),
        CheckConstraint(
            (
                "scope IN ("
                "'run', "
                "'test_case'"
                ")"
            ),
            name="ck_hvee_observations_scope",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'success', "
                "'abstained', "
                "'unsupported', "
                "'timed_out', "
                "'failed', "
                "'cancelled', "
                "'invalid'"
                ")"
            ),
            name="ck_hvee_observations_status",
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
            name="ck_hvee_observations_value_type",
        ),
        CheckConstraint(
            (
                "(scope = 'run' AND test_case_id IS NULL) "
                "OR "
                "(scope = 'test_case' AND test_case_id IS NOT NULL)"
            ),
            name="ck_hvee_observations_scope_target",
        ),
        CheckConstraint(
            """
            (
                status = 'success'
                AND
                (
                    (
                        value_type = 'number'
                        AND number_value IS NOT NULL
                        AND integer_value IS NULL
                        AND boolean_value IS NULL
                        AND string_value IS NULL
                        AND json_value IS NULL
                    )
                    OR
                    (
                        value_type = 'integer'
                        AND number_value IS NULL
                        AND integer_value IS NOT NULL
                        AND boolean_value IS NULL
                        AND string_value IS NULL
                        AND json_value IS NULL
                    )
                    OR
                    (
                        value_type = 'boolean'
                        AND number_value IS NULL
                        AND integer_value IS NULL
                        AND boolean_value IS NOT NULL
                        AND string_value IS NULL
                        AND json_value IS NULL
                    )
                    OR
                    (
                        value_type = 'string'
                        AND number_value IS NULL
                        AND integer_value IS NULL
                        AND boolean_value IS NULL
                        AND string_value IS NOT NULL
                        AND json_value IS NULL
                    )
                    OR
                    (
                        value_type = 'json'
                        AND number_value IS NULL
                        AND integer_value IS NULL
                        AND boolean_value IS NULL
                        AND string_value IS NULL
                        AND json_value IS NOT NULL
                    )
                )
            )
            OR
            (
                status <> 'success'
                AND number_value IS NULL
                AND integer_value IS NULL
                AND boolean_value IS NULL
                AND string_value IS NULL
                AND json_value IS NULL
                AND status_detail IS NOT NULL
                AND length(trim(status_detail)) > 0
            )
            """,
            name="ck_hvee_observations_status_value",
        ),
        CheckConstraint(
            "length(trim(evaluation_type)) > 0",
            name=(
                "ck_hvee_observations_"
                "evaluation_type_not_blank"
            ),
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
    )

    evaluation_run_id = Column(
        Integer,
        ForeignKey(
            "evaluation_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    test_case_id = Column(
        Integer,
        ForeignKey(
            "test_cases.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    metric_definition_id = Column(
        Integer,
        ForeignKey(
            "hvee_metric_definitions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    evaluator_version_id = Column(
        Integer,
        ForeignKey(
            "hvee_evaluator_versions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    evaluation_type = Column(
        String(50),
        nullable=False,
        index=True,
    )

    scope = Column(
        String(32),
        nullable=False,
    )

    status = Column(
        String(32),
        nullable=False,
    )

    value_type = Column(
        String(32),
        nullable=False,
    )

    number_value = Column(
        Float,
        nullable=True,
    )

    integer_value = Column(
        BigInteger,
        nullable=True,
    )

    boolean_value = Column(
        Boolean,
        nullable=True,
    )

    string_value = Column(
        Text,
        nullable=True,
    )

    json_value = Column(
        JSON(none_as_null=True),
        nullable=True,
    )

    status_detail = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class HveeDecision(Base):
    """
    Persisted HVEE decision bound to one immutable result provenance.

    The row stores queryable decision summaries plus a deterministic
    decision payload and digest. Scientific evidence itself remains
    owned by EvaluationResultProvenance rather than being duplicated
    here.
    """

    __tablename__ = "hvee_decisions"

    __table_args__ = (
        UniqueConstraint(
            "result_provenance_id",
            "policy_sha256",
            "schema_version",
            name=(
                "uq_hvee_decisions_"
                "provenance_policy_schema"
            ),
        ),
        CheckConstraint(
            "schema_version >= 1",
            name=(
                "ck_hvee_decisions_"
                "positive_schema_version"
            ),
        ),
        CheckConstraint(
            "length(trim(evaluation_type)) > 0",
            name=(
                "ck_hvee_decisions_"
                "evaluation_type_not_blank"
            ),
        ),
        CheckConstraint(
            "length(trim(policy_key)) > 0",
            name=(
                "ck_hvee_decisions_"
                "policy_key_not_blank"
            ),
        ),
        CheckConstraint(
            "length(trim(policy_version)) > 0",
            name=(
                "ck_hvee_decisions_"
                "policy_version_not_blank"
            ),
        ),
        CheckConstraint(
            "length(policy_sha256) = 64",
            name=(
                "ck_hvee_decisions_"
                "policy_sha256_length"
            ),
        ),
        CheckConstraint(
            "length(provenance_sha256) = 64",
            name=(
                "ck_hvee_decisions_"
                "provenance_sha256_length"
            ),
        ),
        CheckConstraint(
            "length(observation_evidence_sha256) = 64",
            name=(
                "ck_hvee_decisions_"
                "observation_evidence_sha256_length"
            ),
        ),
        CheckConstraint(
            (
                "integrity_assessment IN ("
                "'valid', "
                "'invalid'"
                ")"
            ),
            name=(
                "ck_hvee_decisions_"
                "integrity_assessment"
            ),
        ),
        CheckConstraint(
            (
                "evidence_assessment IN ("
                "'sufficient', "
                "'insufficient'"
                ")"
            ),
            name=(
                "ck_hvee_decisions_"
                "evidence_assessment"
            ),
        ),
        CheckConstraint(
            (
                "critical_assessment IN ("
                "'clear', "
                "'violated'"
                ")"
            ),
            name=(
                "ck_hvee_decisions_"
                "critical_assessment"
            ),
        ),
        CheckConstraint(
            (
                "claim_assessment IN ("
                "'supported', "
                "'contradicted', "
                "'unresolved'"
                ")"
            ),
            name=(
                "ck_hvee_decisions_"
                "claim_assessment"
            ),
        ),
        CheckConstraint(
            (
                "verdict IN ("
                "'pass', "
                "'fail', "
                "'inconclusive', "
                "'invalid'"
                ")"
            ),
            name="ck_hvee_decisions_verdict",
        ),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name=(
                "ck_hvee_decisions_"
                "reason_not_blank"
            ),
        ),
        CheckConstraint(
            "length(decision_sha256) = 64",
            name=(
                "ck_hvee_decisions_"
                "decision_sha256_length"
            ),
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
    )

    result_provenance_id = Column(
        Integer,
        ForeignKey(
            "evaluation_result_provenances.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    schema_version = Column(
        Integer,
        nullable=False,
    )

    evaluation_type = Column(
        String(50),
        nullable=False,
        index=True,
    )

    policy_key = Column(
        String(200),
        nullable=False,
    )

    policy_version = Column(
        String(100),
        nullable=False,
    )

    policy_sha256 = Column(
        String(64),
        nullable=False,
    )

    provenance_sha256 = Column(
        String(64),
        nullable=False,
    )

    observation_evidence_sha256 = Column(
        String(64),
        nullable=False,
    )

    integrity_assessment = Column(
        String(32),
        nullable=False,
    )

    evidence_assessment = Column(
        String(32),
        nullable=False,
    )

    critical_assessment = Column(
        String(32),
        nullable=False,
    )

    claim_assessment = Column(
        String(32),
        nullable=False,
    )

    verdict = Column(
        String(32),
        nullable=False,
        index=True,
    )

    reason = Column(
        String(100),
        nullable=False,
    )

    decision_payload = Column(
        JSON,
        nullable=False,
    )

    decision_sha256 = Column(
        String(64),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class HveeMatchedReleaseDecision(Base):
    """
    Immutable matched-release decision for an ordered run pair.

    The application independently verifies all persisted provenance
    and observation evidence before constructing this snapshot through
    the pure HVEE evaluation layer.
    """

    __tablename__ = "hvee_matched_release_decisions"

    __table_args__ = (
        UniqueConstraint(
            "baseline_run_id",
            "candidate_run_id",
            "target_sha256",
            "policy_sha256",
            "schema_version",
            name=(
                "uq_hvee_matched_release_decisions_"
                "target_policy_schema"
            ),
        ),
        CheckConstraint(
            "baseline_run_id <> candidate_run_id",
            name=(
                "ck_hvee_matched_release_decisions_"
                "distinct_runs"
            ),
        ),
        CheckConstraint(
            "schema_version > 0",
            name=(
                "ck_hvee_matched_release_decisions_"
                "schema_version_positive"
            ),
        ),
        CheckConstraint(
            "length(target_sha256) = 64",
            name=(
                "ck_hvee_matched_release_decisions_"
                "target_sha256_length"
            ),
        ),
        CheckConstraint(
            "length(trim(evaluation_type)) > 0",
            name=(
                "ck_hvee_matched_release_decisions_"
                "evaluation_type_nonblank"
            ),
        ),
        CheckConstraint(
            "length(trim(policy_key)) > 0",
            name=(
                "ck_hvee_matched_release_decisions_"
                "policy_key_nonblank"
            ),
        ),
        CheckConstraint(
            "length(trim(policy_version)) > 0",
            name=(
                "ck_hvee_matched_release_decisions_"
                "policy_version_nonblank"
            ),
        ),
        CheckConstraint(
            "length(policy_sha256) = 64",
            name=(
                "ck_hvee_matched_release_decisions_"
                "policy_sha256_length"
            ),
        ),
        CheckConstraint(
            "integrity_assessment IN ('valid', 'invalid')",
            name=(
                "ck_hvee_matched_release_decisions_"
                "integrity_assessment"
            ),
        ),
        CheckConstraint(
            (
                "evidence_assessment IN "
                "('sufficient', 'insufficient')"
            ),
            name=(
                "ck_hvee_matched_release_decisions_"
                "evidence_assessment"
            ),
        ),
        CheckConstraint(
            "critical_assessment IN ('clear', 'violated')",
            name=(
                "ck_hvee_matched_release_decisions_"
                "critical_assessment"
            ),
        ),
        CheckConstraint(
            (
                "claim_assessment IN "
                "('supported', 'contradicted', 'unresolved')"
            ),
            name=(
                "ck_hvee_matched_release_decisions_"
                "claim_assessment"
            ),
        ),
        CheckConstraint(
            (
                "verdict IN "
                "('pass', 'fail', 'inconclusive', 'invalid')"
            ),
            name=(
                "ck_hvee_matched_release_decisions_verdict"
            ),
        ),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name=(
                "ck_hvee_matched_release_decisions_"
                "reason_nonblank"
            ),
        ),
        CheckConstraint(
            "length(decision_sha256) = 64",
            name=(
                "ck_hvee_matched_release_decisions_"
                "decision_sha256_length"
            ),
        ),
        Index(
            "ix_hvee_matched_release_decisions_baseline_run",
            "baseline_run_id",
        ),
        Index(
            "ix_hvee_matched_release_decisions_candidate_run",
            "candidate_run_id",
        ),
        Index(
            "ix_hvee_matched_release_decisions_evaluation_type",
            "evaluation_type",
        ),
        Index(
            "ix_hvee_matched_release_decisions_verdict",
            "verdict",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
    )

    baseline_run_id = Column(
        Integer,
        ForeignKey(
            "evaluation_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    candidate_run_id = Column(
        Integer,
        ForeignKey(
            "evaluation_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    target_sha256 = Column(
        String(64),
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

    policy_key = Column(
        String(200),
        nullable=False,
    )

    policy_version = Column(
        String(100),
        nullable=False,
    )

    policy_sha256 = Column(
        String(64),
        nullable=False,
    )

    integrity_assessment = Column(
        String(32),
        nullable=False,
    )

    evidence_assessment = Column(
        String(32),
        nullable=False,
    )

    critical_assessment = Column(
        String(32),
        nullable=False,
    )

    claim_assessment = Column(
        String(32),
        nullable=False,
    )

    verdict = Column(
        String(32),
        nullable=False,
    )

    reason = Column(
        String(100),
        nullable=False,
    )

    decision_payload = Column(
        JSON,
        nullable=False,
    )

    decision_sha256 = Column(
        String(64),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class HveeMatchedReleaseDecisionBinding(Base):
    """
    Verified provenance pair for one declared matched test case.

    Digests are retained with the referenced provenance identities so
    a persisted decision remains bound to the exact evidence used.
    """

    __tablename__ = "hvee_matched_release_decision_bindings"

    __table_args__ = (
        UniqueConstraint(
            "matched_release_decision_id",
            "test_case_id",
            name=(
                "uq_hvee_matched_release_bindings_"
                "decision_case"
            ),
        ),
        UniqueConstraint(
            "matched_release_decision_id",
            "baseline_result_provenance_id",
            name=(
                "uq_hvee_matched_release_bindings_"
                "decision_baseline"
            ),
        ),
        UniqueConstraint(
            "matched_release_decision_id",
            "candidate_result_provenance_id",
            name=(
                "uq_hvee_matched_release_bindings_"
                "decision_candidate"
            ),
        ),
        CheckConstraint(
            (
                "baseline_result_provenance_id "
                "<> candidate_result_provenance_id"
            ),
            name=(
                "ck_hvee_matched_release_bindings_"
                "distinct_provenances"
            ),
        ),
        CheckConstraint(
            "length(baseline_provenance_sha256) = 64",
            name="ck_hvee_mrd_bindings_baseline_provenance_sha256",
        ),
        CheckConstraint(
            (
                "length("
                "baseline_observation_evidence_sha256"
                ") = 64"
            ),
            name="ck_hvee_mrd_bindings_baseline_observation_sha256",
        ),
        CheckConstraint(
            "length(candidate_provenance_sha256) = 64",
            name="ck_hvee_mrd_bindings_candidate_provenance_sha256",
        ),
        CheckConstraint(
            (
                "length("
                "candidate_observation_evidence_sha256"
                ") = 64"
            ),
            name="ck_hvee_mrd_bindings_candidate_observation_sha256",
        ),
        Index(
            "ix_hvee_matched_release_bindings_test_case",
            "test_case_id",
        ),
        Index(
            (
                "ix_hvee_matched_release_bindings_"
                "baseline_provenance"
            ),
            "baseline_result_provenance_id",
        ),
        Index(
            (
                "ix_hvee_matched_release_bindings_"
                "candidate_provenance"
            ),
            "candidate_result_provenance_id",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
    )

    matched_release_decision_id = Column(
        Integer,
        ForeignKey(
            "hvee_matched_release_decisions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    test_case_id = Column(
        Integer,
        ForeignKey("test_cases.id"),
        nullable=False,
    )

    baseline_result_provenance_id = Column(
        Integer,
        ForeignKey("evaluation_result_provenances.id"),
        nullable=False,
    )

    baseline_provenance_sha256 = Column(
        String(64),
        nullable=False,
    )

    baseline_observation_evidence_sha256 = Column(
        String(64),
        nullable=False,
    )

    candidate_result_provenance_id = Column(
        Integer,
        ForeignKey("evaluation_result_provenances.id"),
        nullable=False,
    )

    candidate_provenance_sha256 = Column(
        String(64),
        nullable=False,
    )

    candidate_observation_evidence_sha256 = Column(
        String(64),
        nullable=False,
    )
