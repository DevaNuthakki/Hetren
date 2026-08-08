from sqlalchemy import inspect

from app.hvee_models import HveeDecision


def test_hvee_decision_table_identity():
    assert HveeDecision.__tablename__ == "hvee_decisions"


def test_hvee_decision_columns_are_stable():
    assert {
        column.name
        for column in HveeDecision.__table__.columns
    } == {
        "id",
        "result_provenance_id",
        "schema_version",
        "evaluation_type",
        "policy_key",
        "policy_version",
        "policy_sha256",
        "provenance_sha256",
        "observation_evidence_sha256",
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


def test_hvee_decision_required_columns_are_not_nullable():
    nullable = {
        column.name: column.nullable
        for column in HveeDecision.__table__.columns
    }

    assert nullable == {
        "id": False,
        "result_provenance_id": False,
        "schema_version": False,
        "evaluation_type": False,
        "policy_key": False,
        "policy_version": False,
        "policy_sha256": False,
        "provenance_sha256": False,
        "observation_evidence_sha256": False,
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


def test_hvee_decision_foreign_key_targets_result_provenance():
    foreign_keys = list(
        HveeDecision.__table__.foreign_keys
    )

    assert len(foreign_keys) == 1

    foreign_key = foreign_keys[0]

    assert (
        foreign_key.parent.name
        == "result_provenance_id"
    )
    assert (
        foreign_key.target_fullname
        == "evaluation_result_provenances.id"
    )
    assert foreign_key.ondelete == "CASCADE"


def test_hvee_decision_idempotency_constraint_is_stable():
    constraints = {
        constraint.name: constraint
        for constraint
        in HveeDecision.__table__.constraints
        if constraint.name is not None
    }

    constraint = constraints[
        "uq_hvee_decisions_provenance_policy_schema"
    ]

    assert [
        column.name
        for column in constraint.columns
    ] == [
        "result_provenance_id",
        "policy_sha256",
        "schema_version",
    ]


def test_hvee_decision_query_indexes_are_present():
    indexes = {
        index.name: tuple(
            column.name
            for column in index.columns
        )
        for index in HveeDecision.__table__.indexes
    }

    assert indexes == {
        "ix_hvee_decisions_evaluation_type": (
            "evaluation_type",
        ),
        "ix_hvee_decisions_result_provenance_id": (
            "result_provenance_id",
        ),
        "ix_hvee_decisions_verdict": (
            "verdict",
        ),
    }


def test_hvee_decision_schema_has_no_direct_result_foreign_key():
    column_names = {
        column.name
        for column in HveeDecision.__table__.columns
    }

    assert "evaluation_result_id" not in column_names
