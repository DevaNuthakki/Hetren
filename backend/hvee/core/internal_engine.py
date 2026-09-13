from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import math
import re
from typing import Protocol

from hvee.core.contracts import HveeContractError
from hvee.core.experiment_protocol import (
    ExperimentDefinition,
    ExperimentEngineKind,
    ExperimentObservation,
    ExperimentObservationStatus,
    ExperimentProposal,
    ExperimentProtocolBundle,
    build_experiment_protocol_bundle,
    calculate_experiment_proposal_sha256,
    verify_experiment_protocol_bundle,
)


INTERNAL_ENGINE_KEY = "internal_engine"
INTERNAL_ENGINE_VERSION = "1.0.0-synthetic-foundation"

_INTERNAL_OPERATION_VERSION = "1.0.0"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class InternalInterventionKind(StrEnum):
    CAPTURE_ACTIVATION_SUMMARY = "capture_activation_summary"
    ZERO_MODULE_OUTPUT = "zero_module_output"


@dataclass(
    frozen=True,
    slots=True,
)
class InternalRuntimeCapability:
    runtime_key: str
    runtime_version: str
    runtime_identity_sha256: str
    runtime_model_sha256: str
    supported_interventions: tuple[
        InternalInterventionKind,
        ...,
    ]
    raw_tensor_egress: bool = False


@dataclass(
    frozen=True,
    slots=True,
)
class InternalModuleTarget:
    module_path: str
    module_kind: str
    target_identity_sha256: str
    runtime_model_sha256: str
    module_index: int | None = None
    head_index: int | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class InternalExperimentRequest:
    request_key: str
    request_version: str
    campaign_key: str
    campaign_version: str
    subject_sha256: str
    expected_runtime_identity_sha256: str
    expected_runtime_model_sha256: str
    target: InternalModuleTarget
    intervention_kind: InternalInterventionKind
    baseline_identity_sha256: str
    intervention_identity_sha256: str
    estimated_cost_units: int
    maximum_experiments: int
    maximum_cost_units: int
    reason_code: str
    source_evidence_sha256: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class InternalActivationSummary:
    shape: tuple[int, ...]
    dtype: str
    element_count: int
    finite_element_count: int
    minimum: float
    maximum: float
    mean: float
    l2_norm: float
    activation_commitment_sha256: str


@dataclass(
    frozen=True,
    slots=True,
)
class InternalInterventionObservation:
    status: ExperimentObservationStatus
    outcome_key: str
    actual_cost_units: int
    runtime_identity_sha256: str
    runtime_model_sha256: str
    target_identity_sha256: str
    intervention_kind: InternalInterventionKind
    baseline_identity_sha256: str
    intervention_identity_sha256: str
    baseline_activation: InternalActivationSummary
    intervention_activation: InternalActivationSummary | None
    raw_tensor_egress_performed: bool
    result_provenance_sha256: str
    observation_evidence_sha256: str


@dataclass(
    frozen=True,
    slots=True,
)
class InternalExperimentResultBundle:
    payload: dict[str, object]
    sha256: str


@dataclass(
    frozen=True,
    slots=True,
)
class InternalEngineExecutionBundle:
    payload: dict[str, object]
    request_sha256: str
    runtime_capability_sha256: str
    result_bundle: InternalExperimentResultBundle
    experiment_protocol_bundle: ExperimentProtocolBundle
    sha256: str


class InternalRuntimeAdapter(Protocol):
    def describe_capability(
        self,
    ) -> InternalRuntimeCapability: ...

    def execute(
        self,
        request: InternalExperimentRequest,
    ) -> InternalInterventionObservation: ...


def _canonical_bytes(
    value: object,
) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError("value is not canonically serializable") from exc


