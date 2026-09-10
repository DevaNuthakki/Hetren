from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from hvee.core.contracts import HveeContractError
from hvee.core.failure_family_investigator import (
    FailureFamilyObservation,
    FailureFamilyObservationSource,
    build_failure_family_boundary_set_bundle,
)


BEHAVIORAL_EVIDENCE_GAIN_PLANNER_SCHEMA_VERSION = 1

_POLICY_NAME = "BEHAVIORAL_EVIDENCE_GAIN_PLANNER_V1"
_OBJECTIVE_NAME = "STRUCTURAL_EVIDENCE_GAIN"
_COVERAGE_POTENTIAL_NAME = "COVERAGE_DISTANCE_MASS"
_BOUNDARY_POTENTIAL_NAME = "KNOWN_OPPOSING_INTERVAL_AMBIGUITY"


class BehavioralEvidenceGainPlannerStatus(str, Enum):
    READY = "ready"
    BUDGET_EXHAUSTED = "budget_exhausted"
    GRID_EXHAUSTED = "grid_exhausted"


class BehavioralEvidenceGainPlannerProposalReason(str, Enum):
    STRUCTURAL_CENTER_BOOTSTRAP = "structural_center_bootstrap"
    MAX_STRUCTURAL_EVIDENCE_GAIN = "max_structural_evidence_gain"


class BehavioralEvidenceGainPlannerCandidateRole(str, Enum):
    GLOBAL_COVERAGE = "global_coverage"
    BOUNDARY_LOCALIZATION = "boundary_localization"


@dataclass(frozen=True)
class BehavioralEvidenceGainPlannerBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        _require_sha256(
            self.sha256,
            field="behavioral evidence-gain planner bundle SHA-256",
        )

        if self.sha256 != calculate_behavioral_evidence_gain_planner_sha256(
            self.payload
        ):
            raise HveeContractError(
                "behavioral evidence-gain planner bundle SHA-256 "
                "does not match payload"
            )


@dataclass(frozen=True)
class _CandidateScore:
    candidate_index: int
    roles: tuple[BehavioralEvidenceGainPlannerCandidateRole, ...]
    coverage_gain: int
    known_boundary_gain: int
    planned_cost_units: int
    total_structural_gain: int

    @property
    def gain_per_cost(self) -> float:
        return self.total_structural_gain / self.planned_cost_units


@dataclass(frozen=True)
class _Proposal:
    candidate_index: int
    reason: BehavioralEvidenceGainPlannerProposalReason
    roles: tuple[BehavioralEvidenceGainPlannerCandidateRole, ...]
    score: _CandidateScore | None


def _require_string(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HveeContractError(f"{field} must be a non-empty string")

    return value


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(f"{field} is invalid")

    return value


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
            "behavioral evidence-gain planner evidence is not canonical JSON"
        ) from exc


def calculate_behavioral_evidence_gain_planner_sha256(
    payload: dict[str, object],
) -> str:
    if not isinstance(payload, dict):
        raise HveeContractError(
            "behavioral evidence-gain planner payload must be an object"
        )

    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _normalize_observations(
    *,
    observations: list[FailureFamilyObservation] | tuple[FailureFamilyObservation, ...],
    candidate_count: int,
) -> tuple[FailureFamilyObservation, ...]:
    if not isinstance(
        observations,
        (
            list,
            tuple,
        ),
    ):
        raise HveeContractError(
            "behavioral evidence-gain planner observations " "must be a list or tuple"
        )

    normalized: list[FailureFamilyObservation] = []

    for item in observations:
        if not isinstance(
            item,
            FailureFamilyObservation,
        ):
            raise HveeContractError(
                "behavioral evidence-gain planner observation is invalid"
            )

        if item.source != FailureFamilyObservationSource.EVALUATION:
            raise HveeContractError(
                "behavioral evidence-gain planner v1 accepts only "
                "evaluated observations"
            )

        if item.cost_units != 1:
            raise HveeContractError(
                "behavioral evidence-gain planner v1 evaluated "
                "observations must cost exactly one unit"
            )

        if item.candidate_index >= candidate_count:
            raise HveeContractError(
                "behavioral evidence-gain planner observation "
                "candidate index is outside candidate grid"
            )

        normalized.append(item)

    normalized.sort(key=lambda item: item.sequence)

    expected_sequences = list(
        range(
            1,
            len(normalized) + 1,
        )
    )

    actual_sequences = [item.sequence for item in normalized]

    if actual_sequences != expected_sequences:
        raise HveeContractError(
            "behavioral evidence-gain planner evaluated observation "
            "sequence must be contiguous from one"
        )

    candidate_indices = [item.candidate_index for item in normalized]

    if len(candidate_indices) != len(set(candidate_indices)):
        raise HveeContractError(
            "behavioral evidence-gain planner observations " "cannot repeat a candidate"
        )

    return tuple(normalized)


