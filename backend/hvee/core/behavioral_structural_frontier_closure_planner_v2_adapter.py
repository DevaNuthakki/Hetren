from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import json

from hvee.core.behavioral_multi_objective_planner_adapter import (
    _normalize_candidate_target_sha256s,
    _normalize_candidate_values,
    _normalize_maximum_evaluations,
    _normalize_observations,
    _observation_payload,
    _parse_observation,
    _require_sha256,
    _require_string,
)
from hvee.core.behavioral_structural_frontier_closure_planner_v2 import (
    PLANNER_KEY,
    PLANNER_VERSION,
    StructuralFrontierPlannerDecision,
    StructuralPlannerVariant,
    build_behavioral_structural_frontier_closure_decision,
    calculate_behavioral_structural_frontier_closure_decision_sha256,
)
from hvee.core.contracts import HveeContractError
from hvee.core.experiment_protocol import (
    ExperimentDefinition,
    ExperimentEngineKind,
    ExperimentProposal,
    ExperimentProtocolBundle,
    build_experiment_protocol_bundle,
    verify_experiment_protocol_bundle,
)
from hvee.core.failure_family_investigator import FailureFamilyObservation


ADAPTER_KEY = "behavioral_structural_frontier_closure_planner_v2_adapter"
ADAPTER_VERSION = "1.0.0"
ADAPTER_SCHEMA_VERSION = 1
ADAPTER_TYPE = "behavioral_structural_frontier_closure_planner_v2_adapter"


class BehavioralStructuralFrontierClosurePlannerV2AdapterStatus(
    str,
    Enum,
):
    READY = "ready"
    GRID_EXHAUSTED = "grid_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class BehavioralStructuralFrontierClosurePlannerV2AdapterBundle:
    payload: dict[str, object]
    experiment_protocol: ExperimentProtocolBundle | None
    sha256: str


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
        raise HveeContractError("V2 adapter payload must be canonical JSON") from exc


def _calculate_sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _jsonable(
    value: object,
) -> object:
    if isinstance(
        value,
        Enum,
    ):
        return value.value

    if is_dataclass(value) and not isinstance(
        value,
        type,
    ):
        return {
            field.name: _jsonable(
                getattr(
                    value,
                    field.name,
                )
            )
            for field in fields(value)
        }

    if isinstance(
        value,
        tuple,
    ):
        return [_jsonable(item) for item in value]

    if isinstance(
        value,
        list,
    ):
        return [_jsonable(item) for item in value]

    if isinstance(
        value,
        dict,
    ):
        return {key: _jsonable(item) for key, item in value.items()}

    if value is None or isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    raise HveeContractError("V2 planner decision contains unsupported evidence value")


def _planner_decision_payload(
    decision: StructuralFrontierPlannerDecision,
) -> dict[str, object]:
    if not isinstance(
        decision,
        StructuralFrontierPlannerDecision,
    ):
        raise HveeContractError(
            "V2 adapter requires canonical structural planner decision"
        )

    payload = _jsonable(decision)

    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("V2 planner decision payload must be an object")

    return payload


def _require_variant(
    value: object,
) -> StructuralPlannerVariant:
    if not isinstance(
        value,
        StructuralPlannerVariant,
    ):
        raise HveeContractError("V2 adapter variant must be StructuralPlannerVariant")

    return value


