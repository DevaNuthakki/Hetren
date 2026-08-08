from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from hvee.core.contracts import HveeContractError
from hvee.core.decision import (
    ClaimAssessment,
    CriticalAssessment,
    DecisionInputs,
    DecisionReason,
    DecisionResult,
    DecisionVerdict,
    EvidenceAssessment,
    IntegrityAssessment,
    decide,
)
from hvee.core.evidence_readiness import EvidenceTarget


DECISION_EVIDENCE_SCHEMA_VERSION = 1


def _require_non_empty_string(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
    ):
        raise HveeContractError(
            f"{name} must be a non-empty string "
            "without surrounding whitespace"
        )

    return value


def _require_positive_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise HveeContractError(
            f"{name} must be a positive integer"
        )

    return value


def _require_sha256_hex(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 hex digest"
        )

    return value


def _canonicalize_json_value(
    value: object,
    *,
    name: str,
) -> object:
    """
    Normalize a JSON-compatible value through deterministic JSON.

    The serialization convention intentionally matches the existing
    Hetren evidence/provenance convention.
    """

    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        return json.loads(serialized)

    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def _canonical_json(
    value: object,
    *,
    name: str,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def _calculate_sha256(
    value: object,
    *,
    name: str,
) -> str:
    canonical = _canonical_json(
        value,
        name=name,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def calculate_policy_sha256(
    *,
    policy_key: str,
    policy_version: str,
    policy_snapshot: dict[str, object],
) -> str:
    """
    Bind both policy identity and policy configuration.

    The snapshot alone is insufficient because two different policy
    identities may legitimately use identical configuration.
    """

    key = _require_non_empty_string(
        name="policy key",
        value=policy_key,
    )
    version = _require_non_empty_string(
        name="policy version",
        value=policy_version,
    )

    snapshot = _canonicalize_json_value(
        policy_snapshot,
        name="policy snapshot",
    )

    if not isinstance(snapshot, dict):
        raise HveeContractError(
            "policy snapshot must be a JSON object"
        )

    body = {
        "key": key,
        "version": version,
        "snapshot": snapshot,
    }

    return _calculate_sha256(
        body,
        name="policy evidence",
    )


def calculate_decision_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="decision evidence",
    )


@dataclass(frozen=True, slots=True)
class DecisionEvidenceBundle:
    payload: dict[str, object]
    policy_sha256: str
    decision_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "decision evidence payload must be a JSON object"
            )

        _require_sha256_hex(
            name="policy SHA-256",
            value=self.policy_sha256,
        )
        _require_sha256_hex(
            name="decision SHA-256",
            value=self.decision_sha256,
        )


