"""Tamper-evident Incident Mode reproduction evidence.

Stage 8 executes the final prepared replay operation:

    compare_behavior_commitments

It consumes verified Stage-7 controlled replay evidence and determines
whether the controlled replay reproduced the behavior originally reported
for the incident.

Important trust boundary
------------------------

Incident Intake v1 stores expected and observed behavior commitments as
opaque SHA-256 commitments. Their presence alone does not prove that they
are transcript commitments or that they are directly comparable with the
Stage-7 generated transcript commitment.

Therefore this stage never infers commitment semantics from matching field
types or digest formats.

Deterministic REPRODUCED / NOT_REPRODUCED verdicts require an explicit
semantic confirmation commitment for the supported comparison basis:

    exact_generated_transcript_sha256_v1

Without that confirmation, the correct verdict is INDETERMINATE.

Even a REPRODUCED verdict does not establish model failure, causality,
counterexample confirmation, contract promotion, release authority, or
qualification authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.incident_controlled_replay import (
    verify_incident_controlled_replay_bundle,
)
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
)


INCIDENT_REPRODUCTION_EVIDENCE_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)


class IncidentReproductionVerdict(StrEnum):
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    INDETERMINATE = "indeterminate"


class IncidentReproductionComparisonBasis(StrEnum):
    EXACT_GENERATED_TRANSCRIPT_SHA256_V1 = (
        "exact_generated_transcript_sha256_v1"
    )
    UNAVAILABLE = "unavailable"


class IncidentReproductionReason(StrEnum):
    EXACT_REPORTED_BEHAVIOR_MATCH = (
        "exact_reported_behavior_match"
    )
    REPORTED_BEHAVIOR_MISMATCH = (
        "reported_behavior_mismatch"
    )
    BEHAVIOR_COMMITMENTS_UNAVAILABLE = (
        "behavior_commitments_unavailable"
    )
    BEHAVIOR_COMMITMENT_SEMANTICS_UNCONFIRMED = (
        "behavior_commitment_semantics_unconfirmed"
    )


_CONTENT_BOUNDARY = {
    "raw_audio_embedded": False,
    "raw_transcript_embedded": False,
    "transport_trace_embedded": False,
    "artifact_bytes_embedded": False,
    "local_artifact_locator_embedded": False,
    "generated_transcript_commitment_embedded": True,
    "expected_behavior_commitment_embedded": False,
    "observed_behavior_commitment_embedded": False,
    "comparison_semantics_confirmation_payload_embedded": False,
    "comparison_semantics_confirmation_commitment_embedded": False,
}

_POLICY = {
    "controlled_replay_must_verify": True,
    "comparison_operation_must_be_deferred_from_stage7": True,
    "opaque_commitments_must_not_be_reinterpreted": True,
    "semantic_confirmation_required_for_deterministic_verdict": True,
    "comparison_semantics_observation_must_be_external_to_verified_payload": True,
    "exact_commitment_equality_only": True,
    "text_normalization_performed": False,
    "fuzzy_matching_performed": False,
    "semantic_similarity_performed": False,
    "successful_reproduction_is_not_model_failure_proof": True,
    "successful_reproduction_is_not_causal_proof": True,
}

_BASE_EVIDENCE_BOUNDARY = {
    "incident_intake_verified": True,
    "replay_preparation_verified": True,
    "environment_manifest_verified": True,
    "runner_compatibility_verified": True,
    "environment_materialization_verified": True,
    "controlled_replay_verified": True,
    "operator_authorization_granted": True,
    "environment_materialized": True,
    "artifact_bytes_reverified_for_replay": True,
    "replay_executed": True,
    "transcriptions_executed": True,
    "replay_output_captured": True,
    "comparison_operation_executed": True,
    "model_failure_verified": False,
    "causal_explanation_claimed": False,
    "counterexample_confirmed": False,
    "contract_promoted": False,
    "blocking_release_gate_enabled": False,
    "qualification_authority": False,
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


def _optional_sha256(
    *,
    name: str,
    value: object,
) -> str | None:
    if value is None:
        return None

    return _require_sha256(
        name=name,
        value=value,
    )


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


def _calculate_sha256(
    value: object,
    *,
    name: str,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            value,
            name=name,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class IncidentReproductionComparisonObservation:
    """External confirmation of how behavior commitments may be compared.

    Stage 8 cannot derive this fact from Intake v1 itself.

    A deterministic comparison basis therefore requires a commitment to
    evidence confirming that the reporter/customer intended the original
    behavior commitments to use the exact generated-transcript SHA scheme.
    """

    basis: IncidentReproductionComparisonBasis
    semantics_confirmation_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.basis,
            IncidentReproductionComparisonBasis,
        ):
            raise HveeContractError(
                "reproduction comparison basis must be canonical"
            )

        if (
            self.basis
            == (
                IncidentReproductionComparisonBasis
                .EXACT_GENERATED_TRANSCRIPT_SHA256_V1
            )
        ):
            if self.semantics_confirmation_sha256 is None:
                raise HveeContractError(
                    "exact reproduction comparison requires "
                    "semantic confirmation"
                )

            _require_sha256(
                name=(
                    "comparison semantics confirmation "
                    "SHA-256"
                ),
                value=(
                    self.semantics_confirmation_sha256
                ),
            )

        elif self.semantics_confirmation_sha256 is not None:
            raise HveeContractError(
                "unavailable comparison basis cannot contain "
                "semantic confirmation"
            )


@dataclass(frozen=True, slots=True)
class IncidentReproductionEvidenceBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "reproduction evidence payload must be a JSON object"
            )

        _require_sha256(
            name="reproduction evidence SHA-256",
            value=self.sha256,
        )


@dataclass(frozen=True, slots=True)
class _ComparisonResult:
    verdict: IncidentReproductionVerdict
    reason: IncidentReproductionReason
    comparable: bool
    reported_behavior_exact_match: bool | None


def _claim_behavior_commitments(
    intake_payload: dict[str, object],
) -> tuple[
    str,
    str | None,
    str | None,
]:
    claim = intake_payload.get("claim")

    if not isinstance(claim, dict):
        raise HveeContractError(
            "reproduction evidence requires canonical incident claim"
        )

    reporter_evidence_sha256 = _require_sha256(
        name="reporter evidence SHA-256",
        value=claim.get(
            "reporter_evidence_sha256"
        ),
    )

    expected = _optional_sha256(
        name="expected behavior commitment SHA-256",
        value=claim.get(
            "expected_behavior_commitment_sha256"
        ),
    )

    observed = _optional_sha256(
        name="observed behavior commitment SHA-256",
        value=claim.get(
            "observed_behavior_commitment_sha256"
        ),
    )

    if (expected is None) != (observed is None):
        raise HveeContractError(
            "expected and observed behavior commitments "
            "must remain paired"
        )

    if (
        expected is not None
        and expected == observed
    ):
        raise HveeContractError(
            "expected and observed behavior commitments "
            "must remain distinct"
        )

    return (
        reporter_evidence_sha256,
        expected,
        observed,
    )


def _controlled_replay_output_commitment(
    payload: dict[str, object],
) -> str:
    execution = payload.get(
        "execution"
    )

    boundary = payload.get(
        "evidence_boundary"
    )

    if not isinstance(
        execution,
        dict,
    ):
        raise HveeContractError(
            "reproduction evidence requires controlled "
            "replay execution"
        )

    if not isinstance(
        boundary,
        dict,
    ):
        raise HveeContractError(
            "reproduction evidence requires controlled "
            "replay boundary"
        )

    if (
        execution.get("status")
        != "executed"
        or boundary.get(
            "replay_executed"
        )
        is not True
        or boundary.get(
            "replay_output_captured"
        )
        is not True
    ):
        raise HveeContractError(
            "reproduction evidence requires completed "
            "controlled replay"
        )

    if (
        boundary.get(
            "behavior_commitments_compared"
        )
        is not False
        or boundary.get(
            "reproduction_claimed"
        )
        is not False
    ):
        raise HveeContractError(
            "controlled replay crossed the Stage-8 boundary"
        )

    output = execution.get("output")

    if not isinstance(
        output,
        dict,
    ):
        raise HveeContractError(
            "controlled replay output commitment is unavailable"
        )

    return _require_sha256(
        name="controlled replay generated transcript SHA-256",
        value=output.get(
            "generated_transcript_sha256"
        ),
    )


def _compare(
    *,
    expected_behavior_sha256: str | None,
    observed_behavior_sha256: str | None,
    replay_behavior_sha256: str,
    observation: IncidentReproductionComparisonObservation,
) -> _ComparisonResult:
    if (
        expected_behavior_sha256 is None
        or observed_behavior_sha256 is None
    ):
        return _ComparisonResult(
            verdict=(
                IncidentReproductionVerdict
                .INDETERMINATE
            ),
            reason=(
                IncidentReproductionReason
                .BEHAVIOR_COMMITMENTS_UNAVAILABLE
            ),
            comparable=False,
            reported_behavior_exact_match=None,
        )

    if (
        observation.basis
        != (
            IncidentReproductionComparisonBasis
            .EXACT_GENERATED_TRANSCRIPT_SHA256_V1
        )
    ):
        return _ComparisonResult(
            verdict=(
                IncidentReproductionVerdict
                .INDETERMINATE
            ),
            reason=(
                IncidentReproductionReason
                .BEHAVIOR_COMMITMENT_SEMANTICS_UNCONFIRMED
            ),
            comparable=False,
            reported_behavior_exact_match=None,
        )

    exact_match = (
        replay_behavior_sha256
        == observed_behavior_sha256
    )

    if exact_match:
        return _ComparisonResult(
            verdict=(
                IncidentReproductionVerdict
                .REPRODUCED
            ),
            reason=(
                IncidentReproductionReason
                .EXACT_REPORTED_BEHAVIOR_MATCH
            ),
            comparable=True,
            reported_behavior_exact_match=True,
        )

    return _ComparisonResult(
        verdict=(
            IncidentReproductionVerdict
            .NOT_REPRODUCED
        ),
        reason=(
            IncidentReproductionReason
            .REPORTED_BEHAVIOR_MISMATCH
        ),
        comparable=True,
        reported_behavior_exact_match=False,
    )


def calculate_incident_reproduction_evidence_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="incident reproduction evidence",
    )


def build_incident_reproduction_evidence_bundle(
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
    comparison_observation: (
        IncidentReproductionComparisonObservation
    ),
) -> IncidentReproductionEvidenceBundle:
    intake_sha256 = _require_sha256(
        name="reproduction intake SHA-256",
        value=expected_intake_sha256,
    )

    replay_preparation_sha256 = _require_sha256(
        name="reproduction replay preparation SHA-256",
        value=expected_replay_preparation_sha256,
    )

    environment_manifest_sha256 = _require_sha256(
        name="reproduction environment manifest SHA-256",
        value=expected_environment_manifest_sha256,
    )

    runner_compatibility_sha256 = _require_sha256(
        name="reproduction runner compatibility SHA-256",
        value=expected_runner_compatibility_sha256,
    )

    environment_materialization_sha256 = _require_sha256(
        name="reproduction environment materialization SHA-256",
        value=expected_environment_materialization_sha256,
    )

    controlled_replay_sha256 = _require_sha256(
        name="reproduction controlled replay SHA-256",
        value=expected_controlled_replay_sha256,
    )

    if not isinstance(
        comparison_observation,
        IncidentReproductionComparisonObservation,
    ):
        raise HveeContractError(
            "reproduction comparison observation "
            "must be canonical"
        )

    upstream_payloads = (
        intake_payload,
        replay_preparation_payload,
        environment_manifest_payload,
        runner_compatibility_payload,
        environment_materialization_payload,
        controlled_replay_payload,
    )

    if not all(
        isinstance(value, dict)
        for value in upstream_payloads
    ):
        raise HveeContractError(
            "reproduction upstream evidence "
            "must be JSON objects"
        )

    if not verify_incident_controlled_replay_bundle(
        payload=controlled_replay_payload,
        expected_sha256=(
            controlled_replay_sha256
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
    ):
        raise HveeContractError(
            "reproduction evidence requires verified "
            "controlled replay"
        )

    (
        reporter_evidence_sha256,
        expected_behavior_sha256,
        observed_behavior_sha256,
    ) = _claim_behavior_commitments(
        intake_payload
    )

    replay_behavior_sha256 = (
        _controlled_replay_output_commitment(
            controlled_replay_payload
        )
    )

    comparison = _compare(
        expected_behavior_sha256=(
            expected_behavior_sha256
        ),
        observed_behavior_sha256=(
            observed_behavior_sha256
        ),
        replay_behavior_sha256=(
            replay_behavior_sha256
        ),
        observation=(
            comparison_observation
        ),
    )

    reproduced = (
        comparison.verdict
        == IncidentReproductionVerdict.REPRODUCED
    )

    compared = comparison.comparable

    incident = intake_payload.get(
        "incident"
    )

    if not isinstance(
        incident,
        dict,
    ):
        raise HveeContractError(
            "reproduction incident identity must be canonical"
        )

    comparison_payload = {
        "operation": "compare_behavior_commitments",
        "status": (
            "compared"
            if compared
            else "indeterminate"
        ),
        "basis": (
            comparison_observation
            .basis
            .value
        ),
        "semantics_confirmation_sha256": (
            comparison_observation
            .semantics_confirmation_sha256
        ),
        "reporter_evidence_sha256": (
            reporter_evidence_sha256
        ),
        "expected_behavior_commitment_sha256": (
            expected_behavior_sha256
        ),
        "reported_observed_behavior_commitment_sha256": (
            observed_behavior_sha256
        ),
        "controlled_replay_behavior_commitment_sha256": (
            replay_behavior_sha256
        ),
        "reported_behavior_exact_match": (
            comparison.reported_behavior_exact_match
        ),
        "verdict": comparison.verdict.value,
        "reason": comparison.reason.value,
    }

    evidence_boundary = {
        **_BASE_EVIDENCE_BOUNDARY,
        "behavior_commitments_compared": (
            compared
        ),
        "reproduction_determined": (
            comparison.verdict
            != IncidentReproductionVerdict.INDETERMINATE
        ),
        "reproduction_claimed": (
            reproduced
        ),
    }

    content_boundary = {
        **_CONTENT_BOUNDARY,
        "expected_behavior_commitment_embedded": (
            expected_behavior_sha256 is not None
        ),
        "observed_behavior_commitment_embedded": (
            observed_behavior_sha256 is not None
        ),
        "comparison_semantics_confirmation_commitment_embedded": (
            comparison_observation
            .semantics_confirmation_sha256
            is not None
        ),
    }

    payload: dict[str, object] = {
        "schema_version": (
            INCIDENT_REPRODUCTION_EVIDENCE_SCHEMA_VERSION
        ),
        "type": "incident_reproduction_evidence",
        "evaluation_type": intake_payload[
            "evaluation_type"
        ],
        "incident": {
            "key": incident["key"],
            "version": incident["version"],
            "intake_sha256": intake_sha256,
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
        },
        "comparison": comparison_payload,
        "policy": dict(
            _POLICY
        ),
        "content_boundary": (
            content_boundary
        ),
        "evidence_boundary": (
            evidence_boundary
        ),
    }

    canonical = _canonical_json_value(
        payload,
        name="incident reproduction evidence",
    )

    if not isinstance(
        canonical,
        dict,
    ):
        raise HveeContractError(
            "reproduction evidence must be a JSON object"
        )

    return IncidentReproductionEvidenceBundle(
        payload=canonical,
        sha256=(
            calculate_incident_reproduction_evidence_sha256(
                canonical
            )
        ),
    )


def verify_incident_reproduction_evidence_bundle(
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
    comparison_observation: (
        IncidentReproductionComparisonObservation
    ),
) -> bool:
    try:
        reproduction_sha256 = _require_sha256(
            name="expected reproduction evidence SHA-256",
            value=expected_sha256,
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        rebuilt = (
            build_incident_reproduction_evidence_bundle(
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
                comparison_observation=(
                    comparison_observation
                ),
            )
        )

        return (
            payload == rebuilt.payload
            and reproduction_sha256
            == rebuilt.sha256
            and (
                calculate_incident_reproduction_evidence_sha256(
                    payload
                )
                == reproduction_sha256
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
    "INCIDENT_REPRODUCTION_EVIDENCE_SCHEMA_VERSION",
    "IncidentReproductionComparisonBasis",
    "IncidentReproductionComparisonObservation",
    "IncidentReproductionEvidenceBundle",
    "IncidentReproductionReason",
    "IncidentReproductionVerdict",
    "build_incident_reproduction_evidence_bundle",
    "calculate_incident_reproduction_evidence_sha256",
    "verify_incident_reproduction_evidence_bundle",
]