def _calculate_sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_identifier(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise HveeContractError(field + " must be a string")

    normalized = value.strip()

    if not normalized:
        raise HveeContractError(field + " must not be empty")

    if normalized != value:
        raise HveeContractError(field + " must not contain surrounding whitespace")

    if len(normalized) > 512:
        raise HveeContractError(field + " is too long")

    return normalized


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(
        value,
        str,
    ) or not _SHA256_RE.fullmatch(value):
        raise HveeContractError(field + " must be a lowercase SHA-256 digest")

    return value


def _require_positive_integer(
    value: object,
    *,
    field: str,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value <= 0
    ):
        raise HveeContractError(field + " must be a positive integer")

    return value


def _require_optional_nonnegative_integer(
    value: object,
    *,
    field: str,
) -> int | None:
    if value is None:
        return None

    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 0
    ):
        raise HveeContractError(field + " must be a non-negative integer or null")

    return value


def _require_finite_float(
    value: object,
    *,
    field: str,
) -> float:
    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        raise HveeContractError(field + " must be numeric")

    result = float(value)

    if not math.isfinite(result):
        raise HveeContractError(field + " must be finite")

    return result


def _activation_payload(
    summary: InternalActivationSummary,
) -> dict[str, object]:
    if not isinstance(
        summary,
        InternalActivationSummary,
    ):
        raise HveeContractError("activation summary has invalid type")

    if (
        not isinstance(
            summary.shape,
            tuple,
        )
        or not summary.shape
    ):
        raise HveeContractError("activation shape must be a non-empty tuple")

    shape = []

    for value in summary.shape:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
            or value <= 0
        ):
            raise HveeContractError(
                "activation shape dimensions must be positive integers"
            )

        shape.append(value)

    dtype = _require_identifier(
        summary.dtype,
        field="activation dtype",
    )

    element_count = _require_positive_integer(
        summary.element_count,
        field="activation element_count",
    )

    expected_element_count = math.prod(shape)

    if element_count != expected_element_count:
        raise HveeContractError("activation element_count does not match shape")

    finite_element_count = _require_positive_integer(
        summary.finite_element_count,
        field="activation finite_element_count",
    )

    if finite_element_count > element_count:
        raise HveeContractError("activation finite_element_count exceeds element_count")

    minimum = _require_finite_float(
        summary.minimum,
        field="activation minimum",
    )

    maximum = _require_finite_float(
        summary.maximum,
        field="activation maximum",
    )

    mean = _require_finite_float(
        summary.mean,
        field="activation mean",
    )

    l2_norm = _require_finite_float(
        summary.l2_norm,
        field="activation l2_norm",
    )

    if minimum > maximum:
        raise HveeContractError("activation minimum exceeds maximum")

    if l2_norm < 0.0:
        raise HveeContractError("activation l2_norm must be non-negative")

    commitment = _require_sha256(
        summary.activation_commitment_sha256,
        field="activation_commitment_sha256",
    )

    return {
        "activation_commitment_sha256": (commitment),
        "dtype": dtype,
        "element_count": (element_count),
        "finite_element_count": (finite_element_count),
        "l2_norm": l2_norm,
        "maximum": maximum,
        "mean": mean,
        "minimum": minimum,
        "shape": shape,
    }


def _target_payload(
    target: InternalModuleTarget,
) -> dict[str, object]:
    if not isinstance(
        target,
        InternalModuleTarget,
    ):
        raise HveeContractError("target has invalid type")

    module_path = _require_identifier(
        target.module_path,
        field="module_path",
    )

    module_kind = _require_identifier(
        target.module_kind,
        field="module_kind",
    )

    target_identity_sha256 = _require_sha256(
        target.target_identity_sha256,
        field="target_identity_sha256",
    )

    runtime_model_sha256 = _require_sha256(
        target.runtime_model_sha256,
        field="target.runtime_model_sha256",
    )

    module_index = _require_optional_nonnegative_integer(
        target.module_index,
        field="module_index",
    )

    head_index = _require_optional_nonnegative_integer(
        target.head_index,
        field="head_index",
    )

    return {
        "head_index": head_index,
        "module_index": module_index,
        "module_kind": module_kind,
        "module_path": module_path,
        "runtime_model_sha256": (runtime_model_sha256),
        "target_identity_sha256": (target_identity_sha256),
    }


