"""Deterministic, budget-bounded adaptive scenario search evidence.

The search operates over a finite ordered grid on one numeric axis.  It
proposes the lower endpoint, then the upper endpoint, and subsequently
bisects either the narrowest observed pass/fail bracket or the widest
unexplored same-verdict gap.  Every accepted observation must match the
proposal that was deterministically implied by the preceding observations.

Proposals are not observations.  Only entries carrying immutable execution,
observation, and decision evidence are treated as executed scenarios.  The
contract makes no claim about unexecuted outcomes, causality, minimality, or
qualification authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict
from hvee.core.observed_boundary import (
    ObservedBoundaryBundle,
    ObservedBoundaryEndpoint,
    build_observed_boundary_bundle,
)


ADAPTIVE_SCENARIO_SEARCH_SCHEMA_VERSION = 1

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)

_EVIDENCE_BOUNDARY = {
    "observations_require_execution_evidence": True,
    "next_proposal_is_an_observation": False,
    "unexecuted_outcomes_inferred": False,
    "causal_explanation_claimed": False,
    "minimality_claimed": False,
    "qualification_authority": False,
}


class AdaptiveSearchStatus(StrEnum):
    READY = "ready"
    BOUNDARY_BRACKETED = "boundary_bracketed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANDIDATE_GRID_EXHAUSTED = "candidate_grid_exhausted"


class AdaptiveProposalReason(StrEnum):
    INITIAL_LOWER = "initial_lower"
    INITIAL_UPPER = "initial_upper"
    REFINE_OBSERVED_BRACKET = "refine_observed_bracket"
    EXPLORE_LARGEST_GAP = "explore_largest_gap"


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or _IDENTIFIER_PATTERN.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )

    return value


def _require_non_empty_string(
    *,
    name: str,
    value: object,
    max_length: int = 200,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > max_length
    ):
        raise HveeContractError(
            f"{name} must be a non-empty trimmed string "
            f"of at most {max_length} characters"
        )

    return value


def _require_sha256_hex(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 hex digest"
        )

    return value


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return json.loads(serialized)
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def _canonical_json(
    value: object,
    *,
    name: str,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def _calculate_sha256(
    value: object,
    *,
    name: str,
) -> str:
    canonical = _canonical_json(
        value,
        name=name,
    )
    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _canonical_scalar_parameters(
    value: object,
    *,
    name: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HveeContractError(
            f"{name} must be a JSON object"
        )

    normalized: dict[str, object] = {}

    for key, parameter in value.items():
        normalized_key = _require_identifier(
            name=f"{name} key",
            value=key,
        )

        if parameter is None or isinstance(
            parameter,
            (bool, int, str),
        ):
            normalized_parameter = parameter
        elif isinstance(parameter, float):
            if not math.isfinite(parameter):
                raise HveeContractError(
                    f"numeric {name} values must be finite"
                )
            normalized_parameter = parameter
        else:
            raise HveeContractError(
                f"{name} must contain scalar JSON values"
            )

        if isinstance(normalized_parameter, str):
            _require_non_empty_string(
                name=f"string {name} value",
                value=normalized_parameter,
            )

        normalized[normalized_key] = normalized_parameter

    canonical = _canonical_json_value(
        normalized,
        name=name,
    )

    if not isinstance(canonical, dict):
        raise HveeContractError(
            f"{name} must be a JSON object"
        )

    return canonical


def _normalize_axis_value(
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise HveeContractError(
            "adaptive search candidate values must be finite numbers"
        )

    normalized = float(value)
    return 0.0 if normalized == 0.0 else normalized


def _canonical_candidate_values(
    value: object,
) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise HveeContractError(
            "adaptive search requires at least two candidate values"
        )

    normalized = tuple(
        _normalize_axis_value(candidate)
        for candidate in value
    )

    for lower, upper in zip(normalized, normalized[1:]):
        width = upper - lower
        if lower >= upper or not math.isfinite(width):
            raise HveeContractError(
                "adaptive search candidate values must be strictly "
                "increasing, unique, and separated by finite widths"
            )

    if not math.isfinite(normalized[-1] - normalized[0]):
        raise HveeContractError(
            "adaptive search candidate span must be finite"
        )

    return normalized


@dataclass(frozen=True, slots=True)
class AdaptiveScenarioObservation:
    """One actually executed observation in the adaptive trajectory."""

    sequence: int
    candidate_index: int
    scenario_sha256: str
    verdict: DecisionVerdict
    result_provenance_sha256: str
    observation_evidence_sha256: str
    decision_evidence_sha256: str
    counterexample_evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 1
        ):
            raise HveeContractError(
                "adaptive observation sequence must be a positive integer"
            )

        if (
            isinstance(self.candidate_index, bool)
            or not isinstance(self.candidate_index, int)
            or self.candidate_index < 0
        ):
            raise HveeContractError(
                "adaptive observation candidate index must be "
                "a non-negative integer"
            )

        for name, value in (
            ("scenario SHA-256", self.scenario_sha256),
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
            _require_sha256_hex(
                name=name,
                value=value,
            )

        if self.verdict not in {
            DecisionVerdict.PASS,
            DecisionVerdict.FAIL,
        }:
            raise HveeContractError(
                "adaptive observations require pass or fail verdicts"
            )

        if self.verdict == DecisionVerdict.FAIL:
            _require_sha256_hex(
                name="counterexample evidence SHA-256",
                value=self.counterexample_evidence_sha256,
            )
        elif self.counterexample_evidence_sha256 is not None:
            raise HveeContractError(
                "passing adaptive observations cannot reference "
                "counterexample evidence"
            )


@dataclass(frozen=True, slots=True)
class AdaptiveScenarioSearchBundle:
    payload: dict[str, object]
    candidate_values_sha256: str
    invariant_parameters_sha256: str
    sha256: str
    observed_boundary: ObservedBoundaryBundle | None

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "adaptive scenario search payload must be a JSON object"
            )

        for name, value in (
            (
                "candidate values SHA-256",
                self.candidate_values_sha256,
            ),
            (
                "invariant parameters SHA-256",
                self.invariant_parameters_sha256,
            ),
            (
                "adaptive search SHA-256",
                self.sha256,
            ),
        ):
            _require_sha256_hex(
                name=name,
                value=value,
            )

        if (
            self.observed_boundary is not None
            and not isinstance(
                self.observed_boundary,
                ObservedBoundaryBundle,
            )
        ):
            raise HveeContractError(
                "observed boundary must be a canonical boundary bundle"
            )


@dataclass(frozen=True, slots=True)
class _Proposal:
    candidate_index: int
    reason: AdaptiveProposalReason


def calculate_candidate_values_sha256(
    candidate_values: list[int | float]
    | tuple[int | float, ...],
) -> str:
    normalized = _canonical_candidate_values(
        candidate_values
    )
    return _calculate_sha256(
        list(normalized),
        name="adaptive search candidate values",
    )


def calculate_adaptive_scenario_search_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="adaptive scenario search evidence",
    )


def _select_observed_bracket(
    observations: tuple[AdaptiveScenarioObservation, ...],
) -> tuple[
    AdaptiveScenarioObservation,
    AdaptiveScenarioObservation,
] | None:
    by_index = sorted(
        observations,
        key=lambda observation: observation.candidate_index,
    )
    candidates: list[
        tuple[
            int,
            int,
            AdaptiveScenarioObservation,
            AdaptiveScenarioObservation,
        ]
    ] = []

    for lower, upper in zip(by_index, by_index[1:]):
        if lower.verdict != upper.verdict:
            candidates.append(
                (
                    upper.candidate_index - lower.candidate_index,
                    lower.candidate_index,
                    lower,
                    upper,
                )
            )

    if not candidates:
        return None

    _, _, lower, upper = min(candidates)
    return lower, upper


def _derive_search_state(
    *,
    candidate_count: int,
    maximum_observations: int,
    observations: tuple[AdaptiveScenarioObservation, ...],
) -> tuple[
    AdaptiveSearchStatus,
    tuple[
        AdaptiveScenarioObservation,
        AdaptiveScenarioObservation,
    ] | None,
    _Proposal | None,
]:
    bracket = _select_observed_bracket(observations)

    if bracket is not None:
        lower, upper = bracket
        gap = upper.candidate_index - lower.candidate_index

        if gap == 1:
            return (
                AdaptiveSearchStatus.BOUNDARY_BRACKETED,
                bracket,
                None,
            )

    if len(observations) == candidate_count:
        return (
            AdaptiveSearchStatus.CANDIDATE_GRID_EXHAUSTED,
            bracket,
            None,
        )

    if len(observations) >= maximum_observations:
        return (
            AdaptiveSearchStatus.BUDGET_EXHAUSTED,
            bracket,
            None,
        )

    if not observations:
        return (
            AdaptiveSearchStatus.READY,
            bracket,
            _Proposal(
                candidate_index=0,
                reason=AdaptiveProposalReason.INITIAL_LOWER,
            ),
        )

    if len(observations) == 1:
        return (
            AdaptiveSearchStatus.READY,
            bracket,
            _Proposal(
                candidate_index=candidate_count - 1,
                reason=AdaptiveProposalReason.INITIAL_UPPER,
            ),
        )

    if bracket is not None:
        lower, upper = bracket
        return (
            AdaptiveSearchStatus.READY,
            bracket,
            _Proposal(
                candidate_index=(
                    lower.candidate_index
                    + upper.candidate_index
                )
                // 2,
                reason=(
                    AdaptiveProposalReason.REFINE_OBSERVED_BRACKET
                ),
            ),
        )

    ordered = sorted(
        observations,
        key=lambda observation: observation.candidate_index,
    )
    gaps = [
        (
            upper.candidate_index - lower.candidate_index,
            lower.candidate_index,
            upper.candidate_index,
        )
        for lower, upper in zip(ordered, ordered[1:])
        if upper.candidate_index - lower.candidate_index > 1
    ]

    if not gaps:
        return (
            AdaptiveSearchStatus.CANDIDATE_GRID_EXHAUSTED,
            bracket,
            None,
        )

    largest_gap = max(gap for gap, _, _ in gaps)
    _, lower_index, upper_index = min(
        gap
        for gap in gaps
        if gap[0] == largest_gap
    )

    return (
        AdaptiveSearchStatus.READY,
        bracket,
        _Proposal(
            candidate_index=(lower_index + upper_index) // 2,
            reason=AdaptiveProposalReason.EXPLORE_LARGEST_GAP,
        ),
    )


def _observation_payload(
    *,
    observation: AdaptiveScenarioObservation,
    candidate_values: tuple[float, ...],
) -> dict[str, object]:
    return {
        "sequence": observation.sequence,
        "candidate_index": observation.candidate_index,
        "axis_value": candidate_values[
            observation.candidate_index
        ],
        "scenario_sha256": observation.scenario_sha256,
        "verdict": observation.verdict.value,
        "evidence": {
            "result_provenance_sha256": (
                observation.result_provenance_sha256
            ),
            "observation_evidence_sha256": (
                observation.observation_evidence_sha256
            ),
            "decision_evidence_sha256": (
                observation.decision_evidence_sha256
            ),
            "counterexample_evidence_sha256": (
                observation.counterexample_evidence_sha256
            ),
        },
    }


def _bracket_payload(
    *,
    bracket: tuple[
        AdaptiveScenarioObservation,
        AdaptiveScenarioObservation,
    ],
    candidate_values: tuple[float, ...],
) -> dict[str, object]:
    lower, upper = bracket
    lower_value = candidate_values[lower.candidate_index]
    upper_value = candidate_values[upper.candidate_index]
    candidate_gap = upper.candidate_index - lower.candidate_index

    return {
        "lower": {
            "candidate_index": lower.candidate_index,
            "axis_value": lower_value,
            "scenario_sha256": lower.scenario_sha256,
            "verdict": lower.verdict.value,
        },
        "upper": {
            "candidate_index": upper.candidate_index,
            "axis_value": upper_value,
            "scenario_sha256": upper.scenario_sha256,
            "verdict": upper.verdict.value,
        },
        "candidate_gap": candidate_gap,
        "axis_width": upper_value - lower_value,
        "adjacent_candidates": candidate_gap == 1,
    }


def _build_observed_boundary(
    *,
    evaluation_type: str,
    boundary_key: str,
    boundary_version: str,
    search_key: str,
    search_version: str,
    axis_key: str,
    axis_version: str,
    axis_unit: str | None,
    invariant_parameters: dict[str, object],
    candidate_values: tuple[float, ...],
    bracket: tuple[
        AdaptiveScenarioObservation,
        AdaptiveScenarioObservation,
    ],
) -> ObservedBoundaryBundle:
    endpoints = tuple(
        ObservedBoundaryEndpoint(
            axis_value=candidate_values[
                observation.candidate_index
            ],
            scenario_sha256=observation.scenario_sha256,
            verdict=observation.verdict,
            result_provenance_sha256=(
                observation.result_provenance_sha256
            ),
            observation_evidence_sha256=(
                observation.observation_evidence_sha256
            ),
            decision_evidence_sha256=(
                observation.decision_evidence_sha256
            ),
            counterexample_evidence_sha256=(
                observation.counterexample_evidence_sha256
            ),
        )
        for observation in bracket
    )

    return build_observed_boundary_bundle(
        evaluation_type=evaluation_type,
        boundary_key=boundary_key,
        boundary_version=boundary_version,
        search_key=search_key,
        search_version=search_version,
        axis_key=axis_key,
        axis_version=axis_version,
        axis_unit=axis_unit,
        invariant_parameters=invariant_parameters,
        endpoints=endpoints,
    )


def build_adaptive_scenario_search_bundle(
    *,
    evaluation_type: str,
    search_key: str,
    search_version: str,
    boundary_key: str,
    boundary_version: str,
    axis_key: str,
    axis_version: str,
    axis_unit: str | None,
    candidate_values: list[int | float]
    | tuple[int | float, ...],
    invariant_parameters: dict[str, object],
    maximum_observations: int,
    observations: list[AdaptiveScenarioObservation]
    | tuple[AdaptiveScenarioObservation, ...],
) -> AdaptiveScenarioSearchBundle:
    normalized_evaluation_type = _require_identifier(
        name="evaluation type",
        value=evaluation_type,
    )
    normalized_search_key = _require_identifier(
        name="search key",
        value=search_key,
    )
    normalized_search_version = _require_non_empty_string(
        name="search version",
        value=search_version,
        max_length=100,
    )
    normalized_boundary_key = _require_identifier(
        name="boundary key",
        value=boundary_key,
    )
    normalized_boundary_version = _require_non_empty_string(
        name="boundary version",
        value=boundary_version,
        max_length=100,
    )
    normalized_axis_key = _require_identifier(
        name="axis key",
        value=axis_key,
    )
    normalized_axis_version = _require_non_empty_string(
        name="axis version",
        value=axis_version,
        max_length=100,
    )

    normalized_axis_unit: str | None = None
    if axis_unit is not None:
        normalized_axis_unit = _require_non_empty_string(
            name="axis unit",
            value=axis_unit,
            max_length=64,
        )

    normalized_candidates = _canonical_candidate_values(
        candidate_values
    )
    candidate_values_sha256 = _calculate_sha256(
        list(normalized_candidates),
        name="adaptive search candidate values",
    )
    normalized_invariants = _canonical_scalar_parameters(
        invariant_parameters,
        name="adaptive search invariant parameters",
    )
    invariant_parameters_sha256 = _calculate_sha256(
        normalized_invariants,
        name="adaptive search invariant parameters",
    )

    if (
        isinstance(maximum_observations, bool)
        or not isinstance(maximum_observations, int)
        or maximum_observations < 2
        or maximum_observations > len(normalized_candidates)
    ):
        raise HveeContractError(
            "maximum observations must be between two and the "
            "candidate count"
        )

    if (
        not isinstance(observations, (list, tuple))
        or not all(
            isinstance(
                observation,
                AdaptiveScenarioObservation,
            )
            for observation in observations
        )
    ):
        raise HveeContractError(
            "adaptive observations must be a sequence of canonical "
            "observations"
        )

    normalized_observations = tuple(observations)
    accepted: list[AdaptiveScenarioObservation] = []

    for expected_sequence, observation in enumerate(
        normalized_observations,
        start=1,
    ):
        if observation.sequence != expected_sequence:
            raise HveeContractError(
                "adaptive observation sequences must be contiguous "
                "and ordered"
            )

        if observation.candidate_index >= len(normalized_candidates):
            raise HveeContractError(
                "adaptive observation candidate index is outside "
                "the candidate grid"
            )

        _, _, proposal = _derive_search_state(
            candidate_count=len(normalized_candidates),
            maximum_observations=maximum_observations,
            observations=tuple(accepted),
        )

        if proposal is None:
            raise HveeContractError(
                "adaptive observations cannot continue after the "
                "search becomes terminal"
            )

        if observation.candidate_index != proposal.candidate_index:
            raise HveeContractError(
                "adaptive observation does not match the deterministic "
                "proposal trajectory"
            )

        if any(
            prior.scenario_sha256 == observation.scenario_sha256
            for prior in accepted
        ):
            raise HveeContractError(
                "adaptive observations require distinct scenarios"
            )

        accepted.append(observation)

    status, bracket, next_proposal = _derive_search_state(
        candidate_count=len(normalized_candidates),
        maximum_observations=maximum_observations,
        observations=normalized_observations,
    )

    observed_boundary: ObservedBoundaryBundle | None = None
    if status == AdaptiveSearchStatus.BOUNDARY_BRACKETED:
        if bracket is None:
            raise HveeContractError(
                "a bracketed search requires observed endpoints"
            )
        observed_boundary = _build_observed_boundary(
            evaluation_type=normalized_evaluation_type,
            boundary_key=normalized_boundary_key,
            boundary_version=normalized_boundary_version,
            search_key=normalized_search_key,
            search_version=normalized_search_version,
            axis_key=normalized_axis_key,
            axis_version=normalized_axis_version,
            axis_unit=normalized_axis_unit,
            invariant_parameters=normalized_invariants,
            candidate_values=normalized_candidates,
            bracket=bracket,
        )

    proposal_payload: dict[str, object] | None = None
    if next_proposal is not None:
        proposal_payload = {
            "candidate_index": next_proposal.candidate_index,
            "axis_value": normalized_candidates[
                next_proposal.candidate_index
            ],
            "reason": next_proposal.reason.value,
        }

    payload: dict[str, object] = {
        "schema_version": ADAPTIVE_SCENARIO_SEARCH_SCHEMA_VERSION,
        "type": "adaptive_scenario_search",
        "evaluation_type": normalized_evaluation_type,
        "search": {
            "key": normalized_search_key,
            "version": normalized_search_version,
            "status": status.value,
        },
        "boundary_contract": {
            "key": normalized_boundary_key,
            "version": normalized_boundary_version,
        },
        "axis": {
            "key": normalized_axis_key,
            "version": normalized_axis_version,
            "unit": normalized_axis_unit,
            "candidate_values": list(normalized_candidates),
            "candidate_values_sha256": candidate_values_sha256,
        },
        "invariants": {
            "parameters": normalized_invariants,
            "sha256": invariant_parameters_sha256,
        },
        "budget": {
            "maximum_observations": maximum_observations,
            "observed_count": len(normalized_observations),
            "remaining_observations": (
                maximum_observations
                - len(normalized_observations)
            ),
        },
        "observations": [
            _observation_payload(
                observation=observation,
                candidate_values=normalized_candidates,
            )
            for observation in normalized_observations
        ],
        "outcome": {
            "observed_bracket": (
                _bracket_payload(
                    bracket=bracket,
                    candidate_values=normalized_candidates,
                )
                if bracket is not None
                else None
            ),
            "next_proposal": proposal_payload,
            "observed_boundary_sha256": (
                observed_boundary.sha256
                if observed_boundary is not None
                else None
            ),
        },
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="adaptive scenario search evidence",
    )

    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "adaptive scenario search must be a JSON object"
        )

    return AdaptiveScenarioSearchBundle(
        payload=canonical_payload,
        candidate_values_sha256=candidate_values_sha256,
        invariant_parameters_sha256=(
            invariant_parameters_sha256
        ),
        sha256=calculate_adaptive_scenario_search_sha256(
            canonical_payload
        ),
        observed_boundary=observed_boundary,
    )


def _parse_observation(
    value: object,
) -> AdaptiveScenarioObservation:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "sequence",
            "candidate_index",
            "axis_value",
            "scenario_sha256",
            "verdict",
            "evidence",
        }
    ):
        raise HveeContractError(
            "invalid adaptive observation shape"
        )

    evidence = value.get("evidence")
    if (
        not isinstance(evidence, dict)
        or set(evidence)
        != {
            "result_provenance_sha256",
            "observation_evidence_sha256",
            "decision_evidence_sha256",
            "counterexample_evidence_sha256",
        }
    ):
        raise HveeContractError(
            "invalid adaptive observation evidence"
        )

    _normalize_axis_value(value.get("axis_value"))

    return AdaptiveScenarioObservation(
        sequence=value.get("sequence"),
        candidate_index=value.get("candidate_index"),
        scenario_sha256=value.get("scenario_sha256"),
        verdict=DecisionVerdict(value.get("verdict")),
        result_provenance_sha256=evidence.get(
            "result_provenance_sha256"
        ),
        observation_evidence_sha256=evidence.get(
            "observation_evidence_sha256"
        ),
        decision_evidence_sha256=evidence.get(
            "decision_evidence_sha256"
        ),
        counterexample_evidence_sha256=evidence.get(
            "counterexample_evidence_sha256"
        ),
    )


def verify_adaptive_scenario_search_bundle(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "schema_version",
                "type",
                "evaluation_type",
                "search",
                "boundary_contract",
                "axis",
                "invariants",
                "budget",
                "observations",
                "outcome",
                "evidence_boundary",
            }
            or payload.get("schema_version")
            != ADAPTIVE_SCENARIO_SEARCH_SCHEMA_VERSION
            or payload.get("type")
            != "adaptive_scenario_search"
            or payload.get("evidence_boundary")
            != _EVIDENCE_BOUNDARY
        ):
            return False

        search = payload.get("search")
        boundary_contract = payload.get("boundary_contract")
        axis = payload.get("axis")
        invariants = payload.get("invariants")
        budget = payload.get("budget")
        observations_payload = payload.get("observations")
        outcome = payload.get("outcome")

        if (
            not isinstance(search, dict)
            or set(search) != {"key", "version", "status"}
            or not isinstance(boundary_contract, dict)
            or set(boundary_contract) != {"key", "version"}
            or not isinstance(axis, dict)
            or set(axis)
            != {
                "key",
                "version",
                "unit",
                "candidate_values",
                "candidate_values_sha256",
            }
            or not isinstance(invariants, dict)
            or set(invariants) != {"parameters", "sha256"}
            or not isinstance(budget, dict)
            or set(budget)
            != {
                "maximum_observations",
                "observed_count",
                "remaining_observations",
            }
            or not isinstance(observations_payload, list)
            or not isinstance(outcome, dict)
            or set(outcome)
            != {
                "observed_bracket",
                "next_proposal",
                "observed_boundary_sha256",
            }
        ):
            return False

        observations = tuple(
            _parse_observation(observation)
            for observation in observations_payload
        )

        rebuilt = build_adaptive_scenario_search_bundle(
            evaluation_type=payload.get("evaluation_type"),
            search_key=search.get("key"),
            search_version=search.get("version"),
            boundary_key=boundary_contract.get("key"),
            boundary_version=boundary_contract.get("version"),
            axis_key=axis.get("key"),
            axis_version=axis.get("version"),
            axis_unit=axis.get("unit"),
            candidate_values=axis.get("candidate_values"),
            invariant_parameters=invariants.get("parameters"),
            maximum_observations=budget.get(
                "maximum_observations"
            ),
            observations=observations,
        )

        stored_candidate_sha256 = _require_sha256_hex(
            name="stored candidate values SHA-256",
            value=axis.get("candidate_values_sha256"),
        )
        stored_invariant_sha256 = _require_sha256_hex(
            name="stored invariant parameters SHA-256",
            value=invariants.get("sha256"),
        )
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected adaptive search SHA-256",
            value=expected_sha256,
        )

        return (
            payload == rebuilt.payload
            and search.get("status")
            == rebuilt.payload["search"]["status"]
            and stored_candidate_sha256
            == rebuilt.candidate_values_sha256
            and stored_invariant_sha256
            == rebuilt.invariant_parameters_sha256
            and normalized_expected_sha256
            == rebuilt.sha256
        )

    except (
        HveeContractError,
        IndexError,
        TypeError,
        ValueError,
    ):
        return False