def _observation_payload(
    item: FailureFamilyObservation,
) -> dict[str, object]:
    return {
        "sequence": item.sequence,
        "candidate_index": item.candidate_index,
        "verdict": item.verdict.value,
        "source": item.source.value,
        "cost_units": item.cost_units,
        "scenario_sha256": item.scenario_sha256,
        "result_provenance_sha256": item.result_provenance_sha256,
        "observation_evidence_sha256": item.observation_evidence_sha256,
        "decision_evidence_sha256": item.decision_evidence_sha256,
        "counterexample_evidence_sha256": item.counterexample_evidence_sha256,
    }


def _observed_map(
    observations: tuple[FailureFamilyObservation, ...],
) -> dict[int, str]:
    return {item.candidate_index: item.verdict.value for item in observations}


def _coverage_potential(
    *,
    candidate_count: int,
    observed_indices: set[int],
) -> int | None:
    if not observed_indices:
        return None

    return sum(
        min(abs(candidate - observed) for observed in observed_indices)
        for candidate in range(candidate_count)
        if candidate not in observed_indices
    )


def _coverage_gain(
    *,
    candidate_count: int,
    observed_indices: set[int],
    candidate_index: int,
) -> int:
    if not observed_indices:
        raise HveeContractError(
            "coverage gain is undefined before bootstrap observation"
        )

    if candidate_index in observed_indices:
        raise HveeContractError("coverage gain candidate must be unobserved")

    before = _coverage_potential(
        candidate_count=candidate_count,
        observed_indices=observed_indices,
    )

    if before is None:
        raise HveeContractError("coverage potential unexpectedly unavailable")

    after = _coverage_potential(
        candidate_count=candidate_count,
        observed_indices={
            *observed_indices,
            candidate_index,
        },
    )

    if after is None:
        raise HveeContractError(
            "post-candidate coverage potential unexpectedly unavailable"
        )

    gain = before - after

    if gain <= 0:
        raise HveeContractError(
            "unobserved candidate must provide positive coverage gain"
        )

    return gain


def _opposing_intervals(
    observations: tuple[FailureFamilyObservation, ...],
) -> tuple[tuple[int, int], ...]:
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
        if (upper - lower > 1 and observed[lower] != observed[upper])
    )


def _known_boundary_potential(
    observations: tuple[FailureFamilyObservation, ...],
) -> int:
    return sum(upper - lower - 1 for lower, upper in _opposing_intervals(observations))


def _containing_opposing_interval(
    *,
    observations: tuple[FailureFamilyObservation, ...],
    candidate_index: int,
) -> tuple[int, int] | None:
    matches = [
        (
            lower,
            upper,
        )
        for lower, upper in _opposing_intervals(observations)
        if lower < candidate_index < upper
    ]

    if len(matches) > 1:
        raise HveeContractError(
            "candidate cannot belong to multiple consecutive "
            "observed opposing intervals"
        )

    if not matches:
        return None

    return matches[0]


def _known_boundary_gain(
    *,
    observations: tuple[FailureFamilyObservation, ...],
    candidate_index: int,
) -> int:
    interval = _containing_opposing_interval(
        observations=observations,
        candidate_index=candidate_index,
    )

    if interval is None:
        return 0

    lower, upper = interval

    gain = min(
        candidate_index - lower,
        upper - candidate_index,
    )

    if gain <= 0:
        raise HveeContractError(
            "known-boundary gain must be positive inside " "an opposing interval"
        )

    return gain


