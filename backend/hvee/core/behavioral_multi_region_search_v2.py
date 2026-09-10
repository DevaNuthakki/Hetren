from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
    build_failure_family_boundary_set_bundle,
)


BEHAVIORAL_MULTI_REGION_SEARCH_V2_SCHEMA_VERSION = 1


class BehavioralMultiRegionSearchV2Status(
    str,
    Enum,
):
    READY = "ready"
    BUDGET_EXHAUSTED = "budget_exhausted"
    GRID_EXHAUSTED = "grid_exhausted"


class BehavioralMultiRegionSearchV2ProposalReason(
    str,
    Enum,
):
    INITIAL_CENTER = "initial_center"
    GUARANTEED_BOUNDARY_CLOSURE = "guaranteed_boundary_closure"
    EXPLORE_FARTHEST_UNOBSERVED = "explore_farthest_unobserved"


@dataclass(frozen=True)
class BehavioralMultiRegionSearchV2Bundle:
    payload: dict[
        str,
        object,
    ]
    sha256: str


@dataclass(frozen=True)
class _Proposal:
    candidate_index: int
    reason: BehavioralMultiRegionSearchV2ProposalReason


def _canonical_json_bytes(
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
            "multi-region V2 evidence must " "be canonical JSON"
        ) from exc


def _canonical_sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def calculate_behavioral_multi_region_search_v2_sha256(
    payload: object,
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("multi-region V2 payload " "must be an object")

    return _canonical_sha256(payload)


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
    ):
        raise HveeContractError(f"{field} must be " "a non-empty string")

    return value


def _normalize_candidate_values(
    values: object,
) -> tuple[
    float,
    ...,
]:
    if (
        not isinstance(
            values,
            (
                list,
                tuple,
            ),
        )
        or len(values) < 2
    ):
        raise HveeContractError(
            "multi-region V2 candidate values " "require at least two ordered values"
        )

    normalized = []

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
            raise HveeContractError(
                "multi-region V2 candidate values " "must be numeric"
            )

        numeric = float(value)

        if not math.isfinite(numeric):
            raise HveeContractError(
                "multi-region V2 candidate values " "must be finite"
            )

        normalized.append(numeric)

    if any(
        upper <= lower
        for lower, upper in zip(
            normalized,
            normalized[1:],
        )
    ):
        raise HveeContractError(
            "multi-region V2 candidate values " "must be strictly increasing"
        )

    return tuple(normalized)


def _normalize_invariants(
    value: object,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        value,
        dict,
    ):
        raise HveeContractError(
            "multi-region V2 invariant " "parameters must be an object"
        )

    normalized = {}

    for key, item in value.items():
        normalized_key = _require_string(
            key,
            field=("multi-region V2 " "invariant key"),
        )

        normalized[normalized_key] = item

    _canonical_json_bytes(normalized)

    return normalized


def _normalize_observations(
    *,
    observations: object,
    candidate_count: int,
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
    ):
        raise HveeContractError("multi-region V2 observations " "must be a sequence")

    normalized = tuple(observations)

    seen_indices = set()

    for ordinal, item in enumerate(
        normalized,
        start=1,
    ):
        if not isinstance(
            item,
            FailureFamilyObservation,
        ):
            raise HveeContractError(
                "multi-region V2 observations " "must use FailureFamilyObservation"
            )

        if item.source != FailureFamilyObservationSource.EVALUATION:
            raise HveeContractError(
                "multi-region V2 global search " "accepts evaluation observations only"
            )

        if item.sequence != ordinal:
            raise HveeContractError(
                "multi-region V2 observation "
                "sequence must be contiguous "
                "and one-based"
            )

        if (
            isinstance(
                item.candidate_index,
                bool,
            )
            or not isinstance(
                item.candidate_index,
                int,
            )
            or item.candidate_index < 0
            or item.candidate_index >= candidate_count
        ):
            raise HveeContractError(
                "multi-region V2 observation " "candidate index is invalid"
            )

        if item.candidate_index in seen_indices:
            raise HveeContractError(
                "multi-region V2 observations " "cannot repeat candidates"
            )

        if item.verdict not in {
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        }:
            raise HveeContractError(
                "multi-region V2 observation " "verdict must be PASS or FAIL"
            )

        if item.cost_units != 1:
            raise HveeContractError(
                "multi-region V2 global " "observation cost must equal one"
            )

        seen_indices.add(item.candidate_index)

    return normalized


