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


BEHAVIORAL_MULTI_REGION_SEARCH_V2_1_SCHEMA_VERSION = 1

_POLICY_NAME = "BOUNDED_BOUNDARY_TRANSACTION_WITH_COVERAGE_RESET"

_ELIGIBLE_OPPOSING_INTERVAL_WIDTHS = (
    2,
    3,
    4,
)

_MAXIMUM_BOUNDARY_TRANSACTION_ACTIONS = 2

_EVIDENCE_BOUNDARY = {
    "development_evidence_only": True,
    "behavioral_performance_qualified": False,
    "real_ai_generalization_established": False,
    "production_release_authority": False,
    "hidden_pattern_used": False,
    "future_oracle_verdict_used": False,
    "model_inference_performed": False,
    "asr_execution_performed": False,
    "incident_policy_modified": False,
}


class BehavioralMultiRegionSearchV21Status(
    str,
    Enum,
):
    READY = "ready"
    BUDGET_EXHAUSTED = "budget_exhausted"
    GRID_EXHAUSTED = "grid_exhausted"


class BehavioralMultiRegionSearchV21ProposalReason(
    str,
    Enum,
):
    INITIAL_CENTER = "initial_center"
    BOUNDARY_TRANSACTION_REFINEMENT = "boundary_transaction_refinement"
    COVERAGE_RESET = "coverage_reset"
    MAXIMIN_COVERAGE = "maximin_coverage"


class BehavioralMultiRegionSearchV21PlannerState(
    str,
    Enum,
):
    NORMAL = "normal"
    BOUNDARY_TRANSACTION_ACTIVE = "boundary_transaction_active"
    COVERAGE_RESET_REQUIRED = "coverage_reset_required"


@dataclass(
    frozen=True,
)
class _BoundaryTransaction:
    lower: int
    upper: int
    actions_used: int

    def __post_init__(
        self,
    ) -> None:
        if (
            isinstance(
                self.lower,
                bool,
            )
            or not isinstance(
                self.lower,
                int,
            )
            or isinstance(
                self.upper,
                bool,
            )
            or not isinstance(
                self.upper,
                int,
            )
            or self.lower < 0
            or self.upper <= self.lower
        ):
            raise HveeContractError("V2.1 boundary transaction interval is invalid")

        if (
            isinstance(
                self.actions_used,
                bool,
            )
            or not isinstance(
                self.actions_used,
                int,
            )
            or self.actions_used < 0
            or self.actions_used > _MAXIMUM_BOUNDARY_TRANSACTION_ACTIONS
        ):
            raise HveeContractError("V2.1 boundary transaction action count is invalid")


@dataclass(
    frozen=True,
)
class _PlannerState:
    state: BehavioralMultiRegionSearchV21PlannerState
    transaction: _BoundaryTransaction | None = None

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.state,
            BehavioralMultiRegionSearchV21PlannerState,
        ):
            raise HveeContractError("V2.1 planner state is invalid")

        requires_transaction = (
            self.state
            == BehavioralMultiRegionSearchV21PlannerState.BOUNDARY_TRANSACTION_ACTIVE
        )

        if requires_transaction != (self.transaction is not None):
            raise HveeContractError("V2.1 planner transaction state is inconsistent")


@dataclass(
    frozen=True,
)
class _Proposal:
    candidate_index: int
    reason: BehavioralMultiRegionSearchV21ProposalReason

    def __post_init__(
        self,
    ) -> None:
        if (
            isinstance(
                self.candidate_index,
                bool,
            )
            or not isinstance(
                self.candidate_index,
                int,
            )
            or self.candidate_index < 0
        ):
            raise HveeContractError("V2.1 proposal candidate index is invalid")

        if not isinstance(
            self.reason,
            BehavioralMultiRegionSearchV21ProposalReason,
        ):
            raise HveeContractError("V2.1 proposal reason is invalid")