def _capability_payload(
    capability: InternalRuntimeCapability,
) -> dict[str, object]:
    if not isinstance(
        capability,
        InternalRuntimeCapability,
    ):
        raise HveeContractError("runtime capability has invalid type")

    runtime_key = _require_identifier(
        capability.runtime_key,
        field="runtime_key",
    )

    runtime_version = _require_identifier(
        capability.runtime_version,
        field="runtime_version",
    )

    runtime_identity_sha256 = _require_sha256(
        capability.runtime_identity_sha256,
        field="runtime_identity_sha256",
    )

    runtime_model_sha256 = _require_sha256(
        capability.runtime_model_sha256,
        field="runtime_model_sha256",
    )

    if (
        not isinstance(
            capability.supported_interventions,
            tuple,
        )
        or not capability.supported_interventions
    ):
        raise HveeContractError("supported_interventions must be a non-empty tuple")

    interventions = []

    for item in capability.supported_interventions:
        if not isinstance(
            item,
            InternalInterventionKind,
        ):
            raise HveeContractError(
                "runtime capability contains an invalid intervention"
            )

        interventions.append(item.value)

    if len(interventions) != len(set(interventions)):
        raise HveeContractError("supported_interventions contains duplicates")

    if capability.raw_tensor_egress is not False:
        raise HveeContractError("Internal Engine V1 forbids raw tensor egress")

    return {
        "raw_tensor_egress": False,
        "runtime_identity_sha256": (runtime_identity_sha256),
        "runtime_key": runtime_key,
        "runtime_model_sha256": (runtime_model_sha256),
        "runtime_version": runtime_version,
        "supported_interventions": (sorted(interventions)),
    }


def _request_payload(
    request: InternalExperimentRequest,
) -> dict[str, object]:
    if not isinstance(
        request,
        InternalExperimentRequest,
    ):
        raise HveeContractError("internal experiment request has invalid type")

    request_key = _require_identifier(
        request.request_key,
        field="request_key",
    )

    request_version = _require_identifier(
        request.request_version,
        field="request_version",
    )

    campaign_key = _require_identifier(
        request.campaign_key,
        field="campaign_key",
    )

    campaign_version = _require_identifier(
        request.campaign_version,
        field="campaign_version",
    )

    subject_sha256 = _require_sha256(
        request.subject_sha256,
        field="subject_sha256",
    )

    expected_runtime_identity_sha256 = _require_sha256(
        request.expected_runtime_identity_sha256,
        field="expected_runtime_identity_sha256",
    )

    expected_runtime_model_sha256 = _require_sha256(
        request.expected_runtime_model_sha256,
        field="expected_runtime_model_sha256",
    )

    target = _target_payload(request.target)

    if not isinstance(
        request.intervention_kind,
        InternalInterventionKind,
    ):
        raise HveeContractError("intervention_kind has invalid type")

    baseline_identity_sha256 = _require_sha256(
        request.baseline_identity_sha256,
        field="baseline_identity_sha256",
    )

    intervention_identity_sha256 = _require_sha256(
        request.intervention_identity_sha256,
        field="intervention_identity_sha256",
    )

    estimated_cost_units = _require_positive_integer(
        request.estimated_cost_units,
        field="estimated_cost_units",
    )

    maximum_experiments = _require_positive_integer(
        request.maximum_experiments,
        field="maximum_experiments",
    )

    maximum_cost_units = _require_positive_integer(
        request.maximum_cost_units,
        field="maximum_cost_units",
    )

    if estimated_cost_units > (maximum_cost_units):
        raise HveeContractError("estimated cost exceeds maximum_cost_units")

    reason_code = _require_identifier(
        request.reason_code,
        field="reason_code",
    )

    source_evidence_sha256 = (
        None
        if (request.source_evidence_sha256 is None)
        else _require_sha256(
            request.source_evidence_sha256,
            field="source_evidence_sha256",
        )
    )

    if target["runtime_model_sha256"] != expected_runtime_model_sha256:
        raise HveeContractError(
            "target runtime model does not match requested runtime model"
        )

    return {
        "baseline_identity_sha256": (baseline_identity_sha256),
        "campaign_key": campaign_key,
        "campaign_version": (campaign_version),
        "estimated_cost_units": (estimated_cost_units),
        "expected_runtime_identity_sha256": (expected_runtime_identity_sha256),
        "expected_runtime_model_sha256": (expected_runtime_model_sha256),
        "intervention_identity_sha256": (intervention_identity_sha256),
        "intervention_kind": (request.intervention_kind.value),
        "maximum_cost_units": (maximum_cost_units),
        "maximum_experiments": (maximum_experiments),
        "reason_code": reason_code,
        "request_key": request_key,
        "request_version": request_version,
        "source_evidence_sha256": (source_evidence_sha256),
        "subject_sha256": (subject_sha256),
        "target": target,
    }


