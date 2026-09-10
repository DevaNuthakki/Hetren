from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.observed_boundary import (
    ObservedBoundaryBundle,
    ObservedBoundaryEndpoint,
    build_observed_boundary_bundle,
    verify_observed_boundary_bundle,
)


FAILURE_FAMILY_INVESTIGATOR_SCHEMA_VERSION = 1
FAILURE_FAMILY_BOUNDARY_SET_SCHEMA_VERSION = 1


class FailureFamilySearchMode(str, Enum):
    GLOBAL = "global"
    INCIDENT_ANCHORED = "incident_anchored"


class FailureFamilyObservationSource(str, Enum):
    EVALUATION = "evaluation"
    INCIDENT_ANCHOR = "incident_anchor"


class FailureFamilySearchStatus(str, Enum):
    READY = "ready"
    BUDGET_EXHAUSTED = "budget_exhausted"
    GRID_EXHAUSTED = "grid_exhausted"
    INCIDENT_REGION_CHARACTERIZED = "incident_region_characterized"


class FailureFamilyProposalReason(str, Enum):
    INITIAL_CENTER = "initial_center"
    REFINE_OPPOSING_INTERVAL = "refine_opposing_interval"
    EXPLORE_FARTHEST_UNOBSERVED = "explore_farthest_unobserved"
    EXPAND_INCIDENT_LEFT = "expand_incident_left"
    EXPAND_INCIDENT_RIGHT = "expand_incident_right"


@dataclass(frozen=True)
class FailureFamilyObservation:
    sequence: int
    candidate_index: int
    verdict: DecisionVerdict
    source: FailureFamilyObservationSource
    cost_units: int
    scenario_sha256: str
    result_provenance_sha256: str
    observation_evidence_sha256: str
    decision_evidence_sha256: str
    counterexample_evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise HveeContractError(
                "failure-family observation sequence " "must be a non-negative integer"
            )

        if (
            isinstance(self.candidate_index, bool)
            or not isinstance(self.candidate_index, int)
            or self.candidate_index < 0
        ):
            raise HveeContractError(
                "failure-family candidate index " "must be a non-negative integer"
            )

        if self.verdict not in {
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        }:
            raise HveeContractError(
                "failure-family observations require " "pass or fail verdict"
            )

        if not isinstance(
            self.source,
            FailureFamilyObservationSource,
        ):
            raise HveeContractError("failure-family observation source is invalid")

        if (
            isinstance(self.cost_units, bool)
            or not isinstance(self.cost_units, int)
            or self.cost_units < 0
        ):
            raise HveeContractError(
                "failure-family cost units must be " "a non-negative integer"
            )

        if self.source == FailureFamilyObservationSource.INCIDENT_ANCHOR:
            if self.sequence != 0:
                raise HveeContractError("incident anchor sequence must be zero")

            if self.cost_units != 0:
                raise HveeContractError(
                    "incident anchor must have zero " "new evaluation cost"
                )

            if self.verdict != DecisionVerdict.FAIL:
                raise HveeContractError("incident anchor must be failing")

        else:
            if self.sequence < 1:
                raise HveeContractError(
                    "evaluated observations require " "positive sequence"
                )

            if self.cost_units != 1:
                raise HveeContractError(
                    "v1 evaluated observations cost " "exactly one unit"
                )

        for field, value in (
            (
                "scenario SHA-256",
                self.scenario_sha256,
            ),
            (
                "result provenance SHA-256",
                self.result_provenance_sha256,
            ),
            (
                "observation evidence SHA-256",
                self.observation_evidence_sha256,
            ),
            (
                "decision evidence SHA-256",
                self.decision_evidence_sha256,
            ),
        ):
            _require_sha256(
                value,
                field=field,
            )

        if self.verdict == DecisionVerdict.FAIL:
            _require_sha256(
                self.counterexample_evidence_sha256,
                field=("counterexample evidence SHA-256"),
            )

        elif self.counterexample_evidence_sha256 is not None:
            raise HveeContractError(
                "passing failure-family observations "
                "cannot reference counterexample evidence"
            )


@dataclass(frozen=True)
class FailureFamilyBoundarySetBundle:
    payload: dict[str, object]
    boundaries: tuple[
        ObservedBoundaryBundle,
        ...,
    ]
    sha256: str


@dataclass(frozen=True)
class FailureFamilyInvestigatorBundle:
    payload: dict[str, object]
    boundary_set: FailureFamilyBoundarySetBundle
    sha256: str


