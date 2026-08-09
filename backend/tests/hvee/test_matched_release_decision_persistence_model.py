from sqlalchemy import CheckConstraint, UniqueConstraint

from app.hvee_models import (
    HveeMatchedReleaseDecision,
    HveeMatchedReleaseDecisionBinding,
)


def test_matched_release_table_identities_are_stable():
    assert (
        HveeMatchedReleaseDecision.__tablename__
        == "hvee_matched_release_decisions"
    )
    assert (
        HveeMatchedReleaseDecisionBinding.__tablename__
        == "hvee_matched_release_decision_bindings"
    )


def test_matched_release_decision_columns_are_stable():
    assert {
        column.name
        for column
        in HveeMatchedReleaseDecision.__table__.columns
    } == {
        "id",
        "baseline_run_id",
        "candidate_run_id",
        "target_sha256",
        "schema_version",
        "evaluation_type",
        "policy_key",
        "policy_version",
        "policy_sha256",
        "integrity_assessment",
        "evidence_assessment",
        "critical_assessment",
        "claim_assessment",
        "verdict",
        "reason",
        "decision_payload",
        "decision_sha256",
        "created_at",
    }


def test_matched_release_binding_columns_are_stable():
    assert {
        column.name
        for column
        in HveeMatchedReleaseDecisionBinding.__table__.columns
    } == {
        "id",
        "matched_release_decision_id",
        "test_case_id",
        "baseline_result_provenance_id",
        "baseline_provenance_sha256",
        "baseline_observation_evidence_sha256",
        "candidate_result_provenance_id",
        "candidate_provenance_sha256",
        "candidate_observation_evidence_sha256",
    }


def test_matched_release_decision_columns_are_required():
    nullable = {
        column.name: column.nullable
        for column
        in HveeMatchedReleaseDecision.__table__.columns
    }

    assert nullable == {
        "id": False,
        "baseline_run_id": False,
        "candidate_run_id": False,
        "target_sha256": False,
        "schema_version": False,
        "evaluation_type": False,
        "policy_key": False,
        "policy_version": False,
        "policy_sha256": False,
        "integrity_assessment": False,
        "evidence_assessment": False,
        "critical_assessment": False,
        "claim_assessment": False,
        "verdict": False,
        "reason": False,
        "decision_payload": False,
        "decision_sha256": False,
        "created_at": False,
    }


def test_matched_release_binding_columns_are_required():
    nullable = {
        column.name: column.nullable
        for column
        in HveeMatchedReleaseDecisionBinding.__table__.columns
    }

    assert nullable == {
        "id": False,
        "matched_release_decision_id": False,
        "test_case_id": False,
        "baseline_result_provenance_id": False,
        "baseline_provenance_sha256": False,
        "baseline_observation_evidence_sha256": False,
        "candidate_result_provenance_id": False,
        "candidate_provenance_sha256": False,
        "candidate_observation_evidence_sha256": False,
    }


def test_matched_release_decision_run_foreign_keys_are_stable():
    foreign_keys = {
        foreign_key.parent.name: (
            foreign_key.target_fullname,
            foreign_key.ondelete,
        )
        for foreign_key
        in HveeMatchedReleaseDecision.__table__.foreign_keys
    }

    assert foreign_keys == {
        "baseline_run_id": (
            "evaluation_runs.id",
            "CASCADE",
        ),
        "candidate_run_id": (
            "evaluation_runs.id",
            "CASCADE",
        ),
    }


def test_matched_release_binding_foreign_keys_are_stable():
    foreign_keys = {
        foreign_key.parent.name: (
            foreign_key.target_fullname,
            foreign_key.ondelete,
        )
        for foreign_key
        in HveeMatchedReleaseDecisionBinding.__table__.foreign_keys
    }

    assert foreign_keys == {
        "matched_release_decision_id": (
            "hvee_matched_release_decisions.id",
            "CASCADE",
        ),
        "test_case_id": (
            "test_cases.id",
            None,
        ),
        "baseline_result_provenance_id": (
            "evaluation_result_provenances.id",
            None,
        ),
        "candidate_result_provenance_id": (
            "evaluation_result_provenances.id",
            None,
        ),
    }


def test_matched_release_decision_identity_is_stable():
    constraints = {
        constraint.name: constraint
        for constraint
        in HveeMatchedReleaseDecision.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    identity = constraints[
        "uq_hvee_matched_release_decisions_target_policy_schema"
    ]

    assert [
        column.name
        for column in identity.columns
    ] == [
        "baseline_run_id",
        "candidate_run_id",
        "target_sha256",
        "policy_sha256",
        "schema_version",
    ]


def test_matched_release_binding_uniqueness_is_stable():
    constraints = {
        constraint.name: constraint
        for constraint
        in HveeMatchedReleaseDecisionBinding.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert {
        name: tuple(
            column.name
            for column in constraint.columns
        )
        for name, constraint in constraints.items()
    } == {
        "uq_hvee_matched_release_bindings_decision_case": (
            "matched_release_decision_id",
            "test_case_id",
        ),
        "uq_hvee_matched_release_bindings_decision_baseline": (
            "matched_release_decision_id",
            "baseline_result_provenance_id",
        ),
        "uq_hvee_matched_release_bindings_decision_candidate": (
            "matched_release_decision_id",
            "candidate_result_provenance_id",
        ),
    }


def test_matched_release_distinct_side_checks_are_present():
    root_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint
        in HveeMatchedReleaseDecision.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    binding_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint
        in HveeMatchedReleaseDecisionBinding.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert root_checks[
        "ck_hvee_matched_release_decisions_distinct_runs"
    ] == "baseline_run_id <> candidate_run_id"

    assert binding_checks[
        "ck_hvee_matched_release_bindings_distinct_provenances"
    ] == (
        "baseline_result_provenance_id "
        "<> candidate_result_provenance_id"
    )


def test_matched_release_query_indexes_are_stable():
    root_indexes = {
        index.name: tuple(
            column.name
            for column in index.columns
        )
        for index
        in HveeMatchedReleaseDecision.__table__.indexes
    }
    binding_indexes = {
        index.name: tuple(
            column.name
            for column in index.columns
        )
        for index
        in HveeMatchedReleaseDecisionBinding.__table__.indexes
    }

    assert root_indexes == {
        "ix_hvee_matched_release_decisions_baseline_run": (
            "baseline_run_id",
        ),
        "ix_hvee_matched_release_decisions_candidate_run": (
            "candidate_run_id",
        ),
        "ix_hvee_matched_release_decisions_evaluation_type": (
            "evaluation_type",
        ),
        "ix_hvee_matched_release_decisions_verdict": (
            "verdict",
        ),
    }

    assert binding_indexes == {
        "ix_hvee_matched_release_bindings_test_case": (
            "test_case_id",
        ),
        "ix_hvee_matched_release_bindings_baseline_provenance": (
            "baseline_result_provenance_id",
        ),
        "ix_hvee_matched_release_bindings_candidate_provenance": (
            "candidate_result_provenance_id",
        ),
    }