def calculate_internal_runtime_capability_sha256(
    capability: InternalRuntimeCapability,
) -> str:
    return _calculate_sha256(_capability_payload(capability))


def calculate_internal_experiment_request_sha256(
    request: InternalExperimentRequest,
) -> str:
    return _calculate_sha256(_request_payload(request))


def _observation_base_payload(
    *,
    status: ExperimentObservationStatus,
    outcome_key: str,
    actual_cost_units: int,
    runtime_identity_sha256: str,
    runtime_model_sha256: str,
    target_identity_sha256: str,
    intervention_kind: InternalInterventionKind,
    baseline_identity_sha256: str,
    intervention_identity_sha256: str,
    baseline_activation: InternalActivationSummary,
    intervention_activation: InternalActivationSummary | None,
    raw_tensor_egress_performed: bool,
) -> dict[str, object]:
    if not isinstance(
        status,
        ExperimentObservationStatus,
    ):
        raise HveeContractError("internal observation status has invalid type")

    outcome_key = _require_identifier(
        outcome_key,
        field="outcome_key",
    )

    actual_cost_units = _require_positive_integer(
        actual_cost_units,
        field="actual_cost_units",
    )

    runtime_identity_sha256 = _require_sha256(
        runtime_identity_sha256,
        field="observation.runtime_identity_sha256",
    )

    runtime_model_sha256 = _require_sha256(
        runtime_model_sha256,
        field="observation.runtime_model_sha256",
    )

    target_identity_sha256 = _require_sha256(
        target_identity_sha256,
        field="observation.target_identity_sha256",
    )

    if not isinstance(
        intervention_kind,
        InternalInterventionKind,
    ):
        raise HveeContractError("observation intervention kind has invalid type")

    baseline_identity_sha256 = _require_sha256(
        baseline_identity_sha256,
        field="observation.baseline_identity_sha256",
    )

    intervention_identity_sha256 = _require_sha256(
        intervention_identity_sha256,
        field="observation.intervention_identity_sha256",
    )

    baseline_payload = _activation_payload(baseline_activation)

    intervention_payload = (
        None
        if intervention_activation is None
        else _activation_payload(intervention_activation)
    )

    if raw_tensor_egress_performed is not False:
        raise HveeContractError("raw tensor egress is forbidden")

    if intervention_kind == InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY:
        if intervention_payload is not None:
            raise HveeContractError(
                "capture-only observation must not contain intervention activation"
            )

    elif intervention_kind == InternalInterventionKind.ZERO_MODULE_OUTPUT:
        if intervention_payload is None:
            raise HveeContractError(
                "zero-module observation requires intervention activation"
            )

    return {
        "actual_cost_units": (actual_cost_units),
        "baseline_activation": (baseline_payload),
        "baseline_identity_sha256": (baseline_identity_sha256),
        "intervention_activation": (intervention_payload),
        "intervention_identity_sha256": (intervention_identity_sha256),
        "intervention_kind": (intervention_kind.value),
        "outcome_key": outcome_key,
        "raw_tensor_egress_performed": (False),
        "runtime_identity_sha256": (runtime_identity_sha256),
        "runtime_model_sha256": (runtime_model_sha256),
        "status": status.value,
        "target_identity_sha256": (target_identity_sha256),
    }


