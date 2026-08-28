"""Domain-neutral identity for one declared AI-system change.

An ``AIChangeSet`` says what changed between a baseline system and a candidate
system.  It does not predict impact, select experiments, evaluate either
system, or authorize a release.  Those responsibilities remain separate so a
later planner cannot quietly rewrite the input after seeing results.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError


AI_CHANGE_SET_SCHEMA_VERSION = 1
AI_CHANGE_SET_KEY = "hetren.core.ai-change-set"
AI_CHANGE_SET_VERSION = "1.0.0"

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SEMANTIC_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class AIChangeKind(StrEnum):
    """Supported component-change categories in schema v1."""

    MODEL = "model"
    PROMPT = "prompt"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    DATA = "data"
    POLICY = "policy"
    RUNTIME = "runtime"
    HARDWARE = "hardware"
    ENVIRONMENT = "environment"


class AIChangeRiskTier(StrEnum):
    """Declared pre-execution risk; never inferred from observed results."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AIChangeComponent:
    """One content-addressed component transition."""

    kind: AIChangeKind
    component_key: str
    baseline_identity_sha256: str
    candidate_identity_sha256: str
    declared_behavior_impacts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AIChangeKind):
            raise HveeContractError("AI change kind must be canonical")
        _require_identifier("component key", self.component_key)
        _require_sha256(
            "baseline component identity",
            self.baseline_identity_sha256,
        )
        _require_sha256(
            "candidate component identity",
            self.candidate_identity_sha256,
        )
        if self.baseline_identity_sha256 == self.candidate_identity_sha256:
            raise HveeContractError(
                "AI change component identities must differ"
            )
        _require_ordered_identifiers(
            "declared behavior impacts",
            self.declared_behavior_impacts,
        )


@dataclass(frozen=True, slots=True)
class AIChangeSetDefinition:
    """Frozen declaration consumed by assurance planning."""

    change_set_key: str
    change_set_version: str
    baseline_system_key: str
    candidate_system_key: str
    risk_tier: AIChangeRiskTier
    purpose: str
    components: tuple[AIChangeComponent, ...]
    declared_unknowns: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier("change-set key", self.change_set_key)
        _require_version("change-set version", self.change_set_version)
        _require_identifier("baseline system key", self.baseline_system_key)
        _require_identifier("candidate system key", self.candidate_system_key)
        if self.baseline_system_key == self.candidate_system_key:
            raise HveeContractError(
                "baseline and candidate system keys must differ"
            )
        if not isinstance(self.risk_tier, AIChangeRiskTier):
            raise HveeContractError("AI change risk tier must be canonical")
        if (
            not isinstance(self.purpose, str)
            or self.purpose != self.purpose.strip()
            or not self.purpose
        ):
            raise HveeContractError(
                "AI change purpose must be non-empty canonical text"
            )
        if not isinstance(self.components, tuple) or not self.components:
            raise HveeContractError(
                "AI change set requires at least one component"
            )
        if any(
            not isinstance(component, AIChangeComponent)
            for component in self.components
        ):
            raise HveeContractError(
                "AI change components must be canonical"
            )
        component_keys = tuple(
            component.component_key for component in self.components
        )
        if component_keys != tuple(sorted(component_keys)):
            raise HveeContractError(
                "AI change components must be ordered by component key"
            )
        if len(component_keys) != len(set(component_keys)):
            raise HveeContractError(
                "AI change component keys must be unique"
            )
        _require_ordered_identifiers(
            "declared unknowns",
            self.declared_unknowns,
        )


@dataclass(frozen=True, slots=True)
class AIChangeSetBundle:
    """Canonical content-addressed change-set artifact."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise HveeContractError(
                "AI change-set payload must be a JSON object"
            )
        _require_sha256("AI change-set SHA-256", self.sha256)


def _require_identifier(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or _IDENTIFIER.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical lowercase identifier"
        )
    return value


def _require_version(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or _SEMANTIC_VERSION.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be a semantic version"
        )
    return value


def _require_sha256(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _require_ordered_identifiers(
    name: str,
    value: object,
) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not value:
        raise HveeContractError(f"{name} must be a non-empty tuple")
    for item in value:
        _require_identifier(name, item)
    if value != tuple(sorted(value)) or len(value) != len(set(value)):
        raise HveeContractError(
            f"{name} must contain unique identifiers in lexical order"
        )
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise HveeContractError(
            "AI change-set content must be canonical JSON"
        ) from error


def calculate_ai_change_set_sha256(payload: object) -> str:
    """Return the canonical payload identity."""

    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _component_payload(component: AIChangeComponent) -> dict[str, object]:
    return {
        "kind": component.kind.value,
        "component_key": component.component_key,
        "baseline_identity_sha256": component.baseline_identity_sha256,
        "candidate_identity_sha256": component.candidate_identity_sha256,
        "declared_behavior_impacts": list(
            component.declared_behavior_impacts
        ),
    }


def build_ai_change_set(
    definition: AIChangeSetDefinition,
) -> AIChangeSetBundle:
    """Build one deterministic, non-authoritative change declaration."""

    if not isinstance(definition, AIChangeSetDefinition):
        raise HveeContractError(
            "AI change-set definition must be canonical"
        )
    payload: dict[str, object] = {
        "schema_version": AI_CHANGE_SET_SCHEMA_VERSION,
        "artifact": {
            "key": AI_CHANGE_SET_KEY,
            "version": AI_CHANGE_SET_VERSION,
            "type": "ai_change_set",
        },
        "change_set": {
            "key": definition.change_set_key,
            "version": definition.change_set_version,
            "purpose": definition.purpose,
            "risk_tier": definition.risk_tier.value,
            "comparison_direction": "baseline_to_candidate",
        },
        "systems": {
            "baseline": definition.baseline_system_key,
            "candidate": definition.candidate_system_key,
        },
        "components": [
            _component_payload(component)
            for component in definition.components
        ],
        "declared_unknowns": list(definition.declared_unknowns),
        "evidence_boundary": {
            "impact_predicted": False,
            "experiments_selected": False,
            "systems_executed": False,
            "outcomes_observed": False,
            "release_decision_issued": False,
            "production_authority": False,
        },
    }
    return AIChangeSetBundle(
        payload=payload,
        sha256=calculate_ai_change_set_sha256(payload),
    )


def verify_ai_change_set(
    *,
    payload: object,
    expected_sha256: str,
    definition: AIChangeSetDefinition,
) -> bool:
    """Verify identity and exact reconstruction from the frozen definition."""

    try:
        expected = _require_sha256(
            "expected AI change-set SHA-256",
            expected_sha256,
        )
        if not isinstance(payload, dict):
            return False
        rebuilt = build_ai_change_set(definition)
        return (
            calculate_ai_change_set_sha256(payload) == expected
            and payload == rebuilt.payload
            and expected == rebuilt.sha256
        )
    except (HveeContractError, TypeError, ValueError):
        return False


__all__ = [
    "AI_CHANGE_SET_KEY",
    "AI_CHANGE_SET_SCHEMA_VERSION",
    "AI_CHANGE_SET_VERSION",
    "AIChangeComponent",
    "AIChangeKind",
    "AIChangeRiskTier",
    "AIChangeSetBundle",
    "AIChangeSetDefinition",
    "build_ai_change_set",
    "calculate_ai_change_set_sha256",
    "verify_ai_change_set",
]
