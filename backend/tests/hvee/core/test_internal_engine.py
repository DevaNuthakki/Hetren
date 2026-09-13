from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib

import pytest

from hvee.core.contracts import HveeContractError
from hvee.core.experiment_protocol import (
    ExperimentEngineKind,
    ExperimentObservationStatus,
    verify_experiment_protocol_bundle,
)
from hvee.core.internal_engine import (
    INTERNAL_ENGINE_KEY,
    INTERNAL_ENGINE_VERSION,
    InternalActivationSummary,
    InternalExperimentRequest,
    InternalInterventionKind,
    InternalModuleTarget,
    InternalRuntimeCapability,
    build_internal_intervention_observation,
    calculate_internal_engine_execution_sha256,
    execute_internal_experiment,
    verify_internal_engine_execution_bundle,
    verify_internal_intervention_observation,
)


SUBJECT_SHA = "1" * 64
RUNTIME_SHA = "2" * 64
MODEL_SHA = "3" * 64
TARGET_SHA = "4" * 64
BASELINE_SHA = "5" * 64
CAPTURE_INTERVENTION_SHA = "6" * 64
ZERO_INTERVENTION_SHA = "7" * 64
SOURCE_EVIDENCE_SHA = "8" * 64
BASELINE_ACTIVATION_SHA = "9" * 64
ZERO_ACTIVATION_SHA = "a" * 64


def _summary(
    *,
    zero=False,
):
    if zero:
        return InternalActivationSummary(
            shape=(2, 3, 4),
            dtype="float32",
            element_count=24,
            finite_element_count=24,
            minimum=0.0,
            maximum=0.0,
            mean=0.0,
            l2_norm=0.0,
            activation_commitment_sha256=(ZERO_ACTIVATION_SHA),
        )

    return InternalActivationSummary(
        shape=(2, 3, 4),
        dtype="float32",
        element_count=24,
        finite_element_count=24,
        minimum=-2.0,
        maximum=3.0,
        mean=0.25,
        l2_norm=7.5,
        activation_commitment_sha256=(BASELINE_ACTIVATION_SHA),
    )


def _target(
    *,
    module_path="encoder.blocks.3",
    target_sha=TARGET_SHA,
    model_sha=MODEL_SHA,
):
    return InternalModuleTarget(
        module_path=module_path,
        module_kind="transformer_block",
        target_identity_sha256=(target_sha),
        runtime_model_sha256=(model_sha),
        module_index=3,
        head_index=None,
    )


def _request(
    *,
    intervention_kind=(InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY),
    target=None,
    runtime_sha=RUNTIME_SHA,
    model_sha=MODEL_SHA,
    maximum_cost_units=4,
    estimated_cost_units=2,
):
    if target is None:
        target = _target(model_sha=model_sha)

    intervention_sha = (
        CAPTURE_INTERVENTION_SHA
        if (intervention_kind == InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY)
        else ZERO_INTERVENTION_SHA
    )

    return InternalExperimentRequest(
        request_key="internal-probe-001",
        request_version="1.0.0",
        campaign_key="internal-foundation",
        campaign_version="1.0.0",
        subject_sha256=SUBJECT_SHA,
        expected_runtime_identity_sha256=(runtime_sha),
        expected_runtime_model_sha256=(model_sha),
        target=target,
        intervention_kind=(intervention_kind),
        baseline_identity_sha256=(BASELINE_SHA),
        intervention_identity_sha256=(intervention_sha),
        estimated_cost_units=(estimated_cost_units),
        maximum_experiments=1,
        maximum_cost_units=(maximum_cost_units),
        reason_code="mechanistic_probe",
        source_evidence_sha256=(SOURCE_EVIDENCE_SHA),
    )