def _observed_map(
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> dict[
    int,
    FailureFamilyObservation,
]:
    return {item.candidate_index: item for item in observations}


def _guaranteed_boundary_closure_candidate(
    *,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> int | None:
    if len(observations) < 2:
        return None

    ordered = sorted(
        observations,
        key=lambda item: (item.candidate_index),
    )

    candidates = []

    for lower, upper in zip(
        ordered,
        ordered[1:],
    ):
        if lower.verdict == upper.verdict:
            continue

        if upper.candidate_index - lower.candidate_index != 2:
            continue

        candidates.append(lower.candidate_index + 1)

    if not candidates:
        return None

    return min(candidates)


def _farthest_unobserved_candidate(
    *,
    candidate_count: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> int | None:
    observed = set(item.candidate_index for item in observations)

    unobserved = [index for index in range(candidate_count) if index not in observed]

    if not unobserved:
        return None

    if not observed:
        return candidate_count // 2

    ranked = []

    for index in unobserved:
        minimum_distance = min(
            abs(index - observed_index) for observed_index in observed
        )

        ranked.append(
            (
                -minimum_distance,
                index,
            )
        )

    return min(ranked)[1]


def _derive_proposal(
    *,
    candidate_count: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
    previous_proposal_reason: BehavioralMultiRegionSearchV2ProposalReason | None,
) -> _Proposal | None:
    if not observations:
        return _Proposal(
            candidate_index=(candidate_count // 2),
            reason=(BehavioralMultiRegionSearchV2ProposalReason.INITIAL_CENTER),
        )

    closure_candidate = _guaranteed_boundary_closure_candidate(
        observations=(observations),
    )

    if (
        closure_candidate is not None
        and previous_proposal_reason
        != BehavioralMultiRegionSearchV2ProposalReason.GUARANTEED_BOUNDARY_CLOSURE
    ):
        return _Proposal(
            candidate_index=(closure_candidate),
            reason=(
                BehavioralMultiRegionSearchV2ProposalReason.GUARANTEED_BOUNDARY_CLOSURE
            ),
        )

    coverage_candidate = _farthest_unobserved_candidate(
        candidate_count=(candidate_count),
        observations=(observations),
    )

    if coverage_candidate is None:
        return None

    return _Proposal(
        candidate_index=(coverage_candidate),
        reason=(
            BehavioralMultiRegionSearchV2ProposalReason.EXPLORE_FARTHEST_UNOBSERVED
        ),
    )


def _derive_status_and_proposal(
    *,
    candidate_count: int,
    maximum_evaluations: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
    previous_proposal_reason: BehavioralMultiRegionSearchV2ProposalReason | None,
) -> tuple[
    BehavioralMultiRegionSearchV2Status,
    _Proposal | None,
]:
    evaluated_count = len(observations)

    if evaluated_count == candidate_count:
        return (
            BehavioralMultiRegionSearchV2Status.GRID_EXHAUSTED,
            None,
        )

    if evaluated_count >= maximum_evaluations:
        return (
            BehavioralMultiRegionSearchV2Status.BUDGET_EXHAUSTED,
            None,
        )

    proposal = _derive_proposal(
        candidate_count=(candidate_count),
        observations=(observations),
        previous_proposal_reason=(previous_proposal_reason),
    )

    if proposal is None:
        return (
            BehavioralMultiRegionSearchV2Status.GRID_EXHAUSTED,
            None,
        )

    return (
        BehavioralMultiRegionSearchV2Status.READY,
        proposal,
    )


def _observation_payload(
    item: FailureFamilyObservation,
) -> dict[
    str,
    object,
]:
    return {
        "sequence": (item.sequence),
        "candidate_index": (item.candidate_index),
        "verdict": (item.verdict.value),
        "source": (item.source.value),
        "cost_units": (item.cost_units),
        "scenario_sha256": (item.scenario_sha256),
        "result_provenance_sha256": (item.result_provenance_sha256),
        "observation_evidence_sha256": (item.observation_evidence_sha256),
        "decision_evidence_sha256": (item.decision_evidence_sha256),
        "counterexample_evidence_sha256": (item.counterexample_evidence_sha256),
    }


def build_behavioral_multi_region_search_v2_bundle(
    *,
    evaluation_type: str,
    search_key: str,
    search_version: str,
    boundary_key: str,
    boundary_version: str,
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
    invariant_parameters: dict[
        str,
        object,
    ],
    maximum_evaluations: int,
    observations: (
        list[FailureFamilyObservation]
        | tuple[
            FailureFamilyObservation,
            ...,
        ]
    ),
) -> BehavioralMultiRegionSearchV2Bundle:
    normalized_evaluation_type = _require_string(
        evaluation_type,
        field="evaluation type",
    )

    normalized_search_key = _require_string(
        search_key,
        field="search key",
    )

    normalized_search_version = _require_string(
        search_version,
        field="search version",
    )

    normalized_boundary_key = _require_string(
        boundary_key,
        field="boundary key",
    )

    normalized_boundary_version = _require_string(
        boundary_version,
        field="boundary version",
    )

    normalized_axis_key = _require_string(
        axis_key,
        field="axis key",
    )

    normalized_axis_version = _require_string(
        axis_version,
        field="axis version",
    )

    normalized_axis_unit = None

    if axis_unit is not None:
        normalized_axis_unit = _require_string(
            axis_unit,
            field="axis unit",
        )

    normalized_candidates = _normalize_candidate_values(candidate_values)

    normalized_invariants = _normalize_invariants(invariant_parameters)

    candidate_count = len(normalized_candidates)

    if (
        isinstance(
            maximum_evaluations,
            bool,
        )
        or not isinstance(
            maximum_evaluations,
            int,
        )
        or maximum_evaluations < 1
        or maximum_evaluations > candidate_count
    ):
        raise HveeContractError(
            "multi-region V2 maximum evaluations "
            "must be between one and candidate count"
        )

    normalized_observations = _normalize_observations(
        observations=(observations),
        candidate_count=(candidate_count),
    )

    accepted = []

    previous_proposal_reason = None

    for item in normalized_observations:
        (
            status,
            proposal,
        ) = _derive_status_and_proposal(
            candidate_count=(candidate_count),
            maximum_evaluations=(maximum_evaluations),
            observations=tuple(accepted),
            previous_proposal_reason=(previous_proposal_reason),
        )

        if status != BehavioralMultiRegionSearchV2Status.READY or proposal is None:
            raise HveeContractError(
                "multi-region V2 observations " "cannot continue after terminal state"
            )

        if item.candidate_index != proposal.candidate_index:
            raise HveeContractError(
                "multi-region V2 observation "
                "does not match deterministic "
                "proposal trajectory"
            )

        accepted.append(item)

        previous_proposal_reason = proposal.reason

    (
        status,
        proposal,
    ) = _derive_status_and_proposal(
        candidate_count=(candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(normalized_observations),
        previous_proposal_reason=(previous_proposal_reason),
    )

    boundary_set = build_failure_family_boundary_set_bundle(
        evaluation_type=(normalized_evaluation_type),
        boundary_key=(normalized_boundary_key),
        boundary_version=(normalized_boundary_version),
        search_key=(normalized_search_key),
        search_version=(normalized_search_version),
        axis_key=(normalized_axis_key),
        axis_version=(normalized_axis_version),
        axis_unit=(normalized_axis_unit),
        candidate_values=(normalized_candidates),
        invariant_parameters=(normalized_invariants),
        observations=(normalized_observations),
    )

    proposal_payload = None

    if proposal is not None:
        proposal_payload = {
            "candidate_index": (proposal.candidate_index),
            "axis_value": (normalized_candidates[proposal.candidate_index]),
            "reason": (proposal.reason.value),
        }

    exact_regions = boundary_set.payload["failure_regions"]["exactly_characterized"]

    payload: dict[
        str,
        object,
    ] = {
        "schema_version": (BEHAVIORAL_MULTI_REGION_SEARCH_V2_SCHEMA_VERSION),
        "type": ("behavioral_multi_region_search_v2"),
        "evaluation_type": (normalized_evaluation_type),
        "search": {
            "key": (normalized_search_key),
            "version": (normalized_search_version),
            "status": (status.value),
            "policy": ("coverage_with_nonchaining_guaranteed_boundary_closure"),
        },
        "boundary_contract": {
            "key": (normalized_boundary_key),
            "version": (normalized_boundary_version),
        },
        "axis": {
            "key": (normalized_axis_key),
            "version": (normalized_axis_version),
            "unit": (normalized_axis_unit),
            "candidate_values": list(normalized_candidates),
        },
        "invariants": {
            "parameters": (normalized_invariants),
            "sha256": (_canonical_sha256(normalized_invariants)),
        },
        "budget": {
            "maximum_evaluations": (maximum_evaluations),
            "evaluated_count": (len(normalized_observations)),
            "remaining_evaluations": (
                maximum_evaluations - len(normalized_observations)
            ),
        },
        "observations": [
            _observation_payload(item) for item in normalized_observations
        ],
        "outcome": {
            "localized_boundary_count": (boundary_set.payload["boundaries"]["count"]),
            "exact_failure_region_count": (len(exact_regions)),
            "boundary_set_sha256": (boundary_set.sha256),
            "next_proposal": (proposal_payload),
        },
        "evidence_boundary": {
            "design_policy_precommitted": (True),
            "parameter_free_policy": (True),
            "tuned_explore_exploit_ratio": (False),
            "tuned_threshold": (False),
            "one_step_boundary_closure_priority": (True),
            "maximin_global_coverage": (True),
            "wide_opposing_interval_automatic_priority": (False),
            "maximum_consecutive_boundary_closures": (1),
            "closure_starvation_prevention": (True),
            "coverage_required_after_boundary_closure": (True),
            "single_boundary_component_reused": (True),
            "multi_boundary_representation_reused": (True),
            "incident_policy_changed": (False),
            "search_execution_performed": (bool(normalized_observations)),
            "execution_evidence_verified": (False),
            "run05_v2_development_evaluation_performed": (False),
            "fresh_qualification_performed": (False),
            "behavioral_performance_qualified": (False),
            "real_ai_generalization_established": (False),
            "model_inference_performed": (False),
        },
    }

    return BehavioralMultiRegionSearchV2Bundle(
        payload=payload,
        sha256=(calculate_behavioral_multi_region_search_v2_sha256(payload)),
    )


def verify_behavioral_multi_region_search_v2_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        if (
            not isinstance(
                expected_sha256,
                str,
            )
            or len(expected_sha256) != 64
        ):
            return False

        int(
            expected_sha256,
            16,
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        return (
            calculate_behavioral_multi_region_search_v2_sha256(payload)
            == expected_sha256.lower()
        )

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False
