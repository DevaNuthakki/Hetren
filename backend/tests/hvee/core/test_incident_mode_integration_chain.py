"""Unstubbed Incident Mode integration chain.

This test deliberately lives outside the Stage-6, Stage-7, Stage-8,
and Stage-9 unit-test modules because those modules contain local
autouse monkeypatch fixtures that isolate their individual stages.

Nothing in this test replaces a production verifier.

The complete evidence chain is built with the real production
builders and every downstream SHA-256 identity comes from the
actual upstream bundle that was just produced.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

from hvee.core.incident_controlled_replay import (
    IncidentControlledReplayArtifactObservation,
    IncidentControlledReplayExecutionObservation,
    IncidentControlledReplayOutputObservation,
    build_incident_controlled_replay_bundle,
    verify_incident_controlled_replay_bundle,
)
from hvee.core.incident_environment_manifest import (
    verify_incident_environment_manifest_bundle,
)
from hvee.core.incident_environment_materialization import (
    IncidentMaterializedRequirementObservation,
    IncidentOperatorAuthorization,
    build_incident_environment_materialization_bundle,
    verify_incident_environment_materialization_bundle,
)
from hvee.core.incident_intake import (
    verify_incident_intake_bundle,
)
from hvee.core.incident_governance_assurance import (
    IncidentGovernanceAssuranceDefinition,
    IncidentGovernanceAssuranceProtocolDefinition,
    IncidentGovernanceDisposition,
    IncidentGovernanceIntegrationVerificationContext,
    IncidentGovernanceReviewer,
    IncidentGovernanceReviewerDecision,
    IncidentGovernanceReviewerKind,
    IncidentGovernanceReviewerRole,
    build_incident_governance_assurance_bundle,
    build_incident_governance_assurance_protocol_bundle,
    verify_incident_governance_assurance_bundle,
    verify_incident_governance_assurance_protocol_bundle,
)
from hvee.core.incident_integration_gate import (
    build_incident_integration_gate_bundle,
    verify_incident_integration_gate_bundle,
)
from hvee.core.incident_replay_preparation import (
    verify_incident_replay_preparation_bundle,
)
from hvee.core.incident_reproduction_evidence import (
    IncidentReproductionComparisonBasis,
    IncidentReproductionComparisonObservation,
    build_incident_reproduction_evidence_bundle,
    verify_incident_reproduction_evidence_bundle,
)
from hvee.core.incident_runner_compatibility import (
    build_incident_runner_compatibility_bundle,
    verify_incident_runner_compatibility_bundle,
)


_REQUIRED_CAPABILITIES = (
    "asr",
    "incident_replay",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _load_real_fixture_module() -> ModuleType:
    """Load only the existing real Stage-1-to-4 fixture builders.

    test_incident_runner_compatibility.py does not contain an
    autouse verifier replacement. Its helpers construct actual
    Intake, Replay Preparation, Environment Manifest, and runner
    observations using production builders.
    """

    path = Path(__file__).with_name(
        "test_incident_runner_compatibility.py"
    )

    spec = (
        importlib.util.spec_from_file_location(
            "_incident_real_chain_fixture",
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "real Incident compatibility fixture "
            "module could not be loaded"
        )

    module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        module
    )

    return module


def _materialization_observations(
    compatibility_payload: dict[str, object],
) -> tuple[
    IncidentMaterializedRequirementObservation,
    ...,
]:
    compatibility = (
        compatibility_payload[
            "compatibility"
        ]
    )

    assert isinstance(
        compatibility,
        dict,
    )

    requirements = compatibility[
        "requirements"
    ]

    assert isinstance(
        requirements,
        list,
    )

    observations: list[
        IncidentMaterializedRequirementObservation
    ] = []

    for requirement in requirements:
        assert isinstance(
            requirement,
            dict,
        )

        requirement_name = requirement[
            "requirement"
        ]

        observed_commitment = requirement[
            "observed_commitment_sha256"
        ]

        # The decisive chain deliberately upgrades all
        # materializable context requirements to exact.
        # Therefore every requirement reaching Stage 6
        # must already carry an independently observed
        # commitment.
        assert requirement[
            "level"
        ] == "exact"

        assert isinstance(
            observed_commitment,
            str,
        )

        observations.append(
            IncidentMaterializedRequirementObservation(
                requirement=(
                    requirement_name
                ),
                observed_commitment_sha256=(
                    observed_commitment
                ),
            )
        )

    return tuple(
        observations
    )


def _controlled_replay_artifacts(
    preparation_payload: dict[str, object],
) -> tuple[
    IncidentControlledReplayArtifactObservation,
    ...,
]:
    artifact_verification = (
        preparation_payload[
            "artifact_verification"
        ]
    )

    assert isinstance(
        artifact_verification,
        dict,
    )

    receipts = artifact_verification[
        "receipts"
    ]

    assert isinstance(
        receipts,
        list,
    )

    replay_artifacts = []

    for receipt in receipts:
        assert isinstance(
            receipt,
            dict,
        )

        if receipt["kind"] not in {
            "source_audio",
            "transport_trace",
        }:
            continue

        assert receipt[
            "status"
        ] == "verified"

        replay_artifacts.append(
            IncidentControlledReplayArtifactObservation(
                kind=receipt[
                    "kind"
                ],
                reference_sha256=receipt[
                    "reference_sha256"
                ],
                expected_byte_length=receipt[
                    "expected_byte_length"
                ],
                media_type=receipt[
                    "media_type"
                ],
                observed_sha256=receipt[
                    "observed_sha256"
                ],
                observed_byte_length=receipt[
                    "observed_byte_length"
                ],
            )
        )

    return tuple(
        sorted(
            replay_artifacts,
            key=lambda value: value.identity,
        )
    )


def _completed_replay_operations(
    preparation_payload: dict[str, object],
) -> tuple[str, ...]:
    replay_plan = preparation_payload[
        "replay_plan"
    ]

    assert isinstance(
        replay_plan,
        dict,
    )

    steps = replay_plan[
        "steps"
    ]

    assert isinstance(
        steps,
        list,
    )

    operations = tuple(
        str(step["operation"])
        for step in steps
        if (
            isinstance(
                step,
                dict,
            )
            and step.get(
                "operation"
            )
            != "compare_behavior_commitments"
        )
    )

    assert operations
    assert operations[-1] == (
        "capture_replay_output"
    )

    return operations


def _build_real_incident_mode_chain():
    fixture = (
        _load_real_fixture_module()
    )

    # ---------------------------------------------------------
    # Stage 1: Incident Intake
    # ---------------------------------------------------------

    intake = fixture._intake()

    assert verify_incident_intake_bundle(
        payload=intake.payload,
        expected_sha256=intake.sha256,
    )

    # ---------------------------------------------------------
    # Stage 2: Artifact Verification + Replay Preparation
    # ---------------------------------------------------------

    preparation = fixture._preparation(
        intake=intake
    )

    assert (
        verify_incident_replay_preparation_bundle(
            payload=preparation.payload,
            expected_sha256=preparation.sha256,
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
        )
    )

    # ---------------------------------------------------------
    # Stage 3: Environment Replay Manifest
    # ---------------------------------------------------------

    manifest = (
        fixture._environment_manifest(
            intake=intake,
            preparation=preparation,
        )
    )

    assert (
        verify_incident_environment_manifest_bundle(
            payload=manifest.payload,
            expected_sha256=manifest.sha256,
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
        )
    )

    # ---------------------------------------------------------
    # Stage 4: Runner Compatibility
    #
    # Use the real fixture's complete target context and mark
    # every supported materializable context component exact.
    # This gives Stage 6 real observed commitments instead of
    # manufacturing compatible observations afterward.
    # ---------------------------------------------------------

    exact_context_components = (
        "audio",
        "transport",
    )

    compatibility_observation = (
        fixture._runner_observation(
            exact_context_components=(
                exact_context_components
            ),
            supported_materializations=(),
        )
    )

    compatibility = (
        build_incident_runner_compatibility_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            observation=(
                compatibility_observation
            ),
        )
    )

    assert compatibility.payload[
        "compatibility"
    ]["status"] == "exact"

    assert compatibility.payload[
        "compatibility"
    ][
        "ready_for_materialization"
    ] is True

    assert (
        verify_incident_runner_compatibility_bundle(
            payload=compatibility.payload,
            expected_sha256=(
                compatibility.sha256
            ),
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            observation=(
                compatibility_observation
            ),
        )
    )

    # ---------------------------------------------------------
    # Stage 6: Environment Materialization
    #
    # The authorization commitment is independent evidence,
    # not an upstream bundle digest.
    #
    # Every materialization observation comes directly from the
    # real Stage-4 compatibility evidence.
    # ---------------------------------------------------------

    authorization = (
        IncidentOperatorAuthorization(
            granted=True,
            authorization_sha256=(
                _sha256_bytes(
                    b"incident-real-chain-operator-authorization"
                )
            ),
        )
    )

    materialization_observations = (
        _materialization_observations(
            compatibility.payload
        )
    )

    materialization = (
        build_incident_environment_materialization_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            authorization=authorization,
            materialization_observations=(
                materialization_observations
            ),
        )
    )

    assert materialization.payload[
        "materialization"
    ]["status"] == "materialized"

    assert materialization.payload[
        "materialization"
    ][
        "environment_materialized"
    ] is True

    assert (
        verify_incident_environment_materialization_bundle(
            payload=materialization.payload,
            expected_sha256=(
                materialization.sha256
            ),
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
        )
    )

    # ---------------------------------------------------------
    # Stage 7: Controlled Replay Evidence
    #
    # Artifact observations come directly from the real verified
    # preparation receipts. Completed operations come directly
    # from the real replay plan, stopping before Stage 8's
    # compare_behavior_commitments operation.
    # ---------------------------------------------------------

    runtime = intake.payload[
        "context"
    ]["runtime"]

    assert isinstance(
        runtime,
        dict,
    )

    provider_identity = runtime[
        "provider"
    ]

    model_identity = runtime[
        "model"
    ]

    assert isinstance(
        provider_identity,
        dict,
    )

    assert isinstance(
        model_identity,
        dict,
    )

    provider = provider_identity[
        "key"
    ]

    model_name = model_identity[
        "key"
    ]

    assert isinstance(
        provider,
        str,
    )

    assert isinstance(
        model_name,
        str,
    )

    replay_output = (
        IncidentControlledReplayOutputObservation(
            generated_transcript_sha256=(
                _sha256_bytes(
                    b"incident-real-chain-generated-transcript"
                )
            ),
            generated_transcript_utf8_bytes=(
                len(
                    "incident real chain generated transcript"
                    .encode("utf-8")
                )
            ),
            provider=provider,
            model_name=model_name,
            device="cpu",
            compute_type="int8_float32",
        )
    )

    execution_observation = (
        IncidentControlledReplayExecutionObservation(
            completed_operations=(
                _completed_replay_operations(
                    preparation.payload
                )
            ),
            artifacts=(
                _controlled_replay_artifacts(
                    preparation.payload
                )
            ),
            output=replay_output,
        )
    )

    controlled_replay = (
        build_incident_controlled_replay_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            environment_materialization_payload=(
                materialization.payload
            ),
            expected_environment_materialization_sha256=(
                materialization.sha256
            ),
            execution_observation=(
                execution_observation
            ),
        )
    )

    assert controlled_replay.payload[
        "execution"
    ]["status"] == "executed"

    assert controlled_replay.payload[
        "evidence_boundary"
    ]["replay_executed"] is True

    assert controlled_replay.payload[
        "evidence_boundary"
    ][
        "behavior_commitments_compared"
    ] is False

    assert (
        verify_incident_controlled_replay_bundle(
            payload=controlled_replay.payload,
            expected_sha256=(
                controlled_replay.sha256
            ),
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            environment_materialization_payload=(
                materialization.payload
            ),
            expected_environment_materialization_sha256=(
                materialization.sha256
            ),
        )
    )

    # ---------------------------------------------------------
    # Stage 8: Reproduction Evidence
    #
    # No semantic equivalence is manufactured for the test.
    # Opaque reporter commitments remain opaque.
    # ---------------------------------------------------------

    comparison_observation = (
        IncidentReproductionComparisonObservation(
            basis=(
                IncidentReproductionComparisonBasis
                .UNAVAILABLE
            ),
        )
    )

    reproduction = (
        build_incident_reproduction_evidence_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            environment_materialization_payload=(
                materialization.payload
            ),
            expected_environment_materialization_sha256=(
                materialization.sha256
            ),
            controlled_replay_payload=(
                controlled_replay.payload
            ),
            expected_controlled_replay_sha256=(
                controlled_replay.sha256
            ),
            comparison_observation=(
                comparison_observation
            ),
        )
    )

    assert reproduction.payload[
        "comparison"
    ]["verdict"] == "indeterminate"

    assert reproduction.payload[
        "evidence_boundary"
    ][
        "reproduction_claimed"
    ] is False

    assert (
        verify_incident_reproduction_evidence_bundle(
            payload=reproduction.payload,
            expected_sha256=(
                reproduction.sha256
            ),
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            environment_materialization_payload=(
                materialization.payload
            ),
            expected_environment_materialization_sha256=(
                materialization.sha256
            ),
            controlled_replay_payload=(
                controlled_replay.payload
            ),
            expected_controlled_replay_sha256=(
                controlled_replay.sha256
            ),
            comparison_observation=(
                comparison_observation
            ),
        )
    )

    # ---------------------------------------------------------
    # Stage 9: Final Incident Integration Gate
    # ---------------------------------------------------------

    integration = (
        build_incident_integration_gate_bundle(
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            environment_materialization_payload=(
                materialization.payload
            ),
            expected_environment_materialization_sha256=(
                materialization.sha256
            ),
            controlled_replay_payload=(
                controlled_replay.payload
            ),
            expected_controlled_replay_sha256=(
                controlled_replay.sha256
            ),
            reproduction_evidence_payload=(
                reproduction.payload
            ),
            expected_reproduction_evidence_sha256=(
                reproduction.sha256
            ),
            comparison_observation=(
                comparison_observation
            ),
        )
    )

    final = integration.payload[
        "integration"
    ]

    assert final["status"] == (
        "verified_indeterminate"
    )

    assert final[
        "complete_chain_reverified"
    ] is True

    assert final[
        "incident_identity_consistent"
    ] is True

    assert final[
        "upstream_commitments_consistent"
    ] is True

    assert final[
        "stage_boundaries_consistent"
    ] is True

    assert final[
        "integration_verified"
    ] is True

    assert final[
        "reproduction_verdict"
    ] == "indeterminate"

    assert final[
        "reproduction_determined"
    ] is False

    assert final[
        "incident_reproduced"
    ] is False

    assert final[
        "blocking_reasons"
    ] == []

    boundary = integration.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "governance_assurance_completed"
    ] is False

    assert boundary[
        "release_authority_granted"
    ] is False

    assert boundary[
        "qualification_authority"
    ] is False

    assert (
        verify_incident_integration_gate_bundle(
            payload=integration.payload,
            expected_sha256=(
                integration.sha256
            ),
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            environment_materialization_payload=(
                materialization.payload
            ),
            expected_environment_materialization_sha256=(
                materialization.sha256
            ),
            controlled_replay_payload=(
                controlled_replay.payload
            ),
            expected_controlled_replay_sha256=(
                controlled_replay.sha256
            ),
            reproduction_evidence_payload=(
                reproduction.payload
            ),
            expected_reproduction_evidence_sha256=(
                reproduction.sha256
            ),
            comparison_observation=(
                comparison_observation
            ),
        )
    )

    return {
        "intake": intake,
        "preparation": preparation,
        "manifest": manifest,
        "compatibility": compatibility,
        "compatibility_observation": (
            compatibility_observation
        ),
        "materialization": materialization,
        "controlled_replay": controlled_replay,
        "reproduction": reproduction,
        "comparison_observation": (
            comparison_observation
        ),
        "integration": integration,
    }


def test_real_incident_mode_chain_is_verified_indeterminate():
    chain = _build_real_incident_mode_chain()

    integration = chain[
        "integration"
    ]

    assert integration.payload[
        "integration"
    ]["status"] == "verified_indeterminate"

    assert integration.payload[
        "integration"
    ]["integration_verified"] is True

    assert integration.payload[
        "evidence_boundary"
    ]["governance_assurance_completed"] is False


def test_real_incident_mode_chain_reaches_governance_assurance():
    chain = _build_real_incident_mode_chain()

    intake = chain["intake"]
    preparation = chain["preparation"]
    manifest = chain["manifest"]
    compatibility = chain["compatibility"]
    compatibility_observation = chain[
        "compatibility_observation"
    ]
    materialization = chain[
        "materialization"
    ]
    controlled_replay = chain[
        "controlled_replay"
    ]
    reproduction = chain["reproduction"]
    comparison_observation = chain[
        "comparison_observation"
    ]
    integration = chain["integration"]

    verification = (
        IncidentGovernanceIntegrationVerificationContext(
            intake_payload=intake.payload,
            expected_intake_sha256=(
                intake.sha256
            ),
            replay_preparation_payload=(
                preparation.payload
            ),
            expected_replay_preparation_sha256=(
                preparation.sha256
            ),
            environment_manifest_payload=(
                manifest.payload
            ),
            expected_environment_manifest_sha256=(
                manifest.sha256
            ),
            runner_compatibility_payload=(
                compatibility.payload
            ),
            expected_runner_compatibility_sha256=(
                compatibility.sha256
            ),
            required_capabilities=(
                _REQUIRED_CAPABILITIES
            ),
            compatibility_observation=(
                compatibility_observation
            ),
            environment_materialization_payload=(
                materialization.payload
            ),
            expected_environment_materialization_sha256=(
                materialization.sha256
            ),
            controlled_replay_payload=(
                controlled_replay.payload
            ),
            expected_controlled_replay_sha256=(
                controlled_replay.sha256
            ),
            reproduction_evidence_payload=(
                reproduction.payload
            ),
            expected_reproduction_evidence_sha256=(
                reproduction.sha256
            ),
            comparison_observation=(
                comparison_observation
            ),
        )
    )

    reviewers = (
        IncidentGovernanceReviewer(
            role=(
                IncidentGovernanceReviewerRole
                .EVALUATION_REVIEWER
            ),
            key_id=(
                "incident-evaluation-reviewer-001"
            ),
            affiliation_key="hetren-reliability",
            reviewer_kind=(
                IncidentGovernanceReviewerKind.HUMAN
            ),
            qualification_sha256=(
                _sha256_bytes(
                    b"incident-evaluation-reviewer-qualification"
                )
            ),
            authorization_sha256=(
                _sha256_bytes(
                    b"incident-evaluation-reviewer-authorization"
                )
            ),
            independence_attestation_sha256=(
                _sha256_bytes(
                    b"incident-evaluation-reviewer-independence"
                )
            ),
        ),
        IncidentGovernanceReviewer(
            role=(
                IncidentGovernanceReviewerRole
                .RISK_REVIEWER
            ),
            key_id="incident-risk-reviewer-001",
            affiliation_key="hetren-risk",
            reviewer_kind=(
                IncidentGovernanceReviewerKind.HUMAN
            ),
            qualification_sha256=(
                _sha256_bytes(
                    b"incident-risk-reviewer-qualification"
                )
            ),
            authorization_sha256=(
                _sha256_bytes(
                    b"incident-risk-reviewer-authorization"
                )
            ),
            independence_attestation_sha256=(
                _sha256_bytes(
                    b"incident-risk-reviewer-independence"
                )
            ),
        ),
        IncidentGovernanceReviewer(
            role=(
                IncidentGovernanceReviewerRole
                .GOVERNANCE_APPROVER
            ),
            key_id=(
                "incident-governance-council"
            ),
            affiliation_key="hetren-governance",
            reviewer_kind=(
                IncidentGovernanceReviewerKind
                .GOVERNANCE_BODY
            ),
            qualification_sha256=(
                _sha256_bytes(
                    b"incident-governance-council-qualification"
                )
            ),
            authorization_sha256=(
                _sha256_bytes(
                    b"incident-governance-council-authorization"
                )
            ),
            independence_attestation_sha256=(
                _sha256_bytes(
                    b"incident-governance-council-independence"
                )
            ),
        ),
    )

    protocol_definition = (
        IncidentGovernanceAssuranceProtocolDefinition(
            review_id=(
                "incident-governance-review"
            ),
            review_version="1.0.0",
            integration_gate_sha256=(
                integration.sha256
            ),
            reviewers=reviewers,
            review_procedure_sha256=(
                _sha256_bytes(
                    b"incident-governance-review-procedure"
                )
            ),
            reviewer_qualification_policy_sha256=(
                _sha256_bytes(
                    b"incident-governance-reviewer-qualification-policy"
                )
            ),
            conflict_of_interest_policy_sha256=(
                _sha256_bytes(
                    b"incident-governance-conflict-policy"
                )
            ),
            authority_policy_sha256=(
                _sha256_bytes(
                    b"incident-governance-authority-policy"
                )
            ),
        )
    )

    protocol = (
        build_incident_governance_assurance_protocol_bundle(
            integration_gate=integration,
            integration_verification=verification,
            definition=protocol_definition,
        )
    )

    assert (
        verify_incident_governance_assurance_protocol_bundle(
            payload=protocol.payload,
            expected_sha256=protocol.sha256,
            integration_gate=integration,
            integration_verification=verification,
            definition=protocol_definition,
        )
    )

    decisions = tuple(
        IncidentGovernanceReviewerDecision(
            role=reviewer.role,
            reviewer_key_id=reviewer.key_id,
            integration_gate_sha256=(
                integration.sha256
            ),
            disposition=(
                IncidentGovernanceDisposition
                .APPROVED_FOR_ASSURANCE
            ),
            rationale_code=(
                "verified-incident-evidence"
            ),
            rationale_sha256=(
                _sha256_bytes(
                    (
                        "incident-governance-rationale-"
                        f"{reviewer.role.value}"
                    ).encode("utf-8")
                )
            ),
            decision_record_sha256=(
                _sha256_bytes(
                    (
                        "incident-governance-decision-"
                        f"{reviewer.role.value}"
                    ).encode("utf-8")
                )
            ),
            evidence_review_attestation_sha256=(
                _sha256_bytes(
                    (
                        "incident-governance-evidence-review-"
                        f"{reviewer.role.value}"
                    ).encode("utf-8")
                )
            ),
        )
        for reviewer in reviewers
    )

    definition = (
        IncidentGovernanceAssuranceDefinition(
            review_id=(
                protocol_definition.review_id
            ),
            review_version=(
                protocol_definition.review_version
            ),
            protocol_sha256=protocol.sha256,
            integration_gate_sha256=(
                integration.sha256
            ),
            review_environment_sha256=(
                _sha256_bytes(
                    b"incident-governance-review-environment"
                )
            ),
            independence_attestation_sha256=(
                _sha256_bytes(
                    b"incident-governance-review-independence"
                )
            ),
            decisions=decisions,
        )
    )

    assurance = (
        build_incident_governance_assurance_bundle(
            protocol=protocol,
            protocol_definition=(
                protocol_definition
            ),
            integration_gate=integration,
            integration_verification=verification,
            definition=definition,
        )
    )

    assert assurance.payload[
        "review"
    ]["status"] == "assured"

    assert assurance.payload[
        "review"
    ]["unanimous_approval"] is True

    assert assurance.payload[
        "sealed_evidence"
    ]["integration_gate_reverified"] is True

    boundary = assurance.payload[
        "evidence_boundary"
    ]

    assert boundary[
        "governance_assurance_completed"
    ] is True

    assert boundary[
        "model_failure_verified"
    ] is False

    assert boundary[
        "causal_explanation_claimed"
    ] is False

    assert boundary[
        "counterexample_confirmed"
    ] is False

    assert boundary[
        "contract_promoted"
    ] is False

    assert boundary[
        "blocking_release_gate_enabled"
    ] is False

    assert boundary[
        "release_authority_granted"
    ] is False

    assert boundary[
        "qualification_authority"
    ] is False

    assert (
        verify_incident_governance_assurance_bundle(
            payload=assurance.payload,
            expected_sha256=assurance.sha256,
            protocol=protocol,
            protocol_definition=(
                protocol_definition
            ),
            integration_gate=integration,
            integration_verification=verification,
            definition=definition,
        )
    )
