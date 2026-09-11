from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import re

from hvee.core.behavioral_multi_objective_uncertainty_aware_planner import (
    PLANNER_KEY,
    PLANNER_VERSION,
    MultiObjectivePlannerDecision,
    build_behavioral_multi_objective_uncertainty_aware_decision,
)
from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.experiment_protocol import (
    ExperimentDefinition,
    ExperimentEngineKind,
    ExperimentProposal,
    ExperimentProtocolBundle,
    build_experiment_protocol_bundle,
    verify_experiment_protocol_bundle,
)
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
)


ADAPTER_SCHEMA_VERSION = 1
ADAPTER_TYPE = "behavioral_multi_objective_planner_adapter"
ADAPTER_KEY = "behavioral_multi_objective_planner_adapter"
ADAPTER_VERSION = "1.0.0"

OPERATION_KEY = "multi_objective_planner"
OPERATION_VERSION = "1.0.0"
PROPOSAL_KEY = "multi_objective_planner.next"

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class BehavioralMultiObjectivePlannerAdapterStatus(str, Enum):
    READY = "ready"
    GRID_EXHAUSTED = "grid_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class BehavioralMultiObjectivePlannerAdapterBundle:
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
        raise HveeContractError(
            "adapter value is not canonically JSON serializable"
        ) from exc