def build_decision_evidence_bundle(
    *,
    evaluation_type: str,
    target: EvidenceTarget,
    policy_key: str,
    policy_version: str,
    policy_snapshot: dict[str, object],
    result_provenance_id: int,
    provenance_sha256: str,
    observation_evidence_sha256: str,
    integrity: IntegrityAssessment,
    evidence: EvidenceAssessment,
    critical: CriticalAssessment,
    claim: ClaimAssessment,
    decision: DecisionResult,
    readiness_snapshot: dict[str, object],
    findings: list[dict[str, object]]
    | tuple[dict[str, object], ...],
) -> DecisionEvidenceBundle:
    """
    Build deterministic, domain-neutral evidence for one HVEE decision.

    Domain packs own policy semantics, readiness diagnostics, and rule
    findings. This core contract owns identity binding, canonical JSON,
    kernel consistency, and deterministic hashing.
    """

    normalized_evaluation_type = (
        _require_non_empty_string(
            name="evaluation type",
            value=evaluation_type,
        )
    )

    if not isinstance(
        target,
        EvidenceTarget,
    ):
        raise HveeContractError(
            "decision evidence target must be an EvidenceTarget"
        )

    normalized_policy_key = (
        _require_non_empty_string(
            name="policy key",
            value=policy_key,
        )
    )
    normalized_policy_version = (
        _require_non_empty_string(
            name="policy version",
            value=policy_version,
        )
    )

    normalized_provenance_id = (
        _require_positive_integer(
            name="result provenance id",
            value=result_provenance_id,
        )
    )

    normalized_provenance_sha256 = (
        _require_sha256_hex(
            name="provenance SHA-256",
            value=provenance_sha256,
        )
    )
    normalized_observation_sha256 = (
        _require_sha256_hex(
            name="observation evidence SHA-256",
            value=observation_evidence_sha256,
        )
    )

    if not isinstance(
        integrity,
        IntegrityAssessment,
    ):
        raise HveeContractError(
            "decision evidence integrity must be "
            "an IntegrityAssessment"
        )

    if not isinstance(
        evidence,
        EvidenceAssessment,
    ):
        raise HveeContractError(
            "decision evidence sufficiency must be "
            "an EvidenceAssessment"
        )

    if not isinstance(
        critical,
        CriticalAssessment,
    ):
        raise HveeContractError(
            "decision evidence critical assessment must be "
            "a CriticalAssessment"
        )

    if not isinstance(
        claim,
        ClaimAssessment,
    ):
        raise HveeContractError(
            "decision evidence claim assessment must be "
            "a ClaimAssessment"
        )

    if not isinstance(
        decision,
        DecisionResult,
    ):
        raise HveeContractError(
            "decision evidence requires a DecisionResult"
        )

    expected_decision = decide(
        DecisionInputs(
            integrity=integrity,
            critical=critical,
            evidence=evidence,
            claim=claim,
        )
    )

    if decision != expected_decision:
        raise HveeContractError(
            "decision evidence verdict does not match "
            "the HVEE decision kernel"
        )

    normalized_policy_snapshot = (
        _canonicalize_json_value(
            policy_snapshot,
            name="policy snapshot",
        )
    )

    if not isinstance(
        normalized_policy_snapshot,
        dict,
    ):
        raise HveeContractError(
            "policy snapshot must be a JSON object"
        )

    normalized_readiness = (
        _canonicalize_json_value(
            readiness_snapshot,
            name="readiness snapshot",
        )
    )

    if not isinstance(
        normalized_readiness,
        dict,
    ):
        raise HveeContractError(
            "readiness snapshot must be a JSON object"
        )

    if not isinstance(
        findings,
        (list, tuple),
    ):
        raise HveeContractError(
            "decision findings must be a list or tuple"
        )

    normalized_findings: list[
        dict[str, object]
    ] = []

    for finding in findings:
        normalized = _canonicalize_json_value(
            finding,
            name="decision finding",
        )

        if not isinstance(
            normalized,
            dict,
        ):
            raise HveeContractError(
                "each decision finding must be a JSON object"
            )

        normalized_findings.append(
            normalized
        )

    policy_sha256 = calculate_policy_sha256(
        policy_key=normalized_policy_key,
        policy_version=normalized_policy_version,
        policy_snapshot=normalized_policy_snapshot,
    )

    payload: dict[str, object] = {
        "schema_version": (
            DECISION_EVIDENCE_SCHEMA_VERSION
        ),
        "evaluation_type": (
            normalized_evaluation_type
        ),
        "target": {
            "evaluation_run_id": (
                target.evaluation_run_id
            ),
            "test_case_id": (
                target.test_case_id
            ),
        },
        "policy": {
            "key": normalized_policy_key,
            "version": normalized_policy_version,
            "snapshot": (
                normalized_policy_snapshot
            ),
            "sha256": policy_sha256,
        },
        "evidence": {
            "result_provenance_id": (
                normalized_provenance_id
            ),
            "provenance_sha256": (
                normalized_provenance_sha256
            ),
            "observation_evidence_sha256": (
                normalized_observation_sha256
            ),
        },
        "assessments": {
            "integrity": integrity.value,
            "evidence": evidence.value,
            "critical": critical.value,
            "claim": claim.value,
        },
        "readiness": normalized_readiness,
        "findings": normalized_findings,
        "decision": {
            "verdict": decision.verdict.value,
            "reason": decision.reason.value,
        },
    }

    canonical_payload = _canonicalize_json_value(
        payload,
        name="decision evidence",
    )

    if not isinstance(
        canonical_payload,
        dict,
    ):
        raise HveeContractError(
            "decision evidence must be a JSON object"
        )

    return DecisionEvidenceBundle(
        payload=canonical_payload,
        policy_sha256=policy_sha256,
        decision_sha256=(
            calculate_decision_sha256(
                canonical_payload
            )
        ),
    )


