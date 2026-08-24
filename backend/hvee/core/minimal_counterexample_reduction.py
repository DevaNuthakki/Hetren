"""Deterministic evidence for execution-backed counterexample reduction.

The reducer operates over an explicitly declared, ordered set of removable
units.  It attempts to remove one retained unit at a time.  A failing
candidate is accepted as the new current counterexample and restarts the
scan; a passing candidate is rejected and advances the scan.  Completion
proves only one-minimality within the declared units: removing any single
remaining unit was observed to pass in the current reduced context.

Proposals are not observations.  Every recorded attempt carries immutable
execution, observation, and decision evidence.  The contract does not claim
global minimality, causality, unexplored outcomes, or qualification authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict


MINIMAL_COUNTEREXAMPLE_REDUCTION_SCHEMA_VERSION = 1

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)

_EVIDENCE_BOUNDARY = {
    "source_failure_observed": True,
    "attempts_require_execution_evidence": True,
    "next_proposal_is_an_observation": False,
    "minimality_scope": "one_minimal_within_declared_units",
    "global_minimality_claimed": False,
    "unexecuted_outcomes_inferred": False,
    "causal_explanation_claimed": False,
    "neighborhood_explored": False,
    "contract_promoted": False,
    "raw_content_embedded": False,
    "qualification_authority": False,
}


class MinimalReductionStatus(StrEnum):
    READY = "ready"
    ONE_MINIMAL = "one_minimal"
    BUDGET_EXHAUSTED = "budget_exhausted"


class MinimalReductionProposalReason(StrEnum):
    INITIAL_SCAN = "initial_scan"
    CONTINUE_SCAN = "continue_scan"
    RESTART_AFTER_ACCEPTED_REDUCTION = (
        "restart_after_accepted_reduction"
    )


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


@dataclass(frozen=True, slots=True)
class CounterexampleReductionUnit:
    """One removable unit committed without embedding its raw content."""

    key: str
    version: str
    content_sha256: str

    def __post_init__(self) -> None:
        _require_identifier(
            name="counterexample reduction unit key",
            value=self.key,
        )
        _require_non_empty_string(
            name="counterexample reduction unit version",
            value=self.version,
            max_length=100,
        )
        _require_sha256_hex(
            name="counterexample reduction unit content SHA-256",
            value=self.content_sha256,
        )

    @property
    def identity(self) -> tuple[str, str, str]:
        return (
            self.key,
            self.version,
            self.content_sha256,
        )


@dataclass(frozen=True, slots=True)
class CounterexampleReductionObservation:
    """One executed candidate produced by the deterministic reducer."""

    sequence: int
    removed_unit_index: int
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
                "counterexample reduction observation sequence must be "
                "a positive integer"
            )

        if (
            isinstance(self.removed_unit_index, bool)
            or not isinstance(self.removed_unit_index, int)
            or self.removed_unit_index < 0
        ):
            raise HveeContractError(
                "removed unit index must be a non-negative integer"
            )

        for name, value in (
            ("candidate scenario SHA-256", self.scenario_sha256),
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
                "counterexample reduction observations require pass or "
                "fail verdicts"
            )

        if self.verdict == DecisionVerdict.FAIL:
            _require_sha256_hex(
                name="counterexample evidence SHA-256",
                value=self.counterexample_evidence_sha256,
            )
        elif self.counterexample_evidence_sha256 is not None:
            raise HveeContractError(
                "passing reduction observations cannot reference "
                "counterexample evidence"
            )


@dataclass(frozen=True, slots=True)
class MinimalCounterexampleReductionBundle:
    payload: dict[str, object]
    reduction_units_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "minimal counterexample reduction payload must be "
                "a JSON object"
            )

        _require_sha256_hex(
            name="reduction units SHA-256",
            value=self.reduction_units_sha256,
        )
        _require_sha256_hex(
            name="minimal counterexample reduction SHA-256",
            value=self.sha256,
        )


@dataclass(frozen=True, slots=True)
class _ReductionProposal:
    removed_unit_index: int
    retained_unit_indices: tuple[int, ...]
    parent_scenario_sha256: str
    parent_counterexample_evidence_sha256: str
    reason: MinimalReductionProposalReason


@dataclass(frozen=True, slots=True)
class _ReductionState:
    status: MinimalReductionStatus
    current_scenario_sha256: str
    current_counterexample_evidence_sha256: str
    retained_unit_indices: tuple[int, ...]
    scan_position: int
    accepted_reduction_count: int
    rejected_reduction_count: int
    proposal: _ReductionProposal | None


def _unit_payload(
    *,
    index: int,
    unit: CounterexampleReductionUnit,
) -> dict[str, object]:
    return {
        "index": index,
        "key": unit.key,
        "version": unit.version,
        "content_sha256": unit.content_sha256,
    }


def _canonical_reduction_units(
    value: object,
) -> tuple[CounterexampleReductionUnit, ...]:
    if (
        not isinstance(value, (list, tuple))
        or not value
        or not all(
            isinstance(unit, CounterexampleReductionUnit)
            for unit in value
        )
    ):
        raise HveeContractError(
            "counterexample reduction requires an ordered sequence of "
            "reduction units"
        )

    normalized = tuple(value)
    identities = tuple(unit.identity for unit in normalized)
    keys = tuple(unit.key for unit in normalized)

    if len(identities) != len(set(identities)):
        raise HveeContractError(
            "counterexample reduction unit identities must be unique"
        )

    if len(keys) != len(set(keys)):
        raise HveeContractError(
            "counterexample reduction unit keys must be unique"
        )

    return normalized


def calculate_reduction_units_sha256(
    units: list[CounterexampleReductionUnit]
    | tuple[CounterexampleReductionUnit, ...],
) -> str:
    normalized = _canonical_reduction_units(units)
    return _calculate_sha256(
        [
            _unit_payload(index=index, unit=unit)
            for index, unit in enumerate(normalized)
        ],
        name="counterexample reduction units",
    )


def calculate_minimal_counterexample_reduction_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="minimal counterexample reduction evidence",
    )


def _derive_reduction_state(
    *,
    unit_count: int,
    maximum_observations: int,
    source_scenario_sha256: str,
    source_counterexample_evidence_sha256: str,
    observations: tuple[CounterexampleReductionObservation, ...],
) -> _ReductionState:
    retained = tuple(range(unit_count))
    scan_position = 0
    current_scenario_sha256 = source_scenario_sha256
    current_counterexample_evidence_sha256 = (
        source_counterexample_evidence_sha256
    )
    accepted_count = 0
    rejected_count = 0

    for observation in observations:
        if scan_position >= len(retained):
            raise HveeContractError(
                "counterexample reduction observations cannot continue "
                "after one-minimality is established"
            )

        expected_removed_index = retained[scan_position]
        if observation.removed_unit_index != expected_removed_index:
            raise HveeContractError(
                "counterexample reduction observation does not match "
                "the deterministic proposal trajectory"
            )

        if observation.scenario_sha256 == current_scenario_sha256:
            raise HveeContractError(
                "a reduction candidate must differ from its parent "
                "scenario"
            )

        if observation.verdict == DecisionVerdict.FAIL:
            retained = tuple(
                index
                for index in retained
                if index != expected_removed_index
            )
            current_scenario_sha256 = observation.scenario_sha256
            current_counterexample_evidence_sha256 = (
                observation.counterexample_evidence_sha256
            )
            scan_position = 0
            accepted_count += 1
        else:
            scan_position += 1
            rejected_count += 1

    if scan_position >= len(retained):
        return _ReductionState(
            status=MinimalReductionStatus.ONE_MINIMAL,
            current_scenario_sha256=current_scenario_sha256,
            current_counterexample_evidence_sha256=(
                current_counterexample_evidence_sha256
            ),
            retained_unit_indices=retained,
            scan_position=scan_position,
            accepted_reduction_count=accepted_count,
            rejected_reduction_count=rejected_count,
            proposal=None,
        )

    if len(observations) >= maximum_observations:
        return _ReductionState(
            status=MinimalReductionStatus.BUDGET_EXHAUSTED,
            current_scenario_sha256=current_scenario_sha256,
            current_counterexample_evidence_sha256=(
                current_counterexample_evidence_sha256
            ),
            retained_unit_indices=retained,
            scan_position=scan_position,
            accepted_reduction_count=accepted_count,
            rejected_reduction_count=rejected_count,
            proposal=None,
        )

    reason = MinimalReductionProposalReason.CONTINUE_SCAN
    if not observations:
        reason = MinimalReductionProposalReason.INITIAL_SCAN
    elif observations[-1].verdict == DecisionVerdict.FAIL:
        reason = (
            MinimalReductionProposalReason.RESTART_AFTER_ACCEPTED_REDUCTION
        )

    removed_index = retained[scan_position]
    candidate_retained = tuple(
        index
        for index in retained
        if index != removed_index
    )

    return _ReductionState(
        status=MinimalReductionStatus.READY,
        current_scenario_sha256=current_scenario_sha256,
        current_counterexample_evidence_sha256=(
            current_counterexample_evidence_sha256
        ),
        retained_unit_indices=retained,
        scan_position=scan_position,
        accepted_reduction_count=accepted_count,
        rejected_reduction_count=rejected_count,
        proposal=_ReductionProposal(
            removed_unit_index=removed_index,
            retained_unit_indices=candidate_retained,
            parent_scenario_sha256=current_scenario_sha256,
            parent_counterexample_evidence_sha256=(
                current_counterexample_evidence_sha256
            ),
            reason=reason,
        ),
    )


def _proposal_payload(
    *,
    proposal: _ReductionProposal,
    units: tuple[CounterexampleReductionUnit, ...],
) -> dict[str, object]:
    removed_unit = units[proposal.removed_unit_index]
    return {
        "reason": proposal.reason.value,
        "removed_unit": _unit_payload(
            index=proposal.removed_unit_index,
            unit=removed_unit,
        ),
        "retained_unit_indices": list(
            proposal.retained_unit_indices
        ),
        "parent_scenario_sha256": (
            proposal.parent_scenario_sha256
        ),
        "parent_counterexample_evidence_sha256": (
            proposal.parent_counterexample_evidence_sha256
        ),
    }


def _observation_payload(
    *,
    observation: CounterexampleReductionObservation,
    proposal: _ReductionProposal,
    units: tuple[CounterexampleReductionUnit, ...],
) -> dict[str, object]:
    return {
        "sequence": observation.sequence,
        "proposal": _proposal_payload(
            proposal=proposal,
            units=units,
        ),
        "candidate": {
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
        },
        "accepted": observation.verdict == DecisionVerdict.FAIL,
    }


def build_minimal_counterexample_reduction_bundle(
    *,
    evaluation_type: str,
    reduction_key: str,
    reduction_version: str,
    source_scenario_sha256: str,
    source_counterexample_evidence_sha256: str,
    units: list[CounterexampleReductionUnit]
    | tuple[CounterexampleReductionUnit, ...],
    maximum_observations: int,
    observations: list[CounterexampleReductionObservation]
    | tuple[CounterexampleReductionObservation, ...],
) -> MinimalCounterexampleReductionBundle:
    normalized_evaluation_type = _require_identifier(
        name="evaluation type",
        value=evaluation_type,
    )
    normalized_reduction_key = _require_identifier(
        name="counterexample reduction key",
        value=reduction_key,
    )
    normalized_reduction_version = _require_non_empty_string(
        name="counterexample reduction version",
        value=reduction_version,
        max_length=100,
    )
    normalized_source_scenario_sha256 = _require_sha256_hex(
        name="source scenario SHA-256",
        value=source_scenario_sha256,
    )
    normalized_source_counterexample_sha256 = _require_sha256_hex(
        name="source counterexample evidence SHA-256",
        value=source_counterexample_evidence_sha256,
    )
    normalized_units = _canonical_reduction_units(units)
    reduction_units_sha256 = calculate_reduction_units_sha256(
        normalized_units
    )
    theoretical_maximum = (
        len(normalized_units) * (len(normalized_units) + 1) // 2
    )

    if (
        isinstance(maximum_observations, bool)
        or not isinstance(maximum_observations, int)
        or maximum_observations < 1
        or maximum_observations > theoretical_maximum
    ):
        raise HveeContractError(
            "maximum observations must be between one and the "
            "theoretical reduction maximum"
        )

    if (
        not isinstance(observations, (list, tuple))
        or not all(
            isinstance(
                observation,
                CounterexampleReductionObservation,
            )
            for observation in observations
        )
    ):
        raise HveeContractError(
            "counterexample reduction observations must be a sequence "
            "of canonical observations"
        )

    normalized_observations = tuple(observations)
    accepted: list[CounterexampleReductionObservation] = []
    observation_payloads: list[dict[str, object]] = []

    for expected_sequence, observation in enumerate(
        normalized_observations,
        start=1,
    ):
        if observation.sequence != expected_sequence:
            raise HveeContractError(
                "counterexample reduction observation sequences must be "
                "contiguous and ordered"
            )

        prior_state = _derive_reduction_state(
            unit_count=len(normalized_units),
            maximum_observations=maximum_observations,
            source_scenario_sha256=(
                normalized_source_scenario_sha256
            ),
            source_counterexample_evidence_sha256=(
                normalized_source_counterexample_sha256
            ),
            observations=tuple(accepted),
        )

        if prior_state.proposal is None:
            raise HveeContractError(
                "counterexample reduction observations cannot continue "
                "after the reduction becomes terminal"
            )

        if (
            observation.removed_unit_index
            != prior_state.proposal.removed_unit_index
        ):
            raise HveeContractError(
                "counterexample reduction observation does not match "
                "the deterministic proposal trajectory"
            )

        if observation.scenario_sha256 in {
            normalized_source_scenario_sha256,
            *(
                prior.scenario_sha256
                for prior in accepted
            ),
        }:
            raise HveeContractError(
                "counterexample reduction observations require "
                "distinct candidate scenarios"
            )

        observation_payloads.append(
            _observation_payload(
                observation=observation,
                proposal=prior_state.proposal,
                units=normalized_units,
            )
        )
        accepted.append(observation)

    state = _derive_reduction_state(
        unit_count=len(normalized_units),
        maximum_observations=maximum_observations,
        source_scenario_sha256=normalized_source_scenario_sha256,
        source_counterexample_evidence_sha256=(
            normalized_source_counterexample_sha256
        ),
        observations=normalized_observations,
    )
    retained_set = set(state.retained_unit_indices)
    removed_indices = tuple(
        index
        for index in range(len(normalized_units))
        if index not in retained_set
    )

    payload: dict[str, object] = {
        "schema_version": (
            MINIMAL_COUNTEREXAMPLE_REDUCTION_SCHEMA_VERSION
        ),
        "type": "minimal_counterexample_reduction",
        "evaluation_type": normalized_evaluation_type,
        "reduction": {
            "key": normalized_reduction_key,
            "version": normalized_reduction_version,
            "status": state.status.value,
        },
        "source": {
            "scenario_sha256": normalized_source_scenario_sha256,
            "counterexample_evidence_sha256": (
                normalized_source_counterexample_sha256
            ),
        },
        "units": {
            "ordered": [
                _unit_payload(index=index, unit=unit)
                for index, unit in enumerate(normalized_units)
            ],
            "sha256": reduction_units_sha256,
        },
        "budget": {
            "maximum_observations": maximum_observations,
            "theoretical_maximum_observations": theoretical_maximum,
            "observed_count": len(normalized_observations),
            "remaining_observations": (
                maximum_observations
                - len(normalized_observations)
            ),
        },
        "observations": observation_payloads,
        "outcome": {
            "current_scenario_sha256": (
                state.current_scenario_sha256
            ),
            "current_counterexample_evidence_sha256": (
                state.current_counterexample_evidence_sha256
            ),
            "retained_unit_indices": list(
                state.retained_unit_indices
            ),
            "retained_unit_keys": [
                normalized_units[index].key
                for index in state.retained_unit_indices
            ],
            "removed_unit_indices": list(removed_indices),
            "removed_unit_keys": [
                normalized_units[index].key
                for index in removed_indices
            ],
            "accepted_reduction_count": (
                state.accepted_reduction_count
            ),
            "rejected_reduction_count": (
                state.rejected_reduction_count
            ),
            "one_minimal_within_declared_units": (
                state.status == MinimalReductionStatus.ONE_MINIMAL
            ),
            "next_proposal": (
                _proposal_payload(
                    proposal=state.proposal,
                    units=normalized_units,
                )
                if state.proposal is not None
                else None
            ),
        },
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="minimal counterexample reduction evidence",
    )

    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "minimal counterexample reduction must be a JSON object"
        )

    return MinimalCounterexampleReductionBundle(
        payload=canonical_payload,
        reduction_units_sha256=reduction_units_sha256,
        sha256=(
            calculate_minimal_counterexample_reduction_sha256(
                canonical_payload
            )
        ),
    )


def _parse_unit(
    value: object,
    *,
    expected_index: int,
) -> CounterexampleReductionUnit:
    if (
        not isinstance(value, dict)
        or set(value)
        != {"index", "key", "version", "content_sha256"}
        or value.get("index") != expected_index
    ):
        raise HveeContractError(
            "invalid counterexample reduction unit shape"
        )

    return CounterexampleReductionUnit(
        key=value.get("key"),
        version=value.get("version"),
        content_sha256=value.get("content_sha256"),
    )


def _parse_observation(
    value: object,
) -> CounterexampleReductionObservation:
    if (
        not isinstance(value, dict)
        or set(value)
        != {"sequence", "proposal", "candidate", "accepted"}
    ):
        raise HveeContractError(
            "invalid counterexample reduction observation shape"
        )

    proposal = value.get("proposal")
    candidate = value.get("candidate")

    if (
        not isinstance(proposal, dict)
        or set(proposal)
        != {
            "reason",
            "removed_unit",
            "retained_unit_indices",
            "parent_scenario_sha256",
            "parent_counterexample_evidence_sha256",
        }
        or not isinstance(candidate, dict)
        or set(candidate) != {"scenario_sha256", "verdict", "evidence"}
    ):
        raise HveeContractError(
            "invalid counterexample reduction proposal or candidate"
        )

    removed_unit = proposal.get("removed_unit")
    evidence = candidate.get("evidence")
    if (
        not isinstance(removed_unit, dict)
        or set(removed_unit)
        != {"index", "key", "version", "content_sha256"}
        or not isinstance(evidence, dict)
        or set(evidence)
        != {
            "result_provenance_sha256",
            "observation_evidence_sha256",
            "decision_evidence_sha256",
            "counterexample_evidence_sha256",
        }
    ):
        raise HveeContractError(
            "invalid counterexample reduction observation evidence"
        )

    return CounterexampleReductionObservation(
        sequence=value.get("sequence"),
        removed_unit_index=removed_unit.get("index"),
        scenario_sha256=candidate.get("scenario_sha256"),
        verdict=DecisionVerdict(candidate.get("verdict")),
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


def verify_minimal_counterexample_reduction_bundle(
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
                "reduction",
                "source",
                "units",
                "budget",
                "observations",
                "outcome",
                "evidence_boundary",
            }
            or payload.get("schema_version")
            != MINIMAL_COUNTEREXAMPLE_REDUCTION_SCHEMA_VERSION
            or payload.get("type")
            != "minimal_counterexample_reduction"
            or payload.get("evidence_boundary") != _EVIDENCE_BOUNDARY
        ):
            return False

        reduction = payload.get("reduction")
        source = payload.get("source")
        units_payload = payload.get("units")
        budget = payload.get("budget")
        observations_payload = payload.get("observations")
        outcome = payload.get("outcome")

        if (
            not isinstance(reduction, dict)
            or set(reduction) != {"key", "version", "status"}
            or not isinstance(source, dict)
            or set(source)
            != {
                "scenario_sha256",
                "counterexample_evidence_sha256",
            }
            or not isinstance(units_payload, dict)
            or set(units_payload) != {"ordered", "sha256"}
            or not isinstance(units_payload.get("ordered"), list)
            or not isinstance(budget, dict)
            or set(budget)
            != {
                "maximum_observations",
                "theoretical_maximum_observations",
                "observed_count",
                "remaining_observations",
            }
            or not isinstance(observations_payload, list)
            or not isinstance(outcome, dict)
            or set(outcome)
            != {
                "current_scenario_sha256",
                "current_counterexample_evidence_sha256",
                "retained_unit_indices",
                "retained_unit_keys",
                "removed_unit_indices",
                "removed_unit_keys",
                "accepted_reduction_count",
                "rejected_reduction_count",
                "one_minimal_within_declared_units",
                "next_proposal",
            }
        ):
            return False

        units = tuple(
            _parse_unit(unit, expected_index=index)
            for index, unit in enumerate(units_payload["ordered"])
        )
        observations = tuple(
            _parse_observation(observation)
            for observation in observations_payload
        )

        rebuilt = build_minimal_counterexample_reduction_bundle(
            evaluation_type=payload.get("evaluation_type"),
            reduction_key=reduction.get("key"),
            reduction_version=reduction.get("version"),
            source_scenario_sha256=source.get("scenario_sha256"),
            source_counterexample_evidence_sha256=source.get(
                "counterexample_evidence_sha256"
            ),
            units=units,
            maximum_observations=budget.get(
                "maximum_observations"
            ),
            observations=observations,
        )

        stored_units_sha256 = _require_sha256_hex(
            name="stored reduction units SHA-256",
            value=units_payload.get("sha256"),
        )
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected minimal reduction SHA-256",
            value=expected_sha256,
        )

        return (
            payload == rebuilt.payload
            and reduction.get("status")
            == rebuilt.payload["reduction"]["status"]
            and stored_units_sha256
            == rebuilt.reduction_units_sha256
            and normalized_expected_sha256 == rebuilt.sha256
        )

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False
