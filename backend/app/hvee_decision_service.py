from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.evaluation_provenance import (
    EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION,
    verify_evaluation_result_observation_binding,
    verify_evaluation_result_provenance,
)
from app.hvee_models import HveeDecision
from app.hvee_observation_evidence import (
    HveeObservationEvidenceError,
    load_test_case_observation_evidence_records,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision_evidence import (
    DECISION_EVIDENCE_SCHEMA_VERSION,
    DecisionEvidenceBundle,
    verify_decision_evidence_bundle,
)
from hvee.core.evidence_readiness import EvidenceTarget
from hvee.core.observation_evidence import (
    build_observation_evidence_bundle,
)
from hvee.packs.asr.decision_evidence import (
    build_asr_test_case_decision_evidence,
)
from hvee.packs.asr.decision_policy import (
    ASRTestCaseDecisionPolicyV1,
)
from hvee.packs.asr.evaluation import ASR_EVALUATION_TYPE


class HveeDecisionPersistenceError(ValueError):
    """Raised when a verified HVEE decision cannot be staged."""


class HveeDecisionConflictError(
    HveeDecisionPersistenceError
):
    """
    Raised when a persisted decision identity exists with different
    canonical content.
    """


def _load_provenance(
    db: Session,
    *,
    result_provenance_id: int,
) -> models.EvaluationResultProvenance:
    if (
        isinstance(result_provenance_id, bool)
        or not isinstance(
            result_provenance_id,
            int,
        )
        or result_provenance_id < 1
    ):
        raise HveeDecisionPersistenceError(
            "result provenance id must be a positive integer"
        )

    provenance = db.scalar(
        select(
            models.EvaluationResultProvenance
        )
        .where(
            models.EvaluationResultProvenance.id
            == result_provenance_id
        )
        .with_for_update()
    )

    if provenance is None:
        raise HveeDecisionPersistenceError(
            "evaluation result provenance was not found"
        )

    return provenance


def _validate_provenance_parent_binding(
    db: Session,
    *,
    provenance: models.EvaluationResultProvenance,
) -> tuple[
    models.EvaluationResult,
    int,
    int,
]:
    result = db.scalar(
        select(models.EvaluationResult)
        .where(
            models.EvaluationResult.id
            == provenance.result_id
        )
        .with_for_update()
    )

    if result is None:
        raise HveeDecisionPersistenceError(
            "evaluation result provenance has no parent result"
        )

    payload = provenance.provenance_payload

    if not isinstance(payload, dict):
        raise HveeDecisionPersistenceError(
            "evaluation result provenance payload is invalid"
        )

    payload_result = payload.get("result")

    if (
        not isinstance(payload_result, dict)
        or payload_result
        != {
            "id": result.id,
            "run_id": result.run_id,
            "test_case_id": result.test_case_id,
        }
    ):
        raise HveeDecisionPersistenceError(
            "evaluation result provenance is not bound "
            "to its relational result identity"
        )

    evaluation_run = db.scalar(
        select(models.EvaluationRun).where(
            models.EvaluationRun.id
            == result.run_id
        )
    )

    if (
        evaluation_run is None
        or evaluation_run.evaluation_type
        != ASR_EVALUATION_TYPE
        or provenance.evaluation_type
        != ASR_EVALUATION_TYPE
    ):
        raise HveeDecisionPersistenceError(
            "HVEE ASR decision requires ASR provenance"
        )

    return (
        result,
        result.run_id,
        result.test_case_id,
    )


def _build_verified_decision_bundle(
    db: Session,
    *,
    provenance: models.EvaluationResultProvenance,
    policy: ASRTestCaseDecisionPolicyV1,
) -> DecisionEvidenceBundle:
    if (
        provenance.schema_version
        != EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION
    ):
        raise HveeDecisionPersistenceError(
            "HVEE decision persistence requires "
            "current observation-bound provenance"
        )

    if not verify_evaluation_result_provenance(
        provenance
    ):
        raise HveeDecisionPersistenceError(
            "evaluation result provenance failed verification"
        )

    (
        _result,
        evaluation_run_id,
        test_case_id,
    ) = _validate_provenance_parent_binding(
        db,
        provenance=provenance,
    )

    if not verify_evaluation_result_observation_binding(
        db,
        provenance,
    ):
        raise HveeDecisionPersistenceError(
            "persisted observations no longer match "
            "the bound result provenance"
        )

    payload = provenance.provenance_payload

    observation_bundle = payload.get(
        "hvee_observations"
    )

    if not isinstance(
        observation_bundle,
        dict,
    ):
        raise HveeDecisionPersistenceError(
            "result provenance is missing "
            "observation evidence"
        )

    observation_sha256 = (
        observation_bundle.get("sha256")
    )

    try:
        records = (
            load_test_case_observation_evidence_records(
                db,
                evaluation_run_id=evaluation_run_id,
                test_case_id=test_case_id,
            )
        )

        # Rebuild once more from the exact records that will be passed
        # into the policy evaluator. This closes the gap between
        # binding verification and decision construction.
        current_bundle = (
            build_observation_evidence_bundle(
                records
            )
        )

    except (
        HveeObservationEvidenceError,
        HveeContractError,
    ) as exc:
        raise HveeDecisionPersistenceError(
            "persisted observations cannot form "
            "decision evidence"
        ) from exc

    if current_bundle != observation_bundle:
        raise HveeDecisionPersistenceError(
            "decision observations changed after "
            "provenance binding verification"
        )

    try:
        bundle = (
            build_asr_test_case_decision_evidence(
                policy=policy,
                records=records,
                target=EvidenceTarget(
                    evaluation_run_id=(
                        evaluation_run_id
                    ),
                    test_case_id=test_case_id,
                ),
                result_provenance_id=provenance.id,
                provenance_sha256=(
                    provenance.provenance_sha256
                ),
                observation_evidence_sha256=(
                    observation_sha256
                ),
            )
        )

    except HveeContractError as exc:
        raise HveeDecisionPersistenceError(
            "ASR decision evidence could not be constructed"
        ) from exc

    if not verify_decision_evidence_bundle(
        payload=bundle.payload,
        expected_decision_sha256=(
            bundle.decision_sha256
        ),
    ):
        raise HveeDecisionPersistenceError(
            "constructed HVEE decision evidence "
            "failed verification"
        )

    return bundle


def _get_existing_decision(
    db: Session,
    *,
    result_provenance_id: int,
    policy_sha256: str,
) -> HveeDecision | None:
    return db.scalar(
        select(HveeDecision).where(
            HveeDecision.result_provenance_id
            == result_provenance_id,
            HveeDecision.policy_sha256
            == policy_sha256,
            HveeDecision.schema_version
            == DECISION_EVIDENCE_SCHEMA_VERSION,
        )
    )


def _decision_matches_bundle(
    decision: HveeDecision,
    *,
    provenance: models.EvaluationResultProvenance,
    bundle: DecisionEvidenceBundle,
) -> bool:
    payload = bundle.payload
    assessments = payload.get(
        "assessments"
    )
    decision_summary = payload.get(
        "decision"
    )
    evidence = payload.get(
        "evidence"
    )
    policy = payload.get(
        "policy"
    )

    if not all(
        isinstance(value, dict)
        for value in (
            assessments,
            decision_summary,
            evidence,
            policy,
        )
    ):
        return False

    return (
        decision.result_provenance_id
        == provenance.id
        and decision.schema_version
        == DECISION_EVIDENCE_SCHEMA_VERSION
        and decision.evaluation_type
        == payload.get("evaluation_type")
        and decision.policy_key
        == policy.get("key")
        and decision.policy_version
        == policy.get("version")
        and decision.policy_sha256
        == bundle.policy_sha256
        and decision.provenance_sha256
        == provenance.provenance_sha256
        and decision.observation_evidence_sha256
        == evidence.get(
            "observation_evidence_sha256"
        )
        and decision.integrity_assessment
        == assessments.get("integrity")
        and decision.evidence_assessment
        == assessments.get("evidence")
        and decision.critical_assessment
        == assessments.get("critical")
        and decision.claim_assessment
        == assessments.get("claim")
        and decision.verdict
        == decision_summary.get("verdict")
        and decision.reason
        == decision_summary.get("reason")
        and decision.decision_payload
        == bundle.payload
        and decision.decision_sha256
        == bundle.decision_sha256
    )


def _build_decision_row(
    *,
    provenance: models.EvaluationResultProvenance,
    bundle: DecisionEvidenceBundle,
) -> HveeDecision:
    payload = bundle.payload
    assessments = payload["assessments"]
    decision_summary = payload["decision"]
    evidence = payload["evidence"]
    policy = payload["policy"]

    return HveeDecision(
        result_provenance_id=provenance.id,
        schema_version=(
            DECISION_EVIDENCE_SCHEMA_VERSION
        ),
        evaluation_type=payload[
            "evaluation_type"
        ],
        policy_key=policy["key"],
        policy_version=policy["version"],
        policy_sha256=bundle.policy_sha256,
        provenance_sha256=(
            provenance.provenance_sha256
        ),
        observation_evidence_sha256=(
            evidence[
                "observation_evidence_sha256"
            ]
        ),
        integrity_assessment=(
            assessments["integrity"]
        ),
        evidence_assessment=(
            assessments["evidence"]
        ),
        critical_assessment=(
            assessments["critical"]
        ),
        claim_assessment=(
            assessments["claim"]
        ),
        verdict=decision_summary["verdict"],
        reason=decision_summary["reason"],
        decision_payload=bundle.payload,
        decision_sha256=(
            bundle.decision_sha256
        ),
    )


def stage_asr_hvee_decision(
    db: Session,
    *,
    result_provenance_id: int,
    policy: ASRTestCaseDecisionPolicyV1,
) -> HveeDecision:
    """
    Stage one immutable ASR HVEE decision.

    The caller supplies only the policy and provenance identity.
    Verdicts, findings, assessments, evidence digests, and decision
    digests are all derived internally.

    The caller owns the surrounding transaction.
    """

    if not isinstance(
        policy,
        ASRTestCaseDecisionPolicyV1,
    ):
        raise HveeDecisionPersistenceError(
            "HVEE ASR decision requires "
            "ASRTestCaseDecisionPolicyV1"
        )

    provenance = _load_provenance(
        db,
        result_provenance_id=(
            result_provenance_id
        ),
    )

    bundle = _build_verified_decision_bundle(
        db,
        provenance=provenance,
        policy=policy,
    )

    existing = _get_existing_decision(
        db,
        result_provenance_id=provenance.id,
        policy_sha256=bundle.policy_sha256,
    )

    if existing is not None:
        if not _decision_matches_bundle(
            existing,
            provenance=provenance,
            bundle=bundle,
        ):
            raise HveeDecisionConflictError(
                "existing HVEE decision does not match "
                "its canonical decision evidence"
            )

        return existing

    candidate = _build_decision_row(
        provenance=provenance,
        bundle=bundle,
    )

    try:
        # Preserve the caller's outer transaction if another concurrent
        # transaction wins the same decision identity race.
        with db.begin_nested():
            db.add(candidate)
            db.flush()

        return candidate

    except IntegrityError:
        existing = _get_existing_decision(
            db,
            result_provenance_id=(
                provenance.id
            ),
            policy_sha256=(
                bundle.policy_sha256
            ),
        )

        if existing is None:
            raise

        if not _decision_matches_bundle(
            existing,
            provenance=provenance,
            bundle=bundle,
        ):
            raise HveeDecisionConflictError(
                "concurrent HVEE decision conflicts "
                "with canonical evidence"
            )

        return existing