@dataclass(
    frozen=True,
)
class BehavioralMultiRegionSearchV21Bundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(
        self,
    ) -> None:
        if (
            not isinstance(
                self.sha256,
                str,
            )
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise HveeContractError("V2.1 bundle SHA-256 is invalid")

        if self.sha256 != calculate_behavioral_multi_region_search_v2_1_sha256(
            self.payload
        ):
            raise HveeContractError("V2.1 bundle SHA-256 does not match payload")


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        return json.loads(encoded)

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError(f"{name} must contain deterministic JSON") from exc


def _canonical_sha256(
    value: object,
) -> str:
    canonical = _canonical_json_value(
        value,
        name="V2.1 SHA-256 input",
    )

    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def calculate_behavioral_multi_region_search_v2_1_sha256(
    payload: object,
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError("V2.1 payload must be an object")

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
        or not value.strip()
    ):
        raise HveeContractError(f"V2.1 {field} must be a non-empty string")

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
        or not values
    ):
        raise HveeContractError("V2.1 candidate values must be a non-empty sequence")

    normalized: list[float] = []

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
            raise HveeContractError("V2.1 candidate values must be numeric")

        numeric = float(value)

        if not math.isfinite(numeric):
            raise HveeContractError("V2.1 candidate values must be finite")

        normalized.append(numeric)

    if any(
        upper <= lower
        for lower, upper in zip(
            normalized,
            normalized[1:],
        )
    ):
        raise HveeContractError("V2.1 candidate values must be strictly increasing")

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
        raise HveeContractError("V2.1 invariant parameters must be an object")

    canonical = _canonical_json_value(
        value,
        name="V2.1 invariant parameters",
    )

    if not isinstance(
        canonical,
        dict,
    ):
        raise HveeContractError("V2.1 invariant parameters must remain an object")

    if any(
        not isinstance(
            key,
            str,
        )
        or not key
        for key in canonical
    ):
        raise HveeContractError(
            "V2.1 invariant parameter keys must be non-empty strings"
        )

    return canonical


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
        raise HveeContractError("V2.1 observations must be a sequence")

    normalized: list[FailureFamilyObservation] = []

    seen_indices: set[int] = set()

    for expected_sequence, item in enumerate(
        observations,
        start=1,
    ):
        if not isinstance(
            item,
            FailureFamilyObservation,
        ):
            raise HveeContractError(
                "V2.1 observations require failure-family observations"
            )

        if item.source != FailureFamilyObservationSource.EVALUATION:
            raise HveeContractError(
                "V2.1 global search accepts evaluation observations only"
            )

        if item.sequence != expected_sequence:
            raise HveeContractError("V2.1 observation sequence must be contiguous")

        if item.candidate_index >= candidate_count:
            raise HveeContractError("V2.1 observation candidate index is outside grid")

        if item.candidate_index in seen_indices:
            raise HveeContractError("V2.1 observations cannot repeat a candidate")

        seen_indices.add(item.candidate_index)

        normalized.append(item)

    return tuple(normalized)


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