@dataclass(frozen=True)
class _Proposal:
    candidate_index: int
    reason: FailureFamilyProposalReason


_FORBIDDEN_RAW_KEYS = {
    "audio",
    "audio_bytes",
    "generated_text",
    "image",
    "image_bytes",
    "input_text",
    "prediction_text",
    "prompt_text",
    "raw_audio",
    "raw_content",
    "raw_input",
    "raw_output",
    "raw_transcript_text",
    "reference_text",
    "transcript",
}


def _canonical_sha256(
    value: object,
) -> str:
    try:
        encoded = json.dumps(
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
            "failure-family evidence must be canonical JSON"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise HveeContractError(f"{field} must be SHA-256 hex")

    try:
        int(
            value,
            16,
        )
    except ValueError as exc:
        raise HveeContractError(f"{field} must be SHA-256 hex") from exc

    return value.lower()


def _require_string(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not value or len(value) > 200:
        raise HveeContractError(f"{field} must be a non-empty string")

    return value


def _normalize_candidate_values(
    values: object,
) -> tuple[float, ...]:
    if (
        not isinstance(
            values,
            (list, tuple),
        )
        or len(values) < 2
    ):
        raise HveeContractError(
            "failure-family candidate values require " "at least two ordered values"
        )

    normalized: list[float] = []

    for value in values:
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise HveeContractError(
                "failure-family candidate values " "must be numeric"
            )

        numeric = float(value)

        if not math.isfinite(numeric):
            raise HveeContractError("failure-family candidate values " "must be finite")

        normalized.append(numeric)

    if any(
        upper <= lower
        for lower, upper in zip(
            normalized,
            normalized[1:],
        )
    ):
        raise HveeContractError(
            "failure-family candidate values " "must be strictly increasing"
        )

    return tuple(normalized)


def _normalize_invariants(
    value: object,
) -> dict[str, object]:
    if not isinstance(
        value,
        dict,
    ):
        raise HveeContractError("failure-family invariants must be an object")

    normalized: dict[
        str,
        object,
    ] = {}

    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise HveeContractError(
                "failure-family invariant keys " "must be non-empty strings"
            )

        if key.lower() in _FORBIDDEN_RAW_KEYS:
            raise HveeContractError(
                "failure-family invariants contain " "a forbidden raw-content key"
            )

        if item is not None and not isinstance(
            item,
            (
                str,
                int,
                float,
                bool,
            ),
        ):
            raise HveeContractError(
                "failure-family invariant values " "must be JSON scalar values"
            )

        if isinstance(item, float) and not math.isfinite(item):
            raise HveeContractError("failure-family invariant floats " "must be finite")

        normalized[key] = item

    return dict(sorted(normalized.items()))


def _observation_payload(
    observation: FailureFamilyObservation,
) -> dict[str, object]:
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
    if not isinstance(value, dict) or set(value) != {
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
    }:
        raise HveeContractError("stored failure-family observation is invalid")

    return FailureFamilyObservation(
        sequence=value["sequence"],
        candidate_index=value["candidate_index"],
        verdict=DecisionVerdict(value["verdict"]),
        source=(FailureFamilyObservationSource(value["source"])),
        cost_units=value["cost_units"],
        scenario_sha256=value["scenario_sha256"],
        result_provenance_sha256=value["result_provenance_sha256"],
        observation_evidence_sha256=value["observation_evidence_sha256"],
        decision_evidence_sha256=value["decision_evidence_sha256"],
        counterexample_evidence_sha256=value["counterexample_evidence_sha256"],
    )


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
        (list, tuple),
    ) or not all(
        isinstance(
            item,
            FailureFamilyObservation,
        )
        for item in observations
    ):
        raise HveeContractError(
            "failure-family observations must contain " "canonical observations"
        )

    normalized = tuple(observations)

    if any(item.candidate_index >= candidate_count for item in normalized):
        raise HveeContractError(
            "failure-family observation candidate " "is outside the grid"
        )

    indices = [item.candidate_index for item in normalized]

    if len(indices) != len(set(indices)):
        raise HveeContractError(
            "failure-family observations require " "distinct candidate indices"
        )

    scenarios = [item.scenario_sha256 for item in normalized]

    if len(scenarios) != len(set(scenarios)):
        raise HveeContractError(
            "failure-family observations require " "distinct scenarios"
        )

    evaluated = [
        item
        for item in normalized
        if (item.source == FailureFamilyObservationSource.EVALUATION)
    ]

    if [item.sequence for item in evaluated] != list(
        range(
            1,
            len(evaluated) + 1,
        )
    ):
        raise HveeContractError(
            "evaluated failure-family observations "
            "must have contiguous ordered sequences"
        )

    anchors = [
        item
        for item in normalized
        if (item.source == FailureFamilyObservationSource.INCIDENT_ANCHOR)
    ]

    if len(anchors) > 1:
        raise HveeContractError(
            "failure-family evidence allows " "at most one incident anchor"
        )

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


def _localized_boundary_pairs(
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> tuple[
    tuple[int, int],
    ...,
]:
    observed = _observed_map(observations)

    if not observed:
        return ()

    pairs = []

    for lower in range(
        min(observed),
        max(observed),
    ):
        upper = lower + 1

        if (
            lower in observed
            and upper in observed
            and observed[lower].verdict != observed[upper].verdict
        ):
            pairs.append(
                (
                    lower,
                    upper,
                )
            )

    return tuple(pairs)


def _failure_segments(
    *,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
    candidate_count: int,
    boundary_sha_by_pair: dict[
        tuple[int, int],
        str,
    ],
) -> tuple[
    dict[str, object],
    ...,
]:
    observed = _observed_map(observations)

    failing_indices = sorted(
        index
        for index, item in observed.items()
        if item.verdict == DecisionVerdict.FAIL
    )

    if not failing_indices:
        return ()

    segments: list[tuple[int, int]] = []

    lower = failing_indices[0]

    upper = lower

    for index in failing_indices[1:]:
        if index == upper + 1:
            upper = index
            continue

        segments.append(
            (
                lower,
                upper,
            )
        )

        lower = index
        upper = index

    segments.append(
        (
            lower,
            upper,
        )
    )

    result = []

    for lower, upper in segments:
        left_pair = (
            lower - 1,
            lower,
        )

        right_pair = (
            upper,
            upper + 1,
        )

        left_edge = lower == 0

        right_edge = upper == candidate_count - 1

        left_boundary_sha = boundary_sha_by_pair.get(left_pair)

        right_boundary_sha = boundary_sha_by_pair.get(right_pair)

        exact = (left_edge or left_boundary_sha is not None) and (
            right_edge or right_boundary_sha is not None
        )

        result.append(
            {
                "lower_candidate_index": (lower),
                "upper_candidate_index": (upper),
                "observed_failure_count": (upper - lower + 1),
                "left_edge": (left_edge),
                "right_edge": (right_edge),
                "left_boundary_sha256": (left_boundary_sha),
                "right_boundary_sha256": (right_boundary_sha),
                "exactly_characterized": (exact),
            }
        )

    return tuple(result)


def calculate_failure_family_boundary_set_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError(
            "failure-family boundary-set payload " "must be an object"
        )

    return _canonical_sha256(payload)


def build_failure_family_boundary_set_bundle(
    *,
    evaluation_type: str,
    boundary_key: str,
    boundary_version: str,
    search_key: str,
    search_version: str,
    axis_key: str,
    axis_version: str,
    axis_unit: str | None,
    candidate_values: list[int | float] | tuple[int | float, ...],
    invariant_parameters: dict[str, object],
    observations: list[FailureFamilyObservation] | tuple[FailureFamilyObservation, ...],
) -> FailureFamilyBoundarySetBundle:
    normalized_evaluation_type = _require_string(
        evaluation_type,
        field="evaluation type",
    )

    normalized_boundary_key = _require_string(
        boundary_key,
        field="boundary key",
    )

    normalized_boundary_version = _require_string(
        boundary_version,
        field="boundary version",
    )

    normalized_search_key = _require_string(
        search_key,
        field="search key",
    )

    normalized_search_version = _require_string(
        search_version,
        field="search version",
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

    normalized_observations = _normalize_observations(
        observations=observations,
        candidate_count=len(normalized_candidates),
    )

    observed = _observed_map(normalized_observations)

    boundaries: list[ObservedBoundaryBundle] = []

    boundary_records: list[dict[str, object]] = []

    boundary_sha_by_pair: dict[
        tuple[int, int],
        str,
    ] = {}

    for lower, upper in _localized_boundary_pairs(normalized_observations):
        lower_observation = observed[lower]

        upper_observation = observed[upper]

        boundary = build_observed_boundary_bundle(
            evaluation_type=(normalized_evaluation_type),
            boundary_key=(normalized_boundary_key),
            boundary_version=(normalized_boundary_version),
            search_key=(normalized_search_key),
            search_version=(normalized_search_version),
            axis_key=(normalized_axis_key),
            axis_version=(normalized_axis_version),
            axis_unit=(normalized_axis_unit),
            invariant_parameters=(normalized_invariants),
            endpoints=(
                ObservedBoundaryEndpoint(
                    axis_value=(normalized_candidates[lower]),
                    scenario_sha256=(lower_observation.scenario_sha256),
                    verdict=(lower_observation.verdict),
                    result_provenance_sha256=(
                        lower_observation.result_provenance_sha256
                    ),
                    observation_evidence_sha256=(
                        lower_observation.observation_evidence_sha256
                    ),
                    decision_evidence_sha256=(
                        lower_observation.decision_evidence_sha256
                    ),
                    counterexample_evidence_sha256=(
                        lower_observation.counterexample_evidence_sha256
                    ),
                ),
                ObservedBoundaryEndpoint(
                    axis_value=(normalized_candidates[upper]),
                    scenario_sha256=(upper_observation.scenario_sha256),
                    verdict=(upper_observation.verdict),
                    result_provenance_sha256=(
                        upper_observation.result_provenance_sha256
                    ),
                    observation_evidence_sha256=(
                        upper_observation.observation_evidence_sha256
                    ),
                    decision_evidence_sha256=(
                        upper_observation.decision_evidence_sha256
                    ),
                    counterexample_evidence_sha256=(
                        upper_observation.counterexample_evidence_sha256
                    ),
                ),
            ),
        )

        boundaries.append(boundary)

        boundary_sha_by_pair[
            (
                lower,
                upper,
            )
        ] = boundary.sha256

        boundary_records.append(
            {
                "lower_candidate_index": (lower),
                "upper_candidate_index": (upper),
                "direction": (boundary.payload["boundary"]["direction"]),
                "boundary_sha256": (boundary.sha256),
            }
        )

    failure_segments = _failure_segments(
        observations=(normalized_observations),
        candidate_count=len(normalized_candidates),
        boundary_sha_by_pair=(boundary_sha_by_pair),
    )

    exact_regions = [
        dict(segment)
        for segment in failure_segments
        if segment["exactly_characterized"] is True
    ]

    payload: dict[str, object] = {
        "schema_version": (FAILURE_FAMILY_BOUNDARY_SET_SCHEMA_VERSION),
        "type": ("failure_family_boundary_set"),
        "evaluation_type": (normalized_evaluation_type),
        "boundary_contract": {
            "key": (normalized_boundary_key),
            "version": (normalized_boundary_version),
        },
        "search": {
            "key": (normalized_search_key),
            "version": (normalized_search_version),
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
        "observations": [
            _observation_payload(item) for item in (normalized_observations)
        ],
        "boundaries": {
            "count": len(boundary_records),
            "ordered": (boundary_records),
        },
        "failure_regions": {
            "observed_segments": [dict(segment) for segment in (failure_segments)],
            "exactly_characterized": (exact_regions),
            "exact_region_count": len(exact_regions),
        },
        "evidence_boundary": {
            "single_observed_boundary_component_reused": (True),
            "multiple_boundaries_representable": (True),
            "failure_region_identity_representable": (True),
            "arbitrary_unobserved_region_inferred": (False),
            "behavioral_performance_qualified": (False),
            "run05_execution_performed": (False),
            "production_qualified": (False),
            "model_inference_performed": (False),
        },
    }

    return FailureFamilyBoundarySetBundle(
        payload=payload,
        boundaries=tuple(boundaries),
        sha256=(calculate_failure_family_boundary_set_sha256(payload)),
    )


def verify_failure_family_boundary_set_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        expected_sha = _require_sha256(
            expected_sha256,
            field=("expected failure-family " "boundary-set SHA-256"),
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        boundary_contract = payload["boundary_contract"]

        search = payload["search"]

        axis = payload["axis"]

        invariants = payload["invariants"]

        observations = tuple(
            _parse_observation(item) for item in payload["observations"]
        )

        rebuilt = build_failure_family_boundary_set_bundle(
            evaluation_type=payload["evaluation_type"],
            boundary_key=(boundary_contract["key"]),
            boundary_version=(boundary_contract["version"]),
            search_key=(search["key"]),
            search_version=(search["version"]),
            axis_key=(axis["key"]),
            axis_version=(axis["version"]),
            axis_unit=(axis["unit"]),
            candidate_values=(axis["candidate_values"]),
            invariant_parameters=(invariants["parameters"]),
            observations=(observations),
        )

        if rebuilt.payload != payload:
            return False

        if rebuilt.sha256 != expected_sha:
            return False

        for boundary in rebuilt.boundaries:
            if not (
                verify_observed_boundary_bundle(
                    payload=(boundary.payload),
                    expected_sha256=(boundary.sha256),
                )
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


def _opposing_intervals(
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> tuple[
    tuple[int, int],
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


def _farthest_unobserved(
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

    _negative_distance, selected = min(ranked)

    return selected


def _incident_anchor(
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> FailureFamilyObservation | None:
    anchors = [
        item
        for item in observations
        if (item.source == FailureFamilyObservationSource.INCIDENT_ANCHOR)
    ]

    if not anchors:
        return None

    if len(anchors) != 1:
        raise HveeContractError(
            "incident investigation requires " "one incident anchor"
        )

    return anchors[0]


def _incident_region_state(
    *,
    candidate_count: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> tuple[
    int,
    int,
    bool,
    bool,
]:
    anchor = _incident_anchor(observations)

    if anchor is None:
        raise HveeContractError("incident investigation requires " "a failing anchor")

    observed = _observed_map(observations)

    lower = anchor.candidate_index

    while (
        lower > 0
        and lower - 1 in observed
        and observed[lower - 1].verdict == DecisionVerdict.FAIL
    ):
        lower -= 1

    upper = anchor.candidate_index

    while (
        upper + 1 < candidate_count
        and upper + 1 in observed
        and observed[upper + 1].verdict == DecisionVerdict.FAIL
    ):
        upper += 1

    left_complete = lower == 0 or (
        lower - 1 in observed and observed[lower - 1].verdict == DecisionVerdict.PASS
    )

    right_complete = upper == candidate_count - 1 or (
        upper + 1 in observed and observed[upper + 1].verdict == DecisionVerdict.PASS
    )

    return (
        lower,
        upper,
        left_complete,
        right_complete,
    )


def _derive_global_proposal(
    *,
    candidate_count: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> _Proposal | None:
    if not observations:
        return _Proposal(
            candidate_index=(candidate_count // 2),
            reason=(FailureFamilyProposalReason.INITIAL_CENTER),
        )

    opposing = _opposing_intervals(observations)

    if opposing:
        lower, upper = min(
            opposing,
            key=lambda item: (
                item[1] - item[0],
                item[0],
            ),
        )

        return _Proposal(
            candidate_index=(lower + upper) // 2,
            reason=(FailureFamilyProposalReason.REFINE_OPPOSING_INTERVAL),
        )

    candidate_index = _farthest_unobserved(
        candidate_count=(candidate_count),
        observations=(observations),
    )

    if candidate_index is None:
        return None

    return _Proposal(
        candidate_index=(candidate_index),
        reason=(FailureFamilyProposalReason.EXPLORE_FARTHEST_UNOBSERVED),
    )


def _derive_incident_proposal(
    *,
    candidate_count: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> _Proposal | None:
    (
        lower,
        upper,
        left_complete,
        right_complete,
    ) = _incident_region_state(
        candidate_count=(candidate_count),
        observations=(observations),
    )

    if left_complete and right_complete:
        return None

    evaluated_count = sum(
        item.source == FailureFamilyObservationSource.EVALUATION
        for item in observations
    )

    prefer_left = evaluated_count % 2 == 0

    if prefer_left and not left_complete:
        return _Proposal(
            candidate_index=(lower - 1),
            reason=(FailureFamilyProposalReason.EXPAND_INCIDENT_LEFT),
        )

    if not right_complete:
        return _Proposal(
            candidate_index=(upper + 1),
            reason=(FailureFamilyProposalReason.EXPAND_INCIDENT_RIGHT),
        )

    if not left_complete:
        return _Proposal(
            candidate_index=(lower - 1),
            reason=(FailureFamilyProposalReason.EXPAND_INCIDENT_LEFT),
        )

    return None


def _derive_status_and_proposal(
    *,
    mode: FailureFamilySearchMode,
    candidate_count: int,
    maximum_evaluations: int,
    observations: tuple[
        FailureFamilyObservation,
        ...,
    ],
) -> tuple[
    FailureFamilySearchStatus,
    _Proposal | None,
]:
    evaluated_count = sum(
        item.source == FailureFamilyObservationSource.EVALUATION
        for item in observations
    )

    if mode == FailureFamilySearchMode.INCIDENT_ANCHORED:
        (
            _lower,
            _upper,
            left_complete,
            right_complete,
        ) = _incident_region_state(
            candidate_count=(candidate_count),
            observations=(observations),
        )

        if left_complete and right_complete:
            return (
                FailureFamilySearchStatus.INCIDENT_REGION_CHARACTERIZED,
                None,
            )

    if len(observations) == candidate_count:
        return (
            FailureFamilySearchStatus.GRID_EXHAUSTED,
            None,
        )

    if evaluated_count >= maximum_evaluations:
        return (
            FailureFamilySearchStatus.BUDGET_EXHAUSTED,
            None,
        )

    if mode == FailureFamilySearchMode.GLOBAL:
        proposal = _derive_global_proposal(
            candidate_count=(candidate_count),
            observations=(observations),
        )

    else:
        proposal = _derive_incident_proposal(
            candidate_count=(candidate_count),
            observations=(observations),
        )

    if proposal is None:
        return (
            FailureFamilySearchStatus.GRID_EXHAUSTED,
            None,
        )

    return (
        FailureFamilySearchStatus.READY,
        proposal,
    )


def calculate_failure_family_investigator_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(
        payload,
        dict,
    ):
        raise HveeContractError(
            "failure-family investigator payload " "must be an object"
        )

    return _canonical_sha256(payload)


def build_failure_family_investigator_bundle(
    *,
    mode: FailureFamilySearchMode,
    evaluation_type: str,
    investigator_key: str,
    investigator_version: str,
    boundary_key: str,
    boundary_version: str,
    axis_key: str,
    axis_version: str,
    axis_unit: str | None,
    candidate_values: list[int | float] | tuple[int | float, ...],
    invariant_parameters: dict[str, object],
    maximum_evaluations: int,
    observations: list[FailureFamilyObservation] | tuple[FailureFamilyObservation, ...],
) -> FailureFamilyInvestigatorBundle:
    if not isinstance(
        mode,
        FailureFamilySearchMode,
    ):
        raise HveeContractError("failure-family search mode is invalid")

    normalized_evaluation_type = _require_string(
        evaluation_type,
        field="evaluation type",
    )

    normalized_investigator_key = _require_string(
        investigator_key,
        field="investigator key",
    )

    normalized_investigator_version = _require_string(
        investigator_version,
        field="investigator version",
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
        isinstance(maximum_evaluations, bool)
        or not isinstance(
            maximum_evaluations,
            int,
        )
        or maximum_evaluations < 1
    ):
        raise HveeContractError(
            "failure-family maximum evaluations " "must be a positive integer"
        )

    maximum_allowed = (
        candidate_count
        if mode == FailureFamilySearchMode.GLOBAL
        else candidate_count - 1
    )

    if maximum_evaluations > maximum_allowed:
        raise HveeContractError(
            "failure-family maximum evaluations " "exceed available new candidates"
        )

    normalized_observations = _normalize_observations(
        observations=observations,
        candidate_count=(candidate_count),
    )

    anchor = _incident_anchor(normalized_observations)

    if mode == FailureFamilySearchMode.GLOBAL and anchor is not None:
        raise HveeContractError(
            "global failure-family search " "cannot contain incident anchor"
        )

    if mode == FailureFamilySearchMode.INCIDENT_ANCHORED and anchor is None:
        raise HveeContractError(
            "incident-anchored failure-family search " "requires one failing anchor"
        )

    evaluated = [
        item
        for item in (normalized_observations)
        if (item.source == FailureFamilyObservationSource.EVALUATION)
    ]

    accepted: list[FailureFamilyObservation] = []

    if anchor is not None:
        accepted.append(anchor)

    for item in evaluated:
        (
            status,
            proposal,
        ) = _derive_status_and_proposal(
            mode=mode,
            candidate_count=(candidate_count),
            maximum_evaluations=(maximum_evaluations),
            observations=tuple(accepted),
        )

        if status != FailureFamilySearchStatus.READY or proposal is None:
            raise HveeContractError(
                "failure-family observations cannot " "continue after terminal state"
            )

        if item.candidate_index != proposal.candidate_index:
            raise HveeContractError(
                "failure-family observation does not "
                "match deterministic proposal trajectory"
            )

        accepted.append(item)

    (
        status,
        proposal,
    ) = _derive_status_and_proposal(
        mode=mode,
        candidate_count=(candidate_count),
        maximum_evaluations=(maximum_evaluations),
        observations=(normalized_observations),
    )

    boundary_set = build_failure_family_boundary_set_bundle(
        evaluation_type=(normalized_evaluation_type),
        boundary_key=(normalized_boundary_key),
        boundary_version=(normalized_boundary_version),
        search_key=(normalized_investigator_key),
        search_version=(normalized_investigator_version),
        axis_key=(normalized_axis_key),
        axis_version=(normalized_axis_version),
        axis_unit=(normalized_axis_unit),
        candidate_values=(normalized_candidates),
        invariant_parameters=(normalized_invariants),
        observations=(normalized_observations),
    )

    evaluated_count = len(evaluated)

    proposal_payload = None

    if proposal is not None:
        proposal_payload = {
            "candidate_index": (proposal.candidate_index),
            "axis_value": (normalized_candidates[proposal.candidate_index]),
            "reason": (proposal.reason.value),
        }

    exact_regions = boundary_set.payload["failure_regions"]["exactly_characterized"]

    payload: dict[str, object] = {
        "schema_version": (FAILURE_FAMILY_INVESTIGATOR_SCHEMA_VERSION),
        "type": ("failure_family_investigator"),
        "evaluation_type": (normalized_evaluation_type),
        "investigator": {
            "key": (normalized_investigator_key),
            "version": (normalized_investigator_version),
            "mode": (mode.value),
            "status": (status.value),
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
            "evaluated_count": (evaluated_count),
            "remaining_evaluations": (maximum_evaluations - evaluated_count),
            "incident_anchor_cost_units": (0 if anchor is not None else None),
        },
        "observations": [
            _observation_payload(item) for item in (normalized_observations)
        ],
        "outcome": {
            "localized_boundary_count": (boundary_set.payload["boundaries"]["count"]),
            "exact_failure_region_count": len(exact_regions),
            "boundary_set_sha256": (boundary_set.sha256),
            "next_proposal": (proposal_payload),
        },
        "evidence_boundary": {
            "single_boundary_component_reused": (True),
            "multi_boundary_state_supported": (True),
            "multiple_disjoint_failure_regions_supported": (True),
            "incident_anchor_zero_new_cost_supported": (True),
            "search_execution_performed": (bool(evaluated)),
            "execution_evidence_verified": (False),
            "behavioral_performance_qualified": (False),
            "run05_execution_performed": (False),
            "real_ai_generalization_established": (False),
            "production_qualified": (False),
            "model_inference_performed": (False),
        },
    }

    return FailureFamilyInvestigatorBundle(
        payload=payload,
        boundary_set=(boundary_set),
        sha256=(calculate_failure_family_investigator_sha256(payload)),
    )


def verify_failure_family_investigator_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        expected_sha = _require_sha256(
            expected_sha256,
            field=("expected failure-family " "investigator SHA-256"),
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        investigator = payload["investigator"]

        boundary_contract = payload["boundary_contract"]

        axis = payload["axis"]

        invariants = payload["invariants"]

        budget = payload["budget"]

        observations = tuple(
            _parse_observation(item) for item in payload["observations"]
        )

        rebuilt = build_failure_family_investigator_bundle(
            mode=(FailureFamilySearchMode(investigator["mode"])),
            evaluation_type=payload["evaluation_type"],
            investigator_key=(investigator["key"]),
            investigator_version=(investigator["version"]),
            boundary_key=(boundary_contract["key"]),
            boundary_version=(boundary_contract["version"]),
            axis_key=(axis["key"]),
            axis_version=(axis["version"]),
            axis_unit=(axis["unit"]),
            candidate_values=(axis["candidate_values"]),
            invariant_parameters=(invariants["parameters"]),
            maximum_evaluations=(budget["maximum_evaluations"]),
            observations=(observations),
        )

        if rebuilt.payload != payload:
            return False

        if rebuilt.sha256 != expected_sha:
            return False

        return verify_failure_family_boundary_set_bundle(
            payload=(rebuilt.boundary_set.payload),
            expected_sha256=(rebuilt.boundary_set.sha256),
        )

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False