def _candidate_roles(
    *,
    known_boundary_gain: int,
) -> tuple[BehavioralEvidenceGainPlannerCandidateRole, ...]:
    roles = [
        BehavioralEvidenceGainPlannerCandidateRole.GLOBAL_COVERAGE,
    ]

    if known_boundary_gain > 0:
        roles.append(BehavioralEvidenceGainPlannerCandidateRole.BOUNDARY_LOCALIZATION)

    return tuple(roles)


def _candidate_scores(
    *,
    candidate_count: int,
    observations: tuple[FailureFamilyObservation, ...],
) -> tuple[_CandidateScore, ...]:
    if not observations:
        raise HveeContractError("candidate scoring is not applied before bootstrap")

    observed_indices = {item.candidate_index for item in observations}

    scores: list[_CandidateScore] = []

    for candidate_index in range(candidate_count):
        if candidate_index in observed_indices:
            continue

        coverage_gain = _coverage_gain(
            candidate_count=candidate_count,
            observed_indices=observed_indices,
            candidate_index=candidate_index,
        )

        known_boundary_gain = _known_boundary_gain(
            observations=observations,
            candidate_index=candidate_index,
        )

        cost = 1

        scores.append(
            _CandidateScore(
                candidate_index=candidate_index,
                roles=_candidate_roles(
                    known_boundary_gain=known_boundary_gain,
                ),
                coverage_gain=coverage_gain,
                known_boundary_gain=known_boundary_gain,
                planned_cost_units=cost,
                total_structural_gain=(coverage_gain + known_boundary_gain),
            )
        )

    return tuple(scores)


def _dominates(
    left: _CandidateScore,
    right: _CandidateScore,
) -> bool:
    return (
        left.coverage_gain >= right.coverage_gain
        and left.known_boundary_gain >= right.known_boundary_gain
        and left.planned_cost_units <= right.planned_cost_units
        and (
            left.coverage_gain > right.coverage_gain
            or left.known_boundary_gain > right.known_boundary_gain
            or left.planned_cost_units < right.planned_cost_units
        )
    )


def _pareto_frontier(
    scores: tuple[_CandidateScore, ...],
) -> tuple[_CandidateScore, ...]:
    return tuple(
        score
        for score in scores
        if not any(
            _dominates(
                other,
                score,
            )
            for other in scores
            if other is not score
        )
    )


def _select_nonbootstrap_candidate(
    *,
    candidate_count: int,
    observations: tuple[FailureFamilyObservation, ...],
) -> tuple[
    _CandidateScore,
    tuple[_CandidateScore, ...],
    tuple[_CandidateScore, ...],
]:
    scores = _candidate_scores(
        candidate_count=candidate_count,
        observations=observations,
    )

    if not scores:
        raise HveeContractError(
            "non-bootstrap selection requires an unobserved candidate"
        )

    frontier = _pareto_frontier(scores)

    if not frontier:
        raise HveeContractError(
            "behavioral evidence-gain planner Pareto frontier is empty"
        )

    selected = min(
        frontier,
        key=lambda score: (
            -score.gain_per_cost,
            score.planned_cost_units,
            score.candidate_index,
        ),
    )

    maximum_gain_per_cost = max(score.gain_per_cost for score in frontier)

    if selected.gain_per_cost != maximum_gain_per_cost:
        raise HveeContractError("selected candidate does not maximize frozen objective")

    return (
        selected,
        scores,
        frontier,
    )


def _derive_proposal(
    *,
    candidate_count: int,
    observations: tuple[FailureFamilyObservation, ...],
) -> _Proposal | None:
    observed_indices = {item.candidate_index for item in observations}

    if len(observed_indices) >= candidate_count:
        return None

    if not observations:
        candidate_index = candidate_count // 2

        return _Proposal(
            candidate_index=candidate_index,
            reason=(
                BehavioralEvidenceGainPlannerProposalReason.STRUCTURAL_CENTER_BOOTSTRAP
            ),
            roles=(BehavioralEvidenceGainPlannerCandidateRole.GLOBAL_COVERAGE,),
            score=None,
        )

    selected, _scores, _frontier = _select_nonbootstrap_candidate(
        candidate_count=candidate_count,
        observations=observations,
    )

    return _Proposal(
        candidate_index=selected.candidate_index,
        reason=(
            BehavioralEvidenceGainPlannerProposalReason.MAX_STRUCTURAL_EVIDENCE_GAIN
        ),
        roles=selected.roles,
        score=selected,
    )