def build_internal_intervention_observation(
    *,
    status: ExperimentObservationStatus,
    outcome_key: str,
    actual_cost_units: int,
    runtime_identity_sha256: str,
    runtime_model_sha256: str,
    target_identity_sha256: str,
    intervention_kind: InternalInterventionKind,
    baseline_identity_sha256: str,
    intervention_identity_sha256: str,
    baseline_activation: InternalActivationSummary,
    intervention_activation: InternalActivationSummary | None,
    raw_tensor_egress_performed: bool = False,
) -> InternalInterventionObservation:
    base_payload = _observation_base_payload(
        status=status,
        outcome_key=outcome_key,
        actual_cost_units=(actual_cost_units),
        runtime_identity_sha256=(runtime_identity_sha256),
        runtime_model_sha256=(runtime_model_sha256),
        target_identity_sha256=(target_identity_sha256),
        intervention_kind=(intervention_kind),
        baseline_identity_sha256=(baseline_identity_sha256),
        intervention_identity_sha256=(intervention_identity_sha256),
        baseline_activation=(baseline_activation),
        intervention_activation=(intervention_activation),
        raw_tensor_egress_performed=(raw_tensor_egress_performed),
    )

    provenance_payload = {
        "kind": ("hetren_internal_intervention_result_provenance"),
        "observation": base_payload,
        "schema_version": 1,
    }

    provenance_sha256 = _calculate_sha256(provenance_payload)

    evidence_payload = {
        "kind": ("hetren_internal_intervention_observation_evidence"),
        "observation": base_payload,
        "result_provenance_sha256": (provenance_sha256),
        "schema_version": 1,
    }

    evidence_sha256 = _calculate_sha256(evidence_payload)

    return InternalInterventionObservation(
        status=status,
        outcome_key=(str(base_payload["outcome_key"])),
        actual_cost_units=(actual_cost_units),
        runtime_identity_sha256=(runtime_identity_sha256),
        runtime_model_sha256=(runtime_model_sha256),
        target_identity_sha256=(target_identity_sha256),
        intervention_kind=(intervention_kind),
        baseline_identity_sha256=(baseline_identity_sha256),
        intervention_identity_sha256=(intervention_identity_sha256),
        baseline_activation=(baseline_activation),
        intervention_activation=(intervention_activation),
        raw_tensor_egress_performed=False,
        result_provenance_sha256=(provenance_sha256),
        observation_evidence_sha256=(evidence_sha256),
    )