def _calculate_sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def calculate_behavioral_multi_objective_planner_adapter_sha256(
    payload: object,
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("adapter payload must be a dictionary")

    return _calculate_sha256(payload)


def _require_string(
    value: object,
    *,
    field: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value.strip() != value
    ):
        raise HveeContractError(f"{field} must be a non-empty trimmed string")

    return value


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or _SHA256_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(f"{field} must be a lowercase SHA-256")

    return value


def _normalize_candidate_values(
    values: object,
) -> tuple[
    int | float,
    ...,
]:
    if not isinstance(
        values,
        (
            list,
            tuple,
        ),
    ):
        raise HveeContractError("candidate_values must be a list or tuple")

    if len(values) < 2:
        raise HveeContractError("candidate_values require at least two candidates")

    normalized: list[int | float] = []

    for value in values:
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
            raise HveeContractError("candidate values must be numeric and not bool")

        if isinstance(
            value,
            float,
        ) and not math.isfinite(value):
            raise HveeContractError("candidate values must be finite")

        normalized.append(value)

    if len(set(normalized)) != len(normalized):
        raise HveeContractError("candidate values must be unique")

    return tuple(normalized)


def _normalize_candidate_target_sha256s(
    values: object,
    *,
    candidate_count: int,
) -> tuple[
    str,
    ...,
]:
    if not isinstance(
        values,
        (
            list,
            tuple,
        ),
    ):
        raise HveeContractError("candidate_target_sha256s must be a list or tuple")

    if len(values) != candidate_count:
        raise HveeContractError("candidate target SHA count must equal candidate count")

    normalized = tuple(
        _require_sha256(
            value,
            field=("candidate target SHA-256"),
        )
        for value in values
    )

    if len(set(normalized)) != len(normalized):
        raise HveeContractError("candidate target SHA-256 values must be unique")

    return normalized


def _normalize_maximum_evaluations(
    value: object,
    *,
    candidate_count: int,
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
        or value < 1
        or value > candidate_count
    ):
        raise HveeContractError(
            "maximum_evaluations must be between one and candidate count"
        )

    return value


def _normalize_observations(
    *,
    observations: object,
    candidate_count: int,
    candidate_target_sha256s: tuple[
        str,
        ...,
    ],
) -> tuple[
    FailureFamilyObservation,
    ...,
]:
    if not isinstance(
        observations,
        (
            list,
            tuple,
        ),
    ) or not all(
        isinstance(
            item,
            FailureFamilyObservation,
        )
        for item in observations
    ):
        raise HveeContractError(
            "adapter observations must contain canonical FailureFamilyObservation records"
        )

    normalized = tuple(observations)

    candidate_indices: list[int] = []

    scenario_sha256s: list[str] = []

    for expected_sequence, item in enumerate(
        normalized,
        start=1,
    ):
        if item.source is not FailureFamilyObservationSource.EVALUATION:
            raise HveeContractError("adapter v1 accepts evaluation observations only")

        if not isinstance(
            item.verdict,
            DecisionVerdict,
        ) or item.verdict not in (
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        ):
            raise HveeContractError(
                "adapter observations require strict DecisionVerdict PASS or FAIL"
            )

        if item.cost_units != 1:
            raise HveeContractError(
                "adapter evaluation observations cost exactly one unit"
            )

        if item.sequence != expected_sequence:
            raise HveeContractError(
                "adapter evaluation sequences must be contiguous starting at one"
            )

        candidate_index = item.candidate_index

        if (
            isinstance(
                candidate_index,
                bool,
            )
            or not isinstance(
                candidate_index,
                int,
            )
            or candidate_index < 0
            or candidate_index >= candidate_count
        ):
            raise HveeContractError(
                "adapter observation candidate is outside candidate grid"
            )

        expected_scenario_sha = candidate_target_sha256s[candidate_index]

        if item.scenario_sha256 != expected_scenario_sha:
            raise HveeContractError(
                "adapter observation scenario SHA does not match aligned candidate target SHA"
            )

        candidate_indices.append(candidate_index)

        scenario_sha256s.append(item.scenario_sha256)

    if len(candidate_indices) != len(set(candidate_indices)):
        raise HveeContractError(
            "adapter observations require distinct candidate indices"
        )

    if len(scenario_sha256s) != len(set(scenario_sha256s)):
        raise HveeContractError(
            "adapter observations require distinct scenario SHA-256 values"
        )

    return normalized


def _observation_payload(
    observation: FailureFamilyObservation,
) -> dict[
    str,
    object,
]:
    return {
        "sequence": (observation.sequence),
        "candidate_index": (observation.candidate_index),
        "verdict": (observation.verdict.value),
        "source": (observation.source.value),
        "cost_units": (observation.cost_units),
        "scenario_sha256": (observation.scenario_sha256),
        "result_provenance_sha256": (observation.result_provenance_sha256),
        "observation_evidence_sha256": (observation.observation_evidence_sha256),
        "decision_evidence_sha256": (observation.decision_evidence_sha256),
        "counterexample_evidence_sha256": (observation.counterexample_evidence_sha256),
    }


def _parse_observation(
    value: object,
) -> FailureFamilyObservation:
    expected_fields = {
        "sequence",
        "candidate_index",
        "verdict",
        "source",
        "cost_units",
        "scenario_sha256",
        "result_provenance_sha256",
        "observation_evidence_sha256",
        "decision_evidence_sha256",
        "counterexample_evidence_sha256",
    }

    if (
        not isinstance(
            value,
            dict,
        )
        or set(value) != expected_fields
    ):
        raise HveeContractError("stored adapter observation is invalid")

    try:
        verdict = DecisionVerdict(value["verdict"])

        source = FailureFamilyObservationSource(value["source"])

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError("stored adapter observation enum is invalid") from exc

    return FailureFamilyObservation(
        sequence=(value["sequence"]),
        candidate_index=(value["candidate_index"]),
        verdict=verdict,
        source=source,
        cost_units=(value["cost_units"]),
        scenario_sha256=(value["scenario_sha256"]),
        result_provenance_sha256=(value["result_provenance_sha256"]),
        observation_evidence_sha256=(value["observation_evidence_sha256"]),
        decision_evidence_sha256=(value["decision_evidence_sha256"]),
        counterexample_evidence_sha256=(value["counterexample_evidence_sha256"]),
    )


def _candidate_record_payload(
    record,
) -> dict[
    str,
    object,
]:
    return {
        "candidate_index": (record.candidate_index),
        "coverage_gain": (record.coverage_gain),
        "guaranteed_boundary_ambiguity_reduction": (
            record.guaranteed_boundary_ambiguity_reduction
        ),
        "worst_case_boundary_ambiguity_expansion": (
            record.worst_case_boundary_ambiguity_expansion
        ),
        "outcome_boundary_mass_separation": (record.outcome_boundary_mass_separation),
        "outcome_interval_symmetric_difference_count": (
            record.outcome_interval_symmetric_difference_count
        ),
        "pass_boundary_ambiguity": (record.pass_boundary_ambiguity),
        "fail_boundary_ambiguity": (record.fail_boundary_ambiguity),
    }


def _planner_decision_payload(
    decision: MultiObjectivePlannerDecision,
) -> dict[
    str,
    object,
]:
    return {
        "candidate_count": (decision.candidate_count),
        "observed_count": (decision.observed_count),
        "remaining_candidate_count": (decision.remaining_candidate_count),
        "selected_candidate_index": (decision.selected_candidate_index),
        "selection_reason": (decision.selection_reason.value),
        "primary_frontier_candidate_indices": list(
            decision.primary_frontier_candidate_indices
        ),
        "uncertainty_frontier_candidate_indices": list(
            decision.uncertainty_frontier_candidate_indices
        ),
        "unresolved_action_ambiguity": (decision.unresolved_action_ambiguity),
        "candidate_records": [
            _candidate_record_payload(record) for record in decision.candidate_records
        ],
    }


def _derive_status(
    *,
    decision: MultiObjectivePlannerDecision,
    evaluated_count: int,
    maximum_evaluations: int,
) -> BehavioralMultiObjectivePlannerAdapterStatus:
    if decision.terminal:
        return BehavioralMultiObjectivePlannerAdapterStatus.GRID_EXHAUSTED

    if evaluated_count >= maximum_evaluations:
        return BehavioralMultiObjectivePlannerAdapterStatus.BUDGET_EXHAUSTED

    return BehavioralMultiObjectivePlannerAdapterStatus.READY


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
    decision: MultiObjectivePlannerDecision,
    decision_payload: dict[
        str,
        object,
    ],
    decision_sha256: str,
) -> ExperimentProtocolBundle:
    selected_candidate_index = decision.selected_candidate_index

    if selected_candidate_index is None:
        raise HveeContractError("READY adapter decision requires a selected candidate")

    proposal = ExperimentProposal(
        sequence=0,
        proposal_key=(PROPOSAL_KEY),
        target_sha256=(candidate_target_sha256s[selected_candidate_index]),
        parameters={
            "planner_contract": {
                "key": (PLANNER_KEY),
                "version": (PLANNER_VERSION),
            },
            "planner_decision": (deepcopy(decision_payload)),
            "planner_decision_sha256": (decision_sha256),
            "selected_candidate_value": (candidate_values[selected_candidate_index]),
            "axis": {
                "key": (axis_key),
                "version": (axis_version),
                "unit": (axis_unit),
            },
        },
        estimated_cost_units=1,
        reason_code=(decision.selection_reason.value),
        source_evidence_sha256=(decision_sha256),
    )

    protocol = build_experiment_protocol_bundle(
        definition=ExperimentDefinition(
            key=(ADAPTER_KEY),
            version=(ADAPTER_VERSION),
            engine_kind=(ExperimentEngineKind.BEHAVIORAL),
            operation_key=(OPERATION_KEY),
            operation_version=(OPERATION_VERSION),
        ),
        campaign_key=(campaign_key),
        campaign_version=(campaign_version),
        subject_sha256=(subject_sha256),
        maximum_experiments=1,
        maximum_cost_units=1,
        proposals=[proposal],
        observations=[],
    )

    if (
        verify_experiment_protocol_bundle(
            protocol.payload,
            protocol.sha256,
        )
        is not True
    ):
        raise HveeContractError(
            "rebuilt adapter experiment protocol failed verification"
        )

    return protocol


