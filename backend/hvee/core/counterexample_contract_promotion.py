"""Explicit promotion of verified counterexamples into regression contracts.

This module joins the portable evidence chain produced by counterexample
capture, minimal reduction, and neighborhood generation.  It first creates a
deterministic promotion proposal.  A separate, immutable approval record must
then bind that exact proposal before a regression contract can be promoted.

Promotion activates only a shadow regression contract.  It does not create a
blocking release gate, production qualification, certification, causal or
statistical claims, or any other release authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.core.counterexample_evidence import (
    verify_counterexample_evidence_bundle,
)
from hvee.core.minimal_counterexample_reduction import (
    verify_minimal_counterexample_reduction_bundle,
)
from hvee.core.neighborhood_generation import (
    verify_neighborhood_generation_bundle,
)


COUNTEREXAMPLE_CONTRACT_PROPOSAL_SCHEMA_VERSION = 1
COUNTEREXAMPLE_CONTRACT_PROMOTION_SCHEMA_VERSION = 1

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)

_PROPOSAL_EVIDENCE_BOUNDARY = {
    "source_counterexample_verified": True,
    "source_one_minimal_reduction_verified": True,
    "source_complete_neighborhood_verified": True,
    "exact_minimized_scenario_scope": True,
    "explicit_approval_required": True,
    "human_or_governance_review_required": True,
    "approval_recorded": False,
    "contract_promoted": False,
    "activation_mode": "none",
    "blocking_release_gate_enabled": False,
    "release_enforcement_eligible": False,
    "production_qualified": False,
    "certification_issued": False,
    "causal_explanation_claimed": False,
    "statistical_generalization_claimed": False,
    "raw_content_embedded": False,
    "qualification_authority": False,
}

_PROMOTION_EVIDENCE_BOUNDARY = {
    "source_counterexample_verified": True,
    "source_one_minimal_reduction_verified": True,
    "source_complete_neighborhood_verified": True,
    "exact_minimized_scenario_scope": True,
    "explicit_approval_required": True,
    "human_or_governance_review_required": True,
    "human_or_governance_review_recorded": True,
    "approval_recorded": True,
    "contract_promoted": True,
    "activation_mode": "shadow",
    "blocking_release_gate_enabled": False,
    "release_enforcement_eligible": False,
    "production_qualified": False,
    "certification_issued": False,
    "causal_explanation_claimed": False,
    "statistical_generalization_claimed": False,
    "raw_content_embedded": False,
    "qualification_authority": False,
}


class ContractActivationMode(StrEnum):
    SHADOW = "shadow"


class ContractPromotionStatus(StrEnum):
    AWAITING_APPROVAL = "awaiting_approval"
    PROMOTED_TO_SHADOW = "promoted_to_shadow"


class PromotionReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class PromotionReviewerKind(StrEnum):
    HUMAN = "human"
    GOVERNANCE_BODY = "governance_body"


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


def _require_non_negative_integer(
    *,
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise HveeContractError(
            f"{name} must be a non-negative integer"
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
    canonical = _canonical_json(value, name=name)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RegressionContractDefinition:
    """Identity of the versioned shadow regression contract."""

    key: str
    version: str
    suite_key: str
    suite_version: str

    def __post_init__(self) -> None:
        for name, value in (
            ("regression contract key", self.key),
            ("regression suite key", self.suite_key),
        ):
            _require_identifier(name=name, value=value)

        for name, value in (
            ("regression contract version", self.version),
            ("regression suite version", self.suite_version),
        ):
            _require_non_empty_string(
                name=name,
                value=value,
                max_length=100,
            )


@dataclass(frozen=True, slots=True)
class ContractPromotionApproval:
    """One external review record binding an exact proposal digest."""

    proposal_sha256: str
    reviewer_key: str
    reviewer_role_key: str
    reviewer_kind: PromotionReviewerKind
    review_policy_key: str
    review_policy_version: str
    decision: PromotionReviewDecision
    rationale_code: str
    approval_evidence_sha256: str

    def __post_init__(self) -> None:
        _require_sha256_hex(
            name="reviewed proposal SHA-256",
            value=self.proposal_sha256,
        )
        _require_sha256_hex(
            name="approval evidence SHA-256",
            value=self.approval_evidence_sha256,
        )

        for name, value in (
            ("reviewer key", self.reviewer_key),
            ("reviewer role key", self.reviewer_role_key),
            ("review policy key", self.review_policy_key),
            ("approval rationale code", self.rationale_code),
        ):
            _require_identifier(name=name, value=value)

        _require_non_empty_string(
            name="review policy version",
            value=self.review_policy_version,
            max_length=100,
        )

        if not isinstance(self.decision, PromotionReviewDecision):
            raise HveeContractError(
                "promotion review decision must be canonical"
            )
        if not isinstance(self.reviewer_kind, PromotionReviewerKind):
            raise HveeContractError(
                "promotion reviewer kind must be canonical"
            )


@dataclass(frozen=True, slots=True)
class CounterexampleContractProposalBundle:
    payload: dict[str, object]
    contract_specification_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "contract proposal payload must be a JSON object"
            )

        _require_sha256_hex(
            name="contract specification SHA-256",
            value=self.contract_specification_sha256,
        )
        _require_sha256_hex(
            name="contract proposal SHA-256",
            value=self.sha256,
        )


@dataclass(frozen=True, slots=True)
class CounterexampleContractPromotionBundle:
    payload: dict[str, object]
    approval_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "contract promotion payload must be a JSON object"
            )

        _require_sha256_hex(
            name="promotion approval SHA-256",
            value=self.approval_sha256,
        )
        _require_sha256_hex(
            name="contract promotion SHA-256",
            value=self.sha256,
        )


def _canonical_failure_fingerprints(
    value: object,
) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise HveeContractError(
            "contract promotion requires failure fingerprints"
        )

    normalized: list[dict[str, object]] = []
    identities: list[tuple[str, ...]] = []

    for failure in value:
        if (
            not isinstance(failure, dict)
            or set(failure)
            != {
                "key",
                "version",
                "reason_code",
                "metric",
                "evaluator",
            }
        ):
            raise HveeContractError(
                "invalid failure fingerprint shape"
            )

        metric = failure.get("metric")
        evaluator = failure.get("evaluator")
        if (
            not isinstance(metric, dict)
            or set(metric) != {"key", "version"}
            or not isinstance(evaluator, dict)
            or set(evaluator) != {"key", "version"}
        ):
            raise HveeContractError(
                "invalid failure fingerprint metric or evaluator"
            )

        key = _require_identifier(
            name="failure fingerprint key",
            value=failure.get("key"),
        )
        version = _require_non_empty_string(
            name="failure fingerprint version",
            value=failure.get("version"),
            max_length=100,
        )
        reason_code = _require_identifier(
            name="failure fingerprint reason code",
            value=failure.get("reason_code"),
        )
        metric_key = _require_identifier(
            name="failure fingerprint metric key",
            value=metric.get("key"),
        )
        metric_version = _require_non_empty_string(
            name="failure fingerprint metric version",
            value=metric.get("version"),
            max_length=100,
        )
        evaluator_key = _require_identifier(
            name="failure fingerprint evaluator key",
            value=evaluator.get("key"),
        )
        evaluator_version = _require_non_empty_string(
            name="failure fingerprint evaluator version",
            value=evaluator.get("version"),
            max_length=100,
        )

        identities.append(
            (
                key,
                version,
                reason_code,
                metric_key,
                metric_version,
                evaluator_key,
                evaluator_version,
            )
        )
        normalized.append(
            {
                "key": key,
                "version": version,
                "reason_code": reason_code,
                "metric": {
                    "key": metric_key,
                    "version": metric_version,
                },
                "evaluator": {
                    "key": evaluator_key,
                    "version": evaluator_version,
                },
            }
        )

    if len(identities) != len(set(identities)):
        raise HveeContractError(
            "failure fingerprint identities must be unique"
        )

    ordered = tuple(
        failure
        for _, failure in sorted(
            zip(identities, normalized, strict=True),
            key=lambda item: item[0],
        )
    )
    return ordered


def _verified_source_summary(
    *,
    source_counterexample_payload: object,
    source_counterexample_sha256: object,
    source_minimal_reduction_payload: object,
    source_minimal_reduction_sha256: object,
    source_neighborhood_payload: object,
    source_neighborhood_sha256: object,
) -> dict[str, object]:
    if not verify_counterexample_evidence_bundle(
        payload=source_counterexample_payload,
        expected_sha256=source_counterexample_sha256,
    ):
        raise HveeContractError(
            "source counterexample evidence must verify"
        )
    if not verify_minimal_counterexample_reduction_bundle(
        payload=source_minimal_reduction_payload,
        expected_sha256=source_minimal_reduction_sha256,
    ):
        raise HveeContractError(
            "source minimal counterexample reduction must verify"
        )
    if not verify_neighborhood_generation_bundle(
        payload=source_neighborhood_payload,
        expected_sha256=source_neighborhood_sha256,
    ):
        raise HveeContractError(
            "source neighborhood generation must verify"
        )

    if (
        not isinstance(source_counterexample_payload, dict)
        or not isinstance(source_minimal_reduction_payload, dict)
        or not isinstance(source_neighborhood_payload, dict)
    ):
        raise HveeContractError(
            "source evidence payloads must be JSON objects"
        )

    counterexample_sha256 = _require_sha256_hex(
        name="source counterexample SHA-256",
        value=source_counterexample_sha256,
    )
    reduction_sha256 = _require_sha256_hex(
        name="source minimal reduction SHA-256",
        value=source_minimal_reduction_sha256,
    )
    neighborhood_sha256 = _require_sha256_hex(
        name="source neighborhood SHA-256",
        value=source_neighborhood_sha256,
    )

    evaluation_types = {
        source_counterexample_payload.get("evaluation_type"),
        source_minimal_reduction_payload.get("evaluation_type"),
        source_neighborhood_payload.get("evaluation_type"),
    }
    if len(evaluation_types) != 1:
        raise HveeContractError(
            "source evidence evaluation types must match"
        )
    evaluation_type = _require_identifier(
        name="source evaluation type",
        value=next(iter(evaluation_types)),
    )

    scenario = source_counterexample_payload.get("scenario")
    failures = source_counterexample_payload.get("failures")
    reduction = source_minimal_reduction_payload.get("reduction")
    reduction_outcome = source_minimal_reduction_payload.get("outcome")
    neighborhood = source_neighborhood_payload.get("neighborhood")
    neighborhood_source = source_neighborhood_payload.get("source")
    neighborhood_candidates = source_neighborhood_payload.get(
        "candidates"
    )
    neighborhood_outcome = source_neighborhood_payload.get("outcome")

    if not all(
        isinstance(value, dict)
        for value in (
            scenario,
            reduction,
            reduction_outcome,
            neighborhood,
            neighborhood_source,
            neighborhood_candidates,
            neighborhood_outcome,
        )
    ):
        raise HveeContractError(
            "source evidence contains invalid summary objects"
        )

    scenario_sha256 = _require_sha256_hex(
        name="minimized source scenario SHA-256",
        value=scenario.get("sha256"),
    )
    if (
        reduction.get("status") != "one_minimal"
        or reduction_outcome.get("one_minimal_within_declared_units")
        is not True
        or reduction_outcome.get("next_proposal") is not None
    ):
        raise HveeContractError(
            "source reduction must be terminal and one-minimal"
        )
    if (
        reduction_outcome.get("current_scenario_sha256")
        != scenario_sha256
        or reduction_outcome.get(
            "current_counterexample_evidence_sha256"
        )
        != counterexample_sha256
    ):
        raise HveeContractError(
            "source counterexample must be the terminal minimized "
            "counterexample"
        )

    if (
        neighborhood.get("status") != "complete"
        or neighborhood_outcome.get(
            "declared_neighborhood_fully_observed"
        )
        is not True
        or neighborhood_outcome.get("unobserved_candidate_count") != 0
        or neighborhood_outcome.get("next_proposal") is not None
    ):
        raise HveeContractError(
            "source neighborhood must be complete"
        )
    if (
        neighborhood_source.get("scenario_sha256")
        != scenario_sha256
        or neighborhood_source.get(
            "counterexample_evidence_sha256"
        )
        != counterexample_sha256
        or neighborhood_source.get(
            "minimal_counterexample_reduction_sha256"
        )
        != reduction_sha256
    ):
        raise HveeContractError(
            "source neighborhood chain does not match the minimized "
            "counterexample"
        )

    candidates_sha256 = _require_sha256_hex(
        name="source neighborhood candidates SHA-256",
        value=neighborhood_candidates.get("sha256"),
    )
    planned_candidate_count = _require_non_negative_integer(
        name="source planned candidate count",
        value=neighborhood_outcome.get("planned_candidate_count"),
    )
    passing_indices = neighborhood_outcome.get(
        "passing_candidate_indices"
    )
    failing_indices = neighborhood_outcome.get(
        "failing_candidate_indices"
    )
    if not isinstance(passing_indices, list) or not isinstance(
        failing_indices, list
    ):
        raise HveeContractError(
            "source neighborhood verdict indices must be lists"
        )

    return {
        "evaluation_type": evaluation_type,
        "scenario_sha256": scenario_sha256,
        "failure_fingerprints": _canonical_failure_fingerprints(
            failures
        ),
        "counterexample_sha256": counterexample_sha256,
        "reduction_sha256": reduction_sha256,
        "neighborhood_sha256": neighborhood_sha256,
        "candidates_sha256": candidates_sha256,
        "planned_candidate_count": planned_candidate_count,
        "passing_candidate_count": len(passing_indices),
        "failing_candidate_count": len(failing_indices),
        "mixed_observed_verdicts": neighborhood_outcome.get(
            "mixed_observed_verdicts"
        )
        is True,
    }


def _contract_body(
    *,
    definition: RegressionContractDefinition,
    scenario_sha256: str,
    failure_fingerprints: tuple[dict[str, object], ...],
) -> dict[str, object]:
    return {
        "key": definition.key,
        "version": definition.version,
        "status": ContractPromotionStatus.AWAITING_APPROVAL.value,
        "activation_mode": ContractActivationMode.SHADOW.value,
        "suite": {
            "key": definition.suite_key,
            "version": definition.suite_version,
        },
        "scenario": {
            "scope": "exact_minimized_scenario",
            "sha256": scenario_sha256,
        },
        "expectation": {
            "decision_verdict": "pass",
            "forbidden_failure_fingerprints": list(
                failure_fingerprints
            ),
        },
    }


def calculate_regression_contract_specification_sha256(
    contract_body: dict[str, object],
) -> str:
    return _calculate_sha256(
        contract_body,
        name="regression contract specification",
    )


def calculate_counterexample_contract_proposal_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="counterexample contract proposal",
    )


def calculate_counterexample_contract_promotion_sha256(
    payload: dict[str, object],
) -> str:
    return _calculate_sha256(
        payload,
        name="counterexample contract promotion",
    )


def _build_proposal_from_summary(
    *,
    definition: RegressionContractDefinition,
    summary: dict[str, object],
) -> CounterexampleContractProposalBundle:
    evaluation_type = _require_identifier(
        name="proposal evaluation type",
        value=summary.get("evaluation_type"),
    )
    scenario_sha256 = _require_sha256_hex(
        name="proposal scenario SHA-256",
        value=summary.get("scenario_sha256"),
    )
    failure_fingerprints = _canonical_failure_fingerprints(
        list(summary.get("failure_fingerprints", ()))
    )
    planned_candidate_count = _require_non_negative_integer(
        name="proposal planned candidate count",
        value=summary.get("planned_candidate_count"),
    )
    passing_candidate_count = _require_non_negative_integer(
        name="proposal passing candidate count",
        value=summary.get("passing_candidate_count"),
    )
    failing_candidate_count = _require_non_negative_integer(
        name="proposal failing candidate count",
        value=summary.get("failing_candidate_count"),
    )
    mixed_observed_verdicts = (
        summary.get("mixed_observed_verdicts") is True
    )
    if planned_candidate_count < 1:
        raise HveeContractError(
            "proposal requires at least one observed neighborhood "
            "candidate"
        )
    if (
        passing_candidate_count + failing_candidate_count
        != planned_candidate_count
    ):
        raise HveeContractError(
            "proposal neighborhood verdict counts must cover the "
            "planned candidates"
        )
    if mixed_observed_verdicts != bool(
        passing_candidate_count and failing_candidate_count
    ):
        raise HveeContractError(
            "proposal mixed-verdict flag must match verdict counts"
        )

    contract_body = _contract_body(
        definition=definition,
        scenario_sha256=scenario_sha256,
        failure_fingerprints=failure_fingerprints,
    )
    contract_specification_sha256 = (
        calculate_regression_contract_specification_sha256(
            contract_body
        )
    )

    payload: dict[str, object] = {
        "schema_version": (
            COUNTEREXAMPLE_CONTRACT_PROPOSAL_SCHEMA_VERSION
        ),
        "type": "counterexample_contract_promotion_proposal",
        "evaluation_type": evaluation_type,
        "contract": {
            **contract_body,
            "specification_sha256": (
                contract_specification_sha256
            ),
        },
        "source_evidence": {
            "counterexample": {
                "sha256": _require_sha256_hex(
                    name="proposal counterexample SHA-256",
                    value=summary.get("counterexample_sha256"),
                ),
                "verified": True,
            },
            "minimal_counterexample_reduction": {
                "sha256": _require_sha256_hex(
                    name="proposal reduction SHA-256",
                    value=summary.get("reduction_sha256"),
                ),
                "status": "one_minimal",
                "verified": True,
            },
            "neighborhood_generation": {
                "sha256": _require_sha256_hex(
                    name="proposal neighborhood SHA-256",
                    value=summary.get("neighborhood_sha256"),
                ),
                "candidates_sha256": _require_sha256_hex(
                    name="proposal candidates SHA-256",
                    value=summary.get("candidates_sha256"),
                ),
                "status": "complete",
                "planned_candidate_count": (
                    planned_candidate_count
                ),
                "passing_candidate_count": (
                    passing_candidate_count
                ),
                "failing_candidate_count": (
                    failing_candidate_count
                ),
                "mixed_observed_verdicts": (
                    mixed_observed_verdicts
                ),
                "verified": True,
            },
        },
        "promotion": {
            "status": (
                ContractPromotionStatus.AWAITING_APPROVAL.value
            ),
            "explicit_approval_required": True,
            "automatic_promotion_allowed": False,
        },
        "evidence_boundary": dict(_PROPOSAL_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="counterexample contract proposal",
    )
    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "counterexample contract proposal must be a JSON object"
        )

    return CounterexampleContractProposalBundle(
        payload=canonical_payload,
        contract_specification_sha256=(
            contract_specification_sha256
        ),
        sha256=calculate_counterexample_contract_proposal_sha256(
            canonical_payload
        ),
    )


def build_counterexample_contract_proposal_bundle(
    *,
    definition: RegressionContractDefinition,
    source_counterexample_payload: object,
    source_counterexample_sha256: object,
    source_minimal_reduction_payload: object,
    source_minimal_reduction_sha256: object,
    source_neighborhood_payload: object,
    source_neighborhood_sha256: object,
) -> CounterexampleContractProposalBundle:
    if not isinstance(definition, RegressionContractDefinition):
        raise HveeContractError(
            "contract definition must be canonical"
        )

    summary = _verified_source_summary(
        source_counterexample_payload=source_counterexample_payload,
        source_counterexample_sha256=source_counterexample_sha256,
        source_minimal_reduction_payload=(
            source_minimal_reduction_payload
        ),
        source_minimal_reduction_sha256=(
            source_minimal_reduction_sha256
        ),
        source_neighborhood_payload=source_neighborhood_payload,
        source_neighborhood_sha256=source_neighborhood_sha256,
    )
    return _build_proposal_from_summary(
        definition=definition,
        summary=summary,
    )


def _proposal_summary_from_payload(
    payload: dict[str, object],
) -> tuple[RegressionContractDefinition, dict[str, object], str]:
    contract = payload.get("contract")
    source_evidence = payload.get("source_evidence")
    promotion = payload.get("promotion")
    if (
        not isinstance(contract, dict)
        or set(contract)
        != {
            "key",
            "version",
            "status",
            "activation_mode",
            "suite",
            "scenario",
            "expectation",
            "specification_sha256",
        }
        or not isinstance(source_evidence, dict)
        or set(source_evidence)
        != {
            "counterexample",
            "minimal_counterexample_reduction",
            "neighborhood_generation",
        }
        or promotion
        != {
            "status": "awaiting_approval",
            "explicit_approval_required": True,
            "automatic_promotion_allowed": False,
        }
    ):
        raise HveeContractError(
            "invalid counterexample contract proposal shape"
        )

    suite = contract.get("suite")
    scenario = contract.get("scenario")
    expectation = contract.get("expectation")
    counterexample = source_evidence.get("counterexample")
    reduction = source_evidence.get(
        "minimal_counterexample_reduction"
    )
    neighborhood = source_evidence.get("neighborhood_generation")
    if (
        not isinstance(suite, dict)
        or set(suite) != {"key", "version"}
        or not isinstance(scenario, dict)
        or set(scenario) != {"scope", "sha256"}
        or scenario.get("scope") != "exact_minimized_scenario"
        or not isinstance(expectation, dict)
        or set(expectation)
        != {
            "decision_verdict",
            "forbidden_failure_fingerprints",
        }
        or expectation.get("decision_verdict") != "pass"
        or not isinstance(counterexample, dict)
        or set(counterexample) != {"sha256", "verified"}
        or counterexample.get("verified") is not True
        or not isinstance(reduction, dict)
        or set(reduction) != {"sha256", "status", "verified"}
        or reduction.get("status") != "one_minimal"
        or reduction.get("verified") is not True
        or not isinstance(neighborhood, dict)
        or set(neighborhood)
        != {
            "sha256",
            "candidates_sha256",
            "status",
            "planned_candidate_count",
            "passing_candidate_count",
            "failing_candidate_count",
            "mixed_observed_verdicts",
            "verified",
        }
        or neighborhood.get("status") != "complete"
        or neighborhood.get("verified") is not True
        or not isinstance(
            neighborhood.get("mixed_observed_verdicts"), bool
        )
    ):
        raise HveeContractError(
            "invalid contract proposal source or expectation shape"
        )

    definition = RegressionContractDefinition(
        key=contract.get("key"),
        version=contract.get("version"),
        suite_key=suite.get("key"),
        suite_version=suite.get("version"),
    )
    summary = {
        "evaluation_type": payload.get("evaluation_type"),
        "scenario_sha256": scenario.get("sha256"),
        "failure_fingerprints": (
            expectation.get("forbidden_failure_fingerprints")
        ),
        "counterexample_sha256": counterexample.get("sha256"),
        "reduction_sha256": reduction.get("sha256"),
        "neighborhood_sha256": neighborhood.get("sha256"),
        "candidates_sha256": neighborhood.get("candidates_sha256"),
        "planned_candidate_count": neighborhood.get(
            "planned_candidate_count"
        ),
        "passing_candidate_count": neighborhood.get(
            "passing_candidate_count"
        ),
        "failing_candidate_count": neighborhood.get(
            "failing_candidate_count"
        ),
        "mixed_observed_verdicts": neighborhood.get(
            "mixed_observed_verdicts"
        ),
    }
    specification_sha256 = _require_sha256_hex(
        name="stored contract specification SHA-256",
        value=contract.get("specification_sha256"),
    )
    return definition, summary, specification_sha256


def verify_counterexample_contract_proposal_bundle(
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
                "contract",
                "source_evidence",
                "promotion",
                "evidence_boundary",
            }
            or payload.get("schema_version")
            != COUNTEREXAMPLE_CONTRACT_PROPOSAL_SCHEMA_VERSION
            or payload.get("type")
            != "counterexample_contract_promotion_proposal"
            or payload.get("evidence_boundary")
            != _PROPOSAL_EVIDENCE_BOUNDARY
        ):
            return False

        definition, summary, stored_specification_sha256 = (
            _proposal_summary_from_payload(payload)
        )
        rebuilt = _build_proposal_from_summary(
            definition=definition,
            summary=summary,
        )
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected contract proposal SHA-256",
            value=expected_sha256,
        )
        return (
            payload == rebuilt.payload
            and stored_specification_sha256
            == rebuilt.contract_specification_sha256
            and normalized_expected_sha256 == rebuilt.sha256
        )
    except (HveeContractError, TypeError, ValueError):
        return False


def _approval_payload(
    approval: ContractPromotionApproval,
) -> dict[str, object]:
    return {
        "proposal_sha256": approval.proposal_sha256,
        "reviewer": {
            "key": approval.reviewer_key,
            "role_key": approval.reviewer_role_key,
            "kind": approval.reviewer_kind.value,
        },
        "review_policy": {
            "key": approval.review_policy_key,
            "version": approval.review_policy_version,
        },
        "decision": approval.decision.value,
        "rationale_code": approval.rationale_code,
        "approval_evidence_sha256": (
            approval.approval_evidence_sha256
        ),
    }


def calculate_contract_promotion_approval_sha256(
    approval: ContractPromotionApproval,
) -> str:
    if not isinstance(approval, ContractPromotionApproval):
        raise HveeContractError(
            "contract promotion approval must be canonical"
        )
    return _calculate_sha256(
        _approval_payload(approval),
        name="contract promotion approval",
    )


def build_counterexample_contract_promotion_bundle(
    *,
    proposal_payload: object,
    expected_proposal_sha256: object,
    approval: ContractPromotionApproval,
) -> CounterexampleContractPromotionBundle:
    proposal_sha256 = _require_sha256_hex(
        name="expected contract proposal SHA-256",
        value=expected_proposal_sha256,
    )
    if not verify_counterexample_contract_proposal_bundle(
        payload=proposal_payload,
        expected_sha256=proposal_sha256,
    ):
        raise HveeContractError(
            "counterexample contract proposal must verify"
        )
    if not isinstance(approval, ContractPromotionApproval):
        raise HveeContractError(
            "contract promotion approval must be canonical"
        )
    if approval.proposal_sha256 != proposal_sha256:
        raise HveeContractError(
            "approval must bind the exact contract proposal"
        )
    if approval.decision != PromotionReviewDecision.APPROVED:
        raise HveeContractError(
            "a rejected review cannot promote a contract"
        )
    if approval.approval_evidence_sha256 == proposal_sha256:
        raise HveeContractError(
            "approval evidence must be distinct from the proposal"
        )
    if not isinstance(proposal_payload, dict):
        raise HveeContractError(
            "contract proposal payload must be a JSON object"
        )

    contract = proposal_payload["contract"]
    approval_payload = _approval_payload(approval)
    approval_sha256 = calculate_contract_promotion_approval_sha256(
        approval
    )
    payload: dict[str, object] = {
        "schema_version": (
            COUNTEREXAMPLE_CONTRACT_PROMOTION_SCHEMA_VERSION
        ),
        "type": "counterexample_contract_promotion",
        "evaluation_type": proposal_payload["evaluation_type"],
        "proposal": {
            "payload": proposal_payload,
            "sha256": proposal_sha256,
        },
        "approval": {
            **approval_payload,
            "sha256": approval_sha256,
        },
        "promotion": {
            "status": (
                ContractPromotionStatus.PROMOTED_TO_SHADOW.value
            ),
            "contract_key": contract["key"],
            "contract_version": contract["version"],
            "contract_specification_sha256": (
                contract["specification_sha256"]
            ),
            "activation_mode": ContractActivationMode.SHADOW.value,
        },
        "evidence_boundary": dict(_PROMOTION_EVIDENCE_BOUNDARY),
    }

    canonical_payload = _canonical_json_value(
        payload,
        name="counterexample contract promotion",
    )
    if not isinstance(canonical_payload, dict):
        raise HveeContractError(
            "counterexample contract promotion must be a JSON object"
        )

    return CounterexampleContractPromotionBundle(
        payload=canonical_payload,
        approval_sha256=approval_sha256,
        sha256=calculate_counterexample_contract_promotion_sha256(
            canonical_payload
        ),
    )


def _parse_approval(value: object) -> ContractPromotionApproval:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "proposal_sha256",
            "reviewer",
            "review_policy",
            "decision",
            "rationale_code",
            "approval_evidence_sha256",
            "sha256",
        }
    ):
        raise HveeContractError(
            "invalid contract promotion approval shape"
        )

    reviewer = value.get("reviewer")
    policy = value.get("review_policy")
    if (
        not isinstance(reviewer, dict)
        or set(reviewer) != {"key", "role_key", "kind"}
        or not isinstance(policy, dict)
        or set(policy) != {"key", "version"}
    ):
        raise HveeContractError(
            "invalid contract promotion reviewer or policy shape"
        )

    return ContractPromotionApproval(
        proposal_sha256=value.get("proposal_sha256"),
        reviewer_key=reviewer.get("key"),
        reviewer_role_key=reviewer.get("role_key"),
        reviewer_kind=PromotionReviewerKind(reviewer.get("kind")),
        review_policy_key=policy.get("key"),
        review_policy_version=policy.get("version"),
        decision=PromotionReviewDecision(value.get("decision")),
        rationale_code=value.get("rationale_code"),
        approval_evidence_sha256=value.get(
            "approval_evidence_sha256"
        ),
    )


def verify_counterexample_contract_promotion_bundle(
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
                "proposal",
                "approval",
                "promotion",
                "evidence_boundary",
            }
            or payload.get("schema_version")
            != COUNTEREXAMPLE_CONTRACT_PROMOTION_SCHEMA_VERSION
            or payload.get("type")
            != "counterexample_contract_promotion"
            or payload.get("evidence_boundary")
            != _PROMOTION_EVIDENCE_BOUNDARY
        ):
            return False

        proposal = payload.get("proposal")
        approval_payload = payload.get("approval")
        promotion = payload.get("promotion")
        if (
            not isinstance(proposal, dict)
            or set(proposal) != {"payload", "sha256"}
            or not isinstance(approval_payload, dict)
            or not isinstance(promotion, dict)
            or set(promotion)
            != {
                "status",
                "contract_key",
                "contract_version",
                "contract_specification_sha256",
                "activation_mode",
            }
        ):
            return False

        proposal_sha256 = _require_sha256_hex(
            name="stored contract proposal SHA-256",
            value=proposal.get("sha256"),
        )
        approval = _parse_approval(approval_payload)
        rebuilt = build_counterexample_contract_promotion_bundle(
            proposal_payload=proposal.get("payload"),
            expected_proposal_sha256=proposal_sha256,
            approval=approval,
        )
        stored_approval_sha256 = _require_sha256_hex(
            name="stored approval SHA-256",
            value=approval_payload.get("sha256"),
        )
        normalized_expected_sha256 = _require_sha256_hex(
            name="expected contract promotion SHA-256",
            value=expected_sha256,
        )
        return (
            payload == rebuilt.payload
            and stored_approval_sha256 == rebuilt.approval_sha256
            and normalized_expected_sha256 == rebuilt.sha256
        )
    except (HveeContractError, TypeError, ValueError, KeyError):
        return False
