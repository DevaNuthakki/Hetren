from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum

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

from app.hvee_models import (
    HveeMatchedReleaseDecision,
    HveeMatchedReleaseDecisionBinding,
)
from hvee.packs.asr.matched_evidence import (
    build_asr_matched_quality_cohorts,
)
from hvee.packs.asr.release_assurance_policy import (
    ASRMatchedReleaseAssurancePolicyV1,
)
from hvee.packs.asr.release_decision import (
    evaluate_asr_matched_release_decision,
)


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

_MATCHED_RELEASE_DECISION_SCHEMA_VERSION = 1
_MATCHED_RELEASE_POLICY_KEY = (
    "hvee.asr.matched_release_assurance"
)
_MATCHED_RELEASE_POLICY_VERSION = "1"


def _matched_json_value(value):
    if isinstance(value, Enum):
        return value.value

    if (
        is_dataclass(value)
        and not isinstance(value, type)
    ):
        return {
            field.name: _matched_json_value(
                getattr(value, field.name)
            )
            for field in fields(value)
        }

    if isinstance(value, dict):
        converted = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise HveeDecisionPersistenceError(
                    "matched-release canonical payload "
                    "keys must be strings"
                )

            converted[key] = _matched_json_value(
                item
            )

        return converted

    if isinstance(value, (tuple, list)):
        return [
            _matched_json_value(item)
            for item in value
        ]

    if (
        value is None
        or isinstance(
            value,
            (bool, int, float, str),
        )
    ):
        return value

    raise HveeDecisionPersistenceError(
        "matched-release content is not "
        "JSON-compatible"
    )