def _observation_payload(
    observation: InternalInterventionObservation,
) -> dict[str, object]:
    if not isinstance(
        observation,
        InternalInterventionObservation,
    ):
        raise HveeContractError("internal intervention observation has invalid type")

    base_payload = _observation_base_payload(
        status=observation.status,
        outcome_key=(observation.outcome_key),
        actual_cost_units=(observation.actual_cost_units),
        runtime_identity_sha256=(observation.runtime_identity_sha256),
        runtime_model_sha256=(observation.runtime_model_sha256),
        target_identity_sha256=(observation.target_identity_sha256),
        intervention_kind=(observation.intervention_kind),
        baseline_identity_sha256=(observation.baseline_identity_sha256),
        intervention_identity_sha256=(observation.intervention_identity_sha256),
        baseline_activation=(observation.baseline_activation),
        intervention_activation=(observation.intervention_activation),
        raw_tensor_egress_performed=(observation.raw_tensor_egress_performed),
    )

    expected_provenance_sha256 = _calculate_sha256(
        {
            "kind": ("hetren_internal_intervention_result_provenance"),
            "observation": (base_payload),
            "schema_version": 1,
        }
    )

    actual_provenance_sha256 = _require_sha256(
        observation.result_provenance_sha256,
        field="result_provenance_sha256",
    )

    if actual_provenance_sha256 != expected_provenance_sha256:
        raise HveeContractError("internal observation provenance identity mismatch")

    expected_evidence_sha256 = _calculate_sha256(
        {
            "kind": ("hetren_internal_intervention_observation_evidence"),
            "observation": (base_payload),
            "result_provenance_sha256": (expected_provenance_sha256),
            "schema_version": 1,
        }
    )

    actual_evidence_sha256 = _require_sha256(
        observation.observation_evidence_sha256,
        field="observation_evidence_sha256",
    )

    if actual_evidence_sha256 != expected_evidence_sha256:
        raise HveeContractError("internal observation evidence identity mismatch")

    return {
        **base_payload,
        "observation_evidence_sha256": (actual_evidence_sha256),
        "result_provenance_sha256": (actual_provenance_sha256),
    }


def verify_internal_intervention_observation(
    observation: InternalInterventionObservation,
) -> bool:
    try:
        _observation_payload(observation)

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False

    return True


def _validate_execution_binding(
    *,
    request: InternalExperimentRequest,
    capability: InternalRuntimeCapability,
    observation: InternalInterventionObservation,
) -> None:
    request_payload = _request_payload(request)

    capability_payload = _capability_payload(capability)

    observation_payload = _observation_payload(observation)

    if (
        capability_payload["runtime_identity_sha256"]
        != request_payload["expected_runtime_identity_sha256"]
    ):
        raise HveeContractError("runtime identity does not match request")

    if (
        capability_payload["runtime_model_sha256"]
        != request_payload["expected_runtime_model_sha256"]
    ):
        raise HveeContractError("runtime model identity does not match request")

    if (
        request_payload["intervention_kind"]
        not in capability_payload["supported_interventions"]
    ):
        raise HveeContractError("runtime does not support requested intervention")

    if (
        observation_payload["runtime_identity_sha256"]
        != capability_payload["runtime_identity_sha256"]
    ):
        raise HveeContractError("observation runtime identity mismatch")

    if (
        observation_payload["runtime_model_sha256"]
        != capability_payload["runtime_model_sha256"]
    ):
        raise HveeContractError("observation runtime model mismatch")

    target = request_payload["target"]

    if (
        observation_payload["target_identity_sha256"]
        != target["target_identity_sha256"]
    ):
        raise HveeContractError("observation target identity mismatch")

    if observation_payload["intervention_kind"] != request_payload["intervention_kind"]:
        raise HveeContractError("observation intervention mismatch")

    if (
        observation_payload["baseline_identity_sha256"]
        != request_payload["baseline_identity_sha256"]
    ):
        raise HveeContractError("observation baseline identity mismatch")

    if (
        observation_payload["intervention_identity_sha256"]
        != request_payload["intervention_identity_sha256"]
    ):
        raise HveeContractError("observation intervention identity mismatch")

    if observation_payload["actual_cost_units"] > request_payload["maximum_cost_units"]:
        raise HveeContractError("actual internal experiment cost exceeds budget")