class SyntheticInternalRuntime:
    def __init__(
        self,
        *,
        runtime_sha=RUNTIME_SHA,
        model_sha=MODEL_SHA,
        supported=None,
        raw_tensor_egress=False,
        unknown_module=False,
        observation_mutator=None,
    ):
        if supported is None:
            supported = (
                InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY,
                InternalInterventionKind.ZERO_MODULE_OUTPUT,
            )

        self.runtime_sha = runtime_sha
        self.model_sha = model_sha
        self.supported = tuple(supported)
        self.raw_tensor_egress = raw_tensor_egress
        self.unknown_module = unknown_module
        self.observation_mutator = observation_mutator
        self.execution_count = 0

    def describe_capability(
        self,
    ):
        return InternalRuntimeCapability(
            runtime_key="synthetic_internal_runtime",
            runtime_version="1.0.0",
            runtime_identity_sha256=(self.runtime_sha),
            runtime_model_sha256=(self.model_sha),
            supported_interventions=(self.supported),
            raw_tensor_egress=(self.raw_tensor_egress),
        )

    def execute(
        self,
        request,
    ):
        self.execution_count += 1

        if self.unknown_module:
            raise HveeContractError("unknown synthetic module")

        if request.target.module_path != "encoder.blocks.3":
            raise HveeContractError("unknown synthetic module")

        if request.intervention_kind not in self.supported:
            raise HveeContractError("unsupported synthetic intervention")

        intervention_activation = None

        outcome_key = "activation_summary_captured"

        if request.intervention_kind == InternalInterventionKind.ZERO_MODULE_OUTPUT:
            intervention_activation = _summary(zero=True)

            outcome_key = "module_output_zeroed"

        observation = build_internal_intervention_observation(
            status=(ExperimentObservationStatus.COMPLETED),
            outcome_key=(outcome_key),
            actual_cost_units=2,
            runtime_identity_sha256=(self.runtime_sha),
            runtime_model_sha256=(self.model_sha),
            target_identity_sha256=(request.target.target_identity_sha256),
            intervention_kind=(request.intervention_kind),
            baseline_identity_sha256=(request.baseline_identity_sha256),
            intervention_identity_sha256=(request.intervention_identity_sha256),
            baseline_activation=(_summary()),
            intervention_activation=(intervention_activation),
            raw_tensor_egress_performed=False,
        )

        if self.observation_mutator is not None:
            observation = self.observation_mutator(observation)

        return observation


def _execute(
    *,
    request=None,
    runtime=None,
):
    if request is None:
        request = _request()

    if runtime is None:
        runtime = SyntheticInternalRuntime()

    return execute_internal_experiment(
        request=request,
        runtime_adapter=runtime,
    )


def test_internal_engine_identity_is_frozen():
    assert INTERNAL_ENGINE_KEY == ("internal_engine")

    assert INTERNAL_ENGINE_VERSION == ("1.0.0-synthetic-foundation")


@pytest.mark.parametrize(
    "intervention_kind",
    (
        InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY,
        InternalInterventionKind.ZERO_MODULE_OUTPUT,
    ),
)
def test_internal_engine_executes_both_frozen_interventions(
    intervention_kind,
):
    bundle = _execute(request=_request(intervention_kind=(intervention_kind)))

    assert verify_internal_engine_execution_bundle(
        bundle.payload,
        bundle.sha256,
    )

    assert (
        bundle.payload["result"]["observation"]["intervention_kind"]
        == intervention_kind.value
    )


def test_capture_activation_summary_contains_no_raw_tensor():
    bundle = _execute()

    observation = bundle.payload["result"]["observation"]

    assert observation["baseline_activation"]["shape"] == [
        2,
        3,
        4,
    ]

    assert observation["baseline_activation"]["element_count"] == 24

    assert observation["intervention_activation"] is None

    assert observation["raw_tensor_egress_performed"] is False

    assert "tensor" not in (observation["baseline_activation"])


def test_zero_ablation_has_baseline_and_zeroed_intervention_summary():
    bundle = _execute(
        request=_request(
            intervention_kind=(InternalInterventionKind.ZERO_MODULE_OUTPUT)
        )
    )

    observation = bundle.payload["result"]["observation"]

    baseline = observation["baseline_activation"]

    intervention = observation["intervention_activation"]

    assert baseline["l2_norm"] == 7.5

    assert intervention["l2_norm"] == 0.0

    assert intervention["minimum"] == 0.0

    assert intervention["maximum"] == 0.0