def _planner_observation_map(
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> dict[int, object]:
    return {item.candidate_index: item.verdict for item in observations}


def _replay_exact_v2_trajectory(
    *,
    candidate_count: int,
    maximum_evaluations: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
    variant: StructuralPlannerVariant,
) -> None:
    accepted: list[FailureFamilyObservation] = []

    for item in observations:
        if len(accepted) >= maximum_evaluations:
            raise HveeContractError(
                "V2 adapter observations cannot continue after budget terminal state"
            )

        decision = build_behavioral_structural_frontier_closure_decision(
            candidate_count=(candidate_count),
            observations=(_planner_observation_map(tuple(accepted))),
            variant=variant,
        )

        selected = decision.selected_candidate_index

        if selected is None:
            raise HveeContractError(
                "V2 adapter observations cannot continue after planner terminal state"
            )

        if item.candidate_index != selected:
            raise HveeContractError(
                "V2 adapter observation does not match deterministic planner trajectory"
            )

        accepted.append(item)


def _derive_status(
    *,
    decision: StructuralFrontierPlannerDecision,
    evaluated_count: int,
    maximum_evaluations: int,
) -> BehavioralStructuralFrontierClosurePlannerV2AdapterStatus:
    if decision.remaining_candidate_count == 0:
        return BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.GRID_EXHAUSTED

    if evaluated_count >= maximum_evaluations:
        return (
            BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.BUDGET_EXHAUSTED
        )

    if decision.selected_candidate_index is None:
        raise HveeContractError(
            "V2 planner returned no candidate before grid or budget exhaustion"
        )

    return BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.READY


def _build_ready_protocol(
    *,
    campaign_key: str,
    campaign_version: str,
    subject_sha256: str,
    axis_key: str,
    axis_version: str,
    axis_unit: str | None,
    candidate_values: tuple[
        int | float,
        ...,
    ],
    candidate_target_sha256s: tuple[
        str,
        ...,
    ],
    decision: StructuralFrontierPlannerDecision,
    decision_payload: dict[
        str,
        object,
    ],
    decision_sha256: str,
) -> ExperimentProtocolBundle:
    selected = decision.selected_candidate_index

    if selected is None:
        raise HveeContractError("ready V2 adapter state requires selected candidate")

    if selected < 0 or selected >= len(candidate_values):
        raise HveeContractError("V2 selected candidate is outside declared axis")

    target_sha256 = candidate_target_sha256s[selected]

    parameters: dict[
        str,
        object,
    ] = {
        "candidate_index": (selected),
        "axis": {
            "key": (axis_key),
            "version": (axis_version),
            "unit": (axis_unit),
            "value": (candidate_values[selected]),
        },
        "variant": (decision.variant.value),
        "action_class": (decision.action_class.value),
        "selection_phase": (decision.selection_phase),
        "planner_decision": (deepcopy(decision_payload)),
        "planner_decision_sha256": (decision_sha256),
    }

    return build_experiment_protocol_bundle(
        definition=ExperimentDefinition(
            key=ADAPTER_KEY,
            version=ADAPTER_VERSION,
            engine_kind=(ExperimentEngineKind.BEHAVIORAL),
            operation_key=(PLANNER_KEY),
            operation_version=(PLANNER_VERSION),
        ),
        campaign_key=(campaign_key),
        campaign_version=(campaign_version),
        subject_sha256=(subject_sha256),
        maximum_experiments=1,
        maximum_cost_units=1,
        proposals=[
            ExperimentProposal(
                sequence=0,
                proposal_key=(f"{PLANNER_KEY}.next"),
                target_sha256=(target_sha256),
                parameters=(parameters),
                estimated_cost_units=1,
                reason_code=(decision.action_class.value),
                source_evidence_sha256=(decision_sha256),
            )
        ],
        observations=[],
    )


def calculate_behavioral_structural_frontier_closure_planner_v2_adapter_sha256(
    payload: object,
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("V2 adapter payload must be a dictionary")

    return _calculate_sha256(payload)


def build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
    *,
    campaign_key: str,
    campaign_version: str,
    subject_sha256: str,
    axis_key: str,
    axis_version: str,
    axis_unit: str | None,
    candidate_values: (
        list[int | float]
        | tuple[
            int | float,
            ...,
        ]
    ),
    candidate_target_sha256s: (
        list[str]
        | tuple[
            str,
            ...,
        ]
    ),
    maximum_evaluations: int,
    observations: (
        list[FailureFamilyObservation]
        | tuple[
            FailureFamilyObservation,
            ...,
        ]
    ),
    variant: StructuralPlannerVariant,
) -> BehavioralStructuralFrontierClosurePlannerV2AdapterBundle:
    normalized_campaign_key = _require_string(
        campaign_key,
        field=("campaign_key"),
    )

    normalized_campaign_version = _require_string(
        campaign_version,
        field=("campaign_version"),
    )

    normalized_subject_sha256 = _require_sha256(
        subject_sha256,
        field=("subject_sha256"),
    )

    normalized_axis_key = _require_string(
        axis_key,
        field=("axis_key"),
    )

    normalized_axis_version = _require_string(
        axis_version,
        field=("axis_version"),
    )

    normalized_axis_unit = None

    if axis_unit is not None:
        normalized_axis_unit = _require_string(
            axis_unit,
            field=("axis_unit"),
        )

    normalized_variant = _require_variant(variant)

    normalized_candidates = _normalize_candidate_values(candidate_values)

    candidate_count = len(normalized_candidates)

    normalized_targets = _normalize_candidate_target_sha256s(
        candidate_target_sha256s,
        candidate_count=(candidate_count),
    )

    normalized_maximum_evaluations = _normalize_maximum_evaluations(
        maximum_evaluations,
        candidate_count=(candidate_count),
    )

    normalized_observations = _normalize_observations(
        observations=(observations),
        candidate_count=(candidate_count),
        candidate_target_sha256s=(normalized_targets),
    )

    evaluated_count = len(normalized_observations)

    if evaluated_count > normalized_maximum_evaluations:
        raise HveeContractError(
            "V2 adapter observation count exceeds maximum_evaluations"
        )

    _replay_exact_v2_trajectory(
        candidate_count=(candidate_count),
        maximum_evaluations=(normalized_maximum_evaluations),
        observations=(normalized_observations),
        variant=(normalized_variant),
    )

    decision = build_behavioral_structural_frontier_closure_decision(
        candidate_count=(candidate_count),
        observations=(_planner_observation_map(normalized_observations)),
        variant=(normalized_variant),
    )

    decision_payload = _planner_decision_payload(decision)

    decision_sha256 = calculate_behavioral_structural_frontier_closure_decision_sha256(
        decision
    )

    status = _derive_status(
        decision=(decision),
        evaluated_count=(evaluated_count),
        maximum_evaluations=(normalized_maximum_evaluations),
    )

    protocol = None

    if status is BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.READY:
        protocol = _build_ready_protocol(
            campaign_key=(normalized_campaign_key),
            campaign_version=(normalized_campaign_version),
            subject_sha256=(normalized_subject_sha256),
            axis_key=(normalized_axis_key),
            axis_version=(normalized_axis_version),
            axis_unit=(normalized_axis_unit),
            candidate_values=(normalized_candidates),
            candidate_target_sha256s=(normalized_targets),
            decision=(decision),
            decision_payload=(decision_payload),
            decision_sha256=(decision_sha256),
        )

    execution_protocol_payload = None
    execution_protocol_sha256 = None

    if protocol is not None:
        execution_protocol_payload = deepcopy(protocol.payload)

        execution_protocol_sha256 = protocol.sha256

    payload: dict[
        str,
        object,
    ] = {
        "schema_version": (ADAPTER_SCHEMA_VERSION),
        "type": (ADAPTER_TYPE),
        "adapter": {
            "key": (ADAPTER_KEY),
            "version": (ADAPTER_VERSION),
            "status": (status.value),
            "campaign_key": (normalized_campaign_key),
            "campaign_version": (normalized_campaign_version),
            "subject_sha256": (normalized_subject_sha256),
            "variant": (normalized_variant.value),
        },
        "planner": {
            "key": (PLANNER_KEY),
            "version": (PLANNER_VERSION),
            "variant": (normalized_variant.value),
        },
        "axis": {
            "key": (normalized_axis_key),
            "version": (normalized_axis_version),
            "unit": (normalized_axis_unit),
            "candidate_values": list(normalized_candidates),
            "candidate_target_sha256s": list(normalized_targets),
        },
        "budget": {
            "maximum_evaluations": (normalized_maximum_evaluations),
            "evaluated_count": (evaluated_count),
            "remaining_evaluations": (normalized_maximum_evaluations - evaluated_count),
        },
        "observations": [
            _observation_payload(item) for item in normalized_observations
        ],
        "planner_decision": (deepcopy(decision_payload)),
        "planner_decision_sha256": (decision_sha256),
        "execution_envelope": {
            "experiment_protocol": (execution_protocol_payload),
            "experiment_protocol_sha256": (execution_protocol_sha256),
        },
        "evidence_boundary": {
            "planner_mathematics_modified": (False),
            "experiment_protocol_modified": (False),
            "behavioral_engine_modified": (False),
            "planner_performance_evaluated": (False),
            "raw_content_persisted": (False),
            "proposal_suppressed_by_budget": (
                status
                is BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.BUDGET_EXHAUSTED
            ),
            "grid_exhausted": (
                status
                is BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.GRID_EXHAUSTED
            ),
            "variant_locked": (True),
        },
    }

    payload = deepcopy(payload)

    return BehavioralStructuralFrontierClosurePlannerV2AdapterBundle(
        payload=(payload),
        experiment_protocol=(protocol),
        sha256=(
            calculate_behavioral_structural_frontier_closure_planner_v2_adapter_sha256(
                payload
            )
        ),
    )


def verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        normalized_expected_sha256 = _require_sha256(
            expected_sha256,
            field=("expected_sha256"),
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        if set(payload) != {
            "schema_version",
            "type",
            "adapter",
            "planner",
            "axis",
            "budget",
            "observations",
            "planner_decision",
            "planner_decision_sha256",
            "execution_envelope",
            "evidence_boundary",
        }:
            return False

        if payload["schema_version"] != ADAPTER_SCHEMA_VERSION:
            return False

        if payload["type"] != ADAPTER_TYPE:
            return False

        adapter = payload["adapter"]

        planner = payload["planner"]

        axis = payload["axis"]

        budget = payload["budget"]

        observations_payload = payload["observations"]

        execution_envelope = payload["execution_envelope"]

        if not isinstance(
            adapter,
            dict,
        ) or set(adapter) != {
            "key",
            "version",
            "status",
            "campaign_key",
            "campaign_version",
            "subject_sha256",
            "variant",
        }:
            return False

        if adapter["key"] != ADAPTER_KEY or adapter["version"] != ADAPTER_VERSION:
            return False

        variant = StructuralPlannerVariant(adapter["variant"])

        if not isinstance(
            planner,
            dict,
        ) or planner != {
            "key": (PLANNER_KEY),
            "version": (PLANNER_VERSION),
            "variant": (variant.value),
        }:
            return False

        if not isinstance(
            axis,
            dict,
        ) or set(axis) != {
            "key",
            "version",
            "unit",
            "candidate_values",
            "candidate_target_sha256s",
        }:
            return False

        if not isinstance(
            budget,
            dict,
        ) or set(budget) != {
            "maximum_evaluations",
            "evaluated_count",
            "remaining_evaluations",
        }:
            return False

        if not isinstance(
            observations_payload,
            list,
        ):
            return False

        if not isinstance(
            execution_envelope,
            dict,
        ) or set(execution_envelope) != {
            "experiment_protocol",
            "experiment_protocol_sha256",
        }:
            return False

        observations = tuple(_parse_observation(item) for item in observations_payload)

        rebuilt = (
            build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle(
                campaign_key=(adapter["campaign_key"]),
                campaign_version=(adapter["campaign_version"]),
                subject_sha256=(adapter["subject_sha256"]),
                axis_key=(axis["key"]),
                axis_version=(axis["version"]),
                axis_unit=(axis["unit"]),
                candidate_values=(axis["candidate_values"]),
                candidate_target_sha256s=(axis["candidate_target_sha256s"]),
                maximum_evaluations=(budget["maximum_evaluations"]),
                observations=(observations),
                variant=(variant),
            )
        )

        if rebuilt.payload != payload:
            return False

        if rebuilt.sha256 != normalized_expected_sha256:
            return False

        status = BehavioralStructuralFrontierClosurePlannerV2AdapterStatus(
            adapter["status"]
        )

        if status is BehavioralStructuralFrontierClosurePlannerV2AdapterStatus.READY:
            if rebuilt.experiment_protocol is None:
                return False

            protocol_payload = execution_envelope["experiment_protocol"]

            protocol_sha256 = execution_envelope["experiment_protocol_sha256"]

            if protocol_payload is None or protocol_sha256 is None:
                return False

            if (
                verify_experiment_protocol_bundle(
                    protocol_payload,
                    protocol_sha256,
                )
                is not True
            ):
                return False

        else:
            if rebuilt.experiment_protocol is not None:
                return False

            if (
                execution_envelope["experiment_protocol"] is not None
                or execution_envelope["experiment_protocol_sha256"] is not None
            ):
                return False

        return True

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False


__all__ = [
    "ADAPTER_KEY",
    "ADAPTER_SCHEMA_VERSION",
    "ADAPTER_TYPE",
    "ADAPTER_VERSION",
    "BehavioralStructuralFrontierClosurePlannerV2AdapterBundle",
    "BehavioralStructuralFrontierClosurePlannerV2AdapterStatus",
    "build_behavioral_structural_frontier_closure_planner_v2_adapter_bundle",
    "calculate_behavioral_structural_frontier_closure_planner_v2_adapter_sha256",
    "verify_behavioral_structural_frontier_closure_planner_v2_adapter_bundle",
]