def execute_internal_experiment(
    *,
    request: InternalExperimentRequest,
    runtime_adapter: InternalRuntimeAdapter,
) -> InternalEngineExecutionBundle:
    request_payload = _request_payload(request)

    request_sha256 = _calculate_sha256(request_payload)

    capability = runtime_adapter.describe_capability()

    capability_payload = _capability_payload(capability)

    capability_sha256 = _calculate_sha256(capability_payload)

    if capability.runtime_identity_sha256 != request.expected_runtime_identity_sha256:
        raise HveeContractError("injected runtime identity is not authorized")

    if capability.runtime_model_sha256 != request.expected_runtime_model_sha256:
        raise HveeContractError("injected runtime model is not authorized")

    if request.intervention_kind not in capability.supported_interventions:
        raise HveeContractError("requested intervention is not supported")

    observation = runtime_adapter.execute(request)

    _validate_execution_binding(
        request=request,
        capability=capability,
        observation=observation,
    )

    observation_payload = _observation_payload(observation)

    proposal = ExperimentProposal(
        sequence=0,
        proposal_key=(request.request_key),
        target_sha256=(request.target.target_identity_sha256),
        parameters={
            "baseline_identity_sha256": (request.baseline_identity_sha256),
            "intervention_identity_sha256": (request.intervention_identity_sha256),
            "intervention_kind": (request.intervention_kind.value),
            "module_kind": (request.target.module_kind),
            "module_path": (request.target.module_path),
            "runtime_identity_sha256": (capability.runtime_identity_sha256),
            "runtime_model_sha256": (capability.runtime_model_sha256),
        },
        estimated_cost_units=(request.estimated_cost_units),
        reason_code=(request.reason_code),
        source_evidence_sha256=(request.source_evidence_sha256),
    )

    proposal_sha256 = calculate_experiment_proposal_sha256(proposal)

    protocol_observation = ExperimentObservation(
        proposal_sequence=0,
        proposal_sha256=(proposal_sha256),
        status=(observation.status),
        outcome_key=(observation.outcome_key),
        actual_cost_units=(observation.actual_cost_units),
        result_evidence_sha256=(observation.observation_evidence_sha256),
        evaluator_evidence_sha256=None,
    )

    definition = ExperimentDefinition(
        key="hetren.internal_engine",
        version=(INTERNAL_ENGINE_VERSION),
        engine_kind=(ExperimentEngineKind.INTERNAL),
        operation_key=(request.intervention_kind.value),
        operation_version=(_INTERNAL_OPERATION_VERSION),
    )

    protocol_bundle = build_experiment_protocol_bundle(
        definition=definition,
        campaign_key=(request.campaign_key),
        campaign_version=(request.campaign_version),
        subject_sha256=(request.subject_sha256),
        maximum_experiments=(request.maximum_experiments),
        maximum_cost_units=(request.maximum_cost_units),
        proposals=(proposal,),
        observations=(protocol_observation,),
    )

    if not verify_experiment_protocol_bundle(
        protocol_bundle.payload,
        protocol_bundle.sha256,
    ):
        raise HveeContractError("internal experiment protocol verification failed")

    result_payload: dict[
        str,
        object,
    ] = {
        "engine": {
            "key": (INTERNAL_ENGINE_KEY),
            "version": (INTERNAL_ENGINE_VERSION),
        },
        "observation": (observation_payload),
        "request": (request_payload),
        "request_sha256": (request_sha256),
        "runtime_capability": (capability_payload),
        "runtime_capability_sha256": (capability_sha256),
        "schema_version": 1,
    }

    result_sha256 = _calculate_sha256(result_payload)

    result_bundle = InternalExperimentResultBundle(
        payload=result_payload,
        sha256=result_sha256,
    )

    payload: dict[
        str,
        object,
    ] = {
        "engine": {
            "key": (INTERNAL_ENGINE_KEY),
            "version": (INTERNAL_ENGINE_VERSION),
        },
        "evidence_boundary": {
            "causal_mechanism_established": False,
            "experiment_execution_proven": True,
            "production_qualified": False,
            "raw_tensor_egress_performed": False,
            "release_decision_issued": False,
        },
        "experiment_protocol": (protocol_bundle.payload),
        "experiment_protocol_sha256": (protocol_bundle.sha256),
        "request_sha256": (request_sha256),
        "result": (result_payload),
        "result_sha256": (result_sha256),
        "runtime_capability_sha256": (capability_sha256),
        "schema_version": 1,
    }

    execution_sha256 = _calculate_sha256(payload)

    return InternalEngineExecutionBundle(
        payload=payload,
        request_sha256=(request_sha256),
        runtime_capability_sha256=(capability_sha256),
        result_bundle=(result_bundle),
        experiment_protocol_bundle=(protocol_bundle),
        sha256=(execution_sha256),
    )


