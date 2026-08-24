"""Deterministic evidence for local counterexample neighborhoods.

Neighborhood generation starts from one observed failing scenario, normally
the terminal scenario produced by minimal counterexample reduction.  Callers
declare an ordered set of single-mutation candidates around that source.  The
contract proposes each candidate exactly once and records only execution-backed
pass or fail outcomes.

The resulting bundle describes coverage of the declared neighborhood.  It does
not infer unexecuted outcomes, a continuous failure region, causality,
statistical generalization, or qualification authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.decision import DecisionVerdict


NEIGHBORHOOD_GENERATION_SCHEMA_VERSION = 1

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)

_EVIDENCE_BOUNDARY = {
    "source_failure_observed": True,
    "source_minimal_reduction_linked": True,
    "candidate_specifications_committed": True,
    "candidates_are_single_declared_mutations": True,
    "observations_require_execution_evidence": True,
    "next_proposal_is_an_observation": False,
    "declared_neighborhood_scope": (
        "ordered_single_mutation_candidates"
    ),
    "unexecuted_outcomes_inferred": False,
    "continuous_failure_region_claimed": False,
    "causal_explanation_claimed": False,
    "statistical_generalization_claimed": False,
    "contract_promoted": False,
    "raw_content_embedded": False,
    "qualification_authority": False,
}


class NeighborhoodGenerationStatus(StrEnum):
    READY = "ready"
    COMPLETE = "complete"
    BUDGET_EXHAUSTED = "budget_exhausted"


class NeighborhoodMutationDirection(StrEnum):
    LOWER = "lower"
    UPPER = "upper"
    ALTERNATE = "alternate"


class NeighborhoodProposalReason(StrEnum):
    INITIAL_CANDIDATE = "initial_candidate"
    CONTINUE_ORDERED_SCAN = "continue_ordered_scan"


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
class NeighborhoodCandidate:
    """One declared single mutation around the source scenario."""

    key: str
    version: str
    dimension_key: str
    generator_key: str
    generator_version: str
    direction: NeighborhoodMutationDirection
    ordinal_distance: int
    specification_sha256: str

    def __post_init__(self) -> None:
        for name, value in (
            ("neighborhood candidate key", self.key),
            ("neighborhood dimension key", self.dimension_key),
            ("neighborhood generator key", self.generator_key),
        ):
            _require_identifier(
                name=name,
                value=value,
            )

        for name, value in (
            ("neighborhood candidate version", self.version),
            (
                "neighborhood generator version",
                self.generator_version,
            ),
        ):
            _require_non_empty_string(
                name=name,
                value=value,
                max_length=100,
            )

        if not isinstance(
            self.direction,
            NeighborhoodMutationDirection,
        ):
            raise HveeContractError(
                "neighborhood mutation direction must be canonical"
            )

        if (
            isinstance(self.ordinal_distance, bool)
            or not isinstance(self.ordinal_distance, int)
            or self.ordinal_distance < 1
        ):
            raise HveeContractError(
                "neighborhood ordinal distance must be a positive "
                "integer"
            )

        _require_sha256_hex(
            name="neighborhood candidate specification SHA-256",
            value=self.specification_sha256,
        )

    @property
    def identity(self) -> tuple[object, ...]:
        return (
            self.key,
            self.version,
            self.dimension_key,
            self.generator_key,
            self.generator_version,
            self.direction.value,
            self.ordinal_distance,
            self.specification_sha256,
        )

    @property
    def coordinate(self) -> tuple[str, str, int]:
        return (
            self.dimension_key,
            self.direction.value,
            self.ordinal_distance,
        )


@dataclass(frozen=True, slots=True)
class NeighborhoodObservation:
    """One executed neighborhood candidate and its evidence links."""

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
                "neighborhood observation sequence must be a positive "
                "integer"
            )

        if (
            isinstance(self.candidate_index, bool)
            or not isinstance(self.candidate_index, int)
            or self.candidate_index < 0
        ):
            raise HveeContractError(
                "neighborhood candidate index must be a non-negative "
                "integer"
            )

        for name, value in (
            ("neighborhood scenario SHA-256", self.scenario_sha256),
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

        if (
            not isinstance(self.verdict, DecisionVerdict)
            or self.verdict
            not in {
                DecisionVerdict.PASS,
                DecisionVerdict.FAIL,
            }
        ):
            raise HveeContractError(
                "neighborhood observations require pass or fail "
                "verdicts"
            )

        if self.verdict == DecisionVerdict.FAIL:
            _require_sha256_hex(
                name="counterexample evidence SHA-256",
                value=self.counterexample_evidence_sha256,
            )
        elif self.counterexample_evidence_sha256 is not None:
            raise HveeContractError(
                "passing neighborhood observations cannot reference "
                "counterexample evidence"
            )


@dataclass(frozen=True, slots=True)
class NeighborhoodGenerationBundle:
    payload: dict[str, object]
    candidates_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "neighborhood generation payload must be a JSON object"
            )

        _require_sha256_hex(
            name="neighborhood candidates SHA-256",
            value=self.candidates_sha256,
        )
        _require_sha256_hex(
            name="neighborhood generation SHA-256",
            value=self.sha256,
        )


@dataclass(frozen=True, slots=True)
class _NeighborhoodProposal:
    candidate_index: int
    reason: NeighborhoodProposalReason


def _candidate_payload(
    *,
    index: int,
    candidate: NeighborhoodCandidate,
) -> dict[str, object]:
    return {
        "index": index,
        "key": candidate.key,
        "version": candidate.version,
        "dimension_key": candidate.dimension_key,
        "generator": {
            "key": candidate.generator_key,
            "version": candidate.generator_version,
        },
        "mutation": {
            "direction": candidate.direction.value,
            "ordinal_distance": candidate.ordinal_distance,
            "specification_sha256": (
                candidate.specification_sha256
            ),
        },
    }


def _canonical_candidates(
    value: object,
) -> tuple[NeighborhoodCandidate, ...]:
    if (
        not isinstance(value, (list, tuple))
        or not value
        or not all(
            isinstance(candidate, NeighborhoodCandidate)
            for candidate in value
        )
    ):
        raise HveeContractError(
            "neighborhood generation requires an ordered sequence of "
            "canonical candidates"
        )

    normalized = tuple(value)
    identities = tuple(
        candidate.identity
        for candidate in normalized
    )
    keys = tuple(
        candidate.key
        for candidate in normalized
    )
    coordinates = tuple(
        candidate.coordinate
        for candidate in normalized
    )

    if len(identities) != len(set(identities)):
        raise HveeContractError(
            "neighborhood candidate identities must be unique"
        )

    if len(keys) != len(set(keys)):
        raise HveeContractError(
            "neighborhood candidate keys must be unique"
        )

    if len(coordinates) != len(set(coordinates)):
        raise HveeContractError(
            "neighborhood candidate coordinates must be unique"
        )

    return normalized


def calculate_neighborhood_candidates_sha256(
    candidates: list[NeighborhoodCandidate]
    | tuple[NeighborhoodCandidate, ...],
) -> str:
    normalized = _canonical_candidates(candidates)
    return _calculate_sha256(
        [
            _candidate_payload(
                index=index,
                candidate=candidate,
            )
            for index, candidate in enumerate(normalized)
        ],
        name="neighborhood candidates",
    )


def calculate_neighborhood_generation_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="neighborhood generation evidence",
    )


def _derive_status_and_proposal(
    *,
    candidate_count: int,
    maximum_observations: int,
    observation_count: int,
) -> tuple[
    NeighborhoodGenerationStatus,
    _NeighborhoodProposal | None,
]:
    if observation_count == candidate_count:
        return (
            NeighborhoodGenerationStatus.COMPLETE,
            None,
        )

    if observation_count >= maximum_observations:
        return (
            NeighborhoodGenerationStatus.BUDGET_EXHAUSTED,
            None,
        )

    reason = NeighborhoodProposalReason.CONTINUE_ORDERED_SCAN
    if observation_count == 0:
        reason = NeighborhoodProposalReason.INITIAL_CANDIDATE

    return (
        NeighborhoodGenerationStatus.READY,
        _NeighborhoodProposal(
            candidate_index=observation_count,
            reason=reason,
        ),
    )


def _proposal_payload(
    *,
    proposal: _NeighborhoodProposal,
    candidates: tuple[NeighborhoodCandidate, ...],
    source_scenario_sha256: str,
    source_counterexample_evidence_sha256: str,
    source_minimal_reduction_sha256: str,
) -> dict[str, object]:
    return {
        "reason": proposal.reason.value,
        "candidate": _candidate_payload(
            index=proposal.candidate_index,
            candidate=candidates[proposal.candidate_index],
        ),
        "source_scenario_sha256": source_scenario_sha256,
        "source_counterexample_evidence_sha256": (
            source_counterexample_evidence_sha256
        ),
        "source_minimal_reduction_sha256": (
            source_minimal_reduction_sha256
        ),
    }


def _observation_payload(
    *,
    observation: NeighborhoodObservation,
    proposal: _NeighborhoodProposal,
    candidates: tuple[NeighborhoodCandidate, ...],
    source_scenario_sha256: str,
    source_counterexample_evidence_sha256: str,
    source_minimal_reduction_sha256: str,
) -> dict[str, object]:
    return {
        "sequence": observation.sequence,
        "proposal": _proposal_payload(
            proposal=proposal,
            candidates=candidates,
            source_scenario_sha256=source_scenario_sha256,
            source_counterexample_evidence_sha256=(
                source_counterexample_evidence_sha256
            ),
            source_minimal_reduction_sha256=(
                source_minimal_reduction_sha256
            ),
        ),
        "result": {
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
        "observed_as_failure": (
            observation.verdict == DecisionVerdict.FAIL
        ),
    }


def build_neighborhood_generation_bundle(
    *,
    evaluation_type: str,
    neighborhood_key: str,
    neighborhood_version: str,
    source_scenario_sha256: str,
    source_counterexample_evidence_sha256: str,
    source_minimal_reduction_sha256: str,
    candidates: list[NeighborhoodCandidate]
    | tuple[NeighborhoodCandidate, ...],
    maximum_observations: int,
    observations: list[NeighborhoodObservation]
    | tuple[NeighborhoodObservation, ...],
) -> NeighborhoodGenerationBundle:
    normalized_evaluation_type = _require_identifier(
        name="evaluation type",
        value=evaluation_type,
    )
    normalized_neighborhood_key = _require_identifier(
        name="neighborhood key",
        value=neighborhood_key,
    )
    normalized_neighborhood_version = _require_non_empty_string(
        name="neighborhood version",
        value=neighborhood_version,
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
    normalized_source_reduction_sha256 = _require_sha256_hex(
        name="source minimal reduction SHA-256",
        value=source_minimal_reduction_sha256,
    )
    normalized_candidates = _canonical_candidates(candidates)
    candidates_sha256 = calculate_neighborhood_candidates_sha256(
        normalized_candidates
    )

    if (
        isinstance(maximum_observations, bool)
        or not isinstance(maximum_observations, int)
        or maximum_observations < 1
        or maximum_observations > len(normalized_candidates)
    ):
        raise HveeContractError(
            "maximum observations must be between one and the "
            "declared neighborhood candidate count"
        )

    if (
        not isinstance(observations, (list, tuple))
        or not all(
            isinstance(observation, NeighborhoodObservation)
            for observation in observations
        )
    ):
        raise HveeContractError(
            "neighborhood observations must be a sequence of canonical "
            "observations"
        )

    normalized_observations = tuple(observations)
    observation_payloads: list[dict[str, object]] = []
    seen_scenarios = {normalized_source_scenario_sha256}

    for expected_sequence, observation in enumerate(
        normalized_observations,
        start=1,
    ):
        if observation.sequence != expected_sequence:
            raise HveeContractError(
                "neighborhood observation sequences must be contiguous "
                "and ordered"
            )

        prior_status, proposal = _derive_status_and_proposal(
            candidate_count=len(normalized_candidates),
            maximum_observations=maximum_observations,
            observation_count=expected_sequence - 1,
        )

        if (
            prior_status != NeighborhoodGenerationStatus.READY
            or proposal is None
        ):
            raise HveeContractError(
                "neighborhood observations cannot continue after the "
                "generation becomes terminal"
            )

        if observation.candidate_index != proposal.candidate_index:
            raise HveeContractError(
                "neighborhood observation does not match the "
                "deterministic proposal trajectory"
            )

        if observation.scenario_sha256 in seen_scenarios:
            raise HveeContractError(
                "neighborhood observations require distinct candidate "
                "scenarios"
            )

        observation_payloads.append(
            _observation_payload(
                observation=observation,
                proposal=proposal,
                candidates=normalized_candidates,
                source_scenario_sha256=(
                    normalized_source_scenario_sha256
                ),
                source_counterexample_evidence_sha256=(
                    normalized_source_counterexample_sha256
                ),
                source_minimal_reduction_sha256=(
                    normalized_source_reduction_sha256
                ),
            )
        )
        seen_scenarios.add(observation.scenario_sha256)

    status, proposal = _derive_status_and_proposal(
        candidate_count=len(normalized_candidates),
        maximum_observations=maximum_observations,
        observation_count=len(normalized_observations),
    )
    passing_indices = tuple(
        observation.candidate_index
        for observation in normalized_observations
        if observation.verdict == DecisionVerdict.PASS
    )
    failing_indices = tuple(
        observation.candidate_index
        for observation in normalized_observations
        if observation.verdict == DecisionVerdict.FAIL
    )

    payload: dict[str, object] = {
        "schema_version": NEIGHBORHOOD_GENERATION_SCHEMA_VERSION,
        "type": "neighborhood_generation",
        "evaluation_type": normalized_evaluation_type,
        "neighborhood": {
            "key": normalized_neighborhood_key,
            "version": normalized_neighborhood_version,
            "status": status.value,
        },
        "source": {
            "scenario_sha256": normalized_source_scenario_sha256,
            "counterexample_evidence_sha256": (
                normalized_source_counterexample_sha256
            ),
            "minimal_counterexample_reduction_sha256": (
                normalized_source_reduction_sha256
            ),
        },
        "candidates": {
            "ordered": [
                _candidate_payload(
                    index=index,
                    candidate=candidate,
                )
                for index, candidate in enumerate(
                    normalized_candidates
                )
            ],
            "sha256": candidates_sha256,
        },
        "budget": {
            "maximum_observations": maximum_observations,
            "planned_candidate_count": len(normalized_candidates),
            "observed_count": len(normalized_observations),
            "remaining_observations": (
                maximum_observations
                - len(normalized_observations)
            ),
        },
        "observations": observation_payloads,
        "outcome": {
            "planned_candidate_count": len(normalized_candidates),
            "observed_candidate_count": len(
                normalized_observations
            ),
            "unobserved_candidate_count": (
                len(normalized_candidates)
                - len(normalized_observations)
            ),
            "passing_candidate_indices": list(passing_indices),
            "passing_candidate_keys": [
                normalized_candidates[index].key
                for index in passing_indices
            ],
            "failing_candidate_indices": list(failing_indices),
            "failing_candidate_keys": [
                normalized_candidates[index].key
                for index in failing_indices
            ],
            "observed_verdict_counts": {
                "pass": len(passing_indices),
                "fail": len(failing_indices),
            },
            "declared_neighborhood_fully_observed": (
                status == NeighborhoodGenerationStatus.COMPLETE
            ),
            "mixed_observed_verdicts": bool(
                passing_indices and failing_indices
            ),
            "next_proposal": (
                _proposal_payload(
                    proposal=proposal,
                    candidates=normalized_candidates,
                    source_scenario_sha256=(
                        normalized_source_scenario_sha256
                    ),
                    source_counterexample_evidence_sha256=(
                        normalized_source_counterexample_sha256
                    ),
                    source_minimal_reduction_sha256=(
                        normalized_source_reduction_sha256
                    ),
                )
                if proposal is not None
                else None
            ),
        },
        "evidence_boundary": dict(_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="neighborhood generation evidence",
    )

    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "neighborhood generation must be a JSON object"
        )

    return NeighborhoodGenerationBundle(
        payload=canonical_payload,
        candidates_sha256=candidates_sha256,
        sha256=calculate_neighborhood_generation_sha256(
            canonical_payload
        ),
    )


def _parse_candidate(
    value: object,
    *,
    expected_index: int,
) -> NeighborhoodCandidate:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "index",
            "key",
            "version",
            "dimension_key",
            "generator",
            "mutation",
        }
        or value.get("index") != expected_index
    ):
        raise HveeContractError(
            "invalid neighborhood candidate shape"
        )

    generator = value.get("generator")
    mutation = value.get("mutation")
    if (
        not isinstance(generator, dict)
        or set(generator) != {"key", "version"}
        or not isinstance(mutation, dict)
        or set(mutation)
        != {
            "direction",
            "ordinal_distance",
            "specification_sha256",
        }
    ):
        raise HveeContractError(
            "invalid neighborhood candidate generator or mutation"
        )

    return NeighborhoodCandidate(
        key=value.get("key"),
        version=value.get("version"),
        dimension_key=value.get("dimension_key"),
        generator_key=generator.get("key"),
        generator_version=generator.get("version"),
        direction=NeighborhoodMutationDirection(
            mutation.get("direction")
        ),
        ordinal_distance=mutation.get("ordinal_distance"),
        specification_sha256=mutation.get(
            "specification_sha256"
        ),
    )


def _parse_observation(
    value: object,
) -> NeighborhoodObservation:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "sequence",
            "proposal",
            "result",
            "observed_as_failure",
        }
    ):
        raise HveeContractError(
            "invalid neighborhood observation shape"
        )

    proposal = value.get("proposal")
    result = value.get("result")
    if (
        not isinstance(proposal, dict)
        or set(proposal)
        != {
            "reason",
            "candidate",
            "source_scenario_sha256",
            "source_counterexample_evidence_sha256",
            "source_minimal_reduction_sha256",
        }
        or not isinstance(result, dict)
        or set(result) != {"scenario_sha256", "verdict", "evidence"}
    ):
        raise HveeContractError(
            "invalid neighborhood proposal or result shape"
        )

    candidate = proposal.get("candidate")
    evidence = result.get("evidence")
    if (
        not isinstance(candidate, dict)
        or "index" not in candidate
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
            "invalid neighborhood observation evidence"
        )

    return NeighborhoodObservation(
        sequence=value.get("sequence"),
        candidate_index=candidate.get("index"),
        scenario_sha256=result.get("scenario_sha256"),
        verdict=DecisionVerdict(result.get("verdict")),
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


def verify_neighborhood_generation_bundle(
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
                "neighborhood",
                "source",
                "candidates",
                "budget",
                "observations",
                "outcome",
                "evidence_boundary",
            }
            or payload.get("schema_version")
            != NEIGHBORHOOD_GENERATION_SCHEMA_VERSION
            or payload.get("type") != "neighborhood_generation"
            or payload.get("evidence_boundary") != _EVIDENCE_BOUNDARY
        ):
            return False

        neighborhood = payload.get("neighborhood")
        source = payload.get("source")
        candidates_payload = payload.get("candidates")
        budget = payload.get("budget")
        observations_payload = payload.get("observations")
        outcome = payload.get("outcome")

        if (
            not isinstance(neighborhood, dict)
            or set(neighborhood) != {"key", "version", "status"}
            or not isinstance(source, dict)
            or set(source)
            != {
                "scenario_sha256",
                "counterexample_evidence_sha256",
                "minimal_counterexample_reduction_sha256",
            }
            or not isinstance(candidates_payload, dict)
            or set(candidates_payload) != {"ordered", "sha256"}
            or not isinstance(candidates_payload.get("ordered"), list)
            or not isinstance(budget, dict)
            or set(budget)
            != {
                "maximum_observations",
                "planned_candidate_count",
                "observed_count",
                "remaining_observations",
            }
            or not isinstance(observations_payload, list)
            or not isinstance(outcome, dict)
            or set(outcome)
            != {
                "planned_candidate_count",
                "observed_candidate_count",
                "unobserved_candidate_count",
                "passing_candidate_indices",
                "passing_candidate_keys",
                "failing_candidate_indices",
                "failing_candidate_keys",
                "observed_verdict_counts",
                "declared_neighborhood_fully_observed",
                "mixed_observed_verdicts",
                "next_proposal",
            }
        ):
            return False

        candidates = tuple(
            _parse_candidate(candidate, expected_index=index)
            for index, candidate in enumerate(
                candidates_payload["ordered"]
            )
        )
        observations = tuple(
            _parse_observation(observation)
            for observation in observations_payload
        )

        rebuilt = build_neighborhood_generation_bundle(
            evaluation_type=payload.get("evaluation_type"),
            neighborhood_key=neighborhood.get("key"),
            neighborhood_version=neighborhood.get("version"),
            source_scenario_sha256=source.get("scenario_sha256"),
            source_counterexample_evidence_sha256=source.get(
                "counterexample_evidence_sha256"
            ),
            source_minimal_reduction_sha256=source.get(
                "minimal_counterexample_reduction_sha256"
            ),
            candidates=candidates,
            maximum_observations=budget.get(
                "maximum_observations"
            ),
            observations=observations,
        )

        stored_candidates_sha256 = _require_sha256_hex(
            name="stored neighborhood candidates SHA-256",
            value=candidates_payload.get("sha256"),
        )
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected neighborhood generation SHA-256",
            value=expected_sha256,
        )

        return (
            payload == rebuilt.payload
            and neighborhood.get("status")
            == rebuilt.payload["neighborhood"]["status"]
            and stored_candidates_sha256
            == rebuilt.candidates_sha256
            and normalized_expected_sha256 == rebuilt.sha256
        )

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False