def test_shared_experiment_protocol_is_internal():
    bundle = _execute()

    protocol = bundle.experiment_protocol_bundle

    assert (
        protocol.payload["definition"]["engine_kind"]
        == ExperimentEngineKind.INTERNAL.value
    )

    assert verify_experiment_protocol_bundle(
        protocol.payload,
        protocol.sha256,
    )


def test_shared_protocol_never_claims_causal_or_release_authority():
    bundle = _execute()

    boundary = bundle.experiment_protocol_bundle.payload["evidence_boundary"]

    assert boundary["causal_mechanism_established"] is False

    assert boundary["production_qualified"] is False

    assert boundary["release_decision_issued"] is False

    assert boundary["raw_content_persisted"] is False


def test_internal_engine_boundary_never_claims_causal_or_production_authority():
    bundle = _execute()

    boundary = bundle.payload["evidence_boundary"]

    assert boundary == {
        "causal_mechanism_established": False,
        "experiment_execution_proven": True,
        "production_qualified": False,
        "raw_tensor_egress_performed": False,
        "release_decision_issued": False,
    }


def test_exact_replay_is_deterministic():
    first = _execute()
    second = _execute()

    assert first == second
    assert first.sha256 == second.sha256
    assert first.payload == second.payload


def test_execution_sha_helper_matches_bundle():
    bundle = _execute()

    assert calculate_internal_engine_execution_sha256(bundle.payload) == bundle.sha256


def test_runtime_identity_mismatch_fails_before_runtime_execution():
    runtime = SyntheticInternalRuntime(runtime_sha="b" * 64)

    with pytest.raises(HveeContractError):
        _execute(runtime=runtime)

    assert runtime.execution_count == 0


def test_runtime_model_identity_mismatch_fails_before_execution():
    runtime = SyntheticInternalRuntime(model_sha="c" * 64)

    with pytest.raises(HveeContractError):
        _execute(runtime=runtime)

    assert runtime.execution_count == 0


def test_unsupported_intervention_fails_before_execution():
    runtime = SyntheticInternalRuntime(
        supported=(InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY,)
    )

    request = _request(intervention_kind=(InternalInterventionKind.ZERO_MODULE_OUTPUT))

    with pytest.raises(HveeContractError):
        _execute(
            request=request,
            runtime=runtime,
        )

    assert runtime.execution_count == 0


def test_unknown_module_fails_closed():
    runtime = SyntheticInternalRuntime(unknown_module=True)

    with pytest.raises(HveeContractError):
        _execute(runtime=runtime)

    assert runtime.execution_count == 1


def test_runtime_declaring_raw_tensor_egress_is_rejected():
    runtime = SyntheticInternalRuntime(raw_tensor_egress=True)

    with pytest.raises(HveeContractError):
        _execute(runtime=runtime)

    assert runtime.execution_count == 0


def test_request_budget_rejects_estimated_cost_overrun():
    request = _request(
        maximum_cost_units=1,
        estimated_cost_units=2,
    )

    runtime = SyntheticInternalRuntime()

    with pytest.raises(HveeContractError):
        _execute(
            request=request,
            runtime=runtime,
        )

    assert runtime.execution_count == 0


def test_actual_cost_overrun_is_rejected():
    def mutate(
        observation,
    ):
        return build_internal_intervention_observation(
            status=(observation.status),
            outcome_key=(observation.outcome_key),
            actual_cost_units=5,
            runtime_identity_sha256=(observation.runtime_identity_sha256),
            runtime_model_sha256=(observation.runtime_model_sha256),
            target_identity_sha256=(observation.target_identity_sha256),
            intervention_kind=(observation.intervention_kind),
            baseline_identity_sha256=(observation.baseline_identity_sha256),
            intervention_identity_sha256=(observation.intervention_identity_sha256),
            baseline_activation=(observation.baseline_activation),
            intervention_activation=(observation.intervention_activation),
        )

    runtime = SyntheticInternalRuntime(observation_mutator=mutate)

    with pytest.raises(HveeContractError):
        _execute(runtime=runtime)