def build_behavioral_multi_objective_planner_adapter_bundle(
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
) -> BehavioralMultiObjectivePlannerAdapterBundle:
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
        raise HveeContractError("adapter observation count exceeds maximum_evaluations")

    planner_observations = {
        item.candidate_index: (item.verdict) for item in normalized_observations
    }

    decision = build_behavioral_multi_objective_uncertainty_aware_decision(
        candidate_count=(candidate_count),
        observations=(planner_observations),
    )

    decision_payload = _planner_decision_payload(decision)

    decision_sha256 = _calculate_sha256(decision_payload)

    status = _derive_status(
        decision=decision,
        evaluated_count=(evaluated_count),
        maximum_evaluations=(normalized_maximum_evaluations),
    )

    protocol = None

    if status is BehavioralMultiObjectivePlannerAdapterStatus.READY:
        protocol = _build_ready_protocol(
            campaign_key=(normalized_campaign_key),
            campaign_version=(normalized_campaign_version),
            subject_sha256=(normalized_subject_sha256),
            axis_key=(normalized_axis_key),
            axis_version=(normalized_axis_version),
            axis_unit=(normalized_axis_unit),
            candidate_values=(normalized_candidates),
            candidate_target_sha256s=(normalized_targets),
            decision=decision,
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
        },
        "planner": {
            "key": (PLANNER_KEY),
            "version": (PLANNER_VERSION),
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
                status is BehavioralMultiObjectivePlannerAdapterStatus.BUDGET_EXHAUSTED
            ),
            "grid_exhausted": (
                status is BehavioralMultiObjectivePlannerAdapterStatus.GRID_EXHAUSTED
            ),
            "unresolved_action_ambiguity": (decision.unresolved_action_ambiguity),
        },
    }

    payload = deepcopy(payload)

    return BehavioralMultiObjectivePlannerAdapterBundle(
        payload=payload,
        experiment_protocol=(protocol),
        sha256=(calculate_behavioral_multi_objective_planner_adapter_sha256(payload)),
    )


def verify_behavioral_multi_objective_planner_adapter_bundle(
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

        expected_fields = {
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
        }

        if set(payload) != expected_fields:
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
        }:
            return False

        if adapter["key"] != ADAPTER_KEY or adapter["version"] != ADAPTER_VERSION:
            return False

        if not isinstance(
            planner,
            dict,
        ) or planner != {
            "key": (PLANNER_KEY),
            "version": (PLANNER_VERSION),
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

        rebuilt = build_behavioral_multi_objective_planner_adapter_bundle(
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
        )

        if rebuilt.payload != payload:
            return False

        if rebuilt.sha256 != normalized_expected_sha256:
            return False

        status = BehavioralMultiObjectivePlannerAdapterStatus(adapter["status"])

        if status is BehavioralMultiObjectivePlannerAdapterStatus.READY:
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
    "BehavioralMultiObjectivePlannerAdapterBundle",
    "BehavioralMultiObjectivePlannerAdapterStatus",
    "build_behavioral_multi_objective_planner_adapter_bundle",
    "calculate_behavioral_multi_objective_planner_adapter_sha256",
    "verify_behavioral_multi_objective_planner_adapter_bundle",
]