def _status(
    *,
    candidate_count: int,
    maximum_evaluations: int,
    observations: tuple[FailureFamilyObservation, ...],
) -> BehavioralEvidenceGainPlannerStatus:
    evaluated_count = len(observations)

    if evaluated_count >= candidate_count:
        return BehavioralEvidenceGainPlannerStatus.GRID_EXHAUSTED

    if evaluated_count >= maximum_evaluations:
        return BehavioralEvidenceGainPlannerStatus.BUDGET_EXHAUSTED

    return BehavioralEvidenceGainPlannerStatus.READY


def _replay_observation_history(
    *,
    candidate_count: int,
    maximum_evaluations: int,
    observations: tuple[FailureFamilyObservation, ...],
) -> None:
    accepted: list[FailureFamilyObservation] = []

    for item in observations:
        accepted_tuple = tuple(accepted)

        status = _status(
            candidate_count=candidate_count,
            maximum_evaluations=maximum_evaluations,
            observations=accepted_tuple,
        )

        if status != BehavioralEvidenceGainPlannerStatus.READY:
            raise HveeContractError(
                "behavioral evidence-gain planner observations "
                "cannot continue after terminal state"
            )

        proposal = _derive_proposal(
            candidate_count=candidate_count,
            observations=accepted_tuple,
        )

        if proposal is None:
            raise HveeContractError(
                "behavioral evidence-gain planner trajectory "
                "unexpectedly has no proposal"
            )

        if item.candidate_index != proposal.candidate_index:
            raise HveeContractError(
                "behavioral evidence-gain planner observation does not "
                "match deterministic proposal trajectory"
            )

        accepted.append(item)


def _candidate_score_payload(
    score: _CandidateScore,
    *,
    on_pareto_frontier: bool,
) -> dict[str, object]:
    return {
        "candidate_index": score.candidate_index,
        "roles": [role.value for role in score.roles],
        "coverage_gain": score.coverage_gain,
        "known_boundary_gain": score.known_boundary_gain,
        "planned_cost_units": score.planned_cost_units,
        "total_structural_gain": score.total_structural_gain,
        "gain_per_cost": score.gain_per_cost,
        "on_pareto_frontier": on_pareto_frontier,
    }


def _proposal_payload(
    *,
    proposal: _Proposal,
    candidate_values: tuple[int | float, ...],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_index": proposal.candidate_index,
        "axis_value": candidate_values[proposal.candidate_index],
        "reason": proposal.reason.value,
        "roles": [role.value for role in proposal.roles],
        "structural_evidence": None,
    }

    if proposal.score is not None:
        payload["structural_evidence"] = {
            "coverage_gain": (proposal.score.coverage_gain),
            "known_boundary_gain": (proposal.score.known_boundary_gain),
            "planned_cost_units": (proposal.score.planned_cost_units),
            "total_structural_gain": (proposal.score.total_structural_gain),
            "gain_per_cost": (proposal.score.gain_per_cost),
        }

    return payload