def test_observation_target_identity_mismatch_is_rejected():
    def mutate(
        observation,
    ):
        return build_internal_intervention_observation(
            status=(observation.status),
            outcome_key=(observation.outcome_key),
            actual_cost_units=(observation.actual_cost_units),
            runtime_identity_sha256=(observation.runtime_identity_sha256),
            runtime_model_sha256=(observation.runtime_model_sha256),
            target_identity_sha256=("d" * 64),
            intervention_kind=(observation.intervention_kind),
            baseline_identity_sha256=(observation.baseline_identity_sha256),
            intervention_identity_sha256=(observation.intervention_identity_sha256),
            baseline_activation=(observation.baseline_activation),
            intervention_activation=(observation.intervention_activation),
        )

    with pytest.raises(HveeContractError):
        _execute(runtime=(SyntheticInternalRuntime(observation_mutator=mutate)))


def test_observation_runtime_identity_mismatch_is_rejected():
    def mutate(
        observation,
    ):
        return build_internal_intervention_observation(
            status=(observation.status),
            outcome_key=(observation.outcome_key),
            actual_cost_units=(observation.actual_cost_units),
            runtime_identity_sha256=("e" * 64),
            runtime_model_sha256=(observation.runtime_model_sha256),
            target_identity_sha256=(observation.target_identity_sha256),
            intervention_kind=(observation.intervention_kind),
            baseline_identity_sha256=(observation.baseline_identity_sha256),
            intervention_identity_sha256=(observation.intervention_identity_sha256),
            baseline_activation=(observation.baseline_activation),
            intervention_activation=(observation.intervention_activation),
        )

    with pytest.raises(HveeContractError):
        _execute(runtime=(SyntheticInternalRuntime(observation_mutator=mutate)))


def test_provenance_tampering_is_rejected():
    valid = build_internal_intervention_observation(
        status=(ExperimentObservationStatus.COMPLETED),
        outcome_key="captured",
        actual_cost_units=1,
        runtime_identity_sha256=RUNTIME_SHA,
        runtime_model_sha256=MODEL_SHA,
        target_identity_sha256=TARGET_SHA,
        intervention_kind=(InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY),
        baseline_identity_sha256=(BASELINE_SHA),
        intervention_identity_sha256=(CAPTURE_INTERVENTION_SHA),
        baseline_activation=_summary(),
        intervention_activation=None,
    )

    invalid = replace(
        valid,
        result_provenance_sha256=("f" * 64),
    )

    assert verify_internal_intervention_observation(valid) is True

    assert verify_internal_intervention_observation(invalid) is False


def test_observation_evidence_tampering_is_rejected():
    valid = build_internal_intervention_observation(
        status=(ExperimentObservationStatus.COMPLETED),
        outcome_key="captured",
        actual_cost_units=1,
        runtime_identity_sha256=RUNTIME_SHA,
        runtime_model_sha256=MODEL_SHA,
        target_identity_sha256=TARGET_SHA,
        intervention_kind=(InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY),
        baseline_identity_sha256=(BASELINE_SHA),
        intervention_identity_sha256=(CAPTURE_INTERVENTION_SHA),
        baseline_activation=_summary(),
        intervention_activation=None,
    )

    invalid = replace(
        valid,
        observation_evidence_sha256=("f" * 64),
    )

    assert verify_internal_intervention_observation(invalid) is False


def test_activation_shape_and_element_count_must_agree():
    invalid = InternalActivationSummary(
        shape=(2, 3, 4),
        dtype="float32",
        element_count=23,
        finite_element_count=23,
        minimum=0.0,
        maximum=1.0,
        mean=0.5,
        l2_norm=1.0,
        activation_commitment_sha256=(BASELINE_ACTIVATION_SHA),
    )

    with pytest.raises(HveeContractError):
        build_internal_intervention_observation(
            status=(ExperimentObservationStatus.COMPLETED),
            outcome_key="captured",
            actual_cost_units=1,
            runtime_identity_sha256=RUNTIME_SHA,
            runtime_model_sha256=MODEL_SHA,
            target_identity_sha256=TARGET_SHA,
            intervention_kind=(InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY),
            baseline_identity_sha256=(BASELINE_SHA),
            intervention_identity_sha256=(CAPTURE_INTERVENTION_SHA),
            baseline_activation=invalid,
            intervention_activation=None,
        )


