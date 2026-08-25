"""Application service for Incident Mode reproduction evidence.

Stage 8 is a commitment-comparison stage.

It does not:
- reacquire artifact bytes;
- execute a model;
- transcribe audio;
- access runner-local paths;
- perform fuzzy or semantic text comparison; or
- create qualification/release authority.

The comparison semantics are supplied independently to this service and
converted into a canonical IncidentReproductionComparisonObservation.

The reproduction evidence payload is never allowed to define the semantics
used to verify itself.
"""

from __future__ import annotations

from hvee.core.contracts import HveeContractError
from hvee.core.incident_reproduction_evidence import (
    IncidentReproductionComparisonBasis,
    IncidentReproductionComparisonObservation,
    build_incident_reproduction_evidence_bundle,
    verify_incident_reproduction_evidence_bundle,
)
from hvee.core.incident_runner_compatibility import (
    IncidentRunnerEnvironmentObservation,
)


INCIDENT_REPRODUCTION_RESULT_SCHEMA_VERSION = 1


class IncidentReproductionEvidenceServiceError(
    ValueError
):
    """Stage-8 application input is invalid."""


def build_incident_reproduction_comparison_observation(
    *,
    basis: object,
    semantics_confirmation_sha256: object = None,
) -> IncidentReproductionComparisonObservation:
    if isinstance(
        basis,
        IncidentReproductionComparisonBasis,
    ):
        canonical_basis = basis

    elif isinstance(
        basis,
        str,
    ):
        try:
            canonical_basis = (
                IncidentReproductionComparisonBasis(
                    basis
                )
            )
        except ValueError as exc:
            raise (
                IncidentReproductionEvidenceServiceError(
                    "Incident reproduction comparison "
                    "basis is unsupported."
                )
            ) from exc

    else:
        raise IncidentReproductionEvidenceServiceError(
            "Incident reproduction comparison basis "
            "must be canonical."
        )

    if (
        semantics_confirmation_sha256
        is not None
        and not isinstance(
            semantics_confirmation_sha256,
            str,
        )
    ):
        raise IncidentReproductionEvidenceServiceError(
            "Incident reproduction semantics confirmation "
            "must be a SHA-256 string."
        )

    try:
        return (
            IncidentReproductionComparisonObservation(
                basis=canonical_basis,
                semantics_confirmation_sha256=(
                    semantics_confirmation_sha256
                ),
            )
        )
    except HveeContractError as exc:
        raise (
            IncidentReproductionEvidenceServiceError(
                str(exc)
            )
        ) from exc


def build_incident_reproduction_evidence_result(
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
    comparison_basis: object,
    semantics_confirmation_sha256: object = None,
) -> dict[str, object]:
    comparison_observation = (
        build_incident_reproduction_comparison_observation(
            basis=comparison_basis,
            semantics_confirmation_sha256=(
                semantics_confirmation_sha256
            ),
        )
    )

    try:
        bundle = (
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

    except HveeContractError as exc:
        raise (
            IncidentReproductionEvidenceServiceError(
                "Incident reproduction evidence could "
                "not be built from verified upstream evidence."
            )
        ) from exc

    return {
        "schema_version": (
            INCIDENT_REPRODUCTION_RESULT_SCHEMA_VERSION
        ),
        "type": "incident_reproduction_evidence_result",
        "reproduction_evidence": {
            "payload": bundle.payload,
            "sha256": bundle.sha256,
        },
    }


def verify_incident_reproduction_evidence_result(
    *,
    result: object,
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
    comparison_basis: object,
    semantics_confirmation_sha256: object = None,
) -> bool:
    if not isinstance(
        result,
        dict,
    ):
        return False

    if set(result) != {
        "schema_version",
        "type",
        "reproduction_evidence",
    }:
        return False

    if (
        result.get("schema_version")
        != INCIDENT_REPRODUCTION_RESULT_SCHEMA_VERSION
        or result.get("type")
        != "incident_reproduction_evidence_result"
    ):
        return False

    reproduction_evidence = result.get(
        "reproduction_evidence"
    )

    if (
        not isinstance(
            reproduction_evidence,
            dict,
        )
        or set(
            reproduction_evidence
        )
        != {
            "payload",
            "sha256",
        }
    ):
        return False

    try:
        comparison_observation = (
            build_incident_reproduction_comparison_observation(
                basis=comparison_basis,
                semantics_confirmation_sha256=(
                    semantics_confirmation_sha256
                ),
            )
        )

    except IncidentReproductionEvidenceServiceError:
        return False

    return verify_incident_reproduction_evidence_bundle(
        payload=reproduction_evidence[
            "payload"
        ],
        expected_sha256=reproduction_evidence[
            "sha256"
        ],
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


__all__ = [
    "INCIDENT_REPRODUCTION_RESULT_SCHEMA_VERSION",
    "IncidentReproductionEvidenceServiceError",
    "build_incident_reproduction_comparison_observation",
    "build_incident_reproduction_evidence_result",
    "verify_incident_reproduction_evidence_result",
]