def calculate_internal_engine_execution_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("Internal Engine execution payload must be an object")

    return _calculate_sha256(payload)


def verify_internal_engine_execution_bundle(
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        expected_sha256 = _require_sha256(
            expected_sha256,
            field="expected_sha256",
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        if set(payload) != {
            "engine",
            "evidence_boundary",
            "experiment_protocol",
            "experiment_protocol_sha256",
            "request_sha256",
            "result",
            "result_sha256",
            "runtime_capability_sha256",
            "schema_version",
        }:
            return False

        if payload["schema_version"] != 1:
            return False

        if payload["engine"] != {
            "key": (INTERNAL_ENGINE_KEY),
            "version": (INTERNAL_ENGINE_VERSION),
        }:
            return False

        if payload["evidence_boundary"] != {
            "causal_mechanism_established": False,
            "experiment_execution_proven": True,
            "production_qualified": False,
            "raw_tensor_egress_performed": False,
            "release_decision_issued": False,
        }:
            return False

        protocol_payload = payload["experiment_protocol"]

        protocol_sha256 = _require_sha256(
            payload["experiment_protocol_sha256"],
            field="experiment_protocol_sha256",
        )

        if not (
            verify_experiment_protocol_bundle(
                protocol_payload,
                protocol_sha256,
            )
        ):
            return False

        if (
            protocol_payload["definition"]["engine_kind"]
            != ExperimentEngineKind.INTERNAL.value
        ):
            return False

        result = payload["result"]

        if not isinstance(
            result,
            dict,
        ):
            return False

        if set(result) != {
            "engine",
            "observation",
            "request",
            "request_sha256",
            "runtime_capability",
            "runtime_capability_sha256",
            "schema_version",
        }:
            return False

        if result["schema_version"] != 1:
            return False

        if result["engine"] != payload["engine"]:
            return False

        request_payload = result["request"]

        capability_payload = result["runtime_capability"]

        if _calculate_sha256(request_payload) != result["request_sha256"]:
            return False

        if result["request_sha256"] != payload["request_sha256"]:
            return False

        if _calculate_sha256(capability_payload) != result["runtime_capability_sha256"]:
            return False

        if result["runtime_capability_sha256"] != payload["runtime_capability_sha256"]:
            return False

        if capability_payload["raw_tensor_egress"] is not False:
            return False

        observation = result["observation"]

        if not isinstance(
            observation,
            dict,
        ):
            return False

        if observation["raw_tensor_egress_performed"] is not False:
            return False

        if (
            observation["runtime_identity_sha256"]
            != request_payload["expected_runtime_identity_sha256"]
        ):
            return False

        if (
            observation["runtime_model_sha256"]
            != request_payload["expected_runtime_model_sha256"]
        ):
            return False

        if (
            observation["target_identity_sha256"]
            != request_payload["target"]["target_identity_sha256"]
        ):
            return False

        if observation["intervention_kind"] != request_payload["intervention_kind"]:
            return False

        if protocol_payload["subject_sha256"] != request_payload["subject_sha256"]:
            return False

        if (
            protocol_payload["observations"][0]["result_evidence_sha256"]
            != observation["observation_evidence_sha256"]
        ):
            return False

        if _calculate_sha256(result) != payload["result_sha256"]:
            return False

        if _calculate_sha256(payload) != expected_sha256:
            return False

    except (
        HveeContractError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ):
        return False

    return True