def test_capture_intervention_rejects_second_activation_summary():
    with pytest.raises(HveeContractError):
        build_internal_intervention_observation(
            status=(ExperimentObservationStatus.COMPLETED),
            outcome_key="captured",
            actual_cost_units=1,
            runtime_identity_sha256=RUNTIME_SHA,
            runtime_model_sha256=MODEL_SHA,
            target_identity_sha256=TARGET_SHA,
            intervention_kind=(InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY),
            baseline_identity_sha256=(BASELINE_SHA),
            intervention_identity_sha256=(CAPTURE_INTERVENTION_SHA),
            baseline_activation=_summary(),
            intervention_activation=(_summary(zero=True)),
        )


def test_zero_intervention_requires_intervention_activation_summary():
    with pytest.raises(HveeContractError):
        build_internal_intervention_observation(
            status=(ExperimentObservationStatus.COMPLETED),
            outcome_key="zeroed",
            actual_cost_units=1,
            runtime_identity_sha256=RUNTIME_SHA,
            runtime_model_sha256=MODEL_SHA,
            target_identity_sha256=TARGET_SHA,
            intervention_kind=(InternalInterventionKind.ZERO_MODULE_OUTPUT),
            baseline_identity_sha256=(BASELINE_SHA),
            intervention_identity_sha256=(ZERO_INTERVENTION_SHA),
            baseline_activation=_summary(),
            intervention_activation=None,
        )


def test_execution_verifier_rejects_protocol_tampering():
    bundle = _execute()

    payload = deepcopy(bundle.payload)

    payload["experiment_protocol"]["campaign"]["version"] = "tampered"

    assert not (
        verify_internal_engine_execution_bundle(
            payload,
            bundle.sha256,
        )
    )


def test_execution_verifier_rejects_internal_result_tampering():
    bundle = _execute()

    payload = deepcopy(bundle.payload)

    payload["result"]["observation"]["outcome_key"] = "tampered"

    assert not (
        verify_internal_engine_execution_bundle(
            payload,
            bundle.sha256,
        )
    )


def test_execution_verifier_rejects_wrong_execution_hash():
    bundle = _execute()

    assert not (
        verify_internal_engine_execution_bundle(
            bundle.payload,
            "f" * 64,
        )
    )


def test_result_contains_stable_provenance_and_evidence_hashes():
    bundle = _execute(
        request=_request(
            intervention_kind=(InternalInterventionKind.ZERO_MODULE_OUTPUT)
        )
    )

    observation = bundle.payload["result"]["observation"]

    assert len(observation["result_provenance_sha256"]) == 64

    assert len(observation["observation_evidence_sha256"]) == 64

    assert (
        observation["result_provenance_sha256"]
        != observation["observation_evidence_sha256"]
    )


def test_runtime_executes_exactly_once_per_internal_request():
    runtime = SyntheticInternalRuntime()

    _execute(runtime=runtime)

    assert runtime.execution_count == 1


def test_execution_payload_has_no_tensor_or_model_object_references():
    bundle = _execute(
        request=_request(
            intervention_kind=(InternalInterventionKind.ZERO_MODULE_OUTPUT)
        )
    )

    rendered = repr(bundle.payload)

    assert "tensor(" not in rendered.lower()
    assert "<module" not in rendered.lower()
    assert "<model" not in rendered.lower()


def test_no_behavioral_execution_claim_is_added_to_internal_protocol():
    bundle = _execute()

    assert (
        bundle.payload["experiment_protocol"]["definition"]["engine_kind"] == "internal"
    )

    assert bundle.payload["engine"]["key"] == "internal_engine"