def _opposing_intervals(
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> tuple[
    tuple[
        int,
        int,
    ],
    ...,
]:
    observed = _observed_map(observations)

    ordered = sorted(observed)

    return tuple(
        (
            lower,
            upper,
        )
        for lower, upper in zip(
            ordered,
            ordered[1:],
        )
        if (upper - lower > 1 and observed[lower].verdict != observed[upper].verdict)
    )


def _localization_depth(
    width: int,
) -> int:
    if (
        isinstance(
            width,
            bool,
        )
        or not isinstance(
            width,
            int,
        )
        or width < 1
    ):
        raise HveeContractError("V2.1 opposing interval width is invalid")

    if width == 1:
        return 0

    return math.ceil(math.log2(width))


def _select_bounded_opportunity(
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> _BoundaryTransaction | None:
    candidates = [
        (
            _localization_depth(upper - lower),
            upper - lower,
            lower,
            upper,
        )
        for lower, upper in _opposing_intervals(observations)
        if (upper - lower in _ELIGIBLE_OPPOSING_INTERVAL_WIDTHS)
    ]

    if not candidates:
        return None

    (
        _depth,
        _width,
        lower,
        upper,
    ) = min(candidates)

    return _BoundaryTransaction(
        lower=lower,
        upper=upper,
        actions_used=0,
    )


def _farthest_unobserved_candidate(
    *,
    candidate_count: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> int | None:
    observed = {item.candidate_index for item in observations}

    unobserved = [index for index in range(candidate_count) if index not in observed]

    if not unobserved:
        return None

    if not observed:
        return candidate_count // 2

    ranked = []

    for candidate_index in unobserved:
        nearest_distance = min(
            abs(candidate_index - observed_index) for observed_index in observed
        )

        ranked.append(
            (
                -nearest_distance,
                candidate_index,
            )
        )

    (
        _negative_distance,
        selected,
    ) = min(ranked)

    return selected


def _status(
    *,
    candidate_count: int,
    maximum_evaluations: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> BehavioralMultiRegionSearchV21Status:
    if len(observations) >= candidate_count:
        return BehavioralMultiRegionSearchV21Status.GRID_EXHAUSTED

    if len(observations) >= maximum_evaluations:
        return BehavioralMultiRegionSearchV21Status.BUDGET_EXHAUSTED

    return BehavioralMultiRegionSearchV21Status.READY


def _derive_next_proposal(
    *,
    candidate_count: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
    planner_state: _PlannerState,
) -> tuple[
    _Proposal | None,
    _PlannerState,
]:
    if not observations:
        proposal = _Proposal(
            candidate_index=(candidate_count // 2),
            reason=(BehavioralMultiRegionSearchV21ProposalReason.INITIAL_CENTER),
        )

        return (
            proposal,
            planner_state,
        )

    if (
        planner_state.state
        == BehavioralMultiRegionSearchV21PlannerState.COVERAGE_RESET_REQUIRED
    ):
        candidate_index = _farthest_unobserved_candidate(
            candidate_count=(candidate_count),
            observations=(observations),
        )

        if candidate_index is None:
            return (
                None,
                planner_state,
            )

        return (
            _Proposal(
                candidate_index=(candidate_index),
                reason=(BehavioralMultiRegionSearchV21ProposalReason.COVERAGE_RESET),
            ),
            planner_state,
        )

    if (
        planner_state.state
        == BehavioralMultiRegionSearchV21PlannerState.BOUNDARY_TRANSACTION_ACTIVE
    ):
        transaction = planner_state.transaction

        if transaction is None:
            raise HveeContractError("V2.1 active transaction is missing")

        midpoint = (transaction.lower + transaction.upper) // 2

        observed = _observed_map(observations)

        if midpoint in observed:
            raise HveeContractError(
                "V2.1 active transaction midpoint is already observed"
            )

        return (
            _Proposal(
                candidate_index=midpoint,
                reason=(
                    BehavioralMultiRegionSearchV21ProposalReason.BOUNDARY_TRANSACTION_REFINEMENT
                ),
            ),
            planner_state,
        )

    bounded = _select_bounded_opportunity(observations)

    if bounded is not None:
        active = _PlannerState(
            state=(
                BehavioralMultiRegionSearchV21PlannerState.BOUNDARY_TRANSACTION_ACTIVE
            ),
            transaction=bounded,
        )

        midpoint = (bounded.lower + bounded.upper) // 2

        return (
            _Proposal(
                candidate_index=midpoint,
                reason=(
                    BehavioralMultiRegionSearchV21ProposalReason.BOUNDARY_TRANSACTION_REFINEMENT
                ),
            ),
            active,
        )

    candidate_index = _farthest_unobserved_candidate(
        candidate_count=(candidate_count),
        observations=(observations),
    )

    if candidate_index is None:
        return (
            None,
            planner_state,
        )

    return (
        _Proposal(
            candidate_index=(candidate_index),
            reason=(BehavioralMultiRegionSearchV21ProposalReason.MAXIMIN_COVERAGE),
        ),
        planner_state,
    )


def _advance_planner_state(
    *,
    action_state: _PlannerState,
    proposal: _Proposal,
    observations_after_action: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> _PlannerState:
    if proposal.reason == BehavioralMultiRegionSearchV21ProposalReason.COVERAGE_RESET:
        return _PlannerState(
            state=(BehavioralMultiRegionSearchV21PlannerState.NORMAL),
        )

    if (
        proposal.reason
        != BehavioralMultiRegionSearchV21ProposalReason.BOUNDARY_TRANSACTION_REFINEMENT
    ):
        return _PlannerState(
            state=(BehavioralMultiRegionSearchV21PlannerState.NORMAL),
        )

    transaction = action_state.transaction

    if (
        action_state.state
        != BehavioralMultiRegionSearchV21PlannerState.BOUNDARY_TRANSACTION_ACTIVE
        or transaction is None
    ):
        raise HveeContractError("V2.1 boundary proposal lacks an active transaction")

    observed = _observed_map(observations_after_action)

    relevant_indices = sorted(
        index for index in observed if (transaction.lower <= index <= transaction.upper)
    )

    descendants = [
        (
            lower,
            upper,
        )
        for lower, upper in zip(
            relevant_indices,
            relevant_indices[1:],
        )
        if (observed[lower].verdict != observed[upper].verdict)
    ]

    if len(descendants) != 1:
        raise HveeContractError(
            "V2.1 transaction did not preserve one opposing descendant"
        )

    (
        lower,
        upper,
    ) = descendants[0]

    actions_used = transaction.actions_used + 1

    if upper - lower == 1 or actions_used >= _MAXIMUM_BOUNDARY_TRANSACTION_ACTIONS:
        return _PlannerState(
            state=(BehavioralMultiRegionSearchV21PlannerState.COVERAGE_RESET_REQUIRED),
        )

    return _PlannerState(
        state=(BehavioralMultiRegionSearchV21PlannerState.BOUNDARY_TRANSACTION_ACTIVE),
        transaction=(
            _BoundaryTransaction(
                lower=lower,
                upper=upper,
                actions_used=(actions_used),
            )
        ),
    )


def _replay_observation_history(
    *,
    candidate_count: int,
    maximum_evaluations: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> _PlannerState:
    planner_state = _PlannerState(
        state=(BehavioralMultiRegionSearchV21PlannerState.NORMAL),
    )

    accepted: list[FailureFamilyObservation] = []

    for item in observations:
        current = tuple(accepted)

        if (
            _status(
                candidate_count=(candidate_count),
                maximum_evaluations=(maximum_evaluations),
                observations=(current),
            )
            != BehavioralMultiRegionSearchV21Status.READY
        ):
            raise HveeContractError(
                "V2.1 observations cannot continue after terminal state"
            )

        (
            proposal,
            action_state,
        ) = _derive_next_proposal(
            candidate_count=(candidate_count),
            observations=(current),
            planner_state=(planner_state),
        )

        if proposal is None:
            raise HveeContractError(
                "V2.1 observation exists without deterministic proposal"
            )

        if item.candidate_index != proposal.candidate_index:
            raise HveeContractError(
                "V2.1 observation does not match deterministic trajectory"
            )

        accepted.append(item)

        planner_state = _advance_planner_state(
            action_state=(action_state),
            proposal=(proposal),
            observations_after_action=tuple(accepted),
        )

    return planner_state


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


def _transaction_payload(
    transaction: _BoundaryTransaction | None,
) -> (
    dict[
        str,
        int,
    ]
    | None
):
    if transaction is None:
        return None

    return {
        "lower": (transaction.lower),
        "upper": (transaction.upper),
        "width": (transaction.upper - transaction.lower),
        "actions_used": (transaction.actions_used),
        "maximum_actions": (_MAXIMUM_BOUNDARY_TRANSACTION_ACTIONS),
    }


def build_behavioral_multi_region_search_v2_1_bundle(
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
) -> BehavioralMultiRegionSearchV21Bundle:
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
            "V2.1 maximum evaluations must be between one and candidate count"
        )

    normalized_observations = _normalize_observations(
        observations=(observations),
        candidate_count=(candidate_count),
    )

    if len(normalized_observations) > maximum_evaluations:
        raise HveeContractError("V2.1 observations exceed maximum evaluation budget")

    planner_state = _replay_observation_history(
        candidate_count=(candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(normalized_observations),
    )

    status = _status(
        candidate_count=(candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(normalized_observations),
    )

    proposal = None
    action_state = planner_state

    if status == BehavioralMultiRegionSearchV21Status.READY:
        (
            proposal,
            action_state,
        ) = _derive_next_proposal(
            candidate_count=(candidate_count),
            observations=(normalized_observations),
            planner_state=(planner_state),
        )

        if proposal is None:
            status = BehavioralMultiRegionSearchV21Status.GRID_EXHAUSTED

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
        "schema_version": (BEHAVIORAL_MULTI_REGION_SEARCH_V2_1_SCHEMA_VERSION),
        "type": ("behavioral_multi_region_search_v2_1"),
        "evaluation_type": (normalized_evaluation_type),
        "search": {
            "key": (normalized_search_key),
            "version": (normalized_search_version),
            "status": (status.value),
        },
        "policy": {
            "name": (_POLICY_NAME),
            "eligible_opposing_interval_widths": list(
                _ELIGIBLE_OPPOSING_INTERVAL_WIDTHS
            ),
            "maximum_boundary_transaction_actions": (
                _MAXIMUM_BOUNDARY_TRANSACTION_ACTIONS
            ),
            "coverage_reset_required": True,
            "wide_interval_automatic_refinement": False,
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
            "evaluated_count": len(normalized_observations),
            "remaining_evaluations": (
                maximum_evaluations - len(normalized_observations)
            ),
        },
        "observations": [
            _observation_payload(item) for item in normalized_observations
        ],
        "planner": {
            "state": (planner_state.state.value),
            "active_transaction": (_transaction_payload(planner_state.transaction)),
            "next_action_state": (
                action_state.state.value if proposal is not None else None
            ),
            "next_action_transaction": (
                _transaction_payload(action_state.transaction)
                if proposal is not None
                else None
            ),
        },
        "outcome": {
            "localized_boundary_count": (boundary_set.payload["boundaries"]["count"]),
            "exact_failure_region_count": len(exact_regions),
            "boundary_set_sha256": (boundary_set.sha256),
            "next_proposal": (proposal_payload),
        },
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="V2.1 evidence",
    )

    if not isinstance(
        canonical_payload,
        dict,
    ):
        raise HveeContractError("V2.1 evidence must be a JSON object")

    return BehavioralMultiRegionSearchV21Bundle(
        payload=(canonical_payload),
        sha256=(
            calculate_behavioral_multi_region_search_v2_1_sha256(canonical_payload)
        ),
    )


def verify_behavioral_multi_region_search_v2_1_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        if (
            not isinstance(
                payload,
                dict,
            )
            or not isinstance(
                expected_sha256,
                str,
            )
            or len(expected_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_sha256)
        ):
            return False

        if (
            payload.get("schema_version")
            != BEHAVIORAL_MULTI_REGION_SEARCH_V2_1_SCHEMA_VERSION
            or payload.get("type") != "behavioral_multi_region_search_v2_1"
            or payload.get("evidence_boundary") != _EVIDENCE_BOUNDARY
        ):
            return False

        search = payload.get("search")
        boundary_contract = payload.get("boundary_contract")
        axis = payload.get("axis")
        invariants = payload.get("invariants")
        budget = payload.get("budget")
        observation_payloads = payload.get("observations")

        if (
            not isinstance(
                search,
                dict,
            )
            or not isinstance(
                boundary_contract,
                dict,
            )
            or not isinstance(
                axis,
                dict,
            )
            or not isinstance(
                invariants,
                dict,
            )
            or not isinstance(
                budget,
                dict,
            )
            or not isinstance(
                observation_payloads,
                list,
            )
        ):
            return False

        candidate_values = axis.get("candidate_values")

        if not isinstance(
            candidate_values,
            list,
        ):
            return False

        observations = []

        for item in observation_payloads:
            if not isinstance(
                item,
                dict,
            ):
                return False

            observations.append(
                FailureFamilyObservation(
                    sequence=(item["sequence"]),
                    candidate_index=(item["candidate_index"]),
                    verdict=(DecisionVerdict(item["verdict"])),
                    source=(FailureFamilyObservationSource(item["source"])),
                    cost_units=(item["cost_units"]),
                    scenario_sha256=(item["scenario_sha256"]),
                    result_provenance_sha256=(item["result_provenance_sha256"]),
                    observation_evidence_sha256=(item["observation_evidence_sha256"]),
                    decision_evidence_sha256=(item["decision_evidence_sha256"]),
                    counterexample_evidence_sha256=(
                        item.get("counterexample_evidence_sha256")
                    ),
                )
            )

        rebuilt = build_behavioral_multi_region_search_v2_1_bundle(
            evaluation_type=(payload.get("evaluation_type")),
            search_key=(search.get("key")),
            search_version=(search.get("version")),
            boundary_key=(boundary_contract.get("key")),
            boundary_version=(boundary_contract.get("version")),
            axis_key=(axis.get("key")),
            axis_version=(axis.get("version")),
            axis_unit=(axis.get("unit")),
            candidate_values=(candidate_values),
            invariant_parameters=(invariants.get("parameters")),
            maximum_evaluations=(budget.get("maximum_evaluations")),
            observations=(observations),
        )

        return payload == rebuilt.payload and expected_sha256 == rebuilt.sha256

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False