def _matched_sha256(
    payload: dict[str, object],
) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HveeDecisionPersistenceError(
            "matched-release canonical payload "
            "is invalid"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _matched_enum_text(
    value: object,
    *,
    field_name: str,
) -> str:
    converted = _matched_json_value(value)

    if (
        not isinstance(converted, str)
        or not converted.strip()
    ):
        raise HveeDecisionPersistenceError(
            f"matched-release {field_name} "
            "must be nonblank text"
        )

    return converted


@dataclass(frozen=True, slots=True)
class _VerifiedMatchedEvidence:
    provenance: (
        models.EvaluationResultProvenance
    )
    observation_sha256: str
    records: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class _MatchedBindingSpec:
    test_case_id: int
    baseline: _VerifiedMatchedEvidence
    candidate: _VerifiedMatchedEvidence

    def payload(self) -> dict[str, object]:
        return {
            "test_case_id": self.test_case_id,
            "baseline": {
                "result_provenance_id": (
                    self.baseline.provenance.id
                ),
                "provenance_sha256": (
                    self.baseline.provenance
                    .provenance_sha256
                ),
                "observation_evidence_sha256": (
                    self.baseline
                    .observation_sha256
                ),
            },
            "candidate": {
                "result_provenance_id": (
                    self.candidate.provenance.id
                ),
                "provenance_sha256": (
                    self.candidate.provenance
                    .provenance_sha256
                ),
                "observation_evidence_sha256": (
                    self.candidate
                    .observation_sha256
                ),
            },
        }


@dataclass(frozen=True, slots=True)
class _MatchedReleaseSnapshot:
    target_sha256: str
    policy_sha256: str
    integrity_assessment: str
    evidence_assessment: str
    critical_assessment: str
    claim_assessment: str
    verdict: str
    reason: str
    decision_payload: dict[str, object]
    decision_sha256: str
    bindings: tuple[
        _MatchedBindingSpec,
        ...,
    ]


def _require_positive_id(
    value: object,
    *,
    field_name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise HveeDecisionPersistenceError(
            f"{field_name} must be a "
            "positive integer"
        )

    return value


def _normalize_declared_test_case_ids(
    declared_test_case_ids: object,
) -> tuple[int, ...]:
    if (
        not isinstance(
            declared_test_case_ids,
            tuple,
        )
        or not declared_test_case_ids
    ):
        raise HveeDecisionPersistenceError(
            "declared test-case ids must be "
            "a non-empty tuple"
        )

    normalized = tuple(
        _require_positive_id(
            value,
            field_name=(
                "declared test-case id"
            ),
        )
        for value in declared_test_case_ids
    )

    if len(set(normalized)) != len(normalized):
        raise HveeDecisionPersistenceError(
            "declared test-case ids must "
            "be unique"
        )

    return normalized


def _load_matched_asr_run(
    db: Session,
    *,
    run_id: int,
) -> models.EvaluationRun:
    evaluation_run = db.scalar(
        select(models.EvaluationRun)
        .where(
            models.EvaluationRun.id
            == run_id
        )
        .with_for_update()
    )

    if evaluation_run is None:
        raise HveeDecisionPersistenceError(
            "matched-release evaluation run "
            "was not found"
        )

    if (
        evaluation_run.evaluation_type
        != ASR_EVALUATION_TYPE
    ):
        raise HveeDecisionPersistenceError(
            "matched-release decision "
            "requires ASR runs"
        )

    return evaluation_run


def _validate_matched_test_case_project(
    db: Session,
    *,
    test_case_id: int,
    project_id: int,
) -> None:
    test_case = db.scalar(
        select(models.TestCase).where(
            models.TestCase.id
            == test_case_id
        )
    )

    if test_case is None:
        raise HveeDecisionPersistenceError(
            "declared matched-release test "
            "case was not found"
        )

    dataset = db.scalar(
        select(models.Dataset).where(
            models.Dataset.id
            == test_case.dataset_id
        )
    )

    if (
        dataset is None
        or dataset.project_id != project_id
    ):
        raise HveeDecisionPersistenceError(
            "declared matched-release test case "
            "is outside the run project"
        )


def _load_verified_matched_evidence(
    db: Session,
    *,
    evaluation_run_id: int,
    test_case_id: int,
) -> _VerifiedMatchedEvidence:
    result = db.scalar(
        select(models.EvaluationResult)
        .where(
            models.EvaluationResult.run_id
            == evaluation_run_id,
            models.EvaluationResult.test_case_id
            == test_case_id,
        )
        .with_for_update()
    )

    if result is None:
        raise HveeDecisionPersistenceError(
            "matched-release result was not "
            "found for the declared cohort"
        )

    provenance = db.scalar(
        select(
            models.EvaluationResultProvenance
        )
        .where(
            models.EvaluationResultProvenance
            .result_id
            == result.id
        )
        .with_for_update()
    )

    if provenance is None:
        raise HveeDecisionPersistenceError(
            "matched-release result has "
            "no provenance"
        )

    if (
        provenance.schema_version
        != (
            EVALUATION_RESULT_PROVENANCE_OBSERVATION_EVIDENCE_SCHEMA_VERSION
        )
    ):
        raise HveeDecisionPersistenceError(
            "matched-release persistence "
            "requires current observation-bound "
            "provenance"
        )

    if not verify_evaluation_result_provenance(
        provenance
    ):
        raise HveeDecisionPersistenceError(
            "matched-release result provenance "
            "failed verification"
        )

    (
        parent_result,
        parent_run_id,
        parent_test_case_id,
    ) = _validate_provenance_parent_binding(
        db,
        provenance=provenance,
    )

    if (
        parent_result.id != result.id
        or parent_run_id
        != evaluation_run_id
        or parent_test_case_id
        != test_case_id
    ):
        raise HveeDecisionPersistenceError(
            "matched-release provenance is "
            "bound to the wrong result target"
        )

    if not (
        verify_evaluation_result_observation_binding(
            db,
            provenance,
        )
    ):
        raise HveeDecisionPersistenceError(
            "matched-release observations no "
            "longer match result provenance"
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
            "matched-release provenance is "
            "missing observation evidence"
        )

    observation_sha256 = (
        observation_bundle.get("sha256")
    )

    if (
        not isinstance(
            observation_sha256,
            str,
        )
        or len(observation_sha256) != 64
    ):
        raise HveeDecisionPersistenceError(
            "matched-release observation "
            "evidence digest is invalid"
        )

    try:
        records = tuple(
            load_test_case_observation_evidence_records(
                db,
                evaluation_run_id=(
                    evaluation_run_id
                ),
                test_case_id=test_case_id,
            )
        )

        # Rebuild from the exact records that will enter the
        # matched evaluator, closing the verification-to-use gap.
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
            "persisted observations cannot "
            "form matched-release evidence"
        ) from exc

    if current_bundle != observation_bundle:
        raise HveeDecisionPersistenceError(
            "matched-release observations changed "
            "after provenance verification"
        )

    return _VerifiedMatchedEvidence(
        provenance=provenance,
        observation_sha256=(
            observation_sha256
        ),
        records=records,
    )


def _build_matched_release_snapshot(
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    declared_test_case_ids: tuple[
        int,
        ...,
    ],
    policy: (
        ASRMatchedReleaseAssurancePolicyV1
    ),
    bindings: tuple[
        _MatchedBindingSpec,
        ...,
    ],
) -> _MatchedReleaseSnapshot:
    records = tuple(
        record
        for binding in bindings
        for side in (
            binding.baseline,
            binding.candidate,
        )
        for record in side.records
    )

    try:
        cohorts = (
            build_asr_matched_quality_cohorts(
                baseline_run_id=(
                    baseline_run_id
                ),
                candidate_run_id=(
                    candidate_run_id
                ),
                declared_test_case_ids=(
                    declared_test_case_ids
                ),
                records=records,
            )
        )

        result = (
            evaluate_asr_matched_release_decision(
                cohorts=cohorts,
                policy=policy,
            )
        )
    except HveeContractError as exc:
        raise HveeDecisionPersistenceError(
            "verified evidence cannot form "
            "a matched-release decision"
        ) from exc

    target = {
        "baseline_run_id": baseline_run_id,
        "candidate_run_id": candidate_run_id,
        "declared_test_case_ids": list(
            declared_test_case_ids
        ),
    }
    target_sha256 = _matched_sha256(
        target
    )

    policy_identity = {
        "key": _MATCHED_RELEASE_POLICY_KEY,
        "version": (
            _MATCHED_RELEASE_POLICY_VERSION
        ),
        "parameters": _matched_json_value(
            policy
        ),
    }
    policy_sha256 = _matched_sha256(
        policy_identity
    )

    integrity = _matched_enum_text(
        result.assurance.integrity,
        field_name="integrity assessment",
    )
    evidence = _matched_enum_text(
        result.assurance.evidence,
        field_name="evidence assessment",
    )
    critical = _matched_enum_text(
        result.critical,
        field_name="critical assessment",
    )
    claim = _matched_enum_text(
        result.assurance.claim,
        field_name="claim assessment",
    )
    verdict = _matched_enum_text(
        result.decision.verdict,
        field_name="verdict",
    )
    reason = _matched_enum_text(
        result.decision.reason,
        field_name="reason",
    )

    decision_payload = {
        "schema_version": (
            _MATCHED_RELEASE_DECISION_SCHEMA_VERSION
        ),
        "evaluation_type": (
            ASR_EVALUATION_TYPE
        ),
        "target": target,
        "target_sha256": target_sha256,
        "policy": {
            **policy_identity,
            "sha256": policy_sha256,
        },
        "evidence_bindings": [
            binding.payload()
            for binding in bindings
        ],
        "assessments": {
            "integrity": integrity,
            "evidence": evidence,
            "critical": critical,
            "claim": claim,
        },
        "decision": {
            "verdict": verdict,
            "reason": reason,
        },
        "scientific_result": (
            _matched_json_value(result)
        ),
    }
    decision_sha256 = _matched_sha256(
        decision_payload
    )

    return _MatchedReleaseSnapshot(
        target_sha256=target_sha256,
        policy_sha256=policy_sha256,
        integrity_assessment=integrity,
        evidence_assessment=evidence,
        critical_assessment=critical,
        claim_assessment=claim,
        verdict=verdict,
        reason=reason,
        decision_payload=decision_payload,
        decision_sha256=decision_sha256,
        bindings=bindings,
    )


def _get_existing_matched_release_decision(
    db: Session,
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    snapshot: _MatchedReleaseSnapshot,
) -> HveeMatchedReleaseDecision | None:
    return db.scalar(
        select(
            HveeMatchedReleaseDecision
        ).where(
            HveeMatchedReleaseDecision
            .baseline_run_id
            == baseline_run_id,
            HveeMatchedReleaseDecision
            .candidate_run_id
            == candidate_run_id,
            HveeMatchedReleaseDecision
            .target_sha256
            == snapshot.target_sha256,
            HveeMatchedReleaseDecision
            .policy_sha256
            == snapshot.policy_sha256,
            HveeMatchedReleaseDecision
            .schema_version
            == (
                _MATCHED_RELEASE_DECISION_SCHEMA_VERSION
            ),
        )
    )


def _matched_bindings_match(
    db: Session,
    *,
    decision_id: int,
    snapshot: _MatchedReleaseSnapshot,
) -> bool:
    rows = tuple(
        db.scalars(
            select(
                HveeMatchedReleaseDecisionBinding
            )
            .where(
                HveeMatchedReleaseDecisionBinding
                .matched_release_decision_id
                == decision_id
            )
            .order_by(
                HveeMatchedReleaseDecisionBinding
                .test_case_id
            )
        ).all()
    )

    expected = tuple(
        sorted(
            snapshot.bindings,
            key=lambda item: (
                item.test_case_id
            ),
        )
    )

    if len(rows) != len(expected):
        return False

    return all(
        (
            row.test_case_id
            == binding.test_case_id
            and (
                row.baseline_result_provenance_id
                == binding.baseline.provenance.id
            )
            and (
                row.baseline_provenance_sha256
                == (
                    binding.baseline.provenance
                    .provenance_sha256
                )
            )
            and (
                row.baseline_observation_evidence_sha256
                == (
                    binding.baseline
                    .observation_sha256
                )
            )
            and (
                row.candidate_result_provenance_id
                == binding.candidate.provenance.id
            )
            and (
                row.candidate_provenance_sha256
                == (
                    binding.candidate.provenance
                    .provenance_sha256
                )
            )
            and (
                row.candidate_observation_evidence_sha256
                == (
                    binding.candidate
                    .observation_sha256
                )
            )
        )
        for row, binding in zip(
            rows,
            expected,
            strict=True,
        )
    )


def _matched_release_decision_matches(
    db: Session,
    *,
    decision: HveeMatchedReleaseDecision,
    baseline_run_id: int,
    candidate_run_id: int,
    snapshot: _MatchedReleaseSnapshot,
) -> bool:
    return (
        decision.baseline_run_id
        == baseline_run_id
        and decision.candidate_run_id
        == candidate_run_id
        and decision.target_sha256
        == snapshot.target_sha256
        and decision.schema_version
        == (
            _MATCHED_RELEASE_DECISION_SCHEMA_VERSION
        )
        and decision.evaluation_type
        == ASR_EVALUATION_TYPE
        and decision.policy_key
        == _MATCHED_RELEASE_POLICY_KEY
        and decision.policy_version
        == _MATCHED_RELEASE_POLICY_VERSION
        and decision.policy_sha256
        == snapshot.policy_sha256
        and decision.integrity_assessment
        == snapshot.integrity_assessment
        and decision.evidence_assessment
        == snapshot.evidence_assessment
        and decision.critical_assessment
        == snapshot.critical_assessment
        and decision.claim_assessment
        == snapshot.claim_assessment
        and decision.verdict
        == snapshot.verdict
        and decision.reason
        == snapshot.reason
        and decision.decision_payload
        == snapshot.decision_payload
        and decision.decision_sha256
        == snapshot.decision_sha256
        and _matched_bindings_match(
            db,
            decision_id=decision.id,
            snapshot=snapshot,
        )
    )


def _build_matched_release_decision_row(
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    snapshot: _MatchedReleaseSnapshot,
) -> HveeMatchedReleaseDecision:
    return HveeMatchedReleaseDecision(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        target_sha256=(
            snapshot.target_sha256
        ),
        schema_version=(
            _MATCHED_RELEASE_DECISION_SCHEMA_VERSION
        ),
        evaluation_type=(
            ASR_EVALUATION_TYPE
        ),
        policy_key=(
            _MATCHED_RELEASE_POLICY_KEY
        ),
        policy_version=(
            _MATCHED_RELEASE_POLICY_VERSION
        ),
        policy_sha256=(
            snapshot.policy_sha256
        ),
        integrity_assessment=(
            snapshot.integrity_assessment
        ),
        evidence_assessment=(
            snapshot.evidence_assessment
        ),
        critical_assessment=(
            snapshot.critical_assessment
        ),
        claim_assessment=(
            snapshot.claim_assessment
        ),
        verdict=snapshot.verdict,
        reason=snapshot.reason,
        decision_payload=(
            snapshot.decision_payload
        ),
        decision_sha256=(
            snapshot.decision_sha256
        ),
    )


def _build_matched_release_binding_rows(
    *,
    decision_id: int,
    snapshot: _MatchedReleaseSnapshot,
) -> list[
    HveeMatchedReleaseDecisionBinding
]:
    return [
        HveeMatchedReleaseDecisionBinding(
            matched_release_decision_id=(
                decision_id
            ),
            test_case_id=(
                binding.test_case_id
            ),
            baseline_result_provenance_id=(
                binding.baseline.provenance.id
            ),
            baseline_provenance_sha256=(
                binding.baseline.provenance
                .provenance_sha256
            ),
            baseline_observation_evidence_sha256=(
                binding.baseline
                .observation_sha256
            ),
            candidate_result_provenance_id=(
                binding.candidate.provenance.id
            ),
            candidate_provenance_sha256=(
                binding.candidate.provenance
                .provenance_sha256
            ),
            candidate_observation_evidence_sha256=(
                binding.candidate
                .observation_sha256
            ),
        )
        for binding in snapshot.bindings
    ]


def stage_asr_hvee_matched_release_decision(
    db: Session,
    *,
    baseline_run_id: int,
    candidate_run_id: int,
    declared_test_case_ids: tuple[
        int,
        ...,
    ],
    policy: (
        ASRMatchedReleaseAssurancePolicyV1
    ),
) -> HveeMatchedReleaseDecision:
    """
    Stage one immutable matched ASR release decision.

    All observations, provenance bindings, assessments, statistical
    results, and the final verdict are reconstructed internally from
    persisted evidence. The caller owns the surrounding transaction.
    """

    if not isinstance(
        policy,
        ASRMatchedReleaseAssurancePolicyV1,
    ):
        raise HveeDecisionPersistenceError(
            "matched-release decision requires "
            "ASRMatchedReleaseAssurancePolicyV1"
        )

    baseline_run_id = _require_positive_id(
        baseline_run_id,
        field_name="baseline run id",
    )
    candidate_run_id = _require_positive_id(
        candidate_run_id,
        field_name="candidate run id",
    )

    if baseline_run_id == candidate_run_id:
        raise HveeDecisionPersistenceError(
            "matched-release decision "
            "requires distinct runs"
        )

    test_case_ids = (
        _normalize_declared_test_case_ids(
            declared_test_case_ids
        )
    )

    baseline_run = _load_matched_asr_run(
        db,
        run_id=baseline_run_id,
    )
    candidate_run = _load_matched_asr_run(
        db,
        run_id=candidate_run_id,
    )

    if (
        baseline_run.project_id
        != candidate_run.project_id
    ):
        raise HveeDecisionPersistenceError(
            "matched-release runs must "
            "belong to the same project"
        )

    bindings = []

    for test_case_id in test_case_ids:
        _validate_matched_test_case_project(
            db,
            test_case_id=test_case_id,
            project_id=(
                baseline_run.project_id
            ),
        )

        baseline = (
            _load_verified_matched_evidence(
                db,
                evaluation_run_id=(
                    baseline_run_id
                ),
                test_case_id=test_case_id,
            )
        )
        candidate_evidence = (
            _load_verified_matched_evidence(
                db,
                evaluation_run_id=(
                    candidate_run_id
                ),
                test_case_id=test_case_id,
            )
        )

        bindings.append(
            _MatchedBindingSpec(
                test_case_id=test_case_id,
                baseline=baseline,
                candidate=candidate_evidence,
            )
        )

    snapshot = (
        _build_matched_release_snapshot(
            baseline_run_id=(
                baseline_run_id
            ),
            candidate_run_id=(
                candidate_run_id
            ),
            declared_test_case_ids=(
                test_case_ids
            ),
            policy=policy,
            bindings=tuple(bindings),
        )
    )

    existing = (
        _get_existing_matched_release_decision(
            db,
            baseline_run_id=(
                baseline_run_id
            ),
            candidate_run_id=(
                candidate_run_id
            ),
            snapshot=snapshot,
        )
    )

    if existing is not None:
        if not _matched_release_decision_matches(
            db,
            decision=existing,
            baseline_run_id=(
                baseline_run_id
            ),
            candidate_run_id=(
                candidate_run_id
            ),
            snapshot=snapshot,
        ):
            raise HveeDecisionConflictError(
                "existing matched-release decision "
                "conflicts with canonical evidence"
            )

        return existing

    candidate = (
        _build_matched_release_decision_row(
            baseline_run_id=(
                baseline_run_id
            ),
            candidate_run_id=(
                candidate_run_id
            ),
            snapshot=snapshot,
        )
    )

    try:
        # Preserve the caller's outer transaction if another
        # transaction wins this immutable identity race.
        with db.begin_nested():
            db.add(candidate)
            db.flush()

            db.add_all(
                _build_matched_release_binding_rows(
                    decision_id=candidate.id,
                    snapshot=snapshot,
                )
            )
            db.flush()

        return candidate

    except IntegrityError:
        existing = (
            _get_existing_matched_release_decision(
                db,
                baseline_run_id=(
                    baseline_run_id
                ),
                candidate_run_id=(
                    candidate_run_id
                ),
                snapshot=snapshot,
            )
        )

        if existing is None:
            raise

        if not _matched_release_decision_matches(
            db,
            decision=existing,
            baseline_run_id=(
                baseline_run_id
            ),
            candidate_run_id=(
                candidate_run_id
            ),
            snapshot=snapshot,
        ):
            raise HveeDecisionConflictError(
                "concurrent matched-release "
                "decision conflicts with "
                "canonical evidence"
            )

        return existing
