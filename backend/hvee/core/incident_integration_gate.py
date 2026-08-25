"""Final integration gate for Incident Mode stages 1 through 8.

This gate adds no new execution authority.

It consumes the complete Incident Mode evidence chain:

1. Incident Intake
2. Replay Preparation
3. Environment Manifest
4. Runner Compatibility
5. Environment Materialization
6. Controlled Replay
7. Reproduction Evidence

The reproduction-evidence verifier already transitively rebuilds and
reverifies the complete upstream chain. This final gate invokes that
verification again and additionally checks cross-stage identity,
commitment-link, stage-boundary, and reproduction-verdict consistency.

A verified integration result is intentionally separate from whether the
incident was reproduced.

For example:

    integration_verified = True
    reproduction_verdict = "indeterminate"

is a valid completed Incident Mode outcome.

This stage never establishes model failure, causality, counterexample
confirmation, contract promotion, blocking release authority, production
qualification, or evaluator/governance approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.incident_reproduction_evidence import (
    IncidentReproductionComparisonObservation,
    IncidentReproductionVerdict,
    verify_incident_reproduction_evidence_bundle,
)
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
)


INCIDENT_INTEGRATION_GATE_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)


class IncidentIntegrationStatus(StrEnum):
    VERIFIED_REPRODUCED = "verified_reproduced"
    VERIFIED_NOT_REPRODUCED = (
        "verified_not_reproduced"
    )
    VERIFIED_INDETERMINATE = (
        "verified_indeterminate"
    )
    BLOCKED_INCONSISTENT_CHAIN = (
        "blocked_inconsistent_chain"
    )


@dataclass(frozen=True, slots=True)
class IncidentIntegrationGateBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "incident integration gate payload "
                "must be a JSON object"
            )

        _require_sha256(
            name="incident integration gate SHA-256",
            value=self.sha256,
        )


_CONTENT_BOUNDARY = {
    "raw_audio_embedded": False,
    "raw_transcript_embedded": False,
    "artifact_bytes_embedded": False,
    "transport_trace_embedded": False,
    "local_artifact_locator_embedded": False,
    "environment_values_embedded": False,
    "upstream_payloads_embedded": False,
    "upstream_commitments_embedded": True,
    "reproduction_verdict_embedded": True,
}

_POLICY = {
    "complete_incident_chain_must_reverify": True,
    "cross_stage_identity_must_match": True,
    "cross_stage_commitments_must_match": True,
    "cross_stage_boundaries_must_be_consistent": True,
    "integration_verification_is_not_reproduction": True,
    "reproduction_is_not_model_failure_proof": True,
    "reproduction_is_not_causal_proof": True,
    "governance_assurance_is_separate_stage": True,
    "governance_required_before_qualification_authority": True,
    "integration_gate_executes_no_model": True,
    "integration_gate_executes_no_replay": True,
}


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise HveeContractError(
            f"{name} must be lowercase SHA-256 hex"
        )

    return value


def _canonical_json(
    value: object,
    *,
    name: str,
) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must be deterministic JSON"
        ) from exc


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    return json.loads(
        _canonical_json(
            value,
            name=name,
        )
    )


def calculate_incident_integration_gate_sha256(
    payload: dict[str, object],
) -> str:
    return hashlib.sha256(
        _canonical_json(
            payload,
            name="incident integration gate",
        ).encode("utf-8")
    ).hexdigest()


def _require_root_identity(
    intake_payload: object,
) -> tuple[str, str, str]:
    if not isinstance(
        intake_payload,
        dict,
    ):
        raise HveeContractError(
            "incident integration requires intake payload"
        )

    incident = intake_payload.get(
        "incident"
    )

    evaluation_type = intake_payload.get(
        "evaluation_type"
    )

    if (
        not isinstance(
            incident,
            dict,
        )
        or not isinstance(
            incident.get("key"),
            str,
        )
        or not incident["key"].strip()
        or not isinstance(
            incident.get("version"),
            str,
        )
        or not incident["version"].strip()
        or not isinstance(
            evaluation_type,
            str,
        )
        or not evaluation_type.strip()
    ):
        raise HveeContractError(
            "incident integration root identity "
            "must be canonical"
        )

    return (
        incident["key"],
        incident["version"],
        evaluation_type,
    )


def _all_stage_payloads(
    *,
    intake_payload: object,
    replay_preparation_payload: object,
    environment_manifest_payload: object,
    runner_compatibility_payload: object,
    environment_materialization_payload: object,
    controlled_replay_payload: object,
    reproduction_evidence_payload: object,
) -> tuple[
    tuple[str, object],
    ...,
]:
    return (
        (
            "incident_intake",
            intake_payload,
        ),
        (
            "incident_replay_preparation",
            replay_preparation_payload,
        ),
        (
            "incident_environment_manifest",
            environment_manifest_payload,
        ),
        (
            "incident_runner_compatibility",
            runner_compatibility_payload,
        ),
        (
            "incident_environment_materialization",
            environment_materialization_payload,
        ),
        (
            "incident_controlled_replay",
            controlled_replay_payload,
        ),
        (
            "incident_reproduction_evidence",
            reproduction_evidence_payload,
        ),
    )


def _identity_consistent(
    *,
    stage_payloads: tuple[
        tuple[str, object],
        ...,
    ],
    incident_key: str,
    incident_version: str,
    evaluation_type: str,
) -> bool:
    for _name, payload in stage_payloads:
        if not isinstance(
            payload,
            dict,
        ):
            return False

        incident = payload.get(
            "incident"
        )

        if (
            not isinstance(
                incident,
                dict,
            )
            or incident.get(
                "key"
            )
            != incident_key
            or incident.get(
                "version"
            )
            != incident_version
            or payload.get(
                "evaluation_type"
            )
            != evaluation_type
        ):
            return False

    return True


def _incident_payload(
    payload: object,
) -> dict[str, object] | None:
    if not isinstance(
        payload,
        dict,
    ):
        return None

    incident = payload.get(
        "incident"
    )

    if not isinstance(
        incident,
        dict,
    ):
        return None

    return incident


def _commitments_consistent(
    *,
    replay_preparation_payload: object,
    environment_manifest_payload: object,
    runner_compatibility_payload: object,
    environment_materialization_payload: object,
    controlled_replay_payload: object,
    reproduction_evidence_payload: object,
    intake_sha256: str,
    replay_preparation_sha256: str,
    environment_manifest_sha256: str,
    runner_compatibility_sha256: str,
    environment_materialization_sha256: str,
    controlled_replay_sha256: str,
) -> bool:
    expected = {
        "intake_sha256": (
            intake_sha256
        ),
        "replay_preparation_sha256": (
            replay_preparation_sha256
        ),
        "environment_manifest_sha256": (
            environment_manifest_sha256
        ),
        "runner_compatibility_sha256": (
            runner_compatibility_sha256
        ),
        "environment_materialization_sha256": (
            environment_materialization_sha256
        ),
        "controlled_replay_sha256": (
            controlled_replay_sha256
        ),
    }

    stages = (
        (
            replay_preparation_payload,
            (
                "intake_sha256",
            ),
        ),
        (
            environment_manifest_payload,
            (
                "intake_sha256",
                "replay_preparation_sha256",
            ),
        ),
        (
            runner_compatibility_payload,
            (
                "intake_sha256",
                "replay_preparation_sha256",
                "environment_manifest_sha256",
            ),
        ),
        (
            environment_materialization_payload,
            (
                "intake_sha256",
                "replay_preparation_sha256",
                "environment_manifest_sha256",
                "runner_compatibility_sha256",
            ),
        ),
        (
            controlled_replay_payload,
            (
                "intake_sha256",
                "replay_preparation_sha256",
                "environment_manifest_sha256",
                "runner_compatibility_sha256",
                "environment_materialization_sha256",
            ),
        ),
        (
            reproduction_evidence_payload,
            (
                "intake_sha256",
                "replay_preparation_sha256",
                "environment_manifest_sha256",
                "runner_compatibility_sha256",
                "environment_materialization_sha256",
                "controlled_replay_sha256",
            ),
        ),
    )

    for payload, required_fields in stages:
        incident = _incident_payload(
            payload
        )

        if incident is None:
            return False

        for field_name in required_fields:
            if (
                field_name
                not in incident
                or incident.get(
                    field_name
                )
                != expected[field_name]
            ):
                return False

        for field_name, expected_value in (
            expected.items()
        ):
            if (
                field_name
                in incident
                and incident.get(
                    field_name
                )
                != expected_value
            ):
                return False

    return True


def _replay_preparation_ready(
    payload: object,
) -> bool:
    if not isinstance(
        payload,
        dict,
    ):
        return False

    verification = payload.get(
        "artifact_verification"
    )
    preparation = payload.get(
        "preparation"
    )
    boundary = payload.get(
        "evidence_boundary"
    )

    return (
        isinstance(
            verification,
            dict,
        )
        and isinstance(
            preparation,
            dict,
        )
        and isinstance(
            boundary,
            dict,
        )
        and verification.get(
            "status"
        )
        == "verified"
        and verification.get(
            "all_referenced_artifacts_verified"
        )
        is True
        and verification.get(
            "runner_custody_status"
        )
        == "verified"
        and preparation.get(
            "status"
        )
        == "prepared"
        and preparation.get(
            "replay_plan_prepared"
        )
        is True
        and boundary.get(
            "artifact_bytes_verified"
        )
        is True
        and boundary.get(
            "replay_plan_prepared"
        )
        is True
        and boundary.get(
            "replay_executed"
        )
        is False
    )


def _environment_manifest_ready(
    payload: object,
) -> bool:
    if not isinstance(
        payload,
        dict,
    ):
        return False

    environment = payload.get(
        "environment"
    )
    boundary = payload.get(
        "evidence_boundary"
    )

    return (
        isinstance(
            environment,
            dict,
        )
        and isinstance(
            boundary,
            dict,
        )
        and environment.get(
            "status"
        )
        == "ready"
        and environment.get(
            "materialization_started"
        )
        is False
        and boundary.get(
            "environment_materialized"
        )
        is False
        and boundary.get(
            "replay_executed"
        )
        is False
    )


def _runner_compatibility_ready(
    payload: object,
) -> bool:
    if not isinstance(
        payload,
        dict,
    ):
        return False

    compatibility = payload.get(
        "compatibility"
    )
    boundary = payload.get(
        "evidence_boundary"
    )

    return (
        isinstance(
            compatibility,
            dict,
        )
        and isinstance(
            boundary,
            dict,
        )
        and compatibility.get(
            "status"
        )
        in {
            "exact",
            "compatible",
        }
        and compatibility.get(
            "ready_for_materialization"
        )
        is True
        and boundary.get(
            "environment_materialized"
        )
        is False
        and boundary.get(
            "replay_executed"
        )
        is False
    )


def _materialization_ready(
    payload: object,
) -> bool:
    if not isinstance(
        payload,
        dict,
    ):
        return False

    materialization = payload.get(
        "materialization"
    )
    boundary = payload.get(
        "evidence_boundary"
    )

    return (
        isinstance(
            materialization,
            dict,
        )
        and isinstance(
            boundary,
            dict,
        )
        and materialization.get(
            "status"
        )
        == "materialized"
        and materialization.get(
            "environment_materialized"
        )
        is True
        and boundary.get(
            "operator_authorization_granted"
        )
        is True
        and boundary.get(
            "environment_materialized"
        )
        is True
        and boundary.get(
            "replay_executed"
        )
        is False
    )


def _controlled_replay_ready(
    payload: object,
) -> bool:
    if not isinstance(
        payload,
        dict,
    ):
        return False

    execution = payload.get(
        "execution"
    )
    boundary = payload.get(
        "evidence_boundary"
    )

    return (
        isinstance(
            execution,
            dict,
        )
        and isinstance(
            boundary,
            dict,
        )
        and execution.get(
            "status"
        )
        == "executed"
        and boundary.get(
            "operator_authorization_granted"
        )
        is True
        and boundary.get(
            "environment_materialized"
        )
        is True
        and boundary.get(
            "replay_executed"
        )
        is True
        and boundary.get(
            "replay_output_captured"
        )
        is True
        and boundary.get(
            "behavior_commitments_compared"
        )
        is False
        and boundary.get(
            "reproduction_claimed"
        )
        is False
    )


@dataclass(frozen=True, slots=True)
class _ReproductionConsistency:
    consistent: bool
    verdict: str | None
    determined: bool
    reproduced: bool


def _reproduction_consistency(
    payload: object,
) -> _ReproductionConsistency:
    if not isinstance(
        payload,
        dict,
    ):
        return _ReproductionConsistency(
            consistent=False,
            verdict=None,
            determined=False,
            reproduced=False,
        )

    comparison = payload.get(
        "comparison"
    )
    boundary = payload.get(
        "evidence_boundary"
    )

    if (
        not isinstance(
            comparison,
            dict,
        )
        or not isinstance(
            boundary,
            dict,
        )
    ):
        return _ReproductionConsistency(
            consistent=False,
            verdict=None,
            determined=False,
            reproduced=False,
        )

    verdict = comparison.get(
        "verdict"
    )
    reason = comparison.get(
        "reason"
    )
    status = comparison.get(
        "status"
    )
    exact_match = comparison.get(
        "reported_behavior_exact_match"
    )

    compared = boundary.get(
        "behavior_commitments_compared"
    )
    determined = boundary.get(
        "reproduction_determined"
    )
    claimed = boundary.get(
        "reproduction_claimed"
    )

    if (
        verdict
        == (
            IncidentReproductionVerdict
            .REPRODUCED
            .value
        )
    ):
        consistent = (
            status == "compared"
            and reason
            == "exact_reported_behavior_match"
            and exact_match is True
            and compared is True
            and determined is True
            and claimed is True
        )

        return _ReproductionConsistency(
            consistent=consistent,
            verdict=verdict,
            determined=(
                consistent
            ),
            reproduced=(
                consistent
            ),
        )

    if (
        verdict
        == (
            IncidentReproductionVerdict
            .NOT_REPRODUCED
            .value
        )
    ):
        consistent = (
            status == "compared"
            and reason
            == "reported_behavior_mismatch"
            and exact_match is False
            and compared is True
            and determined is True
            and claimed is False
        )

        return _ReproductionConsistency(
            consistent=consistent,
            verdict=verdict,
            determined=(
                consistent
            ),
            reproduced=False,
        )

    if (
        verdict
        == (
            IncidentReproductionVerdict
            .INDETERMINATE
            .value
        )
    ):
        consistent = (
            status == "indeterminate"
            and reason
            in {
                "behavior_commitments_unavailable",
                "behavior_commitment_semantics_unconfirmed",
            }
            and exact_match is None
            and compared is False
            and determined is False
            and claimed is False
        )

        return _ReproductionConsistency(
            consistent=consistent,
            verdict=verdict,
            determined=False,
            reproduced=False,
        )

    return _ReproductionConsistency(
        consistent=False,
        verdict=None,
        determined=False,
        reproduced=False,
    )


def _stage_boundaries_consistent(
    *,
    replay_preparation_payload: object,
    environment_manifest_payload: object,
    runner_compatibility_payload: object,
    environment_materialization_payload: object,
    controlled_replay_payload: object,
    reproduction_evidence_payload: object,
) -> tuple[
    bool,
    _ReproductionConsistency,
]:
    reproduction = (
        _reproduction_consistency(
            reproduction_evidence_payload
        )
    )

    consistent = all(
        (
            _replay_preparation_ready(
                replay_preparation_payload
            ),
            _environment_manifest_ready(
                environment_manifest_payload
            ),
            _runner_compatibility_ready(
                runner_compatibility_payload
            ),
            _materialization_ready(
                environment_materialization_payload
            ),
            _controlled_replay_ready(
                controlled_replay_payload
            ),
            reproduction.consistent,
        )
    )

    return (
        consistent,
        reproduction,
    )


def _integration_status(
    *,
    verified: bool,
    reproduction: _ReproductionConsistency,
) -> IncidentIntegrationStatus:
    if not verified:
        return (
            IncidentIntegrationStatus
            .BLOCKED_INCONSISTENT_CHAIN
        )

    if (
        reproduction.verdict
        == (
            IncidentReproductionVerdict
            .REPRODUCED
            .value
        )
    ):
        return (
            IncidentIntegrationStatus
            .VERIFIED_REPRODUCED
        )

    if (
        reproduction.verdict
        == (
            IncidentReproductionVerdict
            .NOT_REPRODUCED
            .value
        )
    ):
        return (
            IncidentIntegrationStatus
            .VERIFIED_NOT_REPRODUCED
        )

    return (
        IncidentIntegrationStatus
        .VERIFIED_INDETERMINATE
    )


def build_incident_integration_gate_bundle(
    *,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    runner_compatibility_payload: object,
    expected_runner_compatibility_sha256: object,
    required_capabilities: list[str] | tuple[str, ...],
    compatibility_observation: (
        IncidentRunnerEnvironmentObservation
    ),
    environment_materialization_payload: object,
    expected_environment_materialization_sha256: object,
    controlled_replay_payload: object,
    expected_controlled_replay_sha256: object,
    reproduction_evidence_payload: object,
    expected_reproduction_evidence_sha256: object,
    comparison_observation: (
        IncidentReproductionComparisonObservation
    ),
) -> IncidentIntegrationGateBundle:
    intake_sha256 = _require_sha256(
        name="integration intake SHA-256",
        value=expected_intake_sha256,
    )

    replay_preparation_sha256 = _require_sha256(
        name="integration replay preparation SHA-256",
        value=expected_replay_preparation_sha256,
    )

    environment_manifest_sha256 = _require_sha256(
        name="integration environment manifest SHA-256",
        value=expected_environment_manifest_sha256,
    )

    runner_compatibility_sha256 = _require_sha256(
        name="integration runner compatibility SHA-256",
        value=expected_runner_compatibility_sha256,
    )

    environment_materialization_sha256 = _require_sha256(
        name="integration environment materialization SHA-256",
        value=expected_environment_materialization_sha256,
    )

    controlled_replay_sha256 = _require_sha256(
        name="integration controlled replay SHA-256",
        value=expected_controlled_replay_sha256,
    )

    reproduction_evidence_sha256 = _require_sha256(
        name="integration reproduction evidence SHA-256",
        value=expected_reproduction_evidence_sha256,
    )

    if not isinstance(
        compatibility_observation,
        IncidentRunnerEnvironmentObservation,
    ):
        raise HveeContractError(
            "integration compatibility observation "
            "must be canonical"
        )

    if not isinstance(
        comparison_observation,
        IncidentReproductionComparisonObservation,
    ):
        raise HveeContractError(
            "integration comparison observation "
            "must be canonical"
        )

    (
        incident_key,
        incident_version,
        evaluation_type,
    ) = _require_root_identity(
        intake_payload
    )

    stage_payloads = _all_stage_payloads(
        intake_payload=intake_payload,
        replay_preparation_payload=(
            replay_preparation_payload
        ),
        environment_manifest_payload=(
            environment_manifest_payload
        ),
        runner_compatibility_payload=(
            runner_compatibility_payload
        ),
        environment_materialization_payload=(
            environment_materialization_payload
        ),
        controlled_replay_payload=(
            controlled_replay_payload
        ),
        reproduction_evidence_payload=(
            reproduction_evidence_payload
        ),
    )

    chain_reverified = (
        verify_incident_reproduction_evidence_bundle(
            payload=(
                reproduction_evidence_payload
            ),
            expected_sha256=(
                reproduction_evidence_sha256
            ),
            intake_payload=intake_payload,
            expected_intake_sha256=(
                intake_sha256
            ),
            replay_preparation_payload=(
                replay_preparation_payload
            ),
            expected_replay_preparation_sha256=(
                replay_preparation_sha256
            ),
            environment_manifest_payload=(
                environment_manifest_payload
            ),
            expected_environment_manifest_sha256=(
                environment_manifest_sha256
            ),
            runner_compatibility_payload=(
                runner_compatibility_payload
            ),
            expected_runner_compatibility_sha256=(
                runner_compatibility_sha256
            ),
            required_capabilities=(
                required_capabilities
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            environment_materialization_payload=(
                environment_materialization_payload
            ),
            expected_environment_materialization_sha256=(
                environment_materialization_sha256
            ),
            controlled_replay_payload=(
                controlled_replay_payload
            ),
            expected_controlled_replay_sha256=(
                controlled_replay_sha256
            ),
            comparison_observation=(
                comparison_observation
            ),
        )
    )

    identity_consistent = (
        _identity_consistent(
            stage_payloads=(
                stage_payloads
            ),
            incident_key=incident_key,
            incident_version=(
                incident_version
            ),
            evaluation_type=(
                evaluation_type
            ),
        )
    )

    commitments_consistent = (
        _commitments_consistent(
            replay_preparation_payload=(
                replay_preparation_payload
            ),
            environment_manifest_payload=(
                environment_manifest_payload
            ),
            runner_compatibility_payload=(
                runner_compatibility_payload
            ),
            environment_materialization_payload=(
                environment_materialization_payload
            ),
            controlled_replay_payload=(
                controlled_replay_payload
            ),
            reproduction_evidence_payload=(
                reproduction_evidence_payload
            ),
            intake_sha256=(
                intake_sha256
            ),
            replay_preparation_sha256=(
                replay_preparation_sha256
            ),
            environment_manifest_sha256=(
                environment_manifest_sha256
            ),
            runner_compatibility_sha256=(
                runner_compatibility_sha256
            ),
            environment_materialization_sha256=(
                environment_materialization_sha256
            ),
            controlled_replay_sha256=(
                controlled_replay_sha256
            ),
        )
    )

    (
        boundaries_consistent,
        reproduction,
    ) = _stage_boundaries_consistent(
        replay_preparation_payload=(
            replay_preparation_payload
        ),
        environment_manifest_payload=(
            environment_manifest_payload
        ),
        runner_compatibility_payload=(
            runner_compatibility_payload
        ),
        environment_materialization_payload=(
            environment_materialization_payload
        ),
        controlled_replay_payload=(
            controlled_replay_payload
        ),
        reproduction_evidence_payload=(
            reproduction_evidence_payload
        ),
    )

    verified = all(
        (
            chain_reverified,
            identity_consistent,
            commitments_consistent,
            boundaries_consistent,
        )
    )

    status = _integration_status(
        verified=verified,
        reproduction=reproduction,
    )

    blocking_reasons: list[str] = []

    if not chain_reverified:
        blocking_reasons.append(
            "complete_chain_reverification_failed"
        )

    if not identity_consistent:
        blocking_reasons.append(
            "cross_stage_incident_identity_mismatch"
        )

    if not commitments_consistent:
        blocking_reasons.append(
            "cross_stage_commitment_mismatch"
        )

    if not boundaries_consistent:
        blocking_reasons.append(
            "cross_stage_boundary_inconsistency"
        )

    safe_reproduction_verdict = (
        reproduction.verdict
        if verified
        else None
    )

    safe_reproduction_determined = (
        reproduction.determined
        if verified
        else False
    )

    safe_reproduced = (
        reproduction.reproduced
        if verified
        else False
    )

    payload: dict[str, object] = {
        "schema_version": (
            INCIDENT_INTEGRATION_GATE_SCHEMA_VERSION
        ),
        "type": "incident_integration_gate",
        "evaluation_type": (
            evaluation_type
        ),
        "incident": {
            "key": incident_key,
            "version": incident_version,
            "intake_sha256": (
                intake_sha256
            ),
            "replay_preparation_sha256": (
                replay_preparation_sha256
            ),
            "environment_manifest_sha256": (
                environment_manifest_sha256
            ),
            "runner_compatibility_sha256": (
                runner_compatibility_sha256
            ),
            "environment_materialization_sha256": (
                environment_materialization_sha256
            ),
            "controlled_replay_sha256": (
                controlled_replay_sha256
            ),
            "reproduction_evidence_sha256": (
                reproduction_evidence_sha256
            ),
        },
        "integration": {
            "status": status.value,
            "complete_chain_reverified": (
                chain_reverified
            ),
            "incident_identity_consistent": (
                identity_consistent
            ),
            "upstream_commitments_consistent": (
                commitments_consistent
            ),
            "stage_boundaries_consistent": (
                boundaries_consistent
            ),
            "integration_verified": (
                verified
            ),
            "reproduction_verdict": (
                safe_reproduction_verdict
            ),
            "reproduction_determined": (
                safe_reproduction_determined
            ),
            "incident_reproduced": (
                safe_reproduced
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
        },
        "policy": dict(
            _POLICY
        ),
        "content_boundary": dict(
            _CONTENT_BOUNDARY
        ),
        "evidence_boundary": {
            "final_incident_integration_gate_evaluated": True,
            "complete_incident_chain_reverified": (
                chain_reverified
            ),
            "cross_stage_identity_verified": (
                identity_consistent
            ),
            "cross_stage_commitments_verified": (
                commitments_consistent
            ),
            "cross_stage_boundaries_verified": (
                boundaries_consistent
            ),
            "integration_verified": (
                verified
            ),
            "reproduction_determined": (
                safe_reproduction_determined
            ),
            "reproduction_claimed": (
                safe_reproduced
            ),
            "model_failure_verified": False,
            "causal_explanation_claimed": False,
            "counterexample_confirmed": False,
            "contract_promoted": False,
            "blocking_release_gate_enabled": False,
            "governance_assurance_completed": False,
            "release_authority_granted": False,
            "qualification_authority": False,
        },
    }

    canonical = _canonical_json_value(
        payload,
        name="incident integration gate",
    )

    if not isinstance(
        canonical,
        dict,
    ):
        raise HveeContractError(
            "incident integration gate "
            "must be a JSON object"
        )

    return IncidentIntegrationGateBundle(
        payload=canonical,
        sha256=(
            calculate_incident_integration_gate_sha256(
                canonical
            )
        ),
    )


def verify_incident_integration_gate_bundle(
    *,
    payload: object,
    expected_sha256: object,
    intake_payload: object,
    expected_intake_sha256: object,
    replay_preparation_payload: object,
    expected_replay_preparation_sha256: object,
    environment_manifest_payload: object,
    expected_environment_manifest_sha256: object,
    runner_compatibility_payload: object,
    expected_runner_compatibility_sha256: object,
    required_capabilities: list[str] | tuple[str, ...],
    compatibility_observation: (
        IncidentRunnerEnvironmentObservation
    ),
    environment_materialization_payload: object,
    expected_environment_materialization_sha256: object,
    controlled_replay_payload: object,
    expected_controlled_replay_sha256: object,
    reproduction_evidence_payload: object,
    expected_reproduction_evidence_sha256: object,
    comparison_observation: (
        IncidentReproductionComparisonObservation
    ),
) -> bool:
    try:
        integration_sha256 = _require_sha256(
            name="expected integration gate SHA-256",
            value=expected_sha256,
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        rebuilt = (
            build_incident_integration_gate_bundle(
                intake_payload=intake_payload,
                expected_intake_sha256=(
                    expected_intake_sha256
                ),
                replay_preparation_payload=(
                    replay_preparation_payload
                ),
                expected_replay_preparation_sha256=(
                    expected_replay_preparation_sha256
                ),
                environment_manifest_payload=(
                    environment_manifest_payload
                ),
                expected_environment_manifest_sha256=(
                    expected_environment_manifest_sha256
                ),
                runner_compatibility_payload=(
                    runner_compatibility_payload
                ),
                expected_runner_compatibility_sha256=(
                    expected_runner_compatibility_sha256
                ),
                required_capabilities=(
                    required_capabilities
                ),
                compatibility_observation=(
                    compatibility_observation
                ),
                environment_materialization_payload=(
                    environment_materialization_payload
                ),
                expected_environment_materialization_sha256=(
                    expected_environment_materialization_sha256
                ),
                controlled_replay_payload=(
                    controlled_replay_payload
                ),
                expected_controlled_replay_sha256=(
                    expected_controlled_replay_sha256
                ),
                reproduction_evidence_payload=(
                    reproduction_evidence_payload
                ),
                expected_reproduction_evidence_sha256=(
                    expected_reproduction_evidence_sha256
                ),
                comparison_observation=(
                    comparison_observation
                ),
            )
        )

        return (
            payload
            == rebuilt.payload
            and integration_sha256
            == rebuilt.sha256
            and (
                calculate_incident_integration_gate_sha256(
                    payload
                )
                == integration_sha256
            )
        )

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False


__all__ = [
    "INCIDENT_INTEGRATION_GATE_SCHEMA_VERSION",
    "IncidentIntegrationGateBundle",
    "IncidentIntegrationStatus",
    "build_incident_integration_gate_bundle",
    "calculate_incident_integration_gate_sha256",
    "verify_incident_integration_gate_bundle",
]
