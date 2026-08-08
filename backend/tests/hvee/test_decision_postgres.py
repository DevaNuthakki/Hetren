import hashlib
import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.hvee_models import HveeDecision


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason=(
            "Set RUN_POSTGRES_TESTS=1 to run PostgreSQL "
            "integration tests."
        ),
    ),
]


def _digest(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _build_provenance(
    db: Session,
    *,
    suffix: str,
) -> models.EvaluationResultProvenance:
    project = models.Project(
        name=f"HVEE decision project {suffix}",
    )

    dataset = models.Dataset(
        project=project,
        name=f"HVEE decision dataset {suffix}",
    )

    test_case = models.TestCase(
        dataset=dataset,
        title=f"HVEE decision case {suffix}",
        reference_transcript="one two three",
    )

    run = models.EvaluationRun(
        project=project,
        run_name=f"HVEE decision run {suffix}",
        evaluation_type="asr",
        model_name="postgres-test-model",
        status="completed",
    )

    db.add_all(
        [
            project,
            dataset,
            test_case,
            run,
        ]
    )
    db.flush()

    result = models.EvaluationResult(
        run_id=run.id,
        test_case_id=test_case.id,
        generated_transcript="one two three",
        wer=0.0,
        cer=0.0,
        quality_label="pass",
    )

    db.add(result)
    db.flush()

    payload = {
        "schema_version": 4,
        "source": "postgres_constraint_test",
        "suffix": suffix,
    }

    provenance = models.EvaluationResultProvenance(
        result_id=result.id,
        schema_version=4,
        evaluation_type="asr",
        execution_mode="uploaded_transcript",
        provenance_payload=payload,
        provenance_sha256=_digest(
            f"provenance:{suffix}"
        ),
    )

    db.add(provenance)
    db.flush()

    return provenance


def _build_decision(
    *,
    provenance_id: int,
    provenance_sha256: str,
    suffix: str,
    **overrides: object,
) -> HveeDecision:
    values: dict[str, object] = {
        "result_provenance_id": provenance_id,
        "schema_version": 1,
        "evaluation_type": "asr",
        "policy_key": "hetren.asr.test-case-quality",
        "policy_version": "1.0.0",
        "policy_sha256": _digest(
            f"policy:{suffix}"
        ),
        "provenance_sha256": provenance_sha256,
        "observation_evidence_sha256": _digest(
            f"observations:{suffix}"
        ),
        "integrity_assessment": "valid",
        "evidence_assessment": "sufficient",
        "critical_assessment": "clear",
        "claim_assessment": "supported",
        "verdict": "pass",
        "reason": "claim_supported",
        "decision_payload": {
            "schema_version": 1,
            "source": "postgres_constraint_test",
            "suffix": suffix,
        },
        "decision_sha256": _digest(
            f"decision:{suffix}"
        ),
    }

    values.update(overrides)

    return HveeDecision(**values)


def test_postgres_accepts_valid_hvee_decision(
    postgres_session: Session,
):
    provenance = _build_provenance(
        postgres_session,
        suffix="valid",
    )

    decision = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix="valid",
    )

    postgres_session.add(decision)
    postgres_session.flush()

    assert decision.id is not None
    assert decision.verdict == "pass"
    assert (
        decision.result_provenance_id
        == provenance.id
    )


def test_postgres_rejects_missing_result_provenance(
    postgres_session: Session,
):
    decision = _build_decision(
        provenance_id=2_147_483_647,
        provenance_sha256=_digest(
            "missing-provenance"
        ),
        suffix="missing-provenance",
    )

    postgres_session.add(decision)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_rejects_duplicate_decision_identity(
    postgres_session: Session,
):
    provenance = _build_provenance(
        postgres_session,
        suffix="duplicate",
    )

    first = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix="duplicate",
    )

    duplicate = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix="duplicate",
        decision_sha256=_digest(
            "different-decision-payload"
        ),
    )

    postgres_session.add(first)
    postgres_session.flush()

    postgres_session.add(duplicate)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_allows_different_policy_snapshot_for_same_provenance(
    postgres_session: Session,
):
    provenance = _build_provenance(
        postgres_session,
        suffix="different-policy",
    )

    first = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix="different-policy-a",
    )

    second = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix="different-policy-b",
    )

    postgres_session.add_all(
        [
            first,
            second,
        ]
    )
    postgres_session.flush()

    assert first.id is not None
    assert second.id is not None
    assert first.policy_sha256 != second.policy_sha256


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("integrity_assessment", "unknown"),
        ("evidence_assessment", "unknown"),
        ("critical_assessment", "unknown"),
        ("claim_assessment", "unknown"),
        ("verdict", "unknown"),
    ],
)
def test_postgres_rejects_invalid_decision_enums(
    postgres_session: Session,
    field_name: str,
    invalid_value: str,
):
    provenance = _build_provenance(
        postgres_session,
        suffix=f"invalid-enum-{field_name}",
    )

    decision = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix=f"invalid-enum-{field_name}",
        **{
            field_name: invalid_value,
        },
    )

    postgres_session.add(decision)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    "field_name",
    [
        "policy_sha256",
        "provenance_sha256",
        "observation_evidence_sha256",
        "decision_sha256",
    ],
)
def test_postgres_rejects_wrong_digest_length(
    postgres_session: Session,
    field_name: str,
):
    provenance = _build_provenance(
        postgres_session,
        suffix=f"digest-{field_name}",
    )

    decision_kwargs: dict[str, object] = {
        "provenance_id": provenance.id,
        "provenance_sha256": provenance.provenance_sha256,
        "suffix": f"digest-{field_name}",
    }
    decision_kwargs[field_name] = "a" * 63

    decision = _build_decision(
        **decision_kwargs,
    )

    postgres_session.add(decision)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    "field_name",
    [
        "evaluation_type",
        "policy_key",
        "policy_version",
        "reason",
    ],
)
def test_postgres_rejects_blank_decision_identity_fields(
    postgres_session: Session,
    field_name: str,
):
    provenance = _build_provenance(
        postgres_session,
        suffix=f"blank-{field_name}",
    )

    decision = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix=f"blank-{field_name}",
        **{
            field_name: "   ",
        },
    )

    postgres_session.add(decision)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


@pytest.mark.parametrize(
    "schema_version",
    [
        0,
        -1,
    ],
)
def test_postgres_rejects_non_positive_decision_schema_version(
    postgres_session: Session,
    schema_version: int,
):
    provenance = _build_provenance(
        postgres_session,
        suffix=f"schema-{schema_version}",
    )

    decision = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix=f"schema-{schema_version}",
        schema_version=schema_version,
    )

    postgres_session.add(decision)

    with pytest.raises(IntegrityError):
        postgres_session.flush()

    postgres_session.rollback()


def test_postgres_cascades_decision_when_provenance_is_deleted(
    postgres_session: Session,
):
    provenance = _build_provenance(
        postgres_session,
        suffix="cascade",
    )

    decision = _build_decision(
        provenance_id=provenance.id,
        provenance_sha256=provenance.provenance_sha256,
        suffix="cascade",
    )

    postgres_session.add(decision)
    postgres_session.flush()

    decision_id = decision.id

    assert decision_id is not None

    postgres_session.delete(provenance)
    postgres_session.flush()

    remaining = postgres_session.scalar(
        select(func.count())
        .select_from(HveeDecision)
        .where(HveeDecision.id == decision_id)
    )

    assert remaining == 0