def build_behavioral_evidence_gain_planner_bundle(
    *,
    evaluation_type: str,
    planner_key: str,
    planner_version: str,
    boundary_key: str,
    boundary_version: str,
    axis_key: str,
    axis_version: str,
    axis_unit: str | None,
    candidate_values: list[int | float] | tuple[int | float, ...],
    invariant_parameters: dict[str, object],
    maximum_evaluations: int,
    observations: list[FailureFamilyObservation] | tuple[FailureFamilyObservation, ...],
) -> BehavioralEvidenceGainPlannerBundle:
    normalized_evaluation_type = _require_string(
        evaluation_type,
        field="evaluation type",
    )

    normalized_planner_key = _require_string(
        planner_key,
        field="planner key",
    )

    normalized_planner_version = _require_string(
        planner_version,
        field="planner version",
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
    ):
        raise HveeContractError(
            "behavioral evidence-gain planner maximum evaluations "
            "must be a positive integer"
        )

    boundary_set = build_failure_family_boundary_set_bundle(
        evaluation_type=(normalized_evaluation_type),
        boundary_key=(normalized_boundary_key),
        boundary_version=(normalized_boundary_version),
        search_key=(normalized_planner_key),
        search_version=(normalized_planner_version),
        axis_key=(normalized_axis_key),
        axis_version=(normalized_axis_version),
        axis_unit=(normalized_axis_unit),
        candidate_values=(candidate_values),
        invariant_parameters=(invariant_parameters),
        observations=(observations),
    )

    normalized_candidates = tuple(boundary_set.payload["axis"]["candidate_values"])

    candidate_count = len(normalized_candidates)

    if maximum_evaluations > candidate_count:
        raise HveeContractError(
            "behavioral evidence-gain planner maximum evaluations "
            "cannot exceed candidate count"
        )

    normalized_observations = _normalize_observations(
        observations=observations,
        candidate_count=candidate_count,
    )

    if len(normalized_observations) > maximum_evaluations:
        raise HveeContractError(
            "behavioral evidence-gain planner observations "
            "exceed maximum evaluation budget"
        )

    _replay_observation_history(
        candidate_count=candidate_count,
        maximum_evaluations=maximum_evaluations,
        observations=normalized_observations,
    )

    status = _status(
        candidate_count=candidate_count,
        maximum_evaluations=maximum_evaluations,
        observations=normalized_observations,
    )

    proposal = None

    if status == BehavioralEvidenceGainPlannerStatus.READY:
        proposal = _derive_proposal(
            candidate_count=candidate_count,
            observations=normalized_observations,
        )

        if proposal is None:
            status = BehavioralEvidenceGainPlannerStatus.GRID_EXHAUSTED

    observed_indices = {item.candidate_index for item in normalized_observations}

    coverage_potential = (
        _coverage_potential(
            candidate_count=candidate_count,
            observed_indices=observed_indices,
        )
        if observed_indices
        else None
    )

    known_boundary_potential = _known_boundary_potential(normalized_observations)

    scores: tuple[
        _CandidateScore,
        ...,
    ] = tuple()

    frontier: tuple[
        _CandidateScore,
        ...,
    ] = tuple()

    if status == BehavioralEvidenceGainPlannerStatus.READY and normalized_observations:
        scores = _candidate_scores(
            candidate_count=candidate_count,
            observations=normalized_observations,
        )

        frontier = _pareto_frontier(scores)

    frontier_indices = {score.candidate_index for score in frontier}

    proposal_payload = None

    if proposal is not None:
        proposal_payload = _proposal_payload(
            proposal=proposal,
            candidate_values=normalized_candidates,
        )

    exact_regions = boundary_set.payload["failure_regions"]["exactly_characterized"]

    payload: dict[
        str,
        object,
    ] = {
        "schema_version": (BEHAVIORAL_EVIDENCE_GAIN_PLANNER_SCHEMA_VERSION),
        "type": ("behavioral_evidence_gain_planner"),
        "evaluation_type": (normalized_evaluation_type),
        "planner": {
            "key": (normalized_planner_key),
            "version": (normalized_planner_version),
            "policy": (_POLICY_NAME),
            "objective": (_OBJECTIVE_NAME),
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
        "invariants": (boundary_set.payload["invariants"]),
        "budget": {
            "maximum_evaluations": (maximum_evaluations),
            "evaluated_count": len(normalized_observations),
            "remaining_evaluations": (
                maximum_evaluations - len(normalized_observations)
            ),
            "planned_cost_units_per_candidate": 1,
        },
        "observations": [
            _observation_payload(item) for item in normalized_observations
        ],
        "state": {
            "observed_candidate_count": len(normalized_observations),
            "unobserved_candidate_count": (
                candidate_count - len(normalized_observations)
            ),
            "coverage_potential_name": (_COVERAGE_POTENTIAL_NAME),
            "coverage_potential": (coverage_potential),
            "known_boundary_potential_name": (_BOUNDARY_POTENTIAL_NAME),
            "known_boundary_potential": (known_boundary_potential),
            "opposing_intervals": [
                {
                    "lower_candidate_index": lower,
                    "upper_candidate_index": upper,
                    "interior_ambiguity": (upper - lower - 1),
                }
                for lower, upper in (_opposing_intervals(normalized_observations))
            ],
        },
        "candidate_scoring": {
            "applied": bool(
                status == BehavioralEvidenceGainPlannerStatus.READY
                and normalized_observations
            ),
            "selection_method": ("MAX_TOTAL_STRUCTURAL_GAIN_AFTER_PARETO_DOMINANCE"),
            "learned_weights": False,
            "fixed_width_threshold": False,
            "fixed_transaction_length": False,
            "mandatory_coverage_reset": False,
            "records": [
                _candidate_score_payload(
                    score,
                    on_pareto_frontier=(score.candidate_index in frontier_indices),
                )
                for score in scores
            ],
            "pareto_frontier_candidate_indices": [
                score.candidate_index for score in frontier
            ],
            "dominated_candidate_count": (len(scores) - len(frontier)),
        },
        "outcome": {
            "localized_boundary_count": (boundary_set.payload["boundaries"]["count"]),
            "exact_failure_region_count": len(exact_regions),
            "boundary_set_sha256": (boundary_set.sha256),
            "next_proposal": (proposal_payload),
        },
        "evidence_boundary": {
            "failure_family_observation_reused": True,
            "failure_family_boundary_set_reused": True,
            "unified_experiment_protocol_is_execution_envelope_authority": True,
            "parallel_execution_protocol_created": False,
            "hidden_true_topology_access": False,
            "future_verdict_access": False,
            "probability_model_used": False,
            "closed_864_corpus_used": False,
            "run05_used": False,
            "model_inference_performed": False,
            "asr_execution_performed": False,
            "planner_performance_evaluated": False,
            "behavioral_performance_qualified": False,
            "real_ai_generalization_established": False,
        },
    }

    return BehavioralEvidenceGainPlannerBundle(
        payload=payload,
        sha256=(calculate_behavioral_evidence_gain_planner_sha256(payload)),
    )


def _observation_from_payload(
    payload: dict[str, object],
) -> FailureFamilyObservation:
    from hvee.core.decision import DecisionVerdict

    return FailureFamilyObservation(
        sequence=int(payload["sequence"]),
        candidate_index=int(payload["candidate_index"]),
        verdict=DecisionVerdict(payload["verdict"]),
        source=FailureFamilyObservationSource(payload["source"]),
        cost_units=int(payload["cost_units"]),
        scenario_sha256=str(payload["scenario_sha256"]),
        result_provenance_sha256=str(payload["result_provenance_sha256"]),
        observation_evidence_sha256=str(payload["observation_evidence_sha256"]),
        decision_evidence_sha256=str(payload["decision_evidence_sha256"]),
        counterexample_evidence_sha256=(
            None
            if payload["counterexample_evidence_sha256"] is None
            else str(payload["counterexample_evidence_sha256"])
        ),
    )


def verify_behavioral_evidence_gain_planner_bundle(
    *,
    payload: dict[str, object],
    expected_sha256: str,
) -> bool:
    try:
        _require_sha256(
            expected_sha256,
            field="expected planner SHA-256",
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        expected_fields = {
            "schema_version",
            "type",
            "evaluation_type",
            "planner",
            "boundary_contract",
            "axis",
            "invariants",
            "budget",
            "observations",
            "state",
            "candidate_scoring",
            "outcome",
            "evidence_boundary",
        }

        if set(payload) != expected_fields:
            return False

        if payload["schema_version"] != BEHAVIORAL_EVIDENCE_GAIN_PLANNER_SCHEMA_VERSION:
            return False

        if payload["type"] != "behavioral_evidence_gain_planner":
            return False

        planner = payload["planner"]

        boundary_contract = payload["boundary_contract"]

        axis = payload["axis"]

        invariants = payload["invariants"]

        budget = payload["budget"]

        observation_payloads = payload["observations"]

        if not isinstance(
            planner,
            dict,
        ):
            return False

        if not isinstance(
            boundary_contract,
            dict,
        ):
            return False

        if not isinstance(
            axis,
            dict,
        ):
            return False

        if not isinstance(
            invariants,
            dict,
        ):
            return False

        if not isinstance(
            budget,
            dict,
        ):
            return False

        if not isinstance(
            observation_payloads,
            list,
        ):
            return False

        observations = [
            _observation_from_payload(item) for item in observation_payloads
        ]

        rebuilt = build_behavioral_evidence_gain_planner_bundle(
            evaluation_type=(payload["evaluation_type"]),
            planner_key=(planner["key"]),
            planner_version=(planner["version"]),
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

    except (
        HveeContractError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return False

    if rebuilt.payload != payload:
        return False

    if rebuilt.sha256 != expected_sha256:
        return False

    return True