def verify_decision_evidence_bundle(
    *,
    payload: object,
    expected_decision_sha256: object,
) -> bool:
    """
    Verify one persisted decision-evidence payload.

    This verifies internal canonical binding and universal-kernel
    consistency. Domain-specific re-evaluation remains the
    responsibility of the corresponding domain-pack adapter.
    """

    try:
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "schema_version",
                "evaluation_type",
                "target",
                "policy",
                "evidence",
                "assessments",
                "readiness",
                "findings",
                "decision",
            }
            or payload.get("schema_version")
            != DECISION_EVIDENCE_SCHEMA_VERSION
        ):
            return False

        target_payload = payload.get(
            "target"
        )
        policy_payload = payload.get(
            "policy"
        )
        evidence_payload = payload.get(
            "evidence"
        )
        assessments_payload = payload.get(
            "assessments"
        )
        decision_payload = payload.get(
            "decision"
        )
        readiness_payload = payload.get(
            "readiness"
        )
        findings_payload = payload.get(
            "findings"
        )

        if (
            not isinstance(
                target_payload,
                dict,
            )
            or set(target_payload)
            != {
                "evaluation_run_id",
                "test_case_id",
            }
            or not isinstance(
                policy_payload,
                dict,
            )
            or set(policy_payload)
            != {
                "key",
                "version",
                "snapshot",
                "sha256",
            }
            or not isinstance(
                evidence_payload,
                dict,
            )
            or set(evidence_payload)
            != {
                "result_provenance_id",
                "provenance_sha256",
                "observation_evidence_sha256",
            }
            or not isinstance(
                assessments_payload,
                dict,
            )
            or set(assessments_payload)
            != {
                "integrity",
                "evidence",
                "critical",
                "claim",
            }
            or not isinstance(
                decision_payload,
                dict,
            )
            or set(decision_payload)
            != {
                "verdict",
                "reason",
            }
            or not isinstance(
                readiness_payload,
                dict,
            )
            or not isinstance(
                findings_payload,
                list,
            )
        ):
            return False

        target = EvidenceTarget(
            evaluation_run_id=(
                target_payload.get(
                    "evaluation_run_id"
                )
            ),
            test_case_id=(
                target_payload.get(
                    "test_case_id"
                )
            ),
        )

        integrity = IntegrityAssessment(
            assessments_payload.get(
                "integrity"
            )
        )
        evidence = EvidenceAssessment(
            assessments_payload.get(
                "evidence"
            )
        )
        critical = CriticalAssessment(
            assessments_payload.get(
                "critical"
            )
        )
        claim = ClaimAssessment(
            assessments_payload.get(
                "claim"
            )
        )

        decision = DecisionResult(
            verdict=DecisionVerdict(
                decision_payload.get(
                    "verdict"
                )
            ),
            reason=DecisionReason(
                decision_payload.get(
                    "reason"
                )
            ),
        )

        rebuilt = build_decision_evidence_bundle(
            evaluation_type=payload.get(
                "evaluation_type"
            ),
            target=target,
            policy_key=policy_payload.get(
                "key"
            ),
            policy_version=policy_payload.get(
                "version"
            ),
            policy_snapshot=policy_payload.get(
                "snapshot"
            ),
            result_provenance_id=(
                evidence_payload.get(
                    "result_provenance_id"
                )
            ),
            provenance_sha256=(
                evidence_payload.get(
                    "provenance_sha256"
                )
            ),
            observation_evidence_sha256=(
                evidence_payload.get(
                    "observation_evidence_sha256"
                )
            ),
            integrity=integrity,
            evidence=evidence,
            critical=critical,
            claim=claim,
            decision=decision,
            readiness_snapshot=(
                readiness_payload
            ),
            findings=findings_payload,
        )

        stored_policy_sha256 = (
            policy_payload.get(
                "sha256"
            )
        )

        _require_sha256_hex(
            name="stored policy SHA-256",
            value=stored_policy_sha256,
        )
        normalized_expected_sha256 = (
            _require_sha256_hex(
                name="expected decision SHA-256",
                value=expected_decision_sha256,
            )
        )

        return (
            payload == rebuilt.payload
            and stored_policy_sha256
            == rebuilt.policy_sha256
            and normalized_expected_sha256
            == rebuilt.decision_sha256
        )

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False
